from datetime import date, timedelta

from app.collectors.base import UsageCollector
from app.config import settings
from app.models import CollectionResult, UsageRecord


DEFAULT_TEST_PROMPT = "짧게 인사하고 이 API 호출이 정상이라고 말해주세요."


class GeminiUsageCollector(UsageCollector):
    provider = "gemini"

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
                records=self._sample_records(start_date, end_date),
                dry_run=True,
                message="Gemini 테스트 모드 샘플 사용량을 저장했습니다.",
                status="success",
            )

        return self.collect_api_usage(usage_date=end_date, model=model)

    def collect_api_usage(self, usage_date: date, model: str | None = None) -> CollectionResult:
        selected_model = (model or settings.gemini_model).strip() or settings.gemini_model
        if not settings.gemini_api_key:
            return CollectionResult(
                provider=self.provider,
                records=[],
                dry_run=False,
                message="GEMINI_API_KEY가 설정되어 있지 않습니다.",
                success=False,
                status="failed",
            )

        try:
            from google import genai

            client = genai.Client(api_key=settings.gemini_api_key)
            response, selected_model = _generate_content(client, selected_model)
        except ImportError:
            return CollectionResult(
                provider=self.provider,
                records=[],
                dry_run=False,
                message="google-genai 패키지가 설치되어 있지 않습니다. requirements.txt를 설치해주세요.",
                success=False,
                status="failed",
            )
        except Exception:
            return CollectionResult(
                provider=self.provider,
                records=[],
                dry_run=False,
                message="Gemini API 테스트 호출에 실패했습니다. API 키와 모델명을 확인해주세요.",
                success=False,
                status="failed",
            )

        usage = getattr(response, "usage_metadata", None)
        input_tokens = _safe_int(getattr(usage, "prompt_token_count", 0))
        output_tokens = _safe_int(getattr(usage, "candidates_token_count", 0))
        cached_tokens = 0
        total_tokens = _safe_int(getattr(usage, "total_token_count", 0))
        if total_tokens <= 0:
            total_tokens = input_tokens + output_tokens + cached_tokens

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
            records=[record],
            dry_run=False,
            message="Gemini API 사용량이 저장되었습니다.",
            success=True,
            status="success",
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
                    model=settings.gemini_model,
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


def _safe_int(value: object) -> int:
    try:
        return max(int(value or 0), 0)
    except (TypeError, ValueError):
        return 0


def _generate_content(client: object, selected_model: str) -> tuple[object, str]:
    candidates = [selected_model]
    if selected_model == "gemini-1.5-flash":
        candidates.append("gemini-2.5-flash")
    for model in candidates:
        try:
            return client.models.generate_content(
                model=model,
                contents=DEFAULT_TEST_PROMPT,
            ), model
        except Exception:
            if model == candidates[-1]:
                raise
    raise RuntimeError("Gemini model call failed")
