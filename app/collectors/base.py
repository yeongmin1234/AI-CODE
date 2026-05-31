from abc import ABC, abstractmethod
from datetime import date

from app.models import CollectionResult


class UsageCollector(ABC):
    provider: str

    @abstractmethod
    def collect(self, start_date: date, end_date: date, dry_run: bool = True) -> CollectionResult:
        """Collect usage records for a provider."""
