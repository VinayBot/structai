from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.core.errors import UnauthorizedError
from app.core.security import TokenError, decode_token
from app.models.user import User
from app.services.auth_service import refresh_tokens


class McpAuthError(Exception):
    """Raised when the MCP server has no usable StructAI credentials."""


@dataclass
class _TokenPair:
    access_token: str
    refresh_token: str


class McpSession:
    """Holds the StructAI credentials an MCP server process acts as.

    StructAI access tokens are short-lived (``jwt_access_expire_min``, 15 min by
    default), so a long-running MCP server refreshes them in-process using the
    configured refresh token. Refresh tokens rotate on use (one-time use, per
    ``auth_service.refresh_tokens``), so the refreshed pair only lives in this
    process's memory - if the server restarts, the ``.env`` refresh token may
    already be spent. Re-run ``scripts/mcp_issue_token.py`` to issue a fresh pair
    when that happens.
    """

    def __init__(self, settings: Settings):
        if not settings.mcp_access_token:
            raise McpAuthError(
                "MCP_ACCESS_TOKEN is not set. Run scripts/mcp_issue_token.py and copy the "
                "printed tokens into .env."
            )
        self._tokens = _TokenPair(settings.mcp_access_token, settings.mcp_refresh_token)

    async def get_user(self, session: AsyncSession) -> User:
        try:
            payload = decode_token(self._tokens.access_token, expected_type="access")
        except TokenError as exc:
            await self._refresh(session, exc)
            payload = decode_token(self._tokens.access_token, expected_type="access")

        user = await session.get(User, payload["sub"])
        if user is None or not user.is_active:
            raise McpAuthError("the configured MCP user no longer exists or is inactive")
        return user

    async def _refresh(self, session: AsyncSession, cause: Exception) -> None:
        if not self._tokens.refresh_token:
            raise McpAuthError(
                "the configured MCP_ACCESS_TOKEN expired and no MCP_REFRESH_TOKEN is set. "
                "Run scripts/mcp_issue_token.py to issue a fresh pair."
            ) from cause
        try:
            tokens = await refresh_tokens(session, self._tokens.refresh_token)
        except UnauthorizedError as exc:
            raise McpAuthError(
                "failed to refresh MCP credentials - the refresh token is expired or was "
                "already used. Run scripts/mcp_issue_token.py to issue a fresh pair."
            ) from exc
        self._tokens = _TokenPair(tokens.access_token, tokens.refresh_token)
