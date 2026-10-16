/**
 * Signed-out and banned users' access tokens, as auth_service records them in Redis.
 *
 * Access tokens are self-contained, so without this a token stays usable until it expires
 * (30 minutes) even after the person signs out, resets their password or is banned.
 *   auth:revoked_before:{user id} = time (seconds): every token issued before it is revoked
 *   auth:revoked_sid:{session id} = every token of one signed-in device (signed out, or replayed)
 *   auth:revoked_jti:{token id}   = one token
 */

/** Sends one raw Redis command, e.g. ['MGET', 'a', 'b']. */
export type SendCommand = (args: string[]) => Promise<unknown>;

export interface TokenIdentity {
  id: string;
  sid?: string;
  jti?: string;
  iat?: number;
}

export type RevocationCheck = (token: TokenIdentity) => Promise<boolean>;

/**
 * Without Redis nothing is revoked early. If Redis fails the check lets the token through (and
 * reports it): an outage of the revocation store must not sign everyone out.
 */
export function createRevocationCheck(send: SendCommand | undefined, onError: (err: unknown) => void): RevocationCheck {
  if (!send) return async () => false;
  return async ({ id, sid, jti, iat }) => {
    const keys = [
      `auth:revoked_before:${id}`,
      ...(sid ? [`auth:revoked_sid:${sid}`] : []),
      ...(jti ? [`auth:revoked_jti:${jti}`] : []),
    ];
    let reply: unknown;
    try {
      reply = await send(['MGET', ...keys]);
    } catch (err) {
      onError(err);
      return false;
    }
    const [before, ...others] = Array.isArray(reply) ? reply : [];
    if (before !== null && before !== undefined && (iat ?? 0) < Number(before)) return true;
    return others.some((v) => v !== null && v !== undefined);
  };
}
