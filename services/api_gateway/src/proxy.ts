import { Readable, Transform } from 'node:stream';
import type { Request, Response } from 'express';
import type { CircuitBreaker } from './circuitBreaker.js';
import type { Upstream } from './config.js';
import type { RollingMetrics } from './metrics.js';

// Connection-level headers that must not be forwarded (RFC 9110 §7.6.1), plus headers that
// fetch recomputes itself.
const HOP_BY_HOP = new Set([
  'connection',
  'keep-alive',
  'proxy-authenticate',
  'proxy-authorization',
  'te',
  'trailer',
  'transfer-encoding',
  'upgrade',
  'host',
  'content-length',
  // fetch cannot do "Expect: 100-continue" and fails the whole request (curl sends it on large bodies).
  'expect',
]);

/** Statuses that mean the service itself is in trouble; a 500 is usually one bad request, not an outage. */
const UNHEALTHY = new Set([502, 503, 504]);

export interface ProxyOptions {
  upstream: Upstream;
  breaker: CircuitBreaker;
  path: string;
  timeoutMs: number;
  requestId: string;
  metrics?: RollingMetrics;
  /** Largest body forwarded; a bigger one gets 413 without reaching the service. */
  maxBodyBytes?: number;
}

function tooLarge(res: Response, max: number) {
  res.status(413).json({ detail: `Request body is larger than ${max} bytes` });
}

function requestHeaders(req: Request, requestId: string): Headers {
  const headers = new Headers();
  for (const [name, value] of Object.entries(req.headers)) {
    if (value === undefined || HOP_BY_HOP.has(name)) continue;
    for (const v of Array.isArray(value) ? value : [value]) headers.append(name, v);
  }
  const forwardedFor = req.headers['x-forwarded-for'];
  headers.set('x-forwarded-for', [forwardedFor, req.socket.remoteAddress].filter(Boolean).join(', '));
  headers.set('x-forwarded-proto', req.protocol);
  if (req.headers.host) headers.set('x-forwarded-host', req.headers.host);
  headers.set('x-request-id', requestId);
  // The client's address as the gateway sees it (honouring TRUST_PROXY); replaces any client value.
  if (req.ip) headers.set('x-real-ip', req.ip);
  return headers;
}

function hasBody(req: Request): boolean {
  if (req.method === 'GET' || req.method === 'HEAD') return false;
  return req.headers['transfer-encoding'] !== undefined || Number(req.headers['content-length'] ?? 0) > 0;
}

function retriable(req: Request, err: unknown, sentBody: boolean): boolean {
  if (sentBody || !['GET', 'HEAD', 'OPTIONS'].includes(req.method)) return false;
  if (err instanceof Error && (err.name === 'TimeoutError' || err.name === 'AbortError')) return false;
  const code = (err as { cause?: { code?: string } }).cause?.code;
  return code === 'UND_ERR_SOCKET' || code === 'ECONNRESET' || code === 'EPIPE';
}

/** Forwards the request to the upstream service and streams the response back. */
export async function proxyRequest(req: Request, res: Response, opts: ProxyOptions): Promise<void> {
  const { upstream, breaker, metrics } = opts;
  const max = opts.maxBodyBytes ?? Number.POSITIVE_INFINITY;
  if (Number(req.headers['content-length'] ?? 0) > max) {
    tooLarge(res, max);
    return;
  }

  if (!breaker.tryAcquire()) {
    metrics?.record(0, true);
    res.setHeader('Retry-After', Math.ceil(breaker.retryAfterMs() / 1000).toString());
    res.status(503).json({ detail: `${upstream.name} is temporarily unavailable` });
    return;
  }

  const query = req.originalUrl.includes('?') ? req.originalUrl.slice(req.originalUrl.indexOf('?')) : '';
  const clientGone = new AbortController();
  res.on('close', () => {
    if (!res.writableFinished) clientGone.abort();
  });

  let upstreamResponse: globalThis.Response;
  let bodyTooLarge = false;
  const started = performance.now();
  try {
    const init: RequestInit & { duplex?: 'half' } = {
      method: req.method,
      headers: requestHeaders(req, opts.requestId),
      redirect: 'manual',
      signal: AbortSignal.any([AbortSignal.timeout(opts.timeoutMs), clientGone.signal]),
    };
    if (hasBody(req)) {
      // A chunked body has no length up front: count it as it streams and stop at the limit.
      let seen = 0;
      const counted = req.pipe(
        new Transform({
          transform(chunk: Buffer, _encoding, done) {
            seen += chunk.length;
            if (seen > max) {
              bodyTooLarge = true;
              done(new Error('body too large'));
            } else done(null, chunk);
          },
        }),
      );
      init.body = Readable.toWeb(counted) as ReadableStream;
      init.duplex = 'half';
    }
    const url = upstream.url + opts.path + query;
    try {
      upstreamResponse = await fetch(url, init);
    } catch (err) {
      // A service closes its keep-alive connection after a 500; the next request can land on that
      // socket just before the close is noticed. Requests that are safe to repeat get one retry.
      if (!retriable(req, err, init.body !== undefined)) throw err;
      upstreamResponse = await fetch(url, init);
    }
  } catch (err) {
    if (clientGone.signal.aborted) return; // client disconnected; nothing to answer
    if (bodyTooLarge) {
      breaker.onSuccess(); // the service is fine; the client sent too much
      tooLarge(res, max);
      return;
    }
    breaker.onFailure();
    metrics?.record(performance.now() - started, true);
    const timedOut = err instanceof Error && err.name === 'TimeoutError';
    res
      .status(timedOut ? 504 : 502)
      .json({ detail: timedOut ? `${upstream.name} timed out` : `${upstream.name} is unreachable` });
    return;
  }

  // Only an unreachable or overloaded service opens the circuit. Counting every 500 would let
  // anyone take a service offline for everybody with a handful of requests that make it fail.
  if (UNHEALTHY.has(upstreamResponse.status)) breaker.onFailure();
  else breaker.onSuccess();
  metrics?.record(performance.now() - started, upstreamResponse.status >= 500);

  res.status(upstreamResponse.status);
  upstreamResponse.headers.forEach((value, name) => {
    // fetch has already decoded the body, so the original encoding/length no longer apply.
    if (HOP_BY_HOP.has(name) || name === 'content-encoding' || name === 'set-cookie') return;
    if (name === 'location' && value.startsWith(upstream.url)) value = value.slice(upstream.url.length) || '/';
    res.setHeader(name, value);
  });
  const cookies = upstreamResponse.headers.getSetCookie();
  if (cookies.length) res.setHeader('set-cookie', cookies);

  if (!upstreamResponse.body || req.method === 'HEAD') {
    res.end();
    return;
  }
  const body = Readable.fromWeb(upstreamResponse.body as import('node:stream/web').ReadableStream);
  body.on('error', () => res.destroy());
  body.pipe(res);
}
