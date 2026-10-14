"""Authentication API endpoints for IncidentHub."""

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import get_current_active_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    RefreshTokenRequest,
    RefreshTokenResponse,
    RegisterRequest,
    TokenResponse,
)
from app.schemas.user import UserRead
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register New User",
)
async def register_endpoint(
    data: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> UserRead:
    """Register a new platform user with email normalization and secure Argon2id password hashing.

    Does not automatically create default organizations or memberships.
    """
    user = await auth_service.register_user(db, data)
    return UserRead.model_validate(user)


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="User Login",
)
async def login_endpoint(
    data: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Authenticate user credentials and issue a dual access token and refresh token pair."""
    user_agent = request.headers.get("user-agent")
    user, access_token, refresh_token = await auth_service.authenticate_user(
        db, data, user_agent=user_agent
    )
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserRead.model_validate(user),
    )


@router.post(
    "/refresh",
    response_model=RefreshTokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Refresh Session Tokens",
)
async def refresh_endpoint(
    data: RefreshTokenRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> RefreshTokenResponse:
    """Validate a refresh token, atomically rotate it, and issue a new token pair.

    Replay of a revoked refresh token triggers breach detection and terminates all user sessions.
    """
    user_agent = request.headers.get("user-agent")
    user, new_access_token, new_refresh_token = await auth_service.refresh_session(
        db, data.refresh_token, user_agent=user_agent
    )
    return RefreshTokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserRead.model_validate(user),
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="User Logout",
)
async def logout_endpoint(
    data: LogoutRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Revoke the presented refresh token for the authenticated user session."""
    await auth_service.logout_user(db, data.refresh_token, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/me",
    response_model=UserRead,
    status_code=status.HTTP_200_OK,
    summary="Get Current User Profile",
)
async def me_endpoint(
    current_user: User = Depends(get_current_active_user),
) -> UserRead:
    """Retrieve the currently authenticated active user without exposing credentials or hashes."""
    return UserRead.model_validate(current_user)
