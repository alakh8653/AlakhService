import { randomUUID } from 'node:crypto';
import cors from 'cors';
import express, { type NextFunction, type Request, type Response } from 'express';
import { rateLimit, type Store } from 'express-rate-limit';
import helmet from 'helmet';
import { RedisStore, type RedisReply } from 'rate-limit-redis';
import { AuthError, createTokenVerifier, type AuthenticatedUser } from './auth.js';
import { CircuitBreaker } from './circuitBreaker.js';
import type { GatewayConfig } from './config.js';
import { checkAll } from './health.js';
import { RollingMetrics } from './metrics.js';
import { GatewayMetrics } from './prometheus.js';
import { proxyRequest } from './proxy.js';
import { createRevocationCheck, type SendCommand } from './revocation.js';
import { findRoute, isUpload, requiredAccess, upstreamPath } from './routes.js';

export interface LogEntry {
  requestId: string;
  method: string;
  path: string;
  status: number;
  durationMs: number;
  upstream?: string;
}

export interface AppOptions {
  log?: (entry: LogEntry) => void;
  healthTimeoutMs?: number;
  /** Raw Redis commands (server.ts connects to REDIS_URL): shared rate limits and revocations. */
  redis?: SendCommand;
  /** Also export process metrics (CPU, memory, event loop) on /metrics; server.ts turns this on. */
  processMetrics?: boolean;
}

// Sign-in, sign-up, codes and password resets: guessing targets, so they get their own budget.
const AUTH_LIMITED = /^\/api\/v1\/auth\/(login|register|send-otp|verify-otp|forgot-password|reset-password|refresh)$/;

const defaultLog = (entry: LogEntry) => console.log(JSON.stringify({ msg: 'request', ...entry }));

export function createApp(config: GatewayConfig, options: AppOptions = {}) {
  const log = options.log ?? defaultLog;
  const verifyToken = createTokenVerifier(config.jwtSecret);
  const breakers = new Map(
    Object.keys(config.upstreams).map((key) => [
      key,
      new CircuitBreaker(config.breaker.failureThreshold, config.breaker.resetTimeoutMs),
    ]),
  );
  const metrics = new Map(Object.keys(config.upstreams).map((key) => [key, new RollingMetrics()]));
  const prometheus = new GatewayMetrics(
    breakers,
    Object.fromEntries(Object.values(config.upstreams).map((u) => [u.key, u.name])),
    options.processMetrics,
  );
  const redisError = (err: unknown) => {
    prometheus.redisErrors.inc();
    console.error(JSON.stringify({ msg: 'redis_error', error: err instanceof Error ? err.message : String(err) }));
  };
  const isRevoked = createRevocationCheck(options.redis, redisError);
  // Shared across gateway instances when Redis is there; if Redis fails, requests are let through.
  const limitStore = (prefix: string): Store | undefined =>
    options.redis
      ? new RedisStore({ prefix, sendCommand: (...args: string[]) => options.redis!(args) as Promise<RedisReply> })
      : undefined;

  const app = express();
  app.disable('x-powered-by');
  // Behind a load balancer, the client IP (for rate limits and logs) comes from X-Forwarded-For.
  app.set('trust proxy', config.trustProxy);
  app.use(helmet());
  app.use(cors({ origin: config.corsOrigins, credentials: true }));

  // Request id + one structured log line per request.
  app.use((req: Request, res: Response, next: NextFunction) => {
    const incoming = req.headers['x-request-id'];
    const requestId = typeof incoming === 'string' && /^[\w-]{1,128}$/.test(incoming) ? incoming : randomUUID();
    res.locals.requestId = requestId;
    res.setHeader('x-request-id', requestId);
    const started = performance.now();
    res.on('finish', () => {
      const durationMs = performance.now() - started;
      if (req.path !== '/metrics') prometheus.observe(res.locals.upstream, req.method, res.statusCode, durationMs);
      log({
        requestId,
        method: req.method,
        path: req.path,
        status: res.statusCode,
        durationMs: Math.round(durationMs),
        upstream: res.locals.upstream,
      });
    });
    next();
  });

  app.get('/metrics', prometheus.handler(config.metricsToken, config.production));

  app.get('/health', (_req, res) => {
    res.json({ status: 'healthy', service: 'api_gateway' });
  });

  app.use(
    '/api',
    rateLimit({
      windowMs: config.rateLimit.windowMs,
      limit: config.rateLimit.max,
      standardHeaders: 'draft-8',
      legacyHeaders: false,
      store: limitStore('rl:api:'),
      passOnStoreError: true,
      message: { detail: 'Too many requests, please try again later.' },
    }),
  );
  app.use(
    rateLimit({
      windowMs: config.authRateLimit.windowMs,
      limit: config.authRateLimit.max,
      skip: (req) => !AUTH_LIMITED.test(req.path),
      standardHeaders: 'draft-8',
      legacyHeaders: false,
      store: limitStore('rl:auth:'),
      passOnStoreError: true,
      message: { detail: 'Too many sign-in attempts from this network. Please wait a few minutes and try again.' },
    }),
  );

  /** Verifies the token and role; on success returns the user, otherwise sends the error response. */
  const authorize = async (req: Request, res: Response, access: 'user' | 'admin'): Promise<AuthenticatedUser | null> => {
    let user: AuthenticatedUser;
    try {
      user = await verifyToken(req.headers.authorization);
    } catch (err) {
      const status = err instanceof AuthError ? err.status : 401;
      res.status(status).setHeader('WWW-Authenticate', 'Bearer').json({ detail: (err as Error).message });
      return null;
    }
    if (await isRevoked(user)) {
      res.status(401).setHeader('WWW-Authenticate', 'Bearer').json({ detail: 'Session ended, please sign in again' });
      return null;
    }
    if (access === 'admin' && user.role !== 'admin') {
      res.status(403).json({ detail: 'Admin access required' });
      return null;
    }
    return user;
  };

  // Aggregated health of every service, for the admin dashboard's System Health page.
  app.get('/api/v1/admin/monitoring/health', async (req, res) => {
    if (!(await authorize(req, res, 'admin'))) return;
    const data = await checkAll(Object.values(config.upstreams), options.healthTimeoutMs ?? 3_000);
    res.json({ data });
  });

  // Traffic each service received through the gateway over the last 5 minutes.
  app.get('/api/v1/admin/monitoring/metrics', async (req, res) => {
    if (!(await authorize(req, res, 'admin'))) return;
    const data = Object.values(config.upstreams).map((upstream) => ({
      id: upstream.key,
      service: upstream.name,
      circuit: breakers.get(upstream.key)!.currentState,
      ...metrics.get(upstream.key)!.snapshot(),
    }));
    res.json({ data, windowSeconds: 300 });
  });

  app.use(async (req: Request, res: Response) => {
    const path = req.path;
    // "/events/../metrics" must not reach a route other than the one it was matched (and
    // authorised) against; nothing legitimate needs dot segments or empty segments.
    if (/(^|\/)\.\.?(\/|$)|%2e|%2f|%5c|\/\/|\\/i.test(req.originalUrl.split('?')[0])) {
      res.status(400).json({ detail: 'Invalid path' });
      return;
    }

    const route = findRoute(path);
    if (!route) {
      res.status(404).json({ detail: 'Not found' });
      return;
    }

    // Identity headers are only ever set by the gateway, from a verified token.
    delete req.headers['x-user-id'];
    delete req.headers['x-user-role'];
    const access = requiredAccess(route, req.method);
    if (access !== 'public') {
      const user = await authorize(req, res, access);
      if (!user) return;
      req.headers['x-user-id'] = user.id;
      req.headers['x-user-role'] = user.role;
    }

    const upstream = config.upstreams[route.upstream];
    res.locals.upstream = upstream.name;
    await proxyRequest(req, res, {
      upstream,
      breaker: breakers.get(route.upstream)!,
      path: upstreamPath(route, path),
      timeoutMs: config.upstreamTimeoutMs,
      requestId: res.locals.requestId,
      metrics: metrics.get(route.upstream),
      // Routes that take file uploads are allowed a larger body.
      maxBodyBytes: isUpload(path) ? config.uploadMaxBodyBytes : config.maxBodyBytes,
    });
  });

  return app;
}
