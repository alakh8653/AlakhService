from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis

from app.database import get_db
from app.dependencies import get_redis, get_current_user
from app.schemas.auth import (
    UserCreate, UserLogin, TokenResponse, RefreshTokenRequest,
    OTPRequest, OTPVerify, PasswordResetRequest, PasswordResetConfirm, UserResponse
)
from app.services.auth_service import auth_service
from app.core.exceptions import AuthServiceError, AccountLockedError, UserNotFoundError
from app.core.security import create_access_token, decode_token
from app.models.user import User
from sqlalchemy import select
import structlog

router = APIRouter()
log = structlog.get_logger()


@router.post("/auth/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_create: UserCreate, db: AsyncSession = Depends(get_db)):
    user = await auth_service.register(db, user_create)
    return user


@router.post("/auth/login", response_model=TokenResponse)
async def login(
    login_data: UserLogin,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    return await auth_service.login(db, redis, login_data, request)


@router.post("/auth/refresh", response_model=TokenResponse)
async def refresh(
    body: RefreshTokenRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    return await auth_service.refresh_tokens(db, redis, body.refresh_token, request)


@router.post("/auth/logout")
async def logout(
    body: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user.get("sub")
    await auth_service.logout(db, redis, user_id, body.refresh_token)
    return {"message": "Logged out successfully"}


@router.post("/auth/logout-all")
async def logout_all(
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user.get("sub")
    await auth_service.logout_all_devices(db, redis, user_id)
    return {"message": "Logged out from all devices"}


@router.post("/auth/send-otp")
async def send_otp(
    otp_request: OTPRequest,
    db: AsyncSession = Depends(get_db),
):
    await auth_service.send_otp(db, otp_request)
    return {"message": "OTP sent"}


@router.post("/auth/verify-otp")
async def verify_otp(
    otp_verify: OTPVerify,
    db: AsyncSession = Depends(get_db),
):
    await auth_service.verify_otp(db, otp_verify)
    return {"message": "OTP verified successfully"}


@router.post("/auth/forgot-password")
async def forgot_password(
    body: PasswordResetRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if user:
        reset_token = create_access_token({"sub": str(user.id), "purpose": "password_reset"})
        log.info("password_reset_requested", user_id=user.id, token=reset_token)
    return {"message": "If the email exists, a reset link has been sent"}


@router.post("/auth/reset-password")
async def reset_password(
    body: PasswordResetConfirm,
    db: AsyncSession = Depends(get_db),
):
    await auth_service.reset_password(db, body.token, body.new_password)
    return {"message": "Password reset successfully"}


@router.get("/auth/me", response_model=UserResponse)
async def get_me(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user.get("sub")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
