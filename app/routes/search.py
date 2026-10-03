from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db import get_session
from app.models.user import User
from app.schemas.chats import ChatResponse, MessageResponse
from app.schemas.usage import SearchResponse
from app.services import search_service

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=SearchResponse)
async def search(
    q: str = Query(min_length=1),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SearchResponse:
    result = await search_service.search(session, user_id=user.id, query=q)
    return SearchResponse(
        chats=[ChatResponse.model_validate(c, from_attributes=True) for c in result["chats"]],
        messages=[
            MessageResponse.model_validate(m, from_attributes=True) for m in result["messages"]
        ],
    )
