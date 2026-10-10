import { errors, jwtVerify, type JWTPayload } from 'jose';

export interface AuthenticatedUser {
  id: string;
  role: string;
}

export class AuthError extends Error {
  constructor(
    message: string,
    readonly status: 401 | 403,
  ) {
    super(message);
  }
}

/**
 * Verifies an HS256 access token issued by auth_service.
 *
 * Refresh tokens and single-purpose tokens (e.g. password reset) are signed with the same
 * key, so they are rejected explicitly: only session access tokens may call the API.
 */
export function createTokenVerifier(secret: string) {
  const key = new TextEncoder().encode(secret);

  return async function verifyToken(authorization: string | undefined): Promise<AuthenticatedUser> {
    const match = /^Bearer\s+(.+)$/i.exec(authorization ?? '');
    if (!match) throw new AuthError('Missing bearer token', 401);

    let payload: JWTPayload;
    try {
      ({ payload } = await jwtVerify(match[1], key, { algorithms: ['HS256'] }));
    } catch (err) {
      const reason = err instanceof errors.JWTExpired ? 'Token expired' : 'Invalid token';
      throw new AuthError(reason, 401);
    }

    if (payload.type !== 'access' || payload.purpose !== undefined || typeof payload.sub !== 'string') {
      throw new AuthError('Invalid token', 401);
    }
    return { id: payload.sub, role: typeof payload.role === 'string' ? payload.role : 'user' };
  };
}
