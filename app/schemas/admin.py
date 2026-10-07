from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class AdminUserResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    email: str
    role: str
    is_active: bool
    created_at: datetime


class UpdateRoleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "admin"]


class AdminUsageRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: str
    email: str
    count_today: int
