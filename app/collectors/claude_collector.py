from datetime import date, timedelta

from app.collectors.base import UsageCollector
from app.models import CollectionResult, UsageRecord


class ClaudeUsageCollector(UsageCollector):
    provider = "claude"

    def collect(self, start_date: date, end_date: date, dry_run: bool = True) -> CollectionResult:
        if dry_run:
            return CollectionResult(
                provider=self.provider,
                records=self._sample_records(start_date, end_date),
                dry_run=True,
                message="Claude 테스트 모드 샘플 사용량을 저장했습니다.",
            )

        return CollectionResult(
            provider=self.provider,
            records=[],
            dry_run=dry_run,
            message="Claude 실제 수집기는 아직 활성화되지 않았습니다. 테스트 모드를 사용해주세요.",
            success=False,
        )

    def _sample_records(self, start_date: date, end_date: date) -> list[UsageRecord]:
        records: list[UsageRecord] = []
        current = start_date
        while current <= end_date:
            day_offset = (current - start_date).days
            input_tokens = 7200 + day_offset * 610
            output_tokens = 3100 + day_offset * 270
            cached_tokens = 900 + day_offset * 75
            request_count = 12 + day_offset
            records.append(
                UsageRecord(
                    provider=self.provider,
                    model="claude-3-5-sonnet",
                    usage_date=current,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cached_tokens=cached_tokens,
                    request_count=request_count,
                    cost_usd=0,
                    source="dry-run",
                )
            )
            current += timedelta(days=1)
        return records
