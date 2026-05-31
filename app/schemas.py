from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime


class UsageRecordCreate(BaseModel):
    timestamp: Optional[datetime]
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    total_tokens: int = 0
    request_count: int = 0
    meta: Optional[Any] = None


class UsageRecordOut(UsageRecordCreate):
    id: int

    class Config:
        orm_mode = True


class TokenLimitSet(BaseModel):
    month: str = Field(..., description="YYYY-MM")
    monthly_token_limit: int
