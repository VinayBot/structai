from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.builder import SchemaDef


class StructuredAnswerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(min_length=1, max_length=4000)
    schema_def: SchemaDef
    tier: Literal["fast", "smart"] = "fast"


class PiiMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    found: bool = False
    categories: list[str] = Field(default_factory=list)
    counts: dict[str, int] = Field(default_factory=dict)


class GuardrailsMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pii: PiiMeta = Field(default_factory=PiiMeta)


class StructuredAnswerResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: dict
    provider: str
    model: str
    attempts: int
    meta: GuardrailsMeta = Field(default_factory=GuardrailsMeta)
    prompt_tokens: int = 0
    completion_tokens: int = 0
