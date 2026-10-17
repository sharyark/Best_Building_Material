from pydantic import BaseModel, Field


class VoidIn(BaseModel):
    reason: str = Field(min_length=3, max_length=500)
