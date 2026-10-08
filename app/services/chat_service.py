from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.models.chat import Chat
from app.models.message import Message
from app.services import project_service


async def create_chat(
    session: AsyncSession, *, user_id: str, title: str, project_id: str | None
) -> Chat:
    if project_id is not None:
        await project_service.get_project(session, user_id=user_id, project_id=project_id)

    chat = Chat(user_id=user_id, title=title, project_id=project_id)
    session.add(chat)
    await session.commit()
    return chat


async def list_chats(
    session: AsyncSession,
    *,
    user_id: str,
    project_id: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[Chat], int]:
    filters = [Chat.user_id == user_id]
    if project_id is not None:
        filters.append(Chat.project_id == project_id)

    total = await session.scalar(select(func.count()).select_from(Chat).where(*filters))
    result = await session.scalars(
        select(Chat).where(*filters).order_by(Chat.updated_at.desc()).limit(limit).offset(offset)
    )
    return list(result.all()), total or 0


async def get_chat(session: AsyncSession, *, user_id: str, chat_id: str) -> Chat:
    chat = await session.scalar(select(Chat).where(Chat.id == chat_id, Chat.user_id == user_id))
    if chat is None:
        raise NotFoundError("chat not found")
    return chat


async def delete_chat(session: AsyncSession, *, user_id: str, chat_id: str) -> None:
    chat = await get_chat(session, user_id=user_id, chat_id=chat_id)
    await session.delete(chat)
    await session.commit()


async def list_messages(
    session: AsyncSession,
    *,
    user_id: str,
    chat_id: str,
    chat: Chat | None = None,
    limit: int | None = None,
    offset: int = 0,
    include_total: bool = True,
) -> tuple[list[Message], int]:
    """limit=None (the default) returns the full conversation - used when embedding
    messages into a chat's detail view, where truncating to a page would silently
    hide history. The standalone GET /chats/{id}/messages route opts into a real
    limit for callers that actually want to page through a long conversation.

    `chat`, if the caller already fetched it, saves re-running that lookup - but it's
    never trusted blindly: it must actually match (chat_id, user_id), or this raises
    exactly as if no chat had been found, same as a fresh get_chat() would. `include_total`
    skips the COUNT(*) for a caller (the chat detail route) that doesn't use it.
    """
    if chat is not None:
        if chat.id != chat_id or chat.user_id != user_id:
            raise NotFoundError("chat not found")
    else:
        await get_chat(session, user_id=user_id, chat_id=chat_id)

    total = 0
    if include_total:
        total = (
            await session.scalar(
                select(func.count()).select_from(Message).where(Message.chat_id == chat_id)
            )
            or 0
        )

    stmt = (
        select(Message)
        .where(Message.chat_id == chat_id)
        .order_by(Message.created_at.asc())
        .offset(offset)
    )
    if limit is not None:
        stmt = stmt.limit(limit)
    result = await session.scalars(stmt)
    return list(result.all()), total


async def add_message(
    session: AsyncSession,
    *,
    user_id: str,
    chat_id: str,
    role: str,
    content: str,
    structured_data: dict | None = None,
    provider: str | None = None,
    model: str | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
) -> Message:
    chat = await get_chat(session, user_id=user_id, chat_id=chat_id)

    message = Message(
        chat_id=chat.id,
        role=role,
        content=content,
        structured_data=structured_data,
        provider=provider,
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )
    session.add(message)
    chat.updated_at = datetime.now(UTC)
    await session.commit()
    return message
