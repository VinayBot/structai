import logging
from datetime import UTC, datetime
from urllib.parse import urlencode

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.errors import (
    ConflictError,
    EmailDomainUnreachableError,
    InvalidEmailDomainError,
    ServiceUnavailableError,
    UnauthorizedError,
)
from app.core.security import (
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password_async,
    verify_password_async,
)
from app.guardrails.email import (
    EmailCheckResult,
    check_email,
    load_extra_disposable_domains,
    record_email_block_metric,
)
from app.models.token import RevokedToken
from app.models.user import User
from app.schemas.auth import EmailCheckResponse, TokenResponse, UserResponse
from app.services import github_oauth_client

logger = logging.getLogger(__name__)

_ERROR_FOR_CODE = {
    "disposable_email": ConflictError,
    "likely_email_typo": InvalidEmailDomainError,
    "email_domain_unreachable": EmailDomainUnreachableError,
    "invalid_email_syntax": InvalidEmailDomainError,
}


async def _run_email_check(email: str) -> EmailCheckResult:
    settings = get_settings()
    extra_disposable = load_extra_disposable_domains(settings.email_disposable_domains_file)
    return await check_email(
        email,
        check_mx=settings.email_check_mx,
        mx_timeout=settings.email_check_mx_timeout_seconds,
        extra_disposable_domains=extra_disposable,
    )


async def check_email_address(email: str) -> EmailCheckResponse:
    result = await _run_email_check(email)
    return EmailCheckResponse(
        valid=result.valid,
        message=result.message,
        suggestion=result.suggestion,
        warning=result.mx_warning,
    )


async def register_user(session: AsyncSession, email: str, password: str) -> UserResponse:
    result = await _run_email_check(email)
    if not result.valid:
        record_email_block_metric(result.error_code or "unknown")
        error_cls = _ERROR_FOR_CODE.get(result.error_code or "", InvalidEmailDomainError)
        raise error_cls(result.message or "email rejected", suggestion=result.suggestion)
    if result.mx_warning:
        logger.warning("email MX check failed open: %s", result.mx_warning)

    existing = await session.scalar(select(User).where(User.email == email))
    if existing is not None:
        raise ConflictError("an account with this email already exists")

    user = User(email=email, hashed_password=await hash_password_async(password))
    session.add(user)
    await session.commit()
    return UserResponse(id=user.id, email=user.email, role=user.role)


def _issue_tokens(user_id: str) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(user_id),
        refresh_token=create_refresh_token(user_id),
    )


async def authenticate_user(session: AsyncSession, email: str, password: str) -> TokenResponse:
    user = await session.scalar(select(User).where(User.email == email))
    # An OAuth-only user has no hashed_password - fall through to the same
    # generic "invalid email or password" rather than crashing on None.
    if user is None or user.hashed_password is None:
        raise UnauthorizedError("invalid email or password")
    if not await verify_password_async(password, user.hashed_password):
        raise UnauthorizedError("invalid email or password")
    if not user.is_active:
        raise UnauthorizedError("account is disabled")
    return _issue_tokens(user.id)


def build_github_authorize_url(state: str) -> str:
    settings = get_settings()
    if not settings.github_client_id:
        raise ServiceUnavailableError("GitHub login is not configured on this server")

    params = {
        "client_id": settings.github_client_id,
        "redirect_uri": settings.github_oauth_redirect_uri,
        "scope": "user:email",
        "state": state,
    }
    return f"https://github.com/login/oauth/authorize?{urlencode(params)}"


async def authenticate_with_github(session: AsyncSession, code: str) -> TokenResponse:
    settings = get_settings()
    if not settings.github_client_id or not settings.github_client_secret:
        raise ServiceUnavailableError("GitHub login is not configured on this server")

    github_token = await github_oauth_client.exchange_code_for_token(
        code=code,
        client_id=settings.github_client_id,
        client_secret=settings.github_client_secret,
        redirect_uri=settings.github_oauth_redirect_uri,
    )
    profile = await github_oauth_client.fetch_profile(github_token)

    user = await session.scalar(
        select(User).where(User.oauth_provider == "github", User.oauth_subject == profile.subject)
    )
    if user is None:
        # No account linked to this GitHub identity yet. If an account already
        # exists for the same (verified) email - e.g. they originally signed up
        # with a password - link GitHub to it rather than failing on the
        # unique email constraint or leaving the user with two accounts.
        user = await session.scalar(select(User).where(User.email == profile.email))
        if user is not None:
            user.oauth_provider = "github"
            user.oauth_subject = profile.subject
        else:
            user = User(
                email=profile.email,
                hashed_password=None,
                oauth_provider="github",
                oauth_subject=profile.subject,
            )
            session.add(user)
        await session.commit()

    if not user.is_active:
        raise UnauthorizedError("account is disabled")
    return _issue_tokens(user.id)


async def _is_revoked(session: AsyncSession, jti: str) -> bool:
    return await session.scalar(select(RevokedToken).where(RevokedToken.jti == jti)) is not None


async def _revoke(session: AsyncSession, jti: str, exp: datetime) -> None:
    session.add(RevokedToken(jti=jti, expires_at=exp))
    await session.commit()


async def refresh_tokens(session: AsyncSession, refresh_token: str) -> TokenResponse:
    try:
        payload = decode_token(refresh_token, expected_type="refresh")
    except TokenError as exc:
        raise UnauthorizedError("invalid or expired refresh token") from exc

    jti = payload["jti"]
    if await _is_revoked(session, jti):
        raise UnauthorizedError("refresh token has been revoked")

    user = await session.get(User, payload["sub"])
    if user is None or not user.is_active:
        raise UnauthorizedError("invalid refresh token")

    await _revoke(session, jti, datetime.fromtimestamp(payload["exp"], tz=UTC))
    return _issue_tokens(user.id)


async def logout_user(session: AsyncSession, refresh_token: str) -> None:
    try:
        payload = decode_token(refresh_token, expected_type="refresh")
    except TokenError as exc:
        raise UnauthorizedError("invalid refresh token") from exc

    if not await _is_revoked(session, payload["jti"]):
        await _revoke(session, payload["jti"], datetime.fromtimestamp(payload["exp"], tz=UTC))
