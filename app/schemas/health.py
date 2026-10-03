from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    git_commit: str
    build_time: str


class ReadyResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ready: bool
    db: bool
