from datetime import date

from app.collectors.claude_collector import ClaudeUsageCollector
from app.collectors.gemini_collector import GeminiUsageCollector
from app.collectors.openai_collector import OpenAIUsageCollector
from app.models import CollectionResult
from app.services.collector_run_service import finish_collector_run, start_collector_run
from app.services.usage_service import delete_claude_dry_run_records, upsert_usage_records


COLLECTORS = {
    "openai": OpenAIUsageCollector(),
    "claude": ClaudeUsageCollector(),
    "gemini": GeminiUsageCollector(),
}

DRY_RUN_COLLECTORS = ("openai", "gemini")
API_TEST_PROVIDERS = {"openai", "claude", "gemini"}


def collect_usage(
    provider: str,
    start_date: date,
    end_date: date,
    dry_run: bool = True,
) -> CollectionResult:
    if dry_run:
        delete_claude_dry_run_records()

    if provider == "all":
        provider_names = DRY_RUN_COLLECTORS if dry_run else tuple(COLLECTORS)
        results = [
            collect_provider_usage(
                provider=provider_name,
                start_date=start_date,
                end_date=end_date,
                dry_run=dry_run,
            )
            for provider_name in provider_names
        ]
        records = [record for result in results for record in result.records]
        success = all(result.success for result in results)
        message = "전체 제공자의 사용량을 수집했습니다."
        if dry_run:
            message = "OpenAI와 Gemini 테스트 모드 샘플 사용량을 수집했습니다. Claude 샘플 데이터는 생성하지 않습니다."
        if not success:
            failed = ", ".join(result.provider for result in results if not result.success)
            message = f"일부 제공자 수집에 실패했습니다: {failed}"
        return CollectionResult(
            provider="all",
            records=records,
            dry_run=dry_run,
            message=message,
            success=success,
            status="success" if success else "failed",
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
            message=f"알 수 없는 제공자입니다: {provider}",
            success=False,
            status="failed",
        )
        finish_collector_run(run_id, "failed", result.message)
        return result

    try:
        result = collector.collect(start_date=start_date, end_date=end_date, dry_run=dry_run)
        saved_count = upsert_usage_records(result.records)
        finish_collector_run(
            run_id=run_id,
            status=_result_status(result),
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
            status="failed",
        )


def collect_api_test_usage(provider: str, model: str | None, usage_date: date) -> CollectionResult:
    run_id = start_collector_run(
        provider=provider,
        dry_run=False,
        start_date=usage_date,
        end_date=usage_date,
    )
    collector = COLLECTORS.get(provider)
    if provider not in API_TEST_PROVIDERS or collector is None:
        result = CollectionResult(
            provider=provider,
            records=[],
            dry_run=False,
            message="실제 API 테스트 수집은 OpenAI, Claude, Gemini 중에서 선택할 수 있습니다.",
            success=False,
            status="failed",
        )
        finish_collector_run(run_id, "failed", result.message)
        return result

    try:
        result = collector.collect(start_date=usage_date, end_date=usage_date, dry_run=False, model=model)
        saved_count = upsert_usage_records(result.records)
        finish_collector_run(
            run_id=run_id,
            status=_result_status(result),
            message=result.message,
            records_collected=len(result.records),
            records_saved=saved_count,
        )
        return result
    except Exception:
        message = "API 테스트 수집 중 오류가 발생했습니다. 설정을 확인해주세요."
        finish_collector_run(run_id, "failed", message)
        return CollectionResult(
            provider=provider,
            records=[],
            dry_run=False,
            message=message,
            success=False,
            status="failed",
        )


def _result_status(result: CollectionResult) -> str:
    if result.status:
        return result.status
    return "success" if result.success else "failed"
