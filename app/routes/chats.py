from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db import get_session
from app.models.user import User
from app.schemas.chats import (
    ChatCreateRequest,
    ChatDetailResponse,
    ChatResponse,
    MessageCreateRequest,
    MessageResponse,
)
from app.schemas.pagination import Page
from app.services import chat_service

router = APIRouter(prefix="/chats", tags=["chats"])


@router.post("", response_model=ChatResponse, status_code=201)
async def create_chat(
    body: ChatCreateRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ChatResponse:
    chat = await chat_service.create_chat(
        session, user_id=user.id, title=body.title, project_id=body.project_id
    )
    return ChatResponse.model_validate(chat, from_attributes=True)


@router.get("", response_model=Page[ChatResponse])
async def list_chats(
    project_id: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Page[ChatResponse]:
    chats, total = await chat_service.list_chats(
        session, user_id=user.id, project_id=project_id, limit=limit, offset=offset
    )
    return Page(
        items=[ChatResponse.model_validate(c, from_attributes=True) for c in chats],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{chat_id}", response_model=ChatDetailResponse)
async def get_chat(
    chat_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ChatDetailResponse:
    chat = await chat_service.get_chat(session, user_id=user.id, chat_id=chat_id)
    messages, _total = await chat_service.list_messages(
        session, user_id=user.id, chat_id=chat_id, chat=chat, include_total=False
    )
    return ChatDetailResponse(
        id=chat.id,
        title=chat.title,
        project_id=chat.project_id,
        created_at=chat.created_at,
        updated_at=chat.updated_at,
        messages=[MessageResponse.model_validate(m, from_attributes=True) for m in messages],
    )


@router.delete("/{chat_id}", status_code=204)
async def delete_chat(
    chat_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    await chat_service.delete_chat(session, user_id=user.id, chat_id=chat_id)


@router.post("/{chat_id}/messages", response_model=MessageResponse, status_code=201)
async def add_message(
    chat_id: str,
    body: MessageCreateRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> MessageResponse:
    message = await chat_service.add_message(
        session,
        user_id=user.id,
        chat_id=chat_id,
        role=body.role,
        content=body.content,
        structured_data=body.structured_data,
        provider=body.provider,
        model=body.model,
        prompt_tokens=body.prompt_tokens,
        completion_tokens=body.completion_tokens,
    )
    return MessageResponse.model_validate(message, from_attributes=True)


@router.get("/{chat_id}/messages", response_model=Page[MessageResponse])
async def list_messages(
    chat_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Page[MessageResponse]:
    messages, total = await chat_service.list_messages(
        session, user_id=user.id, chat_id=chat_id, limit=limit, offset=offset
    )
    return Page(
        items=[MessageResponse.model_validate(m, from_attributes=True) for m in messages],
        total=total,
        limit=limit,
        offset=offset,
    )
