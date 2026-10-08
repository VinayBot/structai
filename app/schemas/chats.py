from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ChatCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    project_id: str | None = None


class ChatResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    project_id: str | None
    created_at: datetime
    updated_at: datetime


class MessageCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)
    structured_data: dict | None = None
    provider: str | None = None
    model: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


class MessageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    chat_id: str
    role: str
    content: str
    structured_data: dict | None
    provider: str | None
    model: str | None
    prompt_tokens: int | None
    completion_tokens: int | None
    created_at: datetime


class ChatDetailResponse(ChatResponse):
    messages: list[MessageResponse]
