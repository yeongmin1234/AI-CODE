from datetime import date

from pydantic import BaseModel


class UsageRecordIn(BaseModel):
    provider: str
    model: str
    usage_date: date
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    request_count: int = 0
    cost_usd: float = 0
    source: str = "collector"


class UsageSummary(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    total_tokens: int = 0
    request_count: int = 0
