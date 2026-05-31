from datetime import date, timedelta

from app.collectors.base import UsageCollector
from app.models import CollectionResult, UsageRecord


class OpenAIUsageCollector(UsageCollector):
    provider = "openai"

    def collect(self, start_date: date, end_date: date, dry_run: bool = True) -> CollectionResult:
        if dry_run:
            return CollectionResult(
                provider=self.provider,
                dry_run=True,
                records=self._sample_records(start_date, end_date),
                message="OpenAI 테스트 모드 샘플 사용량을 저장했습니다.",
            )

        return CollectionResult(
            provider=self.provider,
            dry_run=False,
            records=[],
            message="OpenAI 실제 수집기는 아직 활성화되지 않았습니다. 테스트 모드를 사용해주세요.",
            success=False,
        )

    def _sample_records(self, start_date: date, end_date: date) -> list[UsageRecord]:
        records: list[UsageRecord] = []
        current = start_date
        while current <= end_date:
            day_offset = (current - start_date).days
            input_tokens = 9000 + day_offset * 850
            output_tokens = 2500 + day_offset * 330
            cached_tokens = 1200 + day_offset * 90
            request_count = 18 + day_offset

            records.append(
                UsageRecord(
                    provider=self.provider,
                    model="gpt-4o-mini",
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
