from datetime import datetime, timezone

import redis.asyncio as aioredis
import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.background import BackgroundTask

from app.core import risk
from app.core.consent import record_terms_consent
from app.core.exceptions import InvalidCredentialsError
from app.core.mailer import send_otp_code, send_password_reset
from app.core.security import client_ip, create_password_reset_token, describe_device
from app.database import get_db
from app.dependencies import get_current_user, get_redis
from app.models.user import User
from app.schemas.auth import (
    AcceptTerms,
    OTPRequest,
    OTPVerify,
    OTPVerifyResponse,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshTokenRequest,
    SessionResponse,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserResponse,
)
from app.services.auth_service import auth_service

router = APIRouter()
log = structlog.get_logger()


TERMS_REQUIRED = "Please accept the Terms and Privacy Policy"


@router.post("/auth/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_create: UserCreate,
    request: Request,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Creates an account. accepted_terms_version (from GET /legal/current) is required: it is the
    person's acceptance of the Terms and Privacy Policy, kept on the account and in the consent register."""
    version = (user_create.accepted_terms_version or "").strip()
    if not version:
        raise HTTPException(status_code=422, detail=TERMS_REQUIRED)
    user_create.accepted_terms_version = version
    user = await auth_service.register(db, user_create)
    # After the response, once the account is committed.
    background.add_task(
        record_terms_consent, str(user.id), version, client_ip(request), request.headers.get("user-agent")
    )
    return user


@router.post("/auth/accept-terms", response_model=UserResponse)
async def accept_terms(
    body: AcceptTerms,
    request: Request,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Records that a signed-in person accepted a (newer) Terms and Privacy Policy version: older
    accounts, and everyone after the terms change, are asked again by the app."""
    user = await db.get(User, current_user["sub"])
    if user is None or not user.is_active:
        raise HTTPException(status_code=404, detail="User not found")
    user.accepted_terms_version = body.accepted_terms_version.strip()
    user.accepted_terms_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(user)
    background.add_task(
        record_terms_consent,
        str(user.id),
        user.accepted_terms_version,
        client_ip(request),
        request.headers.get("user-agent"),
    )
    return user


@router.post("/auth/login", response_model=TokenResponse)
async def login(
    login_data: UserLogin,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    try:
        return await auth_service.login(db, redis, login_data, request)
    except InvalidCredentialsError as e:
        if not e.locked_out_user_id:
            raise
        # Answered here rather than by the app's error handler so the report can go after the response.
        return JSONResponse(
            status_code=401,
            content={"detail": str(e)},
            background=BackgroundTask(risk.report_risk, e.locked_out_user_id, *risk.LOGIN_LOCKOUT),
        )


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
    if otp_verify.purpose in ("login", "registration"):
        # Confirming a new account's code also signs it in.
        tokens = await auth_service.issue_tokens(db, user, request)
        message = "Signed in" if otp_verify.purpose == "login" else "Account verified"
        return OTPVerifyResponse(message=message, **tokens.model_dump())
    if otp_verify.purpose == "password_reset":
        token = create_password_reset_token(str(user.id), user.hashed_password)
        return OTPVerifyResponse(message="Code verified", reset_token=token)


@router.post("/auth/forgot-password")
async def forgot_password(
    body: PasswordResetRequest,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User).where(func.lower(User.email) == body.email).order_by(User.created_at).limit(1)
    )
    user = result.scalars().first()
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
    redis: aioredis.Redis = Depends(get_redis),
):
    await auth_service.reset_password(db, body.token, body.new_password, redis)
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


@router.get("/auth/sessions", response_model=list[SessionResponse])
async def list_sessions(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Where the caller is signed in: one entry per device, the one making this request marked current."""
    rows = await auth_service.list_sessions(db, current_user["sub"])
    current = current_user.get("sid")
    return [
        SessionResponse(
            id=row.session_id or row.id,
            device=describe_device(row.user_agent),
            ip_address=row.ip_address,
            signed_in_at=row.signed_in_at or row.created_at,
            last_active_at=row.created_at,
            current=bool(current) and row.session_id == current,
        )
        for row in rows
    ]


@router.delete("/auth/sessions/{session_id}")
async def end_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
    current_user: dict = Depends(get_current_user),
):
    """Signs one device out (its refresh and access tokens stop working)."""
    if not await auth_service.end_session(db, redis, current_user["sub"], session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return {"message": "Signed out of that device"}
