/**
 * Route table: which upstream service handles a request path, and who may call it.
 *
 * Every service mounts its API under /api/v1, and each top-level segment belongs to
 * exactly one service, so routing is a longest-prefix match on the path.
 */

export type Access = 'public' | 'user' | 'admin';

export interface Route {
  /** Path prefix, matched on whole segments. */
  prefix: string;
  /** Upstream key from the config. */
  upstream: string;
  /** Replacement for `prefix` in the forwarded path (defaults to `prefix`). */
  rewrite?: string;
  /** Who may call it. Default: any signed-in user. */
  access?: Access;
  /** Methods allowed without a token when access is 'public' (default: all). */
  publicMethods?: string[];
}

const READ_ONLY = ['GET', 'HEAD'];

export const ROUTES: Route[] = [
  // Auth: signing in, registering and password recovery are public; the rest needs a token.
  { prefix: '/api/v1/auth/login', upstream: 'auth', access: 'public' },
  { prefix: '/api/v1/auth/register', upstream: 'auth', access: 'public' },
  { prefix: '/api/v1/auth/refresh', upstream: 'auth', access: 'public' },
  { prefix: '/api/v1/auth/send-otp', upstream: 'auth', access: 'public' },
  { prefix: '/api/v1/auth/verify-otp', upstream: 'auth', access: 'public' },
  { prefix: '/api/v1/auth/forgot-password', upstream: 'auth', access: 'public' },
  { prefix: '/api/v1/auth/reset-password', upstream: 'auth', access: 'public' },
  // Deleting an account with an emailed/texted code, from the web page app stores require.
  { prefix: '/api/v1/auth/delete-account/otp', upstream: 'auth', access: 'public', publicMethods: ['POST'] },
  { prefix: '/api/v1/auth', upstream: 'auth' },
  // The current Terms and Privacy Policy version and page links, shown before signing up.
  { prefix: '/api/v1/legal', upstream: 'auth', access: 'public', publicMethods: READ_ONLY },

  { prefix: '/api/v1/users', upstream: 'user' },
  // Shops and their reviews are public to read; rating, replying and reporting need an account.
  { prefix: '/api/v1/shops', upstream: 'shop', access: 'public', publicMethods: READ_ONLY },
  // Review moderation (the reported-review queue, hiding a review).
  { prefix: '/api/v1/reviews', upstream: 'shop', access: 'admin' },
  // Staff contact details are private to the shop owner (checked by shop_service).
  { prefix: '/api/v1/staff', upstream: 'shop' },
  // Includes each booking's chat (/bookings/{id}/messages) and masked call (/bookings/{id}/call); who may
  // take part is checked by booking_service.
  { prefix: '/api/v1/bookings', upstream: 'booking' },
  // Chat moderation: messages with contact details hidden, and who keeps trying.
  { prefix: '/api/v1/chat-moderation', upstream: 'booking', access: 'admin' },
  // Bookable times of a service: browsing, like the catalogue.
  { prefix: '/api/v1/availability', upstream: 'booking', access: 'public', publicMethods: READ_ONLY },

  // Payment provider webhooks are authenticated by their signatures in payment_service.
  { prefix: '/api/v1/webhooks', upstream: 'payment', access: 'public' },
  { prefix: '/api/v1/payments', upstream: 'payment' },
  { prefix: '/api/v1/accounts', upstream: 'payment' },
  { prefix: '/api/v1/finance', upstream: 'payment', access: 'admin' },
  // A customer's loyalty points and referral code.
  { prefix: '/api/v1/loyalty', upstream: 'payment' },

  { prefix: '/api/v1/notifications', upstream: 'notification' },
  { prefix: '/api/v1/locations', upstream: 'tracking' },
  { prefix: '/api/v1/geofences', upstream: 'tracking' },
  { prefix: '/api/v1/queues', upstream: 'queue' },
  { prefix: '/api/v1/events', upstream: 'analytics' },
  { prefix: '/api/v1/metrics', upstream: 'analytics', access: 'admin' },
  { prefix: '/api/v1/funnels', upstream: 'analytics', access: 'admin' },
  { prefix: '/api/v1/cohorts', upstream: 'analytics', access: 'admin' },
  { prefix: '/api/v1/disputes', upstream: 'dispute' },
  { prefix: '/api/v1/risk', upstream: 'trustRisk', access: 'admin' },
  { prefix: '/api/v1/consent', upstream: 'compliance' },
  { prefix: '/api/v1/gdpr', upstream: 'compliance' },
  { prefix: '/api/v1/pricing', upstream: 'pricing' },
  { prefix: '/api/v1/coupons', upstream: 'pricing' },

  // Browsing the catalogue does not require an account.
  { prefix: '/api/v1/categories', upstream: 'serviceCatalog', access: 'public', publicMethods: READ_ONLY },
  { prefix: '/api/v1/services', upstream: 'serviceCatalog', access: 'public', publicMethods: READ_ONLY },

  // Admin dashboard API (apps/admin_dashboard_web), mapped onto the owning services.
  { prefix: '/api/v1/admin/audit-logs', upstream: 'admin', rewrite: '/api/v1/audit-logs', access: 'admin' },
  { prefix: '/api/v1/admin/disputes', upstream: 'dispute', rewrite: '/api/v1/disputes', access: 'admin' },
  { prefix: '/api/v1/admin/finance', upstream: 'payment', rewrite: '/api/v1/finance', access: 'admin' },
  // Commission rates and shop payouts (batches, mark paid, CSV export); payment_service serves them as is.
  { prefix: '/api/v1/admin/payments', upstream: 'payment', access: 'admin' },
  { prefix: '/api/v1/admin/access', upstream: 'admin', rewrite: '/api/v1/access', access: 'admin' },
  { prefix: '/api/v1/admin/reviews', upstream: 'shop', rewrite: '/api/v1/reviews', access: 'admin' },
  { prefix: '/api/v1/admin/chat', upstream: 'booking', rewrite: '/api/v1/chat-moderation', access: 'admin' },
  // Shop onboarding review (queue, approve, reject); shop_service serves it under the same path.
  { prefix: '/api/v1/admin/shops', upstream: 'shop', access: 'admin' },
  { prefix: '/api/v1/admin', upstream: 'admin', access: 'admin' },
  { prefix: '/api/v1/audit-logs', upstream: 'admin', access: 'admin' },
  { prefix: '/api/v1/system-config', upstream: 'admin', access: 'admin' },
  { prefix: '/api/v1/access', upstream: 'admin', access: 'admin' },
];

/** Routes that take file uploads, allowed the larger UPLOAD_MAX_BODY_BYTES body. */
export const UPLOAD_PATHS: RegExp[] = [
  /^\/api\/v1\/users\/me\/avatar$/,
  // A shop's KYC document (shop_service caps it at DOCUMENT_MAX_BYTES, 5 MB by default).
  /^\/api\/v1\/shops\/[^/]+\/documents\/upload$/,
];

export function isUpload(path: string): boolean {
  return UPLOAD_PATHS.some((pattern) => pattern.test(path));
}

export function matchesPrefix(path: string, prefix: string): boolean {
  return path === prefix || path.startsWith(`${prefix}/`);
}

const BY_LONGEST_PREFIX = [...ROUTES].sort((a, b) => b.prefix.length - a.prefix.length);

export function findRoute(path: string): Route | undefined {
  return BY_LONGEST_PREFIX.find((route) => matchesPrefix(path, route.prefix));
}

/** Path to request on the upstream service. */
export function upstreamPath(route: Route, path: string): string {
  return route.rewrite ? route.rewrite + path.slice(route.prefix.length) : path;
}

export function requiredAccess(route: Route, method: string): Access {
  const access = route.access ?? 'user';
  if (access === 'public' && route.publicMethods && !route.publicMethods.includes(method)) {
    return 'user';
  }
  return access;
}
