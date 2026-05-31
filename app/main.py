from datetime import date
from typing import Any
from urllib.parse import quote

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.db import init_db
from app.models import UsageRecord
from app.services.calculation_service import (
    PROVIDER_LABELS,
    provider_label,
    token_limit_used_percent,
    token_limit_warning_level,
    token_limit_warning_message,
    total_tokens,
)
from app.services.collector_run_service import get_recent_collector_runs
from app.services.collector_service import COLLECTORS, collect_api_test_usage, collect_usage
from app.services.usage_service import (
    delete_manual_usage_record,
    get_daily_summary,
    get_manual_usage_records,
    get_monthly_total,
    get_provider_summary,
    get_provider_usage_share,
    update_manual_usage_record,
    upsert_manual_usage_record,
)


USAGE_NUMBER_KEYS = ("input_tokens", "output_tokens", "cached_tokens", "total_tokens", "request_count")
PROVIDERS = ("openai", "claude", "gemini")
API_TEST_PROVIDERS = ("openai", "claude", "gemini")
OPENAI_QUOTA_MESSAGE = (
    "OpenAI API는 ChatGPT 구독과 별도로 결제/쿼터가 관리됩니다. "
    "API 플랫폼에서 결제수단 또는 사용 한도를 확인해야 합니다."
)

app = FastAPI(title=settings.app_name)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request) -> HTMLResponse:
    today = date.today()
    start_date = today.replace(day=1)
    month_key = today.strftime("%Y-%m")
    selected_provider = _selected_provider(request.query_params.get("provider"))
    provider_filter = None if selected_provider == "all" else selected_provider

    month_total = _safe_usage_total(get_monthly_total(month_key, provider_filter))
    current_total_tokens = month_total["total_tokens"]
    usage_limit_percent = token_limit_used_percent(current_total_tokens)
    remaining_token_limit = max(settings.monthly_token_limit - current_total_tokens, 0)
    collect_status = request.query_params.get("collect_status")
    collect_message = request.query_params.get("collect_message")
    provider_summary = _safe_summary_rows(get_provider_summary(start_date, today, provider_filter))
    daily_summary = _safe_summary_rows(get_daily_summary(start_date, today, provider_filter))
    provider_usage_share = _safe_provider_share(get_provider_usage_share(month_key, provider_filter))
    manual_records = _safe_summary_rows(get_manual_usage_records(start_date, today, provider_filter))
    collector_runs = get_recent_collector_runs()
    api_test_provider_options = _api_test_provider_options(collector_runs)

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "app_name": settings.app_name,
            "provider_options": _provider_options(),
            "selected_provider": selected_provider,
            "daily_summary": daily_summary,
            "daily_summaries": daily_summary,
            "provider_summary": provider_summary,
            "provider_summaries": provider_summary,
            "provider_usage_share": provider_usage_share,
            "provider_ratios": provider_usage_share,
            "month_total": month_total,
            "month_key": month_key,
            "monthly_token_limit": settings.monthly_token_limit,
            "monthly_limit": settings.monthly_token_limit,
            "current_total_tokens": current_total_tokens,
            "remaining_token_limit": remaining_token_limit,
            "token_limit_used_percent": usage_limit_percent,
            "token_limit_bar_percent": min(usage_limit_percent, 100),
            "monthly_usage_percent": usage_limit_percent,
            "token_limit_warning": token_limit_warning_message(usage_limit_percent),
            "token_limit_warning_level": token_limit_warning_level(usage_limit_percent),
            "dry_run_default": settings.dry_run,
            "dry_run": settings.dry_run,
            "collect_message": collect_message,
            "collect_status": collect_status,
            "success_message": collect_message if collect_status == "success" else None,
            "error_message": collect_message if collect_status == "failed" else None,
            "collector_runs": collector_runs,
            "provider_filter_label": provider_label(selected_provider),
            "provider_empty_message": _provider_empty_message(selected_provider),
            "today": today.isoformat(),
            "manual_records": manual_records,
            "manual_provider_options": _manual_provider_options(),
            "api_test_provider_options": api_test_provider_options,
            "openai_quota_notice": _openai_quota_notice(api_test_provider_options),
        },
    )


@app.post("/collect")
def collect(
    provider: str = Form(default="all"),
    dry_run: bool = Form(default=False),
) -> RedirectResponse:
    end_date = date.today()
    start_date = end_date.replace(day=1)
    selected_provider = _selected_provider(provider)
    result = collect_usage(provider=selected_provider, start_date=start_date, end_date=end_date, dry_run=dry_run)
    status = _notice_status(result)
    return RedirectResponse(
        f"/?provider={selected_provider}&collect_status={status}&collect_message={quote(result.message)}",
        status_code=303,
    )


@app.post("/collect/api-test")
def collect_api_test(
    provider: str = Form(...),
    model: str = Form(default=""),
) -> RedirectResponse:
    selected_provider = provider if provider in API_TEST_PROVIDERS else "all"
    result = collect_api_test_usage(provider=provider, model=model.strip() or None, usage_date=date.today())
    status = _notice_status(result)
    redirect_provider = selected_provider if selected_provider != "all" else "all"
    return RedirectResponse(
        f"/?provider={redirect_provider}&collect_status={status}&collect_message={quote(result.message)}",
        status_code=303,
    )


@app.post("/manual")
def create_manual_usage(
    usage_date: str = Form(...),
    provider: str = Form(...),
    model: str = Form(...),
    request_count: int = Form(...),
    input_tokens: int = Form(...),
    output_tokens: int = Form(...),
    cached_tokens: int = Form(...),
) -> RedirectResponse:
    selected_provider = _selected_provider(provider)
    record, error = _manual_record_from_form(
        usage_date=usage_date,
        provider=provider,
        model=model,
        request_count=request_count,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cached_tokens=cached_tokens,
    )
    if error:
        return _redirect_with_message(selected_provider, "failed", error)

    upsert_manual_usage_record(record)
    return _redirect_with_message(selected_provider, "success", "수동 입력 사용량을 저장했습니다.")


@app.post("/manual/{record_id}/update")
def update_manual_usage(
    record_id: int,
    usage_date: str = Form(...),
    provider: str = Form(...),
    model: str = Form(...),
    request_count: int = Form(...),
    input_tokens: int = Form(...),
    output_tokens: int = Form(...),
    cached_tokens: int = Form(...),
) -> RedirectResponse:
    selected_provider = _selected_provider(provider)
    record, error = _manual_record_from_form(
        usage_date=usage_date,
        provider=provider,
        model=model,
        request_count=request_count,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cached_tokens=cached_tokens,
    )
    if error:
        return _redirect_with_message(selected_provider, "failed", error)

    updated = update_manual_usage_record(record_id, record)
    if not updated:
        return _redirect_with_message(selected_provider, "failed", "수정할 수동 입력 기록을 찾을 수 없습니다.")
    return _redirect_with_message(selected_provider, "success", "수동 입력 기록을 수정했습니다.")


@app.post("/manual/{record_id}/delete")
def delete_manual_usage(record_id: int, provider: str = Form(default="all")) -> RedirectResponse:
    selected_provider = _selected_provider(provider)
    deleted = delete_manual_usage_record(record_id)
    if not deleted:
        return _redirect_with_message(selected_provider, "failed", "삭제할 수동 입력 기록을 찾을 수 없습니다.")
    return _redirect_with_message(selected_provider, "success", "수동 입력 기록을 삭제했습니다.")


@app.get("/api/summary")
def api_summary() -> dict:
    today = date.today()
    start_date = today.replace(day=1)
    month_key = today.strftime("%Y-%m")
    month_total = _safe_usage_total(get_monthly_total(month_key))
    current_total_tokens = month_total["total_tokens"]
    usage_limit_percent = token_limit_used_percent(current_total_tokens)
    return {
        "daily": _safe_summary_rows(get_daily_summary(start_date, today)),
        "by_provider_model": _safe_summary_rows(get_provider_summary(start_date, today)),
        "month": month_total,
        "provider_ratios": _safe_provider_share(get_provider_usage_share(month_key)),
        "usage_limit": {
            "month": month_key,
            "monthly_token_limit": settings.monthly_token_limit,
            "current_total_tokens": current_total_tokens,
            "remaining_tokens": max(settings.monthly_token_limit - current_total_tokens, 0),
            "used_percent": usage_limit_percent,
            "warning": token_limit_warning_message(usage_limit_percent),
        },
    }


def _selected_provider(provider: str | None) -> str:
    if provider in COLLECTORS:
        return provider
    if settings.default_provider_filter in COLLECTORS:
        return settings.default_provider_filter
    return "all"


def _provider_options() -> list[dict]:
    return [{"value": value, "label": PROVIDER_LABELS[value]} for value in ("all", *PROVIDERS)]


def _manual_provider_options() -> list[dict]:
    return [{"value": value, "label": PROVIDER_LABELS[value]} for value in PROVIDERS]


def _api_test_provider_options(collector_runs: list[dict]) -> list[dict]:
    latest_status = _latest_api_status_by_provider(collector_runs)
    return [
        _api_provider_option(
            value="openai",
            label=PROVIDER_LABELS["openai"],
            model=settings.openai_model,
            has_key=bool(settings.openai_api_key),
            latest_status=latest_status.get("openai"),
            hint="OPENAI_API_KEY를 사용한 짧은 테스트 호출",
        ),
        {
            "value": "claude",
            "label": PROVIDER_LABELS["claude"],
            "model": settings.claude_model,
            "status": "미연결",
            "status_type": "disabled",
            "enabled": False,
            "hint": "필요하면 수동 입력으로 Claude 사용량을 기록할 수 있습니다.",
        },
        _api_provider_option(
            value="gemini",
            label=PROVIDER_LABELS["gemini"],
            model=settings.gemini_model,
            has_key=bool(settings.gemini_api_key),
            latest_status=latest_status.get("gemini"),
            hint="GEMINI_API_KEY를 사용한 짧은 테스트 호출",
        ),
    ]


def _api_provider_option(
    value: str,
    label: str,
    model: str,
    has_key: bool,
    latest_status: str | None,
    hint: str,
) -> dict:
    if not has_key:
        return {
            "value": value,
            "label": label,
            "model": model,
            "status": "미연결",
            "status_type": "missing_key",
            "enabled": False,
            "hint": hint,
        }
    if latest_status == "quota_insufficient":
        return {
            "value": value,
            "label": label,
            "model": model,
            "status": "쿼터 부족",
            "status_type": "quota_insufficient",
            "enabled": True,
            "hint": "API 키는 있지만 사용 가능한 API 크레딧 또는 쿼터가 부족합니다.",
        }
    if latest_status in {"failed", "error"}:
        return {
            "value": value,
            "label": label,
            "model": model,
            "status": "오류",
            "status_type": "error",
            "enabled": True,
            "hint": "최근 테스트 호출이 실패했습니다. 키와 모델명을 확인해주세요.",
        }
    return {
        "value": value,
        "label": label,
        "model": model,
        "status": "연결 가능",
        "status_type": "available",
        "enabled": True,
        "hint": hint,
    }


def _latest_api_status_by_provider(collector_runs: list[dict]) -> dict[str, str]:
    latest: dict[str, str] = {}
    for run in collector_runs:
        provider = run.get("provider")
        if provider in {"openai", "gemini"} and not run.get("dry_run") and provider not in latest:
            latest[provider] = run.get("status") or ""
    return latest


def _openai_quota_notice(api_test_provider_options: list[dict]) -> str | None:
    for option in api_test_provider_options:
        if option["value"] == "openai" and option["status_type"] == "quota_insufficient":
            return OPENAI_QUOTA_MESSAGE
    return None


def _provider_empty_message(selected_provider: str) -> str:
    if selected_provider == "claude":
        return "Claude 사용량 데이터가 없습니다. 현재 Claude 실제 수집은 비활성화되어 있습니다."
    if selected_provider in PROVIDER_LABELS:
        return f"{PROVIDER_LABELS[selected_provider]} 사용량 데이터가 없습니다."
    return "데이터가 없습니다."


def _manual_record_from_form(
    usage_date: str,
    provider: str,
    model: str,
    request_count: int,
    input_tokens: int,
    output_tokens: int,
    cached_tokens: int,
) -> tuple[UsageRecord | None, str | None]:
    if provider not in PROVIDERS:
        return None, "제공자를 선택해주세요."
    if not model.strip():
        return None, "모델명을 입력해주세요."
    values = [request_count, input_tokens, output_tokens, cached_tokens]
    if any(value < 0 for value in values):
        return None, "요청 수와 토큰 값은 0 이상의 정수만 입력할 수 있습니다."

    try:
        parsed_date = date.fromisoformat(usage_date)
    except ValueError:
        return None, "날짜 형식이 올바르지 않습니다."

    return (
        UsageRecord(
            provider=provider,
            model=model.strip(),
            usage_date=parsed_date,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_tokens=cached_tokens,
            request_count=request_count,
            cost_usd=0,
            source="manual",
        ),
        None,
    )


def _notice_status(result: Any) -> str:
    status = getattr(result, "status", None)
    if status in {"disabled", "quota_insufficient"}:
        return status
    return "success" if getattr(result, "success", False) else "failed"


def _redirect_with_message(provider: str, status: str, message: str) -> RedirectResponse:
    return RedirectResponse(
        f"/?provider={provider}&collect_status={status}&collect_message={quote(message)}",
        status_code=303,
    )


def _safe_usage_total(row: dict | None) -> dict:
    safe = {key: 0 for key in USAGE_NUMBER_KEYS}
    if row:
        safe.update({key: _safe_int(row.get(key)) for key in USAGE_NUMBER_KEYS})
    if safe["total_tokens"] <= 0:
        safe["total_tokens"] = total_tokens(safe["input_tokens"], safe["output_tokens"], safe["cached_tokens"])
    return safe


def _safe_summary_rows(rows: list[dict] | None) -> list[dict]:
    safe_rows: list[dict] = []
    for row in rows or []:
        item: dict[str, Any] = dict(row)
        for key in USAGE_NUMBER_KEYS:
            if key in item:
                item[key] = _safe_int(item.get(key))
        if item.get("total_tokens", 0) <= 0 and {"input_tokens", "output_tokens", "cached_tokens"}.issubset(item):
            item["total_tokens"] = total_tokens(item["input_tokens"], item["output_tokens"], item["cached_tokens"])
        safe_rows.append(item)
    return safe_rows


def _safe_provider_share(rows: list[dict] | None) -> list[dict]:
    safe_rows: list[dict] = []
    for row in rows or []:
        provider = row.get("provider") or "unknown"
        safe_rows.append(
            {
                "provider": provider,
                "label": row.get("label") or provider_label(provider),
                "value": _safe_int(row.get("value")),
                "percent": float(row.get("percent") or 0),
            }
        )
    return safe_rows


def _safe_int(value: Any) -> int:
    try:
        return max(int(value or 0), 0)
    except (TypeError, ValueError):
        return 0


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=True,
    )
