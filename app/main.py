from datetime import date
from urllib.parse import quote

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.db import init_db
from app.services.calculation_service import (
    PROVIDER_LABELS,
    provider_label,
    token_limit_used_percent,
    token_limit_warning_level,
    token_limit_warning_message,
)
from app.services.collector_run_service import get_recent_collector_runs
from app.services.collector_service import COLLECTORS, collect_usage
from app.services.usage_service import (
    get_daily_summary,
    get_monthly_total,
    get_provider_summary,
    get_provider_usage_share,
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
    month_key = today.strftime("%Y-%m")
    selected_provider = _selected_provider(request.query_params.get("provider"))
    provider_filter = None if selected_provider == "all" else selected_provider
    month_total = get_monthly_total(month_key, provider_filter)
    current_total_tokens = month_total.get("total_tokens", 0)
    usage_limit_percent = token_limit_used_percent(current_total_tokens)

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "app_name": settings.app_name,
            "provider_options": _provider_options(),
            "selected_provider": selected_provider,
            "daily_summary": get_daily_summary(today.replace(day=1), today, provider_filter),
            "provider_summary": get_provider_summary(today.replace(day=1), today, provider_filter),
            "provider_usage_share": get_provider_usage_share(month_key, provider_filter),
            "month_total": month_total,
            "month_key": month_key,
            "monthly_token_limit": settings.monthly_token_limit,
            "current_total_tokens": current_total_tokens,
            "remaining_token_limit": settings.monthly_token_limit - current_total_tokens,
            "token_limit_used_percent": usage_limit_percent,
            "token_limit_warning": token_limit_warning_message(usage_limit_percent),
            "token_limit_warning_level": token_limit_warning_level(usage_limit_percent),
            "dry_run_default": settings.dry_run,
            "collect_message": request.query_params.get("collect_message"),
            "collect_status": request.query_params.get("collect_status"),
            "collector_runs": get_recent_collector_runs(),
            "provider_filter_label": provider_label(selected_provider),
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
    status = "success" if result.success else "failed"
    message = quote(result.message)
    return RedirectResponse(
        f"/?provider={selected_provider}&collect_status={status}&collect_message={message}",
        status_code=303,
    )


@app.get("/api/summary")
def api_summary() -> dict:
    today = date.today()
    start_date = today.replace(day=1)
    month_key = today.strftime("%Y-%m")
    month_total = get_monthly_total(month_key)
    current_total_tokens = month_total.get("total_tokens", 0)
    usage_limit_percent = token_limit_used_percent(current_total_tokens)
    return {
        "daily": get_daily_summary(start_date, today),
        "by_provider_model": get_provider_summary(start_date, today),
        "month": month_total,
        "usage_limit": {
            "month": month_key,
            "monthly_token_limit": settings.monthly_token_limit,
            "current_total_tokens": current_total_tokens,
            "remaining_tokens": settings.monthly_token_limit - current_total_tokens,
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
    return [{"value": value, "label": PROVIDER_LABELS[value]} for value in ["all", "openai", "claude", "gemini"]]


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=True,
    )
