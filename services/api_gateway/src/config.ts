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
  /** Tighter per-client limit on sign-in, sign-up, OTP and password-reset requests. */
  authRateLimit: { windowMs: number; max: number };
  /** Shared store for rate limits and token revocation; in-memory limits (per instance) without it. */
  redisUrl?: string;
  /** How many proxies in front of the gateway to trust for the client IP (X-Forwarded-For). */
  trustProxy: number;
  /** Largest request body accepted, in bytes; uploads get [uploadMaxBodyBytes]. */
  maxBodyBytes: number;
  uploadMaxBodyBytes: number;
  /** Bearer token Prometheus must send to read /metrics; without one /metrics is open (not in production). */
  metricsToken?: string;
  production: boolean;
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
  analytics: ['ANALYTICS_SERVICE_URL', 'analytics_service'],
  dispute: ['DISPUTE_SERVICE_URL', 'dispute_service'],
  trustRisk: ['TRUST_RISK_SERVICE_URL', 'trust_risk_service'],
  admin: ['ADMIN_SERVICE_URL', 'admin_service'],
  compliance: ['COMPLIANCE_SERVICE_URL', 'compliance_service'],
  pricing: ['PRICING_ENGINE_URL', 'pricing_engine'],
  serviceCatalog: ['SERVICE_CATALOG_URL', 'service_catalog_service'],
};

/** Placeholder secrets from the examples and compose defaults: never acceptable in production. */
const KNOWN_DEFAULT_SECRETS = new Set([
  'changeme',
  'change-in-production',
  'change-me',
  'secret',
  'dev-secret',
  'your-secret-key',
  'your-super-secret-jwt-key-change-in-production',
]);

/** Refuses to start a production gateway with settings that are only safe on a laptop. */
export function productionProblems(config: Pick<GatewayConfig, 'jwtSecret' | 'corsOrigins' | 'redisUrl'>): string[] {
  const problems: string[] = [];
  if (KNOWN_DEFAULT_SECRETS.has(config.jwtSecret) || config.jwtSecret.length < 32) {
    problems.push('SECRET_KEY is a placeholder or shorter than 32 characters');
  }
  if (config.corsOrigins.includes('*')) problems.push('CORS_ORIGINS must list the dashboard origins, not *');
  if (!config.redisUrl) problems.push('REDIS_URL is required so rate limits and sign-outs apply across instances');
  return problems;
}

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

  const config: GatewayConfig = {
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
    authRateLimit: {
      windowMs: intFromEnv(env, 'AUTH_RATE_LIMIT_WINDOW_MS', 600_000),
      max: intFromEnv(env, 'AUTH_RATE_LIMIT_MAX', 60),
    },
    redisUrl: env.REDIS_URL || undefined,
    trustProxy: intFromEnv(env, 'TRUST_PROXY', 0),
    maxBodyBytes: intFromEnv(env, 'MAX_BODY_BYTES', 1_048_576),
    uploadMaxBodyBytes: intFromEnv(env, 'UPLOAD_MAX_BODY_BYTES', 6_291_456),
    metricsToken: env.METRICS_TOKEN || undefined,
    production: (env.ENVIRONMENT ?? env.NODE_ENV) === 'production',
    upstreamTimeoutMs: intFromEnv(env, 'UPSTREAM_TIMEOUT_MS', 15_000),
    breaker: {
      failureThreshold: intFromEnv(env, 'BREAKER_FAILURE_THRESHOLD', 5),
      resetTimeoutMs: intFromEnv(env, 'BREAKER_RESET_TIMEOUT_MS', 30_000),
    },
    upstreams,
  };
  if (config.production) {
    const problems = productionProblems(config);
    if (problems.length) throw new Error(`Refusing to start in production: ${problems.join('; ')}`);
  }
  return config;
}
