import { request as httpRequest } from 'node:http';
import type { AddressInfo } from 'node:net';
import request from 'supertest';
import { afterEach, describe, expect, it } from 'vitest';
import { createApp } from '../src/app.js';
import { loadConfig, productionProblems } from '../src/config.js';
import { createRevocationCheck } from '../src/revocation.js';
import { SECRET, startUpstream, testConfig, token, type FakeUpstream } from './helpers.js';

const quiet = { log: () => {} };
const upstreams: FakeUpstream[] = [];

async function upstream(...args: Parameters<typeof startUpstream>) {
  const u = await startUpstream(...args);
  upstreams.push(u);
  return u;
}

afterEach(async () => {
  await Promise.all(upstreams.splice(0).map((u) => u.close()));
});

/** A Redis stand-in answering MGET from a plain map (other commands are not needed here). */
function fakeRedis(values: Record<string, string>, calls: string[][] = []) {
  return async (args: string[]) => {
    calls.push(args);
    if (args[0] !== 'MGET') throw new Error(`unexpected ${args[0]}`);
    return args.slice(1).map((k) => values[k] ?? null);
  };
}

describe('request body limits', () => {
  it('refuses an oversized body before it reaches the service', async () => {
    const booking = await upstream();
    const app = createApp(testConfig({ booking: booking.url }, { maxBodyBytes: 100 }), quiet);
    const jwt = await token();

    const ok = await request(app).post('/api/v1/bookings').set('authorization', `Bearer ${jwt}`).send({ notes: 'x'.repeat(50) });
    expect(ok.status).toBe(200);

    const big = await request(app).post('/api/v1/bookings').set('authorization', `Bearer ${jwt}`).send({ notes: 'x'.repeat(500) });
    expect(big.status).toBe(413);
    expect(booking.requests).toHaveLength(1);
  });

  it('counts a chunked body as it streams', async () => {
    const booking = await upstream();
    const app = createApp(testConfig({ booking: booking.url }, { maxBodyBytes: 100 }), quiet);
    const server = app.listen(0);
    const { port } = server.address() as AddressInfo;
    const jwt = await token();
    // No Content-Length: the size is only known as the chunks arrive.
    const status = await new Promise<number>((resolve, reject) => {
      const req = httpRequest(
        { port, method: 'POST', path: '/api/v1/bookings', headers: { authorization: `Bearer ${jwt}`, 'content-type': 'application/json' } },
        (res) => {
          res.resume();
          resolve(res.statusCode!);
        },
      );
      req.on('error', reject);
      for (let i = 0; i < 10; i++) req.write('x'.repeat(50));
      req.end();
    });
    server.close();
    expect(status).toBe(413);
  });

  it('allows uploads a larger body', async () => {
    const user = await upstream();
    const app = createApp(testConfig({ user: user.url }, { maxBodyBytes: 100, uploadMaxBodyBytes: 10_000 }), quiet);
    const res = await request(app)
      .post('/api/v1/users/me/avatar')
      .set('authorization', `Bearer ${await token()}`)
      .attach('file', Buffer.alloc(2_000), 'me.png');
    expect(res.status).toBe(200);
  });
});

describe('signed-out tokens', () => {
  it("rejects a user's tokens issued before they signed out everywhere, were banned or reset their password", async () => {
    const user = await upstream();
    const issuedAt = Math.floor(Date.now() / 1000);
    const app = createApp(testConfig({ user: user.url }), {
      ...quiet,
      redis: fakeRedis({ 'auth:revoked_before:user-1': String(issuedAt + 1) }),
    });
    const res = await request(app).get('/api/v1/users/me').set('authorization', `Bearer ${await token()}`);
    expect(res.status).toBe(401);
    expect(res.body.detail).toBe('Session ended, please sign in again');
    expect(user.requests).toHaveLength(0);

    // A token issued after that (they signed in again) works, and other people are unaffected.
    const later = createApp(testConfig({ user: user.url }), {
      ...quiet,
      redis: fakeRedis({ 'auth:revoked_before:user-1': String(issuedAt - 60) }),
    });
    expect((await request(later).get('/api/v1/users/me').set('authorization', `Bearer ${await token()}`)).status).toBe(200);
    const other = await token({ sub: 'user-2' });
    expect((await request(app).get('/api/v1/users/me').set('authorization', `Bearer ${other}`)).status).toBe(200);
  });

  it('rejects the one token signed out from a device', async () => {
    const user = await upstream();
    const calls: string[][] = [];
    const app = createApp(testConfig({ user: user.url }), {
      ...quiet,
      redis: fakeRedis({ 'auth:revoked_jti:tok-1': '1' }, calls),
    });
    const signedOut = await token({ jti: 'tok-1' });
    expect((await request(app).get('/api/v1/users/me').set('authorization', `Bearer ${signedOut}`)).status).toBe(401);
    expect((await request(app).get('/api/v1/users/me').set('authorization', `Bearer ${await token({ jti: 'tok-2' })}`)).status).toBe(200);
    expect(calls.find((c) => c[0] === 'MGET')).toEqual(['MGET', 'auth:revoked_before:user-1', 'auth:revoked_jti:tok-1']);
  });

  it('lets requests through when Redis is down, and reports it', async () => {
    const errors: unknown[] = [];
    const check = createRevocationCheck(async () => {
      throw new Error('ECONNREFUSED');
    }, (e) => errors.push(e));
    expect(await check({ id: 'user-1', jti: 't', iat: 1 })).toBe(false);
    expect(errors).toHaveLength(1);
    // Without Redis configured nothing is looked up.
    expect(await createRevocationCheck(undefined, () => {})({ id: 'user-1' })).toBe(false);
  });

  it('treats a token without an issue time as older than any sign-out', async () => {
    const check = createRevocationCheck(fakeRedis({ 'auth:revoked_before:u': '100' }), () => {});
    expect(await check({ id: 'u' })).toBe(true);
    expect(await check({ id: 'u', iat: 101 })).toBe(false);
  });
});

describe('sign-in rate limit', () => {
  it('gives sign-in and reset requests their own, tighter budget', async () => {
    const auth = await upstream();
    const catalog = await upstream();
    const app = createApp(
      testConfig({ auth: auth.url, serviceCatalog: catalog.url }, { authRateLimit: { windowMs: 60_000, max: 2 } }),
      quiet,
    );
    const login = () => request(app).post('/api/v1/auth/login').send({ email: 'a@b.c', password: 'x' });
    expect((await login()).status).toBe(200);
    expect((await request(app).post('/api/v1/auth/forgot-password').send({ email: 'a@b.c' })).status).toBe(200);
    const blocked = await login();
    expect(blocked.status).toBe(429);
    expect(blocked.body.detail).toMatch(/Too many sign-in attempts/);
    expect(auth.requests).toHaveLength(2);
    // Browsing is not affected.
    expect((await request(app).get('/api/v1/categories')).status).toBe(200);
  });
});

describe('production settings', () => {
  const env = { ENVIRONMENT: 'production', REDIS_URL: 'redis://redis:6379/0', CORS_ORIGINS: 'https://shop.example.com' };

  it('refuses placeholder secrets, wildcard CORS and a missing Redis', () => {
    expect(() => loadConfig({ ...env, SECRET_KEY: 'changeme' })).toThrow(/SECRET_KEY is a placeholder/);
    expect(() => loadConfig({ ...env, SECRET_KEY: 'short' })).toThrow(/shorter than 32/);
    expect(() => loadConfig({ ...env, SECRET_KEY: 'k'.repeat(40), CORS_ORIGINS: '*' })).toThrow(/CORS_ORIGINS/);
    expect(() => loadConfig({ ...env, SECRET_KEY: 'k'.repeat(40), REDIS_URL: '' })).toThrow(/REDIS_URL/);
  });

  it('starts with real settings, and development keeps working with the dev defaults', () => {
    expect(loadConfig({ ...env, SECRET_KEY: 'k'.repeat(40) }).redisUrl).toBe('redis://redis:6379/0');
    expect(loadConfig({ SECRET_KEY: SECRET }).maxBodyBytes).toBe(1_048_576);
    expect(productionProblems({ jwtSecret: SECRET, corsOrigins: [], redisUrl: undefined })).toHaveLength(2);
  });
});

describe('request hygiene', () => {
  it('drops "Expect: 100-continue" instead of failing the request', async () => {
    const auth = await upstream();
    const app = createApp(testConfig({ auth: auth.url }, { breaker: { failureThreshold: 1, resetTimeoutMs: 60_000 } }), quiet);
    const server = app.listen(0);
    const { port } = server.address() as AddressInfo;
    // As curl does for a large body: ask to continue, then send it.
    const post = () =>
      new Promise<number>((resolve, reject) => {
        const req = httpRequest(
          { port, method: 'POST', path: '/api/v1/auth/login', headers: { expect: '100-continue', 'content-type': 'application/json' } },
          (res) => {
            res.resume();
            resolve(res.statusCode!);
          },
        );
        req.on('continue', () => req.end('{"email":"a@b.c"}'));
        req.on('error', reject);
      });
    for (let i = 0; i < 3; i++) expect(await post()).toBe(200);
    server.close();
    expect(auth.requests[0].headers.expect).toBeUndefined();
  });

  it('refuses dot segments and encoded slashes that would escape the matched route', async () => {
    const analytics = await upstream();
    const app = createApp(testConfig({ analytics: analytics.url }), quiet);
    const jwt = await token();
    for (const path of ['/api/v1/events/../metrics', '/api/v1/events/%2e%2e/metrics', '/api/v1/events/..%2fmetrics', '/api/v1//events']) {
      const res = await request(app).get(path).set('authorization', `Bearer ${jwt}`);
      expect(res.status, path).toBe(400);
    }
    expect(analytics.requests).toHaveLength(0);
  });

  it("tells services the client's address, ignoring one the client made up", async () => {
    const auth = await upstream();
    const app = createApp(testConfig({ auth: auth.url }), quiet);
    await request(app).post('/api/v1/auth/login').set('x-real-ip', '1.2.3.4').send({});
    expect(auth.requests[0].headers['x-real-ip']).not.toBe('1.2.3.4');
    expect(auth.requests[0].headers['x-real-ip']).toMatch(/127\.0\.0\.1|::1/);
  });

  it('checks the session of a token against its sign-out marker', async () => {
    const check = createRevocationCheck(fakeRedis({ 'auth:revoked_sid:s-1': '1' }), () => {});
    expect(await check({ id: 'u', sid: 's-1', iat: 5 })).toBe(true);
    expect(await check({ id: 'u', sid: 's-2', iat: 5 })).toBe(false);
  });
});

describe('dropped connections', () => {
  it('retries a read once when the service closed the connection, but never repeats a write', async () => {
    let dropped = 0;
    const shop = await upstream((_req, res) => {
      if (dropped < 1) {
        dropped++;
        res.socket?.destroy(); // like a keep-alive socket the service closed a moment earlier
        return;
      }
      res.end('{"ok":true}');
    });
    const app = createApp(testConfig({ shop: shop.url }), quiet);
    const read = await request(app).get('/api/v1/shops');
    expect(read.status).toBe(200);
    expect(shop.requests).toHaveLength(2);

    dropped = 0;
    const write = await request(app).post('/api/v1/shops').set('authorization', `Bearer ${await token()}`).send({});
    expect(write.status).toBe(502);
  });
});

describe('Prometheus metrics', () => {
  it('counts requests per service and status, with latency and circuit state', async () => {
    const catalog = await upstream();
    const app = createApp(testConfig({ serviceCatalog: catalog.url }), quiet);
    await request(app).get('/api/v1/categories');
    await request(app).get('/api/v1/nope');
    const res = await request(app).get('/metrics');
    expect(res.status).toBe(200);
    expect(res.headers['content-type']).toMatch(/text\/plain/);
    expect(res.text).toContain('gateway_http_requests_total{upstream="service_catalog_service",method="GET",status="200"} 1');
    expect(res.text).toContain('gateway_http_requests_total{upstream="gateway",method="GET",status="404"} 1');
    expect(res.text).toContain('gateway_http_request_duration_seconds_count{upstream="service_catalog_service"} 1');
    expect(res.text).toContain('gateway_circuit_open{upstream="service_catalog_service"} 0');
  });

  it('needs the metrics token when one is set, and is off in production without one', async () => {
    const guarded = createApp(testConfig({}, { metricsToken: 'scrape-me' }), quiet);
    expect((await request(guarded).get('/metrics')).status).toBe(401);
    expect((await request(guarded).get('/metrics').set('authorization', 'Bearer wrong')).status).toBe(401);
    expect((await request(guarded).get('/metrics').set('authorization', 'Bearer scrape-me')).status).toBe(200);
    const production = createApp(testConfig({}, { production: true }), quiet);
    expect((await request(production).get('/metrics')).status).toBe(404);
  });
});
