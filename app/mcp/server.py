"""StructAI's MCP server - exposes the gateway's capabilities as MCP tools/resources.

Run directly for a quick stdio smoke-test:
    python3 -m app.mcp.server

Point Claude Desktop/Code at it instead; see docs/MCP_SERVER.md for setup.

Design notes:
- This process has no FastAPI request to depend-inject through, so each tool opens
  its own short-lived DB session rather than going through app/core/deps.py.
- Every tool still runs behind the project's real auth, rate limiting, and daily
  quota - see app/mcp/auth.py and the `_authed_session`/`_guard_model_call` helpers
  below - so MCP access carries the same guarantees as the HTTP API, not a
  separate, weaker path into the same data.
- No business logic lives here either: every tool is a thin translation from MCP
  arguments to the exact app/services/* + app/gateway/* calls the HTTP routes make.
"""

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Literal

from mcp.server.fastmcp import FastMCP
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.core.errors import (
    AppError,
    GenerationError,
    GuardrailError,
    PiiDetectedError,
    RateLimitError,
)
from app.db import get_session_maker
from app.gateway.factory import get_gateway
from app.guardrails.injection import is_prompt_injection
from app.guardrails.pii import scan_pii
from app.guardrails.rate_limit import RateLimitExceededError, get_rate_limiter
from app.mcp.auth import McpSession
from app.models.chat import Chat
from app.models.file import FileAttachment
from app.models.project import Project
from app.models.user import User
from app.schemas.builder import FieldDef, SchemaBuildError, SchemaDef, build_model
from app.services import (
    chat_service,
    file_service,
    project_service,
    quota_service,
    search_service,
    structured_service,
    usage_service,
)

mcp = FastMCP(
    name="structai",
    instructions=(
        "Tools for StructAI, a gateway that turns 'ask anything' into JSON guaranteed to "
        "match a schema you define, using local (Ollama) or free-tier (Groq) models. Acts on "
        "behalf of whichever StructAI account MCP_ACCESS_TOKEN belongs to - project/chat data "
        "and usage are scoped to that account."
    ),
)

_mcp_session: McpSession | None = None


def _get_mcp_session() -> McpSession:
    global _mcp_session
    if _mcp_session is None:
        _mcp_session = McpSession(get_settings())
    return _mcp_session


def reset_mcp_session_cache() -> None:
    """Test hook: forces the next tool call to rebuild McpSession from current settings."""
    global _mcp_session
    _mcp_session = None


@asynccontextmanager
async def _authed_session() -> AsyncIterator[tuple[AsyncSession, User]]:
    async with get_session_maker()() as session:
        user = await _get_mcp_session().get_user(session)
        yield session, user


def _guard_prompt(prompt: str, settings: Settings) -> str:
    if is_prompt_injection(prompt):
        raise GuardrailError("prompt was blocked by the injection screen")
    scan = scan_pii(prompt)
    if scan.found and settings.pii_mode == "block":
        raise PiiDetectedError(f"prompt was blocked: PII detected ({', '.join(scan.categories)})")
    return scan.redacted_text if settings.pii_mode == "redact" else prompt


async def _guard_model_call(session: AsyncSession, settings: Settings, user_id: str) -> None:
    """Applies the same per-user rate limit + daily quota the HTTP routes enforce."""
    try:
        get_rate_limiter().check(user_id)
    except RateLimitExceededError as exc:
        raise RateLimitError(str(exc)) from exc
    await quota_service.check_and_increment(
        session, scope="user", key=user_id, limit=settings.daily_quota_user
    )


def _serialize_project(project: Project) -> dict:
    return {
        "id": project.id,
        "name": project.name,
        "created_at": project.created_at.isoformat(),
    }


def _serialize_chat(chat: Chat) -> dict:
    return {
        "id": chat.id,
        "title": chat.title,
        "project_id": chat.project_id,
        "created_at": chat.created_at.isoformat(),
        "updated_at": chat.updated_at.isoformat(),
    }


def _serialize_message(message) -> dict:
    return {
        "id": message.id,
        "chat_id": message.chat_id,
        "role": message.role,
        "content": message.content,
        "structured_data": message.structured_data,
        "provider": message.provider,
        "model": message.model,
        "created_at": message.created_at.isoformat(),
    }


def _serialize_file(attachment: FileAttachment) -> dict:
    return {
        "id": attachment.id,
        "filename": attachment.filename,
        "content_type": attachment.content_type,
        "size_bytes": attachment.size_bytes,
        "chat_id": attachment.chat_id,
        "created_at": attachment.created_at.isoformat(),
    }


@mcp.tool()
async def ask_structured(
    prompt: str,
    fields: list[FieldDef],
    tier: Literal["fast", "smart"] = "fast",
) -> dict:
    """Ask a question and get back JSON guaranteed to validate against `fields`.

    `fields` is StructAI's schema format, e.g.
    [{"name": "capital", "type": "string"}, {"name": "population", "type": "integer"}].
    Allowed types: string, integer, number, boolean, string_list, integer_list.
    Add "required": false to make a field optional. The gateway retries with
    corrective feedback (up to the server's configured attempt limit) until the
    model's answer actually validates, or raises if it never does.
    """
    try:
        schema = SchemaDef(fields=fields)
    except SchemaBuildError as exc:
        raise AppError(str(exc), code="invalid_schema") from exc

    settings = get_settings()
    async with _authed_session() as (session, user):
        await _guard_model_call(session, settings, user.id)
        clean_prompt = _guard_prompt(prompt, settings)

        try:
            result = await structured_service.answer(
                get_gateway(),
                prompt=clean_prompt,
                schema=schema,
                tier=tier,
                max_attempts=settings.structured_max_attempts,
                timeout=settings.structured_timeout_seconds,
                pii_mode=settings.pii_mode,
            )
        except structured_service.StructuredAnswerError as exc:
            raise GenerationError(str(exc)) from exc

    return {
        "data": result.data,
        "provider": result.provider,
        "model": result.model,
        "attempts": result.attempts,
    }


@mcp.tool()
async def validate_schema(fields: list[FieldDef]) -> dict:
    """Check that a StructAI field schema is well-formed and show its JSON Schema."""
    try:
        model = build_model(SchemaDef(fields=fields))
    except SchemaBuildError as exc:
        return {"valid": False, "error": str(exc)}
    return {"valid": True, "json_schema": model.model_json_schema()}


@mcp.tool()
async def list_projects() -> list[dict]:
    """List the configured StructAI account's projects, newest first."""
    async with _authed_session() as (session, user):
        projects = await project_service.list_projects(session, user_id=user.id)
    return [_serialize_project(p) for p in projects]


@mcp.tool()
async def create_project(name: str) -> dict:
    """Create a new project to group chats under."""
    async with _authed_session() as (session, user):
        project = await project_service.create_project(session, user_id=user.id, name=name)
    return _serialize_project(project)


@mcp.tool()
async def list_chats(project_id: str | None = None) -> list[dict]:
    """List chats, optionally filtered to one project, most recently updated first."""
    async with _authed_session() as (session, user):
        chats = await chat_service.list_chats(session, user_id=user.id, project_id=project_id)
    return [_serialize_chat(c) for c in chats]


@mcp.tool()
async def create_chat(title: str, project_id: str | None = None) -> dict:
    """Create a new chat, optionally inside an existing project."""
    async with _authed_session() as (session, user):
        chat = await chat_service.create_chat(
            session, user_id=user.id, title=title, project_id=project_id
        )
    return _serialize_chat(chat)


@mcp.tool()
async def list_messages(chat_id: str) -> list[dict]:
    """List a chat's messages in chronological order."""
    async with _authed_session() as (session, user):
        messages = await chat_service.list_messages(session, user_id=user.id, chat_id=chat_id)
    return [_serialize_message(m) for m in messages]


@mcp.tool()
async def send_message(
    chat_id: str, content: str, role: Literal["user", "assistant"] = "user"
) -> dict:
    """Append a message to a chat (just persists it - does not call a model)."""
    async with _authed_session() as (session, user):
        message = await chat_service.add_message(
            session, user_id=user.id, chat_id=chat_id, role=role, content=content
        )
    return _serialize_message(message)


@mcp.tool()
async def list_files(chat_id: str | None = None) -> list[dict]:
    """List the configured account's stored files, optionally filtered to one chat."""
    async with _authed_session() as (session, user):
        files = await file_service.list_files(session, user_id=user.id, chat_id=chat_id)
    return [_serialize_file(f) for f in files]


@mcp.tool()
async def get_file(file_id: str) -> dict:
    """Get a stored file's metadata (not its binary content) by id."""
    async with _authed_session() as (session, user):
        attachment = await file_service.get_file(session, user_id=user.id, file_id=file_id)
    return _serialize_file(attachment)


@mcp.tool()
async def search(query: str) -> dict:
    """Search the configured account's own chat titles and message content."""
    async with _authed_session() as (session, user):
        results = await search_service.search(session, user_id=user.id, query=query)
    return {
        "chats": [_serialize_chat(c) for c in results["chats"]],
        "messages": [_serialize_message(m) for m in results["messages"]],
    }


@mcp.tool()
async def get_usage() -> dict:
    """Show today's request-quota usage for the configured account."""
    settings = get_settings()
    async with _authed_session() as (session, user):
        return await usage_service.get_usage(
            session,
            user_id=user.id,
            user_limit=settings.daily_quota_user,
        )


@mcp.resource("structai://usage", mime_type="application/json")
async def usage_resource() -> str:
    """Today's request-quota usage for the configured account, as JSON."""
    settings = get_settings()
    async with _authed_session() as (session, user):
        usage = await usage_service.get_usage(
            session,
            user_id=user.id,
            user_limit=settings.daily_quota_user,
        )
    return json.dumps(usage)


@mcp.resource("structai://projects", mime_type="application/json")
async def projects_resource() -> str:
    """The configured account's projects, as a JSON array."""
    async with _authed_session() as (session, user):
        projects = await project_service.list_projects(session, user_id=user.id)
    return json.dumps([_serialize_project(p) for p in projects])


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
