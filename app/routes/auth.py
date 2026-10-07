from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db import get_session
from app.models.user import User
from app.schemas.auth import (
    EmailCheckRequest,
    EmailCheckResponse,
    GithubAuthorizeResponse,
    GithubCallbackRequest,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(
    body: RegisterRequest,
    session: AsyncSession = Depends(get_session),
) -> UserResponse:
    return await auth_service.register_user(session, body.email, body.password)


@router.post("/check-email", response_model=EmailCheckResponse)
async def check_email_route(body: EmailCheckRequest) -> EmailCheckResponse:
    """Pre-submit validation for the registration form - runs the exact same
    guardrail as /auth/register but never creates an account, so the frontend
    can validate-on-blur before the user presses submit."""
    return await auth_service.check_email_address(body.email)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, session: AsyncSession = Depends(get_session)) -> TokenResponse:
    return await auth_service.authenticate_user(session, body.email, body.password)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    body: RefreshRequest, session: AsyncSession = Depends(get_session)
) -> TokenResponse:
    return await auth_service.refresh_tokens(session, body.refresh_token)


@router.post("/logout", status_code=204)
async def logout(body: LogoutRequest, session: AsyncSession = Depends(get_session)) -> None:
    await auth_service.logout_user(session, body.refresh_token)


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse(id=user.id, email=user.email, role=user.role)


@router.get("/github/login", response_model=GithubAuthorizeResponse)
async def github_login(
    state: str = Query(min_length=8, max_length=128),
) -> GithubAuthorizeResponse:
    """Returns the GitHub authorize URL to redirect the browser to. The caller
    (frontend) generates and verifies `state` itself for CSRF protection - this
    endpoint just echoes it into the URL so the backend stays stateless."""
    return GithubAuthorizeResponse(authorize_url=auth_service.build_github_authorize_url(state))


@router.post("/github/callback", response_model=TokenResponse)
async def github_callback(
    body: GithubCallbackRequest, session: AsyncSession = Depends(get_session)
) -> TokenResponse:
    return await auth_service.authenticate_with_github(session, body.code)
