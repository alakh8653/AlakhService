import { request as httpRequest, type IncomingMessage, type Server } from 'node:http';
import type { Duplex } from 'node:stream';
import { createTokenVerifier } from './auth.js';
import type { GatewayConfig } from './config.js';
import { createRevocationCheck, type SendCommand } from './revocation.js';

/**
 * Live sockets forwarded to booking_service: a booking's status (/ws/bookings/{id}) and a shop's queue
 * (/ws/shops/{id}/queue for the shop, /ws/shops/{id}/board for the screen in the shop). The access
 * token comes as ?token= (browsers cannot set headers on a WebSocket) and booking_service checks it, as
 * it does for the same data over HTTP; the gateway also refuses a signed-out or banned user's token
 * (which only it can see, in Redis). Any other upgrade is refused, and one client may hold only a few
 * sockets, so nobody can fill a shop's public board room.
 */
const SOCKET_PATHS = [/^\/api\/v1\/ws\/bookings\/[^/]+$/, /^\/api\/v1\/ws\/shops\/[^/]+\/(queue|board)$/];

export function isSocketPath(path: string): boolean {
  return SOCKET_PATHS.some((pattern) => pattern.test(path));
}

function answer(socket: Duplex, status: number, reason: string) {
  socket.end(`HTTP/1.1 ${status} ${reason}\r\nConnection: close\r\nContent-Length: 0\r\n\r\n`);
}

function head(res: IncomingMessage): string {
  const lines = [`HTTP/1.1 ${res.statusCode} ${res.statusMessage ?? ''}`];
  for (let i = 0; i < res.rawHeaders.length; i += 2) lines.push(`${res.rawHeaders[i]}: ${res.rawHeaders[i + 1]}`);
  return `${lines.join('\r\n')}\r\n\r\n`;
}

export interface SocketOptions {
  redis?: SendCommand;
  /** Open (or opening) sockets one client address may hold. */
  maxPerClient?: number;
}

export const MAX_SOCKETS_PER_CLIENT = 10;

/** The client's address, trusting as many proxies in front of the gateway as Express does (TRUST_PROXY). */
export function clientAddress(req: IncomingMessage, trustProxy: number): string {
  const forwarded = String(req.headers['x-forwarded-for'] ?? '')
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean);
  const chain = [...forwarded, req.socket.remoteAddress ?? ''];
  return chain[Math.max(0, chain.length - 1 - trustProxy)];
}

export function attachWebSockets(server: Server, config: GatewayConfig, options: SocketOptions = {}): void {
  const verifyToken = createTokenVerifier(config.jwtSecret);
  const isRevoked = createRevocationCheck(options.redis, (err) =>
    console.error(JSON.stringify({ msg: 'redis_error', error: err instanceof Error ? err.message : String(err) })),
  );
  const maxPerClient = options.maxPerClient ?? MAX_SOCKETS_PER_CLIENT;
  const open = new Map<string, number>();

  server.on('upgrade', (req: IncomingMessage, socket: Duplex, firstBytes: Buffer) => {
    void forward(req, socket, firstBytes);
  });

  async function forward(req: IncomingMessage, socket: Duplex, firstBytes: Buffer) {
    const url = new URL(req.url ?? '/', 'http://gateway');
    if (!isSocketPath(url.pathname) || (req.headers.upgrade ?? '').toLowerCase() !== 'websocket') {
      answer(socket, 404, 'Not Found');
      return;
    }
    const client = clientAddress(req, config.trustProxy);
    if ((open.get(client) ?? 0) >= maxPerClient) {
      answer(socket, 429, 'Too Many Requests');
      return;
    }
    open.set(client, (open.get(client) ?? 0) + 1);
    let released = false;
    const release = () => {
      if (released) return;
      released = true;
      const left = (open.get(client) ?? 1) - 1;
      if (left > 0) open.set(client, left);
      else open.delete(client);
    };
    // The client hanging up ends its half (server sockets are half-open): either frees the place.
    socket.once('close', release);
    socket.once('end', release);
    const token = url.searchParams.get('token');
    if (token) {
      // A token that does not verify is left to booking_service to refuse, as before.
      const user = await verifyToken(`Bearer ${token}`).catch(() => undefined);
      if (user && (await isRevoked(user))) {
        answer(socket, 401, 'Unauthorized');
        release();
        return;
      }
    }
    if (socket.destroyed) {
      release();
      return;
    }
    const target = new URL(url.pathname + url.search, config.upstreams.booking.url);
    const headers = { ...req.headers, host: target.host, 'x-forwarded-for': client };
    const upstream = httpRequest(target, { method: 'GET', headers });
    upstream.setTimeout(config.upstreamTimeoutMs, () => upstream.destroy(new Error('timeout')));
    upstream.on('upgrade', (res, upstreamSocket, upstreamFirst) => {
      upstream.setTimeout(0);
      socket.write(head(res));
      if (upstreamFirst.length) socket.write(upstreamFirst);
      if (firstBytes.length) upstreamSocket.write(firstBytes);
      upstreamSocket.pipe(socket).pipe(upstreamSocket);
      const close = () => {
        upstreamSocket.destroy();
        socket.destroy();
      };
      for (const side of [upstreamSocket, socket]) {
        side.on('error', close);
        side.on('close', close);
        side.on('end', close);
      }
    });
    // The service answered without upgrading (it refused before accepting): pass its status on.
    upstream.on('response', (res) => {
      answer(socket, res.statusCode ?? 502, res.statusMessage ?? '');
      res.resume();
    });
    upstream.on('error', () => answer(socket, 502, 'Bad Gateway'));
    socket.on('error', () => upstream.destroy());
    upstream.end();
  }
}
