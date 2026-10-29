import { request as httpRequest, type IncomingMessage, type Server } from 'node:http';
import type { Duplex } from 'node:stream';
import type { GatewayConfig } from './config.js';

/**
 * Live sockets forwarded to booking_service: a booking's status (/ws/bookings/{id}) and a shop's queue
 * (/ws/shops/{id}/queue for the shop, /ws/shops/{id}/board for the screen in the shop). The access
 * token comes as ?token= (browsers cannot set headers on a WebSocket) and booking_service checks it, as
 * it does for the same data over HTTP. Any other upgrade is refused.
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

export function attachWebSockets(server: Server, config: GatewayConfig): void {
  server.on('upgrade', (req: IncomingMessage, socket: Duplex, firstBytes: Buffer) => {
    const url = new URL(req.url ?? '/', 'http://gateway');
    if (!isSocketPath(url.pathname) || (req.headers.upgrade ?? '').toLowerCase() !== 'websocket') {
      answer(socket, 404, 'Not Found');
      return;
    }
    const target = new URL(url.pathname + url.search, config.upstreams.booking.url);
    const headers = { ...req.headers, host: target.host, 'x-forwarded-for': req.socket.remoteAddress ?? '' };
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
  });
}
