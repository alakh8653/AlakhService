import redis.asyncio as aioredis
import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.mailer import send_otp_code, send_password_reset
from app.core.security import create_password_reset_token
from app.database import get_db
from app.dependencies import get_current_user, get_redis
from app.models.user import User
from app.schemas.auth import (
    OTPRequest,
    OTPVerify,
    OTPVerifyResponse,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshTokenRequest,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserResponse,
)
from app.services.auth_service import auth_service

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
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    created = await auth_service.send_otp(db, redis, otp_request)
    if created:
        user, code = created
        # Delivered after the response, so known and unknown accounts look the same to the caller.
        background.add_task(send_otp_code, str(user.id), otp_request.phone_or_email, code, otp_request.purpose)
    return {"message": "If the account exists, a code has been sent"}


@router.post("/auth/verify-otp", response_model=OTPVerifyResponse, response_model_exclude_none=True)
async def verify_otp(
    otp_verify: OTPVerify,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    user = await auth_service.verify_otp(db, otp_verify)
    if otp_verify.purpose == "login":
        tokens = await auth_service.issue_tokens(db, user, request)
        return OTPVerifyResponse(message="Signed in", **tokens.model_dump())
    if otp_verify.purpose == "password_reset":
        token = create_password_reset_token(str(user.id), user.hashed_password)
        return OTPVerifyResponse(message="Code verified", reset_token=token)
    return OTPVerifyResponse(message="Account verified")


@router.post("/auth/forgot-password")
async def forgot_password(
    body: PasswordResetRequest,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if user and user.is_active:
        reset_token = create_password_reset_token(str(user.id), user.hashed_password)
        log.info("password_reset_requested", user_id=user.id)
        # Sent after the response, so the reply takes as long whether or not the account exists.
        background.add_task(send_password_reset, str(user.id), user.email, user.full_name, reset_token)
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
