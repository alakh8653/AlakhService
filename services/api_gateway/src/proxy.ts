import { Readable } from 'node:stream';
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
]);

export interface ProxyOptions {
  upstream: Upstream;
  breaker: CircuitBreaker;
  path: string;
  timeoutMs: number;
  requestId: string;
  metrics?: RollingMetrics;
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
  return headers;
}

function hasBody(req: Request): boolean {
  if (req.method === 'GET' || req.method === 'HEAD') return false;
  return req.headers['transfer-encoding'] !== undefined || Number(req.headers['content-length'] ?? 0) > 0;
}

/** Forwards the request to the upstream service and streams the response back. */
export async function proxyRequest(req: Request, res: Response, opts: ProxyOptions): Promise<void> {
  const { upstream, breaker, metrics } = opts;

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
  const started = performance.now();
  try {
    const init: RequestInit & { duplex?: 'half' } = {
      method: req.method,
      headers: requestHeaders(req, opts.requestId),
      redirect: 'manual',
      signal: AbortSignal.any([AbortSignal.timeout(opts.timeoutMs), clientGone.signal]),
    };
    if (hasBody(req)) {
      init.body = Readable.toWeb(req) as ReadableStream;
      init.duplex = 'half';
    }
    upstreamResponse = await fetch(upstream.url + opts.path + query, init);
  } catch (err) {
    if (clientGone.signal.aborted) return; // client disconnected; nothing to answer
    breaker.onFailure();
    metrics?.record(performance.now() - started, true);
    const timedOut = err instanceof Error && err.name === 'TimeoutError';
    res
      .status(timedOut ? 504 : 502)
      .json({ detail: timedOut ? `${upstream.name} timed out` : `${upstream.name} is unreachable` });
    return;
  }

  const failed = upstreamResponse.status >= 500;
  if (failed) breaker.onFailure();
  else breaker.onSuccess();
  metrics?.record(performance.now() - started, failed);

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
