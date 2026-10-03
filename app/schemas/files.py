from datetime import datetime

from pydantic import BaseModel, ConfigDict


class FileResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    filename: str
    content_type: str
    size_bytes: int
    chat_id: str | None
    created_at: datetime
