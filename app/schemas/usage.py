from pydantic import BaseModel, ConfigDict

from app.schemas.chats import ChatResponse, MessageResponse


class UsageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_count_today: int
    user_limit: int


class SearchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chats: list[ChatResponse]
    messages: list[MessageResponse]
