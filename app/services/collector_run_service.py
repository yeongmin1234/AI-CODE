from datetime import date

from app.db import get_db


def start_collector_run(
    provider: str,
    dry_run: bool,
    start_date: date,
    end_date: date,
) -> int:
    with get_db() as db:
        cursor = db.execute(
            """
            INSERT INTO collector_runs (
                provider, dry_run, status, start_date, end_date
            )
            VALUES (?, ?, 'running', ?, ?)
            """,
            (provider, int(dry_run), start_date.isoformat(), end_date.isoformat()),
        )
        return int(cursor.lastrowid)


def finish_collector_run(
    run_id: int,
    status: str,
    message: str,
    records_collected: int = 0,
    records_saved: int = 0,
) -> None:
    safe_message = _sanitize_message(message)
    with get_db() as db:
        db.execute(
            """
            UPDATE collector_runs
            SET
                status = ?,
                finished_at = CURRENT_TIMESTAMP,
                records_collected = ?,
                records_saved = ?,
                message = ?
            WHERE id = ?
            """,
            (status, records_collected, records_saved, safe_message, run_id),
        )


def get_recent_collector_runs(limit: int = 5) -> list[dict]:
    with get_db() as db:
        rows = db.execute(
            """
            SELECT
                provider, dry_run, status, started_at, finished_at,
                start_date, end_date, records_collected, records_saved, message
            FROM collector_runs
            ORDER BY started_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def _sanitize_message(message: str) -> str:
    blocked_fragments = ("sk-", "OPENAI_ADMIN_KEY=", "OPENAI_API_KEY=", "ANTHROPIC_API_KEY=", "GEMINI_API_KEY=")
    if any(fragment in message for fragment in blocked_fragments):
        return "수집 중 오류가 발생했습니다. API 키 설정을 확인해주세요."
    return message[:500]
