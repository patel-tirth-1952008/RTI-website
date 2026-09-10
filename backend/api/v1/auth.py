# backend/api/v1/auth.py

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from config.database import get_db
from schemas.user import (
    UserRegister, UserLogin, TokenResponse,
    UserResponse, UserUpdate, PasswordChange,
    RefreshTokenRequest
)
from services.auth_service import AuthService
from api.middleware.auth_middleware import get_current_user
from models.user import User
from api.middleware.rate_limiter import limiter
import structlog

logger = structlog.get_logger()
router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED
)
@limiter.limit("5/minute")
async def register(
    request: Request,
    data: UserRegister,
    db: AsyncSession = Depends(get_db)
):
    """Register a new user account."""
    try:
        auth_service = AuthService(db)
        user, token_response = await auth_service.register(data)
        return token_response
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(
    request: Request,
    data: UserLogin,
    db: AsyncSession = Depends(get_db)
):
    """Login with email and password."""
    try:
        auth_service = AuthService(db)
        return await auth_service.login(
            data,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("User-Agent"),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    data: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db)
):
    """Refresh access token."""
    try:
        auth_service = AuthService(db)
        return await auth_service.refresh_token(data.refresh_token)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    data: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Logout and invalidate session."""
    auth_service = AuthService(db)
    await auth_service.logout(data.refresh_token)


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current user's profile."""
    auth_service = AuthService(db)
    display_name = auth_service.get_user_display_name(user)

    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=display_name,
        phone=user.phone,
        city=user.city,
        state=user.state,
        role=user.role,
        is_verified=user.is_verified,
        is_bpl=user.is_bpl,
        created_at=user.created_at,
    )