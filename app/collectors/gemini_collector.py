from datetime import date, timedelta

from app.collectors.base import UsageCollector
from app.models import CollectionResult, UsageRecord


class GeminiUsageCollector(UsageCollector):
    provider = "gemini"

    def collect(self, start_date: date, end_date: date, dry_run: bool = True) -> CollectionResult:
        if dry_run:
            return CollectionResult(
                provider=self.provider,
                records=self._sample_records(start_date, end_date),
                dry_run=True,
                message="Gemini 테스트 모드 샘플 사용량을 저장했습니다.",
            )

        return CollectionResult(
            provider=self.provider,
            records=[],
            dry_run=dry_run,
            message="Gemini 실제 수집기는 아직 활성화되지 않았습니다. 테스트 모드를 사용해주세요.",
            success=False,
        )

    def _sample_records(self, start_date: date, end_date: date) -> list[UsageRecord]:
        records: list[UsageRecord] = []
        current = start_date
        while current <= end_date:
            day_offset = (current - start_date).days
            input_tokens = 11500 + day_offset * 720
            output_tokens = 1800 + day_offset * 210
            cached_tokens = 500 + day_offset * 45
            request_count = 20 + day_offset
            records.append(
                UsageRecord(
                    provider=self.provider,
                    model="gemini-1.5-flash",
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
