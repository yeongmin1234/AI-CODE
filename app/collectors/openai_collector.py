from datetime import date, timedelta

from app.collectors.base import UsageCollector
from app.config import settings
from app.models import CollectionResult, UsageRecord


DEFAULT_TEST_PROMPT = "짧게 인사하고 이 API 호출이 정상이라고 말해주세요."
QUOTA_MESSAGE = (
    "OpenAI API 키는 설정되어 있지만, 사용 가능한 API 크레딧 또는 쿼터가 부족합니다. "
    "OpenAI Platform의 Billing/Usage 설정을 확인해주세요."
)


class OpenAIUsageCollector(UsageCollector):
    provider = "openai"

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
                dry_run=True,
                records=self._sample_records(start_date, end_date),
                message="OpenAI 테스트 모드 샘플 사용량을 저장했습니다.",
                status="success",
            )

        return self.collect_api_usage(usage_date=end_date, model=model)

    def collect_api_usage(self, usage_date: date, model: str | None = None) -> CollectionResult:
        selected_model = (model or settings.openai_model).strip() or settings.openai_model
        if not settings.openai_api_key:
            return CollectionResult(
                provider=self.provider,
                dry_run=False,
                records=[],
                message="OPENAI_API_KEY가 설정되어 있지 않습니다.",
                success=False,
                status="missing_key",
            )

        try:
            from openai import OpenAI

            # 일반 API 테스트 호출은 OPENAI_API_KEY만 사용합니다.
            # OPENAI_ADMIN_KEY는 별도의 조직 사용량 조회용 키이며 이 호출에 쓰지 않습니다.
            client = OpenAI(api_key=settings.openai_api_key)
            response = _create_response(client, selected_model)
        except ImportError:
            return CollectionResult(
                provider=self.provider,
                dry_run=False,
                records=[],
                message="openai 패키지가 설치되어 있지 않습니다. requirements.txt를 설치해주세요.",
                success=False,
                status="error",
            )
        except Exception as exc:
            status, message = _openai_error_status_and_message(exc)
            return CollectionResult(
                provider=self.provider,
                dry_run=False,
                records=[],
                message=message,
                success=False,
                status=status,
            )

        input_tokens, output_tokens, cached_tokens, total_tokens = _usage_values(response)
        record = UsageRecord(
            provider=self.provider,
            model=selected_model,
            usage_date=usage_date,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_tokens=cached_tokens,
            request_count=1,
            cost_usd=0,
            source="api",
            total_tokens_override=total_tokens,
        )
        return CollectionResult(
            provider=self.provider,
            dry_run=False,
            records=[record],
            message="OpenAI API 사용량이 저장되었습니다.",
            success=True,
            status="success",
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
                    model=settings.openai_model,
                    usage_date=current,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cached_tokens=cached_tokens,
                    request_count=request_count,
                    cost_usd=0,
                    source="dry_run",
                )
            )
            current += timedelta(days=1)
        return records


def _create_response(client: object, selected_model: str) -> object:
    try:
        return client.responses.create(
            model=selected_model,
            input=DEFAULT_TEST_PROMPT,
            max_output_tokens=128,
        )
    except Exception as responses_exc:
        if _is_quota_error(responses_exc):
            raise
        return client.chat.completions.create(
            model=selected_model,
            messages=[{"role": "user", "content": DEFAULT_TEST_PROMPT}],
            max_tokens=64,
        )


def _usage_values(response: object) -> tuple[int, int, int, int]:
    usage = getattr(response, "usage", None)
    input_tokens = _safe_int(getattr(usage, "input_tokens", getattr(usage, "prompt_tokens", 0)))
    output_tokens = _safe_int(getattr(usage, "output_tokens", getattr(usage, "completion_tokens", 0)))
    input_details = getattr(usage, "input_tokens_details", getattr(usage, "prompt_tokens_details", None))
    cached_tokens = _safe_int(getattr(input_details, "cached_tokens", 0))
    total_tokens = _safe_int(getattr(usage, "total_tokens", 0))
    if total_tokens <= 0:
        total_tokens = input_tokens + output_tokens + cached_tokens
    return input_tokens, output_tokens, cached_tokens, total_tokens


def _openai_error_status_and_message(exc: Exception) -> tuple[str, str]:
    if _is_quota_error(exc):
        return "quota_insufficient", QUOTA_MESSAGE
    return "error", "OpenAI API 테스트 호출에 실패했습니다. API 키와 모델명을 확인해주세요."


def _is_quota_error(exc: Exception) -> bool:
    return getattr(exc, "status_code", None) == 429 or getattr(exc, "code", None) == "insufficient_quota"


def _safe_int(value: object) -> int:
    try:
        return max(int(value or 0), 0)
    except (TypeError, ValueError):
        return 0
