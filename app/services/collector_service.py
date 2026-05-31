from datetime import date

from app.collectors.claude_collector import ClaudeUsageCollector
from app.collectors.gemini_collector import GeminiUsageCollector
from app.collectors.openai_collector import OpenAIUsageCollector
from app.models import CollectionResult
from app.services.collector_run_service import finish_collector_run, start_collector_run
from app.services.usage_service import upsert_usage_records


COLLECTORS = {
    "openai": OpenAIUsageCollector(),
    "claude": ClaudeUsageCollector(),
    "gemini": GeminiUsageCollector(),
}


def collect_usage(
    provider: str,
    start_date: date,
    end_date: date,
    dry_run: bool = True,
) -> CollectionResult:
    if provider == "all":
        results = [
            collect_provider_usage(
                provider=provider_name,
                start_date=start_date,
                end_date=end_date,
                dry_run=dry_run,
            )
            for provider_name in COLLECTORS
        ]
        records = [record for result in results for record in result.records]
        success = all(result.success for result in results)
        if success:
            message = "전체 제공사의 사용량을 수집했습니다."
        else:
            failed = ", ".join(result.provider for result in results if not result.success)
            message = f"일부 제공사 수집에 실패했습니다: {failed}"
        return CollectionResult(
            provider="all",
            records=records,
            dry_run=dry_run,
            message=message,
            success=success,
        )

    return collect_provider_usage(
        provider=provider,
        start_date=start_date,
        end_date=end_date,
        dry_run=dry_run,
    )


def collect_provider_usage(
    provider: str,
    start_date: date,
    end_date: date,
    dry_run: bool = True,
) -> CollectionResult:
    run_id = start_collector_run(
        provider=provider,
        dry_run=dry_run,
        start_date=start_date,
        end_date=end_date,
    )
    collector = COLLECTORS.get(provider)
    if collector is None:
        result = CollectionResult(
            provider=provider,
            records=[],
            dry_run=dry_run,
            message=f"알 수 없는 제공사입니다: {provider}",
            success=False,
        )
        finish_collector_run(run_id, "failed", result.message)
        return result

    try:
        result = collector.collect(start_date=start_date, end_date=end_date, dry_run=dry_run)
        saved_count = upsert_usage_records(result.records)
        finish_collector_run(
            run_id=run_id,
            status="success" if result.success else "failed",
            message=result.message,
            records_collected=len(result.records),
            records_saved=saved_count,
        )
        return result
    except Exception:
        message = "사용량 수집 중 오류가 발생했습니다. 설정을 확인해주세요."
        finish_collector_run(run_id, "failed", message)
        return CollectionResult(
            provider=provider,
            records=[],
            dry_run=dry_run,
            message=message,
            success=False,
        )
