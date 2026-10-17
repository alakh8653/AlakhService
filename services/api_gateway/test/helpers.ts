import { createServer, type IncomingMessage, type ServerResponse } from 'node:http';
import type { AddressInfo } from 'node:net';
import { SignJWT } from 'jose';
import { loadConfig, type GatewayConfig } from '../src/config.js';

export const SECRET = 'test-secret';

export interface RecordedRequest {
  method: string;
  url: string;
  headers: IncomingMessage['headers'];
  body: string;
}

export interface FakeUpstream {
  url: string;
  requests: RecordedRequest[];
  close: () => Promise<void>;
}

type Handler = (req: RecordedRequest, res: ServerResponse) => void;

const echo: Handler = (req, res) => {
  res.setHeader('content-type', 'application/json');
  res.end(JSON.stringify({ method: req.method, url: req.url, body: req.body }));
};

/** Starts an HTTP server on a random port that records every request it receives. */
export async function startUpstream(handler: Handler = echo): Promise<FakeUpstream> {
  const requests: RecordedRequest[] = [];
  const server = createServer((req, res) => {
    const chunks: Buffer[] = [];
    req.on('data', (chunk: Buffer) => chunks.push(chunk));
    req.on('end', () => {
      const recorded = { method: req.method!, url: req.url!, headers: req.headers, body: Buffer.concat(chunks).toString() };
      requests.push(recorded);
      handler(recorded, res);
    });
  });
  await new Promise<void>((resolve) => server.listen(0, '127.0.0.1', resolve));
  const { port } = server.address() as AddressInfo;
  return {
    url: `http://127.0.0.1:${port}`,
    requests,
    close: () => new Promise((resolve) => server.close(() => resolve())),
  };
}

/** A URL nothing is listening on. */
export const UNREACHABLE = 'http://127.0.0.1:9';

export function testConfig(urls: Record<string, string> = {}, overrides: Partial<GatewayConfig> = {}): GatewayConfig {
  const config = loadConfig({ SECRET_KEY: SECRET });
  for (const upstream of Object.values(config.upstreams)) upstream.url = urls[upstream.key] ?? UNREACHABLE;
  return { ...config, upstreamTimeoutMs: 1_000, ...overrides };
}

export async function token(claims: Record<string, unknown> = {}, expiresIn = '15m'): Promise<string> {
  return new SignJWT({ type: 'access', role: 'user', ...claims })
    .setProtectedHeader({ alg: 'HS256' })
    .setSubject(typeof claims.sub === 'string' ? claims.sub : 'user-1')
    .setIssuedAt()
    .setExpirationTime(expiresIn)
    .sign(new TextEncoder().encode(SECRET));
}
