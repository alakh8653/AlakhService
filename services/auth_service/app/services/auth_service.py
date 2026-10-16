import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import redis.asyncio as aioredis
import structlog
from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import (
    AccountLockedError,
    InvalidCredentialsError,
    InvalidTokenError,
    OTPExpiredError,
    OTPInvalidError,
    OTPRateLimitedError,
    OTPTooManyAttemptsError,
    UserAlreadyExistsError,
)
from app.core.revocation import revoke_session, revoke_user_tokens
from app.core.security import (
    PASSWORD_RESET_TYPE,
    client_ip,
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_otp,
    get_device_fingerprint,
    hash_password,
    hash_token,
    password_reset_token_matches,
    verify_otp,
    verify_password,
)
from app.models.user import LoginAttempt, OTPCode, RefreshToken, User
from app.schemas.auth import OTPRequest, OTPVerify, TokenResponse, UserCreate, UserLogin

log = structlog.get_logger()

# Two requests refreshing with the same token at once (an app retrying) are not an attack.
REUSE_GRACE_SECONDS = 30


class AuthService:
    async def register(self, db: AsyncSession, user_create: UserCreate) -> User:
        if user_create.email:
            result = await db.execute(select(User).where(func.lower(User.email) == user_create.email))
            if result.scalars().first():
                raise UserAlreadyExistsError(f"User with email {user_create.email} already exists")
        if user_create.phone:
            result = await db.execute(select(User).where(User.phone == user_create.phone))
            if result.scalar_one_or_none():
                raise UserAlreadyExistsError(f"User with phone {user_create.phone} already exists")

        user = User(
            id=str(uuid.uuid4()),
            email=user_create.email,
            phone=user_create.phone,
            full_name=user_create.full_name,
            hashed_password=hash_password(user_create.password),
            is_active=True,
            is_verified=False,
            is_superuser=False,
            role="user",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(user)
        await db.flush()
        log.info("user_registered", user_id=user.id, email=user.email)
        return user

    async def _find_user(self, db: AsyncSession, identifier: str) -> Optional[User]:
        """The account for an email address or an E.164 phone number."""
        # Emails compare case-insensitively (older accounts may have been stored with capitals).
        condition = func.lower(User.email) == identifier.lower() if "@" in identifier else User.phone == identifier
        result = await db.execute(select(User).where(condition).order_by(User.created_at).limit(1))
        return result.scalars().first()

    async def login(self, db: AsyncSession, redis: aioredis.Redis, login_data: UserLogin, request) -> TokenResponse:
        identifier = login_data.identifier
        ip = client_ip(request)

        await self._check_brute_force(redis, identifier, ip)

        user = await self._find_user(db, identifier)

        if not user or not verify_password(login_data.password, user.hashed_password):
            await self._record_login_attempt(db, identifier, ip, False)
            await self._count_failure(redis, identifier, ip)
            # Keep the audit row: the error makes the request's session roll back.
            await db.commit()
            raise InvalidCredentialsError()

        if not user.is_active:
            raise InvalidCredentialsError("Account is disabled")

        await redis.delete(f"auth:attempts:{identifier}:{ip}")
        await self._record_login_attempt(db, identifier, ip, True)
        return await self.issue_tokens(db, user, request)

    def _session_token(
        self, user: User, request, session_id: str, signed_in_at: datetime
    ) -> tuple[str, str, RefreshToken]:
        """An access token, a refresh token and its row to store, for one session (sign-in on one device)."""
        access_token = create_access_token(
            {"sub": str(user.id), "email": user.email, "role": user.role, "sid": session_id}
        )
        refresh_token_str = create_refresh_token({"sub": str(user.id), "sid": session_id})
        now = datetime.now(timezone.utc)
        row = RefreshToken(
            id=str(uuid.uuid4()),
            user_id=str(user.id),
            token_hash=hash_token(refresh_token_str),
            device_fingerprint=get_device_fingerprint(request),
            session_id=session_id,
            user_agent=(request.headers.get("user-agent") or "")[:255] or None,
            ip_address=client_ip(request),
            signed_in_at=signed_in_at,
            expires_at=now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
            is_revoked=False,
            created_at=now,
        )
        return access_token, refresh_token_str, row

    async def issue_tokens(self, db: AsyncSession, user: User, request) -> TokenResponse:
        access_token, refresh_token_str, row = self._session_token(
            user, request, str(uuid.uuid4()), datetime.now(timezone.utc)
        )
        db.add(row)
        await db.flush()

        log.info("user_logged_in", user_id=user.id)
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token_str,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    async def refresh_tokens(
        self, db: AsyncSession, redis: aioredis.Redis, refresh_token: str, request
    ) -> TokenResponse:
        try:
            payload = decode_token(refresh_token)
        except Exception:
            raise InvalidTokenError("Invalid refresh token") from None

        if payload.get("type") != "refresh":
            raise InvalidTokenError("Not a refresh token")

        token_hash = hash_token(refresh_token)
        result = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
        rt = result.scalar_one_or_none()
        now = datetime.now(timezone.utc)
        if rt is not None and rt.is_revoked:
            # A refresh token is used once. Seeing a spent one again means a copy exists somewhere
            # else (or the app retried): unless it was rotated a moment ago by a parallel request,
            # end the whole session, so whoever holds the copy is signed out too.
            revoked_at = rt.revoked_at
            if revoked_at is not None and revoked_at.tzinfo is None:
                revoked_at = revoked_at.replace(tzinfo=timezone.utc)
            if revoked_at is None or now - revoked_at > timedelta(seconds=REUSE_GRACE_SECONDS):
                await self._end_session(db, redis, rt.user_id, rt.session_id, reason="refresh_token_reused")
                await db.commit()
            raise InvalidTokenError("Refresh token not found or revoked")
        if not rt:
            raise InvalidTokenError("Refresh token not found or revoked")

        rt_expires = rt.expires_at
        if rt_expires.tzinfo is None:
            rt_expires = rt_expires.replace(tzinfo=timezone.utc)
        if rt_expires < now:
            raise InvalidTokenError("Refresh token expired")

        rt.is_revoked = True
        rt.revoked_at = now
        await db.flush()

        user_id = payload.get("sub")
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user or not user.is_active:
            raise InvalidCredentialsError("User not found or inactive")

        # The same session continues (older tokens have no session id: they start one).
        access_token, new_refresh_token, row = self._session_token(
            user, request, rt.session_id or str(uuid.uuid4()), rt.signed_in_at or rt.created_at or now
        )
        db.add(row)
        await db.flush()

        return TokenResponse(
            access_token=access_token,
            refresh_token=new_refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    async def logout(self, db: AsyncSession, redis: aioredis.Redis, user_id: str, refresh_token: str) -> bool:
        token_hash = hash_token(refresh_token)
        result = await db.execute(
            select(RefreshToken).where(and_(RefreshToken.token_hash == token_hash, RefreshToken.user_id == user_id))
        )
        rt = result.scalar_one_or_none()
        if rt:
            await self._end_session(db, redis, user_id, rt.session_id)
        log.info("user_logged_out", user_id=user_id)
        return True

    async def _end_session(
        self, db: AsyncSession, redis: aioredis.Redis, user_id: str, session_id: Optional[str], reason: str = ""
    ) -> None:
        """Revokes a session's refresh tokens and stops its access tokens at the gateway."""
        now = datetime.now(timezone.utc)
        if session_id:
            await db.execute(
                update(RefreshToken)
                .where(RefreshToken.session_id == session_id, RefreshToken.is_revoked == False)  # noqa: E712
                .values(is_revoked=True, revoked_at=now)
            )
            await revoke_session(redis, session_id)
        else:  # a session from before session ids: end everything to be sure
            await self.revoke_all_sessions(db, redis, user_id)
        await db.flush()
        if reason:
            log.warning(reason, user_id=user_id, session_id=session_id)

    async def revoke_all_sessions(self, db: AsyncSession, redis: Optional[aioredis.Redis], user_id: str) -> None:
        """Signs the user out everywhere: refresh tokens revoked, access tokens refused."""
        await db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.is_revoked == False)  # noqa: E712
            .values(is_revoked=True, revoked_at=datetime.now(timezone.utc))
        )
        await db.flush()
        if redis is not None:
            await revoke_user_tokens(redis, user_id)

    async def list_sessions(self, db: AsyncSession, user_id: str) -> list[RefreshToken]:
        """The user's signed-in devices: each session's current refresh token, newest first."""
        result = await db.execute(
            select(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.is_revoked == False,  # noqa: E712
                RefreshToken.expires_at > datetime.now(timezone.utc),
            )
            .order_by(RefreshToken.created_at.desc())
        )
        return list(result.scalars())

    async def end_session(self, db: AsyncSession, redis: aioredis.Redis, user_id: str, session_id: str) -> bool:
        result = await db.execute(
            select(RefreshToken.id).where(RefreshToken.user_id == user_id, RefreshToken.session_id == session_id)
        )
        if result.first() is None:
            return False
        await self._end_session(db, redis, user_id, session_id)
        return True

    async def logout_all_devices(self, db: AsyncSession, redis: aioredis.Redis, user_id: str) -> bool:
        await self.revoke_all_sessions(db, redis, user_id)
        log.info("user_logged_out_all", user_id=user_id)
        return True

    async def send_otp(self, db: AsyncSession, redis: aioredis.Redis, otp_request: OTPRequest) -> Optional[tuple]:
        """Create a code for the account, if there is one, and return (user, code) to deliver.

        Unknown accounts get the same treatment from the caller's point of view, so the endpoint
        does not reveal which emails and phone numbers are registered.
        """
        identifier = otp_request.phone_or_email
        window_key = f"auth:otp_requests:{identifier}"
        count = await redis.incr(window_key)
        if count == 1:
            await redis.expire(window_key, settings.OTP_REQUEST_WINDOW_SECONDS)
        if count > settings.OTP_REQUESTS_PER_WINDOW:
            raise OTPRateLimitedError()

        user = await self._find_user(db, identifier)
        if not user or not user.is_active:
            log.info("otp_requested_unknown_account", purpose=otp_request.purpose)
            return None

        await db.execute(
            update(OTPCode)
            .where(
                and_(OTPCode.user_id == str(user.id), OTPCode.purpose == otp_request.purpose, OTPCode.is_used == False)
            )
            .values(is_used=True)
        )

        plain_code, code_hash = generate_otp()
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=settings.OTP_EXPIRE_SECONDS)

        otp = OTPCode(
            id=str(uuid.uuid4()),
            user_id=str(user.id),
            code_hash=code_hash,
            purpose=otp_request.purpose,
            expires_at=expires_at,
            is_used=False,
            attempts=0,
            created_at=datetime.now(timezone.utc),
        )
        db.add(otp)
        await db.flush()

        log.info("otp_sent", user_id=user.id, purpose=otp_request.purpose)
        return user, plain_code

    async def verify_otp(self, db: AsyncSession, otp_verify: OTPVerify) -> User:
        user = await self._find_user(db, otp_verify.phone_or_email)
        if not user or not user.is_active:
            raise OTPInvalidError()

        now = datetime.now(timezone.utc)
        result = await db.execute(
            select(OTPCode)
            .where(
                and_(
                    OTPCode.user_id == str(user.id),
                    OTPCode.purpose == otp_verify.purpose,
                    OTPCode.is_used == False,
                )
            )
            .order_by(OTPCode.created_at.desc())
            .limit(1)
        )
        otp = result.scalars().first()

        if not otp:
            raise OTPInvalidError("No active OTP found")

        otp_expires = otp.expires_at
        if otp_expires.tzinfo is None:
            otp_expires = otp_expires.replace(tzinfo=timezone.utc)
        if otp_expires < now:
            raise OTPExpiredError()

        if otp.attempts >= 5:
            raise OTPTooManyAttemptsError()

        otp.attempts += 1

        if not verify_otp(otp_verify.code, otp.code_hash):
            # Committed now: the error rolls the request's session back, which would forget the
            # guess and let anyone try every code.
            await db.commit()
            raise OTPInvalidError()

        otp.is_used = True
        if otp_verify.purpose == "registration":
            user.is_verified = True
        await db.flush()

        log.info("otp_verified", user_id=user.id, purpose=otp_verify.purpose)
        return user

    async def reset_password(
        self, db: AsyncSession, token: str, new_password: str, redis: Optional[aioredis.Redis] = None
    ) -> bool:
        try:
            payload = decode_token(token)
        except Exception:
            raise InvalidTokenError() from None

        user_id = payload.get("sub")
        if not user_id or payload.get("type") != PASSWORD_RESET_TYPE:
            raise InvalidTokenError()

        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        # A token issued before the last password change (including by this reset) is spent.
        if not user or not password_reset_token_matches(payload, user.hashed_password):
            raise InvalidTokenError()

        user.hashed_password = hash_password(new_password)
        user.updated_at = datetime.now(timezone.utc)
        # Sign out every session that was opened with the old password.
        await self.revoke_all_sessions(db, redis, user.id)
        log.info("password_reset", user_id=user.id)
        return True

    # Failed sign-ins lock the account out *from that network*: MAX_LOGIN_ATTEMPTS failures from one
    # IP lock it for LOCKOUT_DURATION_SECONDS, doubling each time up to an hour. Locking per account
    # alone would let anyone lock someone else out just by knowing their email. Guessing spread over
    # many IPs is caught by a looser per-account limit (and the gateway limits each IP).
    MAX_LOCKOUT_SECONDS = 3600
    ACCOUNT_WIDE_FAILURES = 20
    ACCOUNT_WIDE_LOCKOUT_SECONDS = 900

    async def _check_brute_force(self, redis: aioredis.Redis, identifier: str, ip: str):
        for key in (f"auth:locked:{identifier}:{ip}", f"auth:locked:{identifier}"):
            if await redis.get(key):
                ttl = await redis.ttl(key)
                raise AccountLockedError(lockout_seconds=int(ttl if ttl > 0 else settings.LOCKOUT_DURATION_SECONDS))

    async def _count_failure(self, redis: aioredis.Redis, identifier: str, ip: str):
        here = f"auth:attempts:{identifier}:{ip}"
        failures = await redis.incr(here)
        await redis.expire(here, 86400)  # how far back repeated lockouts escalate
        if failures % settings.MAX_LOGIN_ATTEMPTS == 0:
            lockout = settings.LOCKOUT_DURATION_SECONDS * 2 ** (failures // settings.MAX_LOGIN_ATTEMPTS - 1)
            await redis.set(f"auth:locked:{identifier}:{ip}", "1", ex=min(lockout, self.MAX_LOCKOUT_SECONDS))
        everywhere = f"auth:attempts:{identifier}"
        total = await redis.incr(everywhere)
        await redis.expire(everywhere, self.ACCOUNT_WIDE_LOCKOUT_SECONDS)
        if total >= self.ACCOUNT_WIDE_FAILURES:
            await redis.set(f"auth:locked:{identifier}", "1", ex=self.ACCOUNT_WIDE_LOCKOUT_SECONDS)
            await redis.delete(everywhere)

    async def _record_login_attempt(self, db: AsyncSession, identifier: str, ip: str, success: bool):
        attempt = LoginAttempt(
            id=str(uuid.uuid4()),
            identifier=identifier,
            ip_address=ip,
            success=success,
            created_at=datetime.now(timezone.utc),
        )
        db.add(attempt)
        await db.flush()


auth_service = AuthService()
