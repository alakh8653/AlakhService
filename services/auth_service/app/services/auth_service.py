import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, delete
import redis.asyncio as aioredis

from app.config import settings
from app.models.user import User, RefreshToken, OTPCode, LoginAttempt
from app.schemas.auth import UserCreate, UserLogin, TokenResponse, OTPRequest, OTPVerify
from app.core.security import (
    hash_password, verify_password, create_access_token, create_refresh_token,
    decode_token, generate_otp, verify_otp, get_device_fingerprint, hash_token
)
from app.core.exceptions import (
    InvalidCredentialsError, UserNotFoundError, UserAlreadyExistsError,
    InvalidTokenError, AccountLockedError, OTPExpiredError, OTPInvalidError,
    OTPTooManyAttemptsError
)

log = structlog.get_logger()


class AuthService:

    async def register(self, db: AsyncSession, user_create: UserCreate) -> User:
        if user_create.email:
            result = await db.execute(select(User).where(User.email == user_create.email))
            if result.scalar_one_or_none():
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

    async def login(self, db: AsyncSession, redis: aioredis.Redis, login_data: UserLogin, request) -> TokenResponse:
        identifier = login_data.email
        ip = request.client.host if request.client else "unknown"

        await self._check_brute_force(redis, identifier, ip)

        result = await db.execute(select(User).where(User.email == login_data.email))
        user = result.scalar_one_or_none()

        if not user or not verify_password(login_data.password, user.hashed_password):
            await self._record_login_attempt(db, identifier, ip, False)
            key = f"auth:attempts:{identifier}"
            await redis.incr(key)
            await redis.expire(key, settings.LOCKOUT_DURATION_SECONDS * 64)
            raise InvalidCredentialsError()

        if not user.is_active:
            raise InvalidCredentialsError("Account is disabled")

        await redis.delete(f"auth:attempts:{identifier}")
        await self._record_login_attempt(db, identifier, ip, True)

        access_token = create_access_token({"sub": str(user.id), "email": user.email, "role": user.role})
        refresh_token_str = create_refresh_token({"sub": str(user.id)})

        fingerprint = get_device_fingerprint(request)
        token_hash = hash_token(refresh_token_str)
        expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

        rt = RefreshToken(
            id=str(uuid.uuid4()),
            user_id=str(user.id),
            token_hash=token_hash,
            device_fingerprint=fingerprint,
            expires_at=expires_at,
            is_revoked=False,
            created_at=datetime.now(timezone.utc),
        )
        db.add(rt)
        await db.flush()

        log.info("user_logged_in", user_id=user.id)
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token_str,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    async def refresh_tokens(self, db: AsyncSession, redis: aioredis.Redis, refresh_token: str, request) -> TokenResponse:
        try:
            payload = decode_token(refresh_token)
        except Exception:
            raise InvalidTokenError("Invalid refresh token")

        if payload.get("type") != "refresh":
            raise InvalidTokenError("Not a refresh token")

        token_hash = hash_token(refresh_token)
        result = await db.execute(
            select(RefreshToken).where(
                and_(RefreshToken.token_hash == token_hash, RefreshToken.is_revoked == False)
            )
        )
        rt = result.scalar_one_or_none()
        if not rt:
            raise InvalidTokenError("Refresh token not found or revoked")

        now = datetime.now(timezone.utc)
        rt_expires = rt.expires_at
        if rt_expires.tzinfo is None:
            rt_expires = rt_expires.replace(tzinfo=timezone.utc)
        if rt_expires < now:
            raise InvalidTokenError("Refresh token expired")

        rt.is_revoked = True
        await db.flush()

        user_id = payload.get("sub")
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user or not user.is_active:
            raise InvalidCredentialsError("User not found or inactive")

        access_token = create_access_token({"sub": str(user.id), "email": user.email, "role": user.role})
        new_refresh_token = create_refresh_token({"sub": str(user.id)})

        fingerprint = get_device_fingerprint(request)
        new_token_hash = hash_token(new_refresh_token)
        new_expires_at = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

        new_rt = RefreshToken(
            id=str(uuid.uuid4()),
            user_id=str(user.id),
            token_hash=new_token_hash,
            device_fingerprint=fingerprint,
            expires_at=new_expires_at,
            is_revoked=False,
            created_at=now,
        )
        db.add(new_rt)
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
            select(RefreshToken).where(
                and_(RefreshToken.token_hash == token_hash, RefreshToken.user_id == user_id)
            )
        )
        rt = result.scalar_one_or_none()
        if rt:
            rt.is_revoked = True
            await db.flush()
        try:
            payload = decode_token(refresh_token)
            exp = payload.get("exp")
            if exp:
                ttl = int(exp - datetime.now(timezone.utc).timestamp())
                if ttl > 0:
                    await redis.setex(f"auth:blacklist:{refresh_token}", ttl, "1")
        except Exception:
            pass
        log.info("user_logged_out", user_id=user_id)
        return True

    async def logout_all_devices(self, db: AsyncSession, redis: aioredis.Redis, user_id: str) -> bool:
        await db.execute(
            update(RefreshToken)
            .where(and_(RefreshToken.user_id == user_id, RefreshToken.is_revoked == False))
            .values(is_revoked=True)
        )
        await db.flush()
        log.info("user_logged_out_all", user_id=user_id)
        return True

    async def send_otp(self, db: AsyncSession, otp_request: OTPRequest) -> bool:
        identifier = otp_request.phone_or_email
        if "@" in identifier:
            result = await db.execute(select(User).where(User.email == identifier))
        else:
            result = await db.execute(select(User).where(User.phone == identifier))
        user = result.scalar_one_or_none()
        if not user:
            raise UserNotFoundError()

        await db.execute(
            update(OTPCode)
            .where(and_(OTPCode.user_id == str(user.id), OTPCode.purpose == otp_request.purpose, OTPCode.is_used == False))
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

        log.info("otp_sent", user_id=user.id, purpose=otp_request.purpose, code=plain_code)
        return True

    async def verify_otp(self, db: AsyncSession, otp_verify: OTPVerify) -> bool:
        identifier = otp_verify.phone_or_email
        if "@" in identifier:
            result = await db.execute(select(User).where(User.email == identifier))
        else:
            result = await db.execute(select(User).where(User.phone == identifier))
        user = result.scalar_one_or_none()
        if not user:
            raise UserNotFoundError()

        now = datetime.now(timezone.utc)
        result = await db.execute(
            select(OTPCode).where(
                and_(
                    OTPCode.user_id == str(user.id),
                    OTPCode.purpose == otp_verify.purpose,
                    OTPCode.is_used == False,
                )
            ).order_by(OTPCode.created_at.desc())
        )
        otp = result.scalar_one_or_none()

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
            await db.flush()
            raise OTPInvalidError()

        otp.is_used = True
        if otp_verify.purpose == "registration":
            user.is_verified = True
        await db.flush()

        log.info("otp_verified", user_id=user.id, purpose=otp_verify.purpose)
        return True

    async def reset_password(self, db: AsyncSession, token: str, new_password: str) -> bool:
        try:
            payload = decode_token(token)
        except Exception:
            raise InvalidTokenError()

        user_id = payload.get("sub")
        if not user_id:
            raise InvalidTokenError()

        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise UserNotFoundError()

        user.hashed_password = hash_password(new_password)
        user.updated_at = datetime.now(timezone.utc)
        await db.flush()
        log.info("password_reset", user_id=user.id)
        return True

    async def _check_brute_force(self, redis: aioredis.Redis, identifier: str, ip: str):
        key = f"auth:attempts:{identifier}"
        attempts_raw = await redis.get(key)
        attempts = int(attempts_raw) if attempts_raw else 0

        if attempts >= settings.MAX_LOGIN_ATTEMPTS:
            multiplier = 2 ** (attempts // settings.MAX_LOGIN_ATTEMPTS - 1)
            lockout = settings.LOCKOUT_DURATION_SECONDS * multiplier
            ttl = await redis.ttl(key)
            remaining = ttl if ttl > 0 else lockout
            raise AccountLockedError(lockout_seconds=int(remaining))

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
