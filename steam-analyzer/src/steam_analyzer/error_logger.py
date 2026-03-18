"""Error logger for steam-analyzer MCP tools.

Stores structured error records in the analysis_logs SQLite table so that
callers can review failures, mark them resolved, and surface suggestions.
"""

import json
import sqlite3
from typing import Any

ANALYSIS_LOGS_SQL = """
CREATE TABLE IF NOT EXISTS analysis_logs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    tool_name     TEXT    NOT NULL,
    params        TEXT    NOT NULL,
    error_type    TEXT    NOT NULL,
    error_message TEXT    NOT NULL,
    suggestion    TEXT    NOT NULL,
    resolved      INTEGER NOT NULL DEFAULT 0,
    resolution    TEXT,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
)
"""


def init_analysis_logs(conn: sqlite3.Connection) -> None:
    """Create the analysis_logs table if it does not already exist."""
    conn.execute(ANALYSIS_LOGS_SQL)
    conn.commit()


def log_error(
    conn: sqlite3.Connection,
    tool_name: str,
    params: dict,
    error_type: str,
    error_message: str,
    suggestion: str,
) -> int:
    """Insert an error record and return the new row ID."""
    cursor = conn.execute(
        """
        INSERT INTO analysis_logs (tool_name, params, error_type, error_message, suggestion)
        VALUES (?, ?, ?, ?, ?)
        """,
        (tool_name, json.dumps(params, ensure_ascii=False), error_type, error_message, suggestion),
    )
    conn.commit()
    return cursor.lastrowid


def resolve_error(conn: sqlite3.Connection, error_id: int, resolution: str) -> None:
    """Mark an error record as resolved and store the resolution text."""
    conn.execute(
        "UPDATE analysis_logs SET resolved = 1, resolution = ? WHERE id = ?",
        (resolution, error_id),
    )
    conn.commit()


def _rows_to_dicts(rows) -> list[dict]:
    """Convert sqlite3.Row objects (or plain tuples with description) to dicts."""
    return [dict(row) for row in rows]


def get_unresolved_logs(conn: sqlite3.Connection, limit: int = 10) -> list[dict]:
    """Return up to *limit* unresolved error records, oldest first."""
    rows = conn.execute(
        "SELECT * FROM analysis_logs WHERE resolved = 0 ORDER BY id ASC LIMIT ?",
        (limit,),
    ).fetchall()
    return _rows_to_dicts(rows)


def get_all_logs(
    conn: sqlite3.Connection,
    unresolved_only: bool = True,
    limit: int = 10,
) -> list[dict]:
    """Return up to *limit* error records.

    If *unresolved_only* is True (default) only unresolved records are returned.
    """
    if unresolved_only:
        rows = conn.execute(
            "SELECT * FROM analysis_logs WHERE resolved = 0 ORDER BY id ASC LIMIT ?",
            (limit,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM analysis_logs ORDER BY id ASC LIMIT ?",
            (limit,),
        ).fetchall()
    return _rows_to_dicts(rows)


def make_error_response(
    conn: sqlite3.Connection,
    tool_name: str,
    params: dict,
    error_type: str,
    error_message: str,
    suggestion: str,
    extra: dict[str, Any] | None = None,
) -> dict:
    """Log the error and return a structured error-response dict.

    The returned dict always contains:
        error (bool): True
        error_id (int): the new DB row ID
        error_type (str)
        error_message (str)
        suggestion (str)

    Any key/value pairs in *extra* are merged into the dict.
    """
    error_id = log_error(conn, tool_name, params, error_type, error_message, suggestion)
    response: dict[str, Any] = {
        "error": True,
        "error_id": error_id,
        "error_type": error_type,
        "error_message": error_message,
        "suggestion": suggestion,
    }
    if extra:
        response.update(extra)
    return response
