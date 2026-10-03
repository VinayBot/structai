from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import Chat
from app.models.message import Message


async def search(session: AsyncSession, *, user_id: str, query: str) -> dict:
    pattern = f"%{query.lower()}%"

    chats_result = await session.scalars(
        select(Chat)
        .where(Chat.user_id == user_id, Chat.title.ilike(pattern))
        .order_by(Chat.updated_at.desc())
    )

    messages_result = await session.scalars(
        select(Message)
        .join(Chat, Chat.id == Message.chat_id)
        .where(Chat.user_id == user_id, Message.content.ilike(pattern))
        .order_by(Message.created_at.desc())
    )

    return {"chats": list(chats_result.all()), "messages": list(messages_result.all())}
