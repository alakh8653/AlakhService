from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.user import UserCreate, UserRead
from app.services.auth_service import authenticate_user, get_user_from_token, register_user
from app.core.security import create_access_token, create_refresh_token
from app.core.exceptions import CredentialsException

router = APIRouter()


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(user_create: UserCreate, db: AsyncSession = Depends(get_db)):
    """Register a new user account."""
    return await register_user(db, user_create)


@router.post("/login")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """Authenticate user and return access + refresh tokens."""
    user = await authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": user.email})
    refresh_token = create_refresh_token(data={"sub": user.email})
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@router.post("/refresh")
async def refresh_token(token: str, db: AsyncSession = Depends(get_db)):
    """Obtain a new access token using a valid refresh token."""
    user = await get_user_from_token(db, token)
    if not user:
        raise CredentialsException()
    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/logout")
async def logout():
    """Logout the current user (client should discard the token)."""
    return {"message": "Successfully logged out"}


@router.post("/forgot-password")
async def forgot_password(email: str, db: AsyncSession = Depends(get_db)):
    """Send a password reset email to the provided address."""
    # In production: generate reset token, store it, and email the user.
    return {"message": "If that email exists, a reset link has been sent"}


@router.post("/reset-password")
async def reset_password(token: str, new_password: str, db: AsyncSession = Depends(get_db)):
    """Reset the user's password using a valid reset token."""
    # In production: validate the token, update the hashed password.
    return {"message": "Password has been reset successfully"}
