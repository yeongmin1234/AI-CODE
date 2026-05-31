import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from app.config import settings


SCHEMA = """
CREATE TABLE IF NOT EXISTS usage_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    usage_date TEXT NOT NULL,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cached_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    request_count INTEGER NOT NULL DEFAULT 0,
    cost_usd REAL NOT NULL DEFAULT 0,
    source TEXT NOT NULL DEFAULT 'collector',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(provider, model, usage_date, source)
);

CREATE INDEX IF NOT EXISTS idx_usage_records_date
ON usage_records(usage_date);

CREATE INDEX IF NOT EXISTS idx_usage_records_provider_model
ON usage_records(provider, model);

CREATE TABLE IF NOT EXISTS collector_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL,
    dry_run INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TEXT,
    start_date TEXT,
    end_date TEXT,
    records_collected INTEGER NOT NULL DEFAULT 0,
    records_saved INTEGER NOT NULL DEFAULT 0,
    message TEXT
);

CREATE INDEX IF NOT EXISTS idx_collector_runs_provider_started
ON collector_runs(provider, started_at);
"""


def _connect(path: Path | None = None) -> sqlite3.Connection:
    connection = sqlite3.connect(path or settings.database_path)
    connection.row_factory = sqlite3.Row
    return connection


@contextmanager
def get_db() -> Iterator[sqlite3.Connection]:
    connection = _connect()
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_db() -> None:
    with get_db() as db:
        db.executescript(SCHEMA)
        _ensure_total_tokens_column(db)
        db.execute(
            """
            UPDATE usage_records
            SET total_tokens = input_tokens + output_tokens + cached_tokens
            WHERE total_tokens = 0
            """
        )


def _ensure_total_tokens_column(db: sqlite3.Connection) -> None:
    columns = [row["name"] for row in db.execute("PRAGMA table_info(usage_records)").fetchall()]
    if "total_tokens" not in columns:
        db.execute("ALTER TABLE usage_records ADD COLUMN total_tokens INTEGER NOT NULL DEFAULT 0")
