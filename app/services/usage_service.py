from datetime import date

from app.db import get_db
from app.models import UsageRecord
from app.services.calculation_service import percent, provider_label


def upsert_usage_records(records: list[UsageRecord]) -> int:
    if not records:
        return 0

    with get_db() as db:
        db.executemany(
            """
            INSERT INTO usage_records (
                provider, model, usage_date, input_tokens, output_tokens,
                cached_tokens, total_tokens, request_count, cost_usd, source
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(provider, model, usage_date, source)
            DO UPDATE SET
                input_tokens = excluded.input_tokens,
                output_tokens = excluded.output_tokens,
                cached_tokens = excluded.cached_tokens,
                total_tokens = excluded.total_tokens,
                request_count = excluded.request_count,
                cost_usd = excluded.cost_usd
            """,
            [
                (
                    record.provider,
                    record.model,
                    record.usage_date.isoformat(),
                    record.input_tokens,
                    record.output_tokens,
                    record.cached_tokens,
                    record.total_tokens,
                    record.request_count,
                    record.cost_usd,
                    record.source,
                )
                for record in records
            ],
        )
    return len(records)


def delete_claude_dry_run_records() -> int:
    with get_db() as db:
        cursor = db.execute(
            "DELETE FROM usage_records WHERE provider = 'claude' AND source = 'dry_run'",
        )
        return cursor.rowcount


def upsert_manual_usage_record(record: UsageRecord) -> int:
    if record.source != "manual":
        raise ValueError("manual source만 저장할 수 있습니다.")
    return upsert_usage_records([record])


def get_manual_usage_records(
    start_date: date | None = None,
    end_date: date | None = None,
    provider: str | None = None,
) -> list[dict]:
    params: list[str] = []
    where = _where_clause(start_date, end_date, provider, params, source="manual")
    return _fetch_all(
        f"""
        SELECT
            id,
            usage_date,
            provider,
            model,
            request_count,
            input_tokens,
            output_tokens,
            cached_tokens,
            total_tokens
        FROM usage_records
        {where}
        ORDER BY usage_date DESC, provider, model
        """,
        params,
    )


def update_manual_usage_record(record_id: int, record: UsageRecord) -> bool:
    if record.source != "manual":
        raise ValueError("manual source만 수정할 수 있습니다.")

    with get_db() as db:
        existing = db.execute(
            "SELECT id FROM usage_records WHERE id = ? AND source = 'manual'",
            (record_id,),
        ).fetchone()
        if existing is None:
            return False

        conflicting = db.execute(
            """
            SELECT id
            FROM usage_records
            WHERE provider = ?
              AND model = ?
              AND usage_date = ?
              AND source = 'manual'
              AND id != ?
            """,
            (record.provider, record.model, record.usage_date.isoformat(), record_id),
        ).fetchone()
        if conflicting:
            db.execute("DELETE FROM usage_records WHERE id = ?", (record_id,))
            db.execute(
                """
                UPDATE usage_records
                SET
                    input_tokens = ?,
                    output_tokens = ?,
                    cached_tokens = ?,
                    total_tokens = ?,
                    request_count = ?,
                    cost_usd = 0
                WHERE id = ?
                """,
                (
                    record.input_tokens,
                    record.output_tokens,
                    record.cached_tokens,
                    record.total_tokens,
                    record.request_count,
                    conflicting["id"],
                ),
            )
            return True

        db.execute(
            """
            UPDATE usage_records
            SET
                provider = ?,
                model = ?,
                usage_date = ?,
                input_tokens = ?,
                output_tokens = ?,
                cached_tokens = ?,
                total_tokens = ?,
                request_count = ?,
                cost_usd = 0
            WHERE id = ? AND source = 'manual'
            """,
            (
                record.provider,
                record.model,
                record.usage_date.isoformat(),
                record.input_tokens,
                record.output_tokens,
                record.cached_tokens,
                record.total_tokens,
                record.request_count,
                record_id,
            ),
        )
        return True


def delete_manual_usage_record(record_id: int) -> bool:
    with get_db() as db:
        cursor = db.execute(
            "DELETE FROM usage_records WHERE id = ? AND source = 'manual'",
            (record_id,),
        )
        return cursor.rowcount > 0


def get_daily_summary(
    start_date: date | None = None,
    end_date: date | None = None,
    provider: str | None = None,
) -> list[dict]:
    params: list[str] = []
    where = _where_clause(start_date, end_date, provider, params)
    return _fetch_all(
        f"""
        SELECT
            usage_date,
            provider,
            model,
            SUM(input_tokens) AS input_tokens,
            SUM(output_tokens) AS output_tokens,
            SUM(cached_tokens) AS cached_tokens,
            SUM(total_tokens) AS total_tokens,
            SUM(request_count) AS request_count
        FROM usage_records
        {where}
        GROUP BY usage_date, provider, model
        ORDER BY usage_date DESC, provider, model
        """,
        params,
    )


def get_provider_summary(
    start_date: date | None = None,
    end_date: date | None = None,
    provider: str | None = None,
) -> list[dict]:
    params: list[str] = []
    where = _where_clause(start_date, end_date, provider, params)
    return _fetch_all(
        f"""
        SELECT
            provider,
            model,
            SUM(input_tokens) AS input_tokens,
            SUM(output_tokens) AS output_tokens,
            SUM(cached_tokens) AS cached_tokens,
            SUM(total_tokens) AS total_tokens,
            SUM(request_count) AS request_count
        FROM usage_records
        {where}
        GROUP BY provider, model
        ORDER BY provider, model
        """,
        params,
    )


def get_monthly_total(year_month: str, provider: str | None = None) -> dict:
    params = [year_month]
    provider_clause = ""
    if provider:
        provider_clause = "AND provider = ?"
        params.append(provider)
    rows = _fetch_all(
        f"""
        SELECT
            COALESCE(SUM(input_tokens), 0) AS input_tokens,
            COALESCE(SUM(output_tokens), 0) AS output_tokens,
            COALESCE(SUM(cached_tokens), 0) AS cached_tokens,
            COALESCE(SUM(total_tokens), 0) AS total_tokens,
            COALESCE(SUM(request_count), 0) AS request_count
        FROM usage_records
        WHERE substr(usage_date, 1, 7) = ?
        {provider_clause}
        """,
        params,
    )
    return rows[0] if rows else {}


def get_provider_usage_share(
    year_month: str,
    provider: str | None = None,
    metric: str = "tokens",
) -> list[dict]:
    rows = _provider_metric_rows(year_month, provider, metric)
    total_value = sum(row["value"] for row in rows)

    return [
        {
            "provider": row["provider"],
            "label": provider_label(row["provider"]),
            "value": row["value"],
            "percent": percent(row["value"], total_value),
        }
        for row in rows
    ]


def _provider_metric_rows(year_month: str, provider: str | None, metric: str) -> list[dict]:
    metric_columns = {
        "tokens": "COALESCE(SUM(total_tokens), 0)",
        "requests": "COALESCE(SUM(request_count), 0)",
    }
    metric_sql = metric_columns.get(metric, metric_columns["tokens"])
    params = [year_month]
    provider_clause = ""
    if provider:
        provider_clause = "AND provider = ?"
        params.append(provider)

    rows = _fetch_all(
        f"""
        SELECT provider, {metric_sql} AS value
        FROM usage_records
        WHERE substr(usage_date, 1, 7) = ?
        {provider_clause}
        GROUP BY provider
        ORDER BY provider
        """,
        params,
    )
    existing = {row["provider"]: float(row["value"] or 0) for row in rows}
    provider_order = ["openai", "claude", "gemini"] if provider is None else [provider]
    return [{"provider": name, "value": existing.get(name, 0.0)} for name in provider_order]


def _where_clause(
    start_date: date | None,
    end_date: date | None,
    provider: str | None,
    params: list[str],
    source: str | None = None,
) -> str:
    clauses: list[str] = []
    if start_date:
        clauses.append("usage_date >= ?")
        params.append(start_date.isoformat())
    if end_date:
        clauses.append("usage_date <= ?")
        params.append(end_date.isoformat())
    if provider:
        clauses.append("provider = ?")
        params.append(provider)
    if source:
        clauses.append("source = ?")
        params.append(source)
    return "WHERE " + " AND ".join(clauses) if clauses else ""


def _fetch_all(query: str, params: list[str] | None = None) -> list[dict]:
    with get_db() as db:
        rows = db.execute(query, params or []).fetchall()
    return [dict(row) for row in rows]
