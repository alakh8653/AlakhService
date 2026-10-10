/** Runtime configuration, read from environment variables. */

export interface Upstream {
  /** Short key used in the route table, e.g. "auth". */
  key: string;
  /** Human-readable service name, as shown on the health page. */
  name: string;
  /** Base URL of the service, e.g. http://auth_service:8000 */
  url: string;
}

export interface GatewayConfig {
  port: number;
  jwtSecret: string;
  corsOrigins: string[];
  rateLimit: { windowMs: number; max: number };
  upstreamTimeoutMs: number;
  breaker: { failureThreshold: number; resetTimeoutMs: number };
  upstreams: Record<string, Upstream>;
}

/** key -> [env var holding the URL, docker compose service name] */
const UPSTREAMS: Record<string, [string, string]> = {
  auth: ['AUTH_SERVICE_URL', 'auth_service'],
  user: ['USER_SERVICE_URL', 'user_service'],
  shop: ['SHOP_SERVICE_URL', 'shop_service'],
  booking: ['BOOKING_SERVICE_URL', 'booking_service'],
  payment: ['PAYMENT_SERVICE_URL', 'payment_service'],
  notification: ['NOTIFICATION_SERVICE_URL', 'notification_service'],
  tracking: ['TRACKING_SERVICE_URL', 'tracking_service'],
  queue: ['QUEUE_SERVICE_URL', 'queue_service'],
  dispatch: ['DISPATCH_SERVICE_URL', 'dispatch_service'],
  analytics: ['ANALYTICS_SERVICE_URL', 'analytics_service'],
  dispute: ['DISPUTE_SERVICE_URL', 'dispute_service'],
  trustRisk: ['TRUST_RISK_SERVICE_URL', 'trust_risk_service'],
  admin: ['ADMIN_SERVICE_URL', 'admin_service'],
  compliance: ['COMPLIANCE_SERVICE_URL', 'compliance_service'],
  pricing: ['PRICING_ENGINE_URL', 'pricing_engine'],
  serviceCatalog: ['SERVICE_CATALOG_URL', 'service_catalog_service'],
  catalog: ['CATALOG_SERVICE_URL', 'catalog_service'],
};

function intFromEnv(env: NodeJS.ProcessEnv, name: string, fallback: number): number {
  const raw = env[name];
  if (raw === undefined || raw === '') return fallback;
  const value = Number.parseInt(raw, 10);
  if (!Number.isFinite(value) || value < 0) {
    throw new Error(`${name} must be a non-negative integer, got "${raw}"`);
  }
  return value;
}

export function loadConfig(env: NodeJS.ProcessEnv = process.env): GatewayConfig {
  // Same variable the Python services read, so tokens issued by auth_service verify here.
  const jwtSecret = env.SECRET_KEY ?? env.JWT_SECRET_KEY;
  if (!jwtSecret) {
    throw new Error('SECRET_KEY (or JWT_SECRET_KEY) must be set to verify access tokens');
  }

  const upstreams: Record<string, Upstream> = {};
  for (const [key, [envVar, composeName]] of Object.entries(UPSTREAMS)) {
    const url = (env[envVar] ?? `http://${composeName}:8000`).replace(/\/+$/, '');
    upstreams[key] = { key, name: composeName, url };
  }

  return {
    port: intFromEnv(env, 'PORT', 3000),
    jwtSecret,
    corsOrigins: (env.CORS_ORIGINS ?? 'http://localhost:5173,http://localhost:5174')
      .split(',')
      .map((origin) => origin.trim())
      .filter(Boolean),
    rateLimit: {
      windowMs: intFromEnv(env, 'RATE_LIMIT_WINDOW_MS', 60_000),
      max: intFromEnv(env, 'RATE_LIMIT_MAX', 300),
    },
    upstreamTimeoutMs: intFromEnv(env, 'UPSTREAM_TIMEOUT_MS', 15_000),
    breaker: {
      failureThreshold: intFromEnv(env, 'BREAKER_FAILURE_THRESHOLD', 5),
      resetTimeoutMs: intFromEnv(env, 'BREAKER_RESET_TIMEOUT_MS', 30_000),
    },
    upstreams,
  };
}
