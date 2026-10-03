from datetime import UTC, datetime

from sqlalchemy import select
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
    session: AsyncSession, *, user_id: str, project_id: str | None = None
) -> list[Chat]:
    stmt = select(Chat).where(Chat.user_id == user_id)
    if project_id is not None:
        stmt = stmt.where(Chat.project_id == project_id)
    result = await session.scalars(stmt.order_by(Chat.updated_at.desc()))
    return list(result.all())


async def get_chat(session: AsyncSession, *, user_id: str, chat_id: str) -> Chat:
    chat = await session.scalar(select(Chat).where(Chat.id == chat_id, Chat.user_id == user_id))
    if chat is None:
        raise NotFoundError("chat not found")
    return chat


async def delete_chat(session: AsyncSession, *, user_id: str, chat_id: str) -> None:
    chat = await get_chat(session, user_id=user_id, chat_id=chat_id)
    await session.delete(chat)
    await session.commit()


async def list_messages(session: AsyncSession, *, user_id: str, chat_id: str) -> list[Message]:
    await get_chat(session, user_id=user_id, chat_id=chat_id)
    result = await session.scalars(
        select(Message).where(Message.chat_id == chat_id).order_by(Message.created_at.asc())
    )
    return list(result.all())


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
) -> Message:
    chat = await get_chat(session, user_id=user_id, chat_id=chat_id)

    message = Message(
        chat_id=chat.id,
        role=role,
        content=content,
        structured_data=structured_data,
        provider=provider,
        model=model,
    )
    session.add(message)
    chat.updated_at = datetime.now(UTC)
    await session.commit()
    return message
