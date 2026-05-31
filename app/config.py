import os
from dataclasses import dataclass
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    app_name: str
    app_host: str
    app_port: int
    database_path: Path
    openai_admin_key: str | None
    openai_api_key: str | None
    anthropic_api_key: str | None
    gemini_api_key: str | None
    dry_run: bool
    default_provider_filter: str
    monthly_token_limit: int


_load_env_file(BASE_DIR / ".env")

settings = Settings(
    app_name=os.getenv("APP_NAME", "AI API Usage Dashboard"),
    app_host=os.getenv("APP_HOST", "127.0.0.1"),
    app_port=_env_int("APP_PORT", 8001),
    database_path=Path(os.getenv("DATABASE_PATH", str(BASE_DIR / "usage.db"))),
    openai_admin_key=os.getenv("OPENAI_ADMIN_KEY") or None,
    openai_api_key=os.getenv("OPENAI_API_KEY") or None,
    anthropic_api_key=os.getenv("ANTHROPIC_API_KEY") or None,
    gemini_api_key=os.getenv("GEMINI_API_KEY") or None,
    dry_run=_env_bool("DEFAULT_DRY_RUN", _env_bool("DRY_RUN", True)),
    default_provider_filter=os.getenv("DEFAULT_PROVIDER_FILTER", "all"),
    monthly_token_limit=max(_env_int("MONTHLY_TOKEN_LIMIT", 1_000_000), 0),
)
