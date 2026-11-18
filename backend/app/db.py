"""SQLite storage for scans and findings, using only the standard library.

Every function opens its own short-lived connection, so it is safe to call from
request handlers and from the background scan thread at the same time.
"""

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import config
from .scanner.models import Finding

SCHEMA = """
CREATE TABLE IF NOT EXISTS scans (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    status       TEXT NOT NULL,          -- RUNNING, COMPLETED or FAILED
    started_at   TEXT NOT NULL,          -- ISO 8601, UTC
    finished_at  TEXT,
    account_ids  TEXT,                   -- JSON list; NULL until "all accounts" is resolved
    error        TEXT                    -- why the scan FAILED
);
CREATE TABLE IF NOT EXISTS findings (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id      INTEGER NOT NULL REFERENCES scans(id),
    check_id     TEXT NOT NULL,
    title        TEXT NOT NULL,
    provider     TEXT NOT NULL,
    account_id   TEXT NOT NULL,
    region       TEXT,
    resource_id  TEXT,
    status       TEXT NOT NULL,
    severity     TEXT NOT NULL,
    details      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_findings_scan_id ON findings(scan_id);
"""

# Columns the findings endpoint may filter on. Only these fixed names are ever put
# into SQL text; the user's values always go in as ? parameters.
FILTER_COLUMNS = ("status", "severity", "provider", "account_id", "check_id")

# FAIL, CANNOT_SCAN, PASS; then CRITICAL..LOW; then check ID; then resource ID.
FINDINGS_ORDER = """
    CASE status WHEN 'FAIL' THEN 0 WHEN 'CANNOT_SCAN' THEN 1 ELSE 2 END,
    CASE severity WHEN 'CRITICAL' THEN 0 WHEN 'HIGH' THEN 1 WHEN 'MEDIUM' THEN 2 ELSE 3 END,
    check_id, resource_id, id
"""


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    """Open a connection, commit if the block succeeds, always close."""
    conn = sqlite3.connect(config.db_path(), timeout=10)
    conn.row_factory = sqlite3.Row  # rows behave like dicts
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def init_db() -> None:
    Path(config.db_path()).parent.mkdir(parents=True, exist_ok=True)
    with connect() as conn:
        # WAL lets readers keep reading while the scan thread writes.
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(SCHEMA)


def fail_interrupted_scans() -> None:
    """A scan still RUNNING at startup was cut off by a restart; it will never finish."""
    with connect() as conn:
        conn.execute(
            "UPDATE scans SET status = 'FAILED', finished_at = ?, error = ? "
            "WHERE status = 'RUNNING'",
            (now(), "Interrupted by a server restart"),
        )


def create_scan(account_ids: list[str] | None) -> int:
    with connect() as conn:
        cursor = conn.execute(
            "INSERT INTO scans (status, started_at, account_ids) VALUES ('RUNNING', ?, ?)",
            (now(), None if account_ids is None else json.dumps(account_ids)),
        )
        return cursor.lastrowid


def set_scan_accounts(scan_id: int, account_ids: list[str]) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE scans SET account_ids = ? WHERE id = ?", (json.dumps(account_ids), scan_id)
        )


def complete_scan(scan_id: int, findings: list[Finding]) -> None:
    # One transaction: the findings and the COMPLETED status appear together.
    with connect() as conn:
        conn.executemany(
            "INSERT INTO findings (scan_id, check_id, title, provider, account_id, region,"
            " resource_id, status, severity, details) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    scan_id,
                    f.check_id,
                    f.title,
                    f.provider,
                    f.account_id,
                    f.region,
                    f.resource_id,
                    f.status.value,
                    f.severity.value,
                    f.details,
                )
                for f in findings
            ],
        )
        conn.execute(
            "UPDATE scans SET status = 'COMPLETED', finished_at = ? WHERE id = ?",
            (now(), scan_id),
        )


def fail_scan(scan_id: int, error: str) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE scans SET status = 'FAILED', finished_at = ?, error = ? WHERE id = ?",
            (now(), error, scan_id),
        )


def get_scan(scan_id: int) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM scans WHERE id = ?", (scan_id,)).fetchone()
    return _scan_row(row) if row else None


def list_scans() -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM scans ORDER BY id DESC").fetchall()
    return [_scan_row(row) for row in rows]


def count_findings(group_by: tuple[str, ...], scan_id: int | None = None) -> list[dict[str, Any]]:
    """COUNT(*) of findings grouped by the given (fixed, trusted) column names."""
    columns = ", ".join(group_by)
    where, params = ("WHERE scan_id = ?", (scan_id,)) if scan_id is not None else ("", ())
    sql = f"SELECT {columns}, COUNT(*) AS n FROM findings {where} GROUP BY {columns}"
    with connect() as conn:
        return [dict(row) for row in conn.execute(sql, params).fetchall()]


def query_findings(
    scan_id: int, filters: dict[str, str | None], page: int, page_size: int
) -> tuple[list[dict[str, Any]], int]:
    """One page of a scan's findings, filtered case-insensitively, plus the total match count."""
    where = ["scan_id = ?"]
    params: list[Any] = [scan_id]
    for column in FILTER_COLUMNS:
        value = filters.get(column)
        if value is not None:
            where.append(f"LOWER({column}) = LOWER(?)")
            params.append(value)
    where_sql = " AND ".join(where)

    with connect() as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM findings WHERE {where_sql}", params).fetchone()[
            0
        ]
        rows = conn.execute(
            f"SELECT * FROM findings WHERE {where_sql} ORDER BY {FINDINGS_ORDER} LIMIT ? OFFSET ?",
            [*params, page_size, (page - 1) * page_size],
        ).fetchall()
    return [dict(row) for row in rows], total


def _scan_row(row: sqlite3.Row) -> dict[str, Any]:
    scan = dict(row)
    scan["account_ids"] = json.loads(scan["account_ids"]) if scan["account_ids"] else None
    return scan
