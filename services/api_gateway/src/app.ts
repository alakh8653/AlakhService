import { randomUUID } from 'node:crypto';
import cors from 'cors';
import express, { type NextFunction, type Request, type Response } from 'express';
import { rateLimit } from 'express-rate-limit';
import helmet from 'helmet';
import { AuthError, createTokenVerifier, type AuthenticatedUser } from './auth.js';
import { CircuitBreaker } from './circuitBreaker.js';
import type { GatewayConfig } from './config.js';
import { checkAll } from './health.js';
import { RollingMetrics } from './metrics.js';
import { proxyRequest } from './proxy.js';
import { findRoute, requiredAccess, upstreamPath } from './routes.js';

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
}

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

  const app = express();
  app.disable('x-powered-by');
  app.use(helmet());
  app.use(cors({ origin: config.corsOrigins, credentials: true }));

  // Request id + one structured log line per request.
  app.use((req: Request, res: Response, next: NextFunction) => {
    const incoming = req.headers['x-request-id'];
    const requestId = typeof incoming === 'string' && /^[\w-]{1,128}$/.test(incoming) ? incoming : randomUUID();
    res.locals.requestId = requestId;
    res.setHeader('x-request-id', requestId);
    const started = performance.now();
    res.on('finish', () =>
      log({
        requestId,
        method: req.method,
        path: req.path,
        status: res.statusCode,
        durationMs: Math.round(performance.now() - started),
        upstream: res.locals.upstream,
      }),
    );
    next();
  });

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
      message: { detail: 'Too many requests, please try again later.' },
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
    });
  });

  return app;
}
