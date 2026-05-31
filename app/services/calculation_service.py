from app.config import settings


PROVIDER_LABELS = {
    "all": "전체",
    "openai": "OpenAI",
    "claude": "Claude",
    "gemini": "Gemini",
}


def total_tokens(input_tokens: int, output_tokens: int, cached_tokens: int) -> int:
    return input_tokens + output_tokens + cached_tokens


def percent(part: float, whole: float) -> float:
    if whole <= 0:
        return 0
    return round(part / whole * 100, 1)


def token_limit_used_percent(total_token_count: int) -> float:
    return min(percent(total_token_count, settings.monthly_token_limit), 999)


def token_limit_warning_message(used_percent: float) -> str | None:
    if used_percent >= 100:
        return "경고: 월간 사용량 한도를 초과했습니다."
    if used_percent >= 80:
        return "주의: 월간 사용량 한도의 80% 이상을 사용했습니다."
    return None


def token_limit_warning_level(used_percent: float) -> str | None:
    if used_percent >= 100:
        return "danger"
    if used_percent >= 80:
        return "notice"
    return None


def provider_label(provider: str) -> str:
    return PROVIDER_LABELS.get(provider, provider)
