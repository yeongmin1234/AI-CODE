from dataclasses import dataclass
from datetime import date

from app.services.calculation_service import total_tokens


@dataclass(frozen=True)
class UsageRecord:
    provider: str
    model: str
    usage_date: date
    input_tokens: int
    output_tokens: int
    cached_tokens: int
    request_count: int
    cost_usd: float
    source: str = "collector"
    total_tokens_override: int | None = None

    @property
    def total_tokens(self) -> int:
        if self.total_tokens_override is not None:
            return max(int(self.total_tokens_override or 0), 0)
        return total_tokens(self.input_tokens, self.output_tokens, self.cached_tokens)


@dataclass(frozen=True)
class CollectionResult:
    provider: str
    records: list[UsageRecord]
    dry_run: bool
    message: str
    success: bool = True
    status: str | None = None
