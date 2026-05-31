from datetime import date

from app.collectors.base import UsageCollector
from app.models import CollectionResult


DISABLED_MESSAGE = (
    "Claude API 키가 설정되어 있지 않아 현재 실제 수집은 비활성화되어 있습니다. "
    "필요하면 수동 입력으로 Claude 사용량을 기록할 수 있습니다."
)


class ClaudeUsageCollector(UsageCollector):
    provider = "claude"

    def collect(
        self,
        start_date: date,
        end_date: date,
        dry_run: bool = True,
        model: str | None = None,
    ) -> CollectionResult:
        if dry_run:
            return CollectionResult(
                provider=self.provider,
                records=[],
                dry_run=True,
                message="Claude는 현재 미연결 상태라 dry-run 샘플 사용량을 생성하지 않습니다.",
                success=True,
                status="skipped",
            )

        return self.collect_api_usage(usage_date=end_date, model=model)

    def collect_api_usage(self, usage_date: date, model: str | None = None) -> CollectionResult:
        return CollectionResult(
            provider=self.provider,
            records=[],
            dry_run=False,
            message=DISABLED_MESSAGE,
            success=True,
            status="disabled",
        )
