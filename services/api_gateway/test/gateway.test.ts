import request from 'supertest';
import { afterEach, describe, expect, it } from 'vitest';
import { createApp } from '../src/app.js';
import { startUpstream, testConfig, token, type FakeUpstream } from './helpers.js';

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

describe('gateway', () => {
  it('reports its own health', async () => {
    const res = await request(createApp(testConfig(), quiet)).get('/health');
    expect(res.status).toBe(200);
    expect(res.body).toEqual({ status: 'healthy', service: 'api_gateway' });
  });

  it('forwards public requests with body, query and tracing headers', async () => {
    const auth = await upstream();
    const app = createApp(testConfig({ auth: auth.url }), quiet);

    const res = await request(app)
      .post('/api/v1/auth/login?next=%2Fhome')
      .set('x-request-id', 'req-123')
      .send({ email: 'a@b.c', password: 'pw' });

    expect(res.status).toBe(200);
    expect(res.headers['x-request-id']).toBe('req-123');
    expect(res.body).toEqual({ method: 'POST', url: '/api/v1/auth/login?next=%2Fhome', body: '{"email":"a@b.c","password":"pw"}' });
    const forwarded = auth.requests[0];
    expect(forwarded.headers['content-type']).toContain('application/json');
    expect(forwarded.headers['x-request-id']).toBe('req-123');
    expect(forwarded.headers['x-forwarded-for']).toBeTruthy();
  });

  it('relays upstream status codes and headers', async () => {
    const booking = await upstream((_req, res) => {
      res.statusCode = 404;
      res.setHeader('content-type', 'application/json');
      res.setHeader('set-cookie', ['a=1', 'b=2']);
      res.end('{"detail":"Booking not found"}');
    });
    const res = await request(createApp(testConfig({ booking: booking.url }), quiet))
      .get('/api/v1/bookings/missing')
      .set('authorization', `Bearer ${await token()}`);
    expect(res.status).toBe(404);
    expect(res.body).toEqual({ detail: 'Booking not found' });
    expect(res.headers['set-cookie']).toEqual(['a=1', 'b=2']);
  });

  it('rewrites redirects that point at the upstream host', async () => {
    const catalog = await upstream((_req, res) => {
      res.statusCode = 307;
      res.setHeader('location', `${catalogUrl}/api/v1/catalog/categories/`);
      res.end();
    });
    const catalogUrl = catalog.url;
    const res = await request(createApp(testConfig({ catalog: catalog.url }), quiet)).get('/api/v1/catalog/categories');
    expect(res.status).toBe(307);
    expect(res.headers.location).toBe('/api/v1/catalog/categories/');
  });

  describe('authentication', () => {
    it('rejects protected routes without a valid access token', async () => {
      const user = await upstream();
      const app = createApp(testConfig({ user: user.url }), quiet);

      expect((await request(app).get('/api/v1/users/me')).status).toBe(401);
      expect((await request(app).get('/api/v1/users/me').set('authorization', 'Bearer nope')).status).toBe(401);
      const expired = await token({}, '-1m');
      const res = await request(app).get('/api/v1/users/me').set('authorization', `Bearer ${expired}`);
      expect(res.status).toBe(401);
      expect(res.body.detail).toBe('Token expired');
      expect(user.requests).toHaveLength(0);
    });

    it('rejects refresh and password-reset tokens', async () => {
      const user = await upstream();
      const app = createApp(testConfig({ user: user.url }), quiet);
      for (const claims of [{ type: 'refresh' }, { purpose: 'password_reset' }]) {
        const res = await request(app).get('/api/v1/users/me').set('authorization', `Bearer ${await token(claims)}`);
        expect(res.status).toBe(401);
      }
      expect(user.requests).toHaveLength(0);
    });

    it('forwards the Authorization header for the service to use', async () => {
      const user = await upstream();
      const jwt = await token();
      const res = await request(createApp(testConfig({ user: user.url }), quiet))
        .get('/api/v1/users/me')
        .set('authorization', `Bearer ${jwt}`);
      expect(res.status).toBe(200);
      expect(user.requests[0].headers.authorization).toBe(`Bearer ${jwt}`);
    });

    it('allows anonymous catalogue browsing but not catalogue writes', async () => {
      const catalog = await upstream();
      const app = createApp(testConfig({ catalog: catalog.url }), quiet);
      expect((await request(app).get('/api/v1/catalog/categories')).status).toBe(200);
      expect((await request(app).post('/api/v1/catalog/categories').send({})).status).toBe(401);
    });
  });

  describe('admin routes', () => {
    it('require the admin role and are rewritten to the owning service', async () => {
      const admin = await upstream();
      const app = createApp(testConfig({ admin: admin.url }), quiet);

      const asUser = await request(app).get('/api/v1/admin/audit-logs').set('authorization', `Bearer ${await token()}`);
      expect(asUser.status).toBe(403);

      const asAdmin = await request(app)
        .get('/api/v1/admin/audit-logs?page=2')
        .set('authorization', `Bearer ${await token({ role: 'admin' })}`);
      expect(asAdmin.status).toBe(200);
      expect(admin.requests.map((r) => r.url)).toEqual(['/api/v1/audit-logs?page=2']);
    });

    it('maps finance reports onto payment_service', async () => {
      const payment = await upstream();
      const res = await request(createApp(testConfig({ payment: payment.url }), quiet))
        .get('/api/v1/admin/finance/revenue?date_from=2026-10-01')
        .set('authorization', `Bearer ${await token({ role: 'admin' })}`);
      expect(res.status).toBe(200);
      expect(payment.requests.map((r) => r.url)).toEqual(['/api/v1/finance/revenue?date_from=2026-10-01']);
    });

    it('reports per-service traffic metrics from proxied requests', async () => {
      let calls = 0;
      const catalog = await upstream((_req, res) => {
        res.statusCode = calls++ === 0 ? 200 : 500;
        res.end('{}');
      });
      const app = createApp(testConfig({ catalog: catalog.url }), quiet);
      await request(app).get('/api/v1/catalog/categories');
      await request(app).get('/api/v1/catalog/categories');

      const res = await request(app)
        .get('/api/v1/admin/monitoring/metrics')
        .set('authorization', `Bearer ${await token({ role: 'admin' })}`);
      expect(res.status).toBe(200);
      const catalogMetrics = res.body.data.find((m: { id: string }) => m.id === 'catalog');
      expect(catalogMetrics).toMatchObject({ service: 'catalog_service', requests: 2, errorRate: 0.5, circuit: 'closed' });
      expect(res.body.data).toHaveLength(17);
    });

    it('forwards the verified identity and strips client-supplied identity headers', async () => {
      const admin = await upstream();
      const app = createApp(testConfig({ admin: admin.url, catalog: admin.url }), quiet);

      await request(app)
        .put('/api/v1/admin/access/roles/r1/permissions')
        .set('authorization', `Bearer ${await token({ role: 'admin' })}`)
        .set('x-user-id', 'spoofed')
        .send({ permissions: [] });
      expect(admin.requests[0].url).toBe('/api/v1/access/roles/r1/permissions');
      expect(admin.requests[0].headers['x-user-id']).toBe('user-1');
      expect(admin.requests[0].headers['x-user-role']).toBe('admin');

      // Public routes never carry an identity, even a spoofed one.
      await request(app).get('/api/v1/catalog/categories').set('x-user-id', 'spoofed').set('x-user-role', 'admin');
      expect(admin.requests[1].headers['x-user-id']).toBeUndefined();
      expect(admin.requests[1].headers['x-user-role']).toBeUndefined();
    });

    it('aggregates service health', async () => {
      const auth = await upstream((_req, res) => {
        res.setHeader('content-type', 'application/json');
        res.end('{"status":"healthy"}');
      });
      const user = await upstream((_req, res) => {
        res.statusCode = 500;
        res.end();
      });
      const res = await request(createApp(testConfig({ auth: auth.url, user: user.url }), { ...quiet, healthTimeoutMs: 500 }))
        .get('/api/v1/admin/monitoring/health')
        .set('authorization', `Bearer ${await token({ role: 'admin' })}`);

      expect(res.status).toBe(200);
      const byId = Object.fromEntries(res.body.data.map((s: { id: string; status: string }) => [s.id, s.status]));
      expect(byId.auth).toBe('healthy');
      expect(byId.user).toBe('degraded');
      expect(byId.booking).toBe('down');
      expect(res.body.data).toHaveLength(17);
    });
  });

  it('returns 404 for unknown API paths', async () => {
    const res = await request(createApp(testConfig(), quiet)).get('/api/v1/nothing-here');
    expect(res.status).toBe(404);
  });

  describe('upstream failures', () => {
    it('returns 502 for an unreachable service and opens the circuit', async () => {
      const app = createApp(testConfig({}, { breaker: { failureThreshold: 2, resetTimeoutMs: 60_000 } }), quiet);
      const get = () => request(app).get('/api/v1/catalog/categories');

      expect((await get()).status).toBe(502);
      expect((await get()).status).toBe(502);
      const rejected = await get();
      expect(rejected.status).toBe(503);
      expect(Number(rejected.headers['retry-after'])).toBeGreaterThan(0);
    });

    it('counts 5xx responses as failures', async () => {
      const catalog = await upstream((_req, res) => {
        res.statusCode = 500;
        res.end();
      });
      const app = createApp(testConfig({ catalog: catalog.url }, { breaker: { failureThreshold: 1, resetTimeoutMs: 60_000 } }), quiet);
      expect((await request(app).get('/api/v1/catalog/categories')).status).toBe(500);
      expect((await request(app).get('/api/v1/catalog/categories')).status).toBe(503);
      expect(catalog.requests).toHaveLength(1);
    });

    it('returns 504 when a service is too slow', async () => {
      const catalog = await upstream((_req, res) => {
        setTimeout(() => res.end('{}'), 500);
      });
      const res = await request(createApp(testConfig({ catalog: catalog.url }, { upstreamTimeoutMs: 100 }), quiet)).get(
        '/api/v1/catalog/categories',
      );
      expect(res.status).toBe(504);
    });
  });

  it('rate-limits API requests per client', async () => {
    const catalog = await upstream();
    const app = createApp(testConfig({ catalog: catalog.url }, { rateLimit: { windowMs: 60_000, max: 2 } }), quiet);
    expect((await request(app).get('/api/v1/catalog/categories')).status).toBe(200);
    expect((await request(app).get('/api/v1/catalog/categories')).status).toBe(200);
    expect((await request(app).get('/api/v1/catalog/categories')).status).toBe(429);
    expect((await request(app).get('/health')).status).toBe(200);
  });
});
