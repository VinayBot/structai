from pydantic import BaseModel, ConfigDict


class Page[T](BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[T]
    total: int
    limit: int
    offset: int
