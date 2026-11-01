import { createServer, request, type Server } from 'node:http';
import type { AddressInfo } from 'node:net';
import type { Duplex } from 'node:stream';
import { afterEach, describe, expect, it } from 'vitest';
import { attachWebSockets, isSocketPath } from '../src/websocket.js';
import { testConfig } from './helpers.js';

const servers: Server[] = [];
// Upgraded sockets leave their server's books: closed by hand after each test.
const sockets: Duplex[] = [];

async function listen(server: Server): Promise<string> {
  servers.push(server);
  await new Promise<void>((resolve) => server.listen(0, '127.0.0.1', resolve));
  return `127.0.0.1:${(server.address() as AddressInfo).port}`;
}

/** booking_service stand-in: upgrades and echoes, or refuses with 403 for a bad token. */
async function fakeBooking(seen: string[]): Promise<string> {
  const server = createServer((_req, res) => res.writeHead(404).end());
  server.on('upgrade', (req, socket: Duplex) => {
    sockets.push(socket);
    seen.push(req.url!);
    if (req.url!.includes('token=bad')) {
      socket.end('HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\n\r\n');
      return;
    }
    socket.write('HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n\r\n');
    socket.on('data', (chunk: Buffer) => socket.write(`echo:${chunk.toString()}`));
  });
  return listen(server);
}

function upgrade(host: string, path: string): Promise<{ status: number; socket?: Duplex }> {
  return new Promise((resolve, reject) => {
    const req = request(`http://${host}${path}`, { headers: { Connection: 'Upgrade', Upgrade: 'websocket' } });
    req.on('upgrade', (res, socket) => resolve({ status: res.statusCode!, socket }));
    req.on('response', (res) => {
      res.resume();
      resolve({ status: res.statusCode! });
    });
    req.on('error', reject);
    req.end();
  });
}

async function gatewayTo(bookingUrl?: string): Promise<string> {
  const gateway = createServer();
  attachWebSockets(gateway, testConfig(bookingUrl ? { booking: bookingUrl } : {}));
  return listen(gateway);
}

afterEach(async () => {
  for (const socket of sockets.splice(0)) socket.destroy();
  await Promise.all(
    servers.splice(0).map(
      (s) =>
        new Promise((resolve) => {
          s.closeAllConnections();
          s.close(resolve);
        }),
    ),
  );
});

describe('live sockets', () => {
  it('knows which paths are sockets', () => {
    expect(isSocketPath('/api/v1/ws/bookings/b1')).toBe(true);
    expect(isSocketPath('/api/v1/ws/shops/s1/queue')).toBe(true);
    expect(isSocketPath('/api/v1/ws/shops/s1/board')).toBe(true);
    expect(isSocketPath('/api/v1/ws/shops/s1/settings')).toBe(false);
    expect(isSocketPath('/api/v1/bookings/b1')).toBe(false);
  });

  it('forwards a shop queue socket to booking_service both ways, token and all', async () => {
    const seen: string[] = [];
    const host = await gatewayTo(`http://${await fakeBooking(seen)}`);
    const { status, socket } = await upgrade(host, '/api/v1/ws/shops/s1/queue?token=t1');
    expect(status).toBe(101);
    expect(seen).toEqual(['/api/v1/ws/shops/s1/queue?token=t1']);
    const reply = new Promise<string>((resolve) => socket!.once('data', (d: Buffer) => resolve(d.toString())));
    socket!.write('ping');
    expect(await reply).toBe('echo:ping');
    socket!.destroy();
  });

  it("passes on the service's refusal and refuses other paths itself", async () => {
    const seen: string[] = [];
    const host = await gatewayTo(`http://${await fakeBooking(seen)}`);
    expect((await upgrade(host, '/api/v1/ws/shops/s1/queue?token=bad')).status).toBe(403);
    expect((await upgrade(host, '/api/v1/ws/admin/everything')).status).toBe(404);
    expect(seen).toEqual(['/api/v1/ws/shops/s1/queue?token=bad']);
  });

  it('answers 502 when booking_service is down', async () => {
    const host = await gatewayTo();
    expect((await upgrade(host, '/api/v1/ws/bookings/b1')).status).toBe(502);
  });
});
