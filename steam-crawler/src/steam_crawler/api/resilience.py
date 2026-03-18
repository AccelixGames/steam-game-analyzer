"""Failure tracking and resilience utilities for Steam API requests."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Optional


# Known failure type classifications
FAILURE_TYPES = (
    "rate_limited",
    "server_error",
    "timeout",
    "parse_error",
    "connection_error",
    "cursor_invalid",
    "data_quality",
    "empty_response",
    "unknown",
)


@dataclass
class FailureTracker:
    """Tracks API failures, classifies them, and persists them to the DB."""

    def classify(
        self,
        http_status: Optional[int] = None,
        error_type: Optional[str] = None,
    ) -> str:
        """Classify a failure into a canonical failure type string."""
        # HTTP status takes priority for common cases
        if http_status == 429:
            return "rate_limited"
        if http_status is not None and 500 <= http_status <= 599:
            return "server_error"

        # Fall back to error_type string
        if error_type is not None:
            if error_type == "timeout":
                return "timeout"
            if error_type == "parse_error":
                return "parse_error"
            if error_type == "connection_error":
                return "connection_error"
            if error_type == "cursor_invalid":
                return "cursor_invalid"
            if error_type == "data_quality":
                return "data_quality"
            if error_type == "empty_response":
                return "empty_response"
            # Any recognised string in FAILURE_TYPES
            if error_type in FAILURE_TYPES:
                return error_type

        return "unknown"

    def log_failure(
        self,
        conn: sqlite3.Connection,
        session_id: int,
        api_name: str,
        step: str,
        http_status: Optional[int] = None,
        error_message: Optional[str] = None,
        appid: Optional[int] = None,
        request_url: Optional[str] = None,
        response_body: Optional[str] = None,
        error_type: Optional[str] = None,
        retry_count: int = 0,
    ) -> int:
        """Insert a failure record. Returns the new row id."""
        failure_type = self.classify(http_status=http_status, error_type=error_type)

        # Truncate response_body to 1000 chars
        if response_body is not None:
            response_body = response_body[:1000]

        cursor = conn.execute(
            """
            INSERT INTO failure_logs
                (session_id, api_name, appid, step, failure_type,
                 http_status, error_message, request_url, response_body,
                 retry_count, resolved)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """,
            (
                session_id,
                api_name,
                appid,
                step,
                failure_type,
                http_status,
                error_message,
                request_url,
                response_body,
                retry_count,
            ),
        )
        conn.commit()
        return cursor.lastrowid

    def resolve_failure(
        self,
        conn: sqlite3.Connection,
        failure_id: int,
        resolution: str,
    ) -> None:
        """Mark a failure as resolved with a resolution note."""
        conn.execute(
            """
            UPDATE failure_logs
            SET resolved = 1, resolution = ?
            WHERE id = ?
            """,
            (resolution, failure_id),
        )
        conn.commit()

    def get_unresolved(
        self,
        conn: sqlite3.Connection,
        session_id: Optional[int] = None,
    ) -> list[dict]:
        """Return all unresolved failure records, optionally filtered by session."""
        if session_id is not None:
            rows = conn.execute(
                "SELECT * FROM failure_logs WHERE resolved = 0 AND session_id = ?",
                (session_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM failure_logs WHERE resolved = 0"
            ).fetchall()
        return [dict(row) for row in rows]

    def get_session_summary(
        self,
        conn: sqlite3.Connection,
        session_id: int,
    ) -> dict:
        """Return a summary of failures for a session."""
        rows = conn.execute(
            "SELECT failure_type, resolved FROM failure_logs WHERE session_id = ?",
            (session_id,),
        ).fetchall()

        total = len(rows)
        resolved = sum(1 for r in rows if r["resolved"])
        by_type: dict[str, int] = {}
        for row in rows:
            ft = row["failure_type"]
            by_type[ft] = by_type.get(ft, 0) + 1

        return {
            "session_id": session_id,
            "total": total,
            "resolved": resolved,
            "unresolved": total - resolved,
            "by_type": by_type,
        }

    def get_retry_targets(
        self,
        conn: sqlite3.Connection,
    ) -> list[dict]:
        """Return unresolved server_error and timeout failures (retry candidates)."""
        rows = conn.execute(
            """
            SELECT * FROM failure_logs
            WHERE resolved = 0
              AND failure_type IN ('server_error', 'timeout')
            ORDER BY created_at
            """
        ).fetchall()
        return [dict(row) for row in rows]

    def check_schema_change_risk(self, conn: sqlite3.Connection) -> bool:
        """Return True if there are 3 or more unresolved parse_error failures."""
        row = conn.execute(
            """
            SELECT COUNT(*) as cnt FROM failure_logs
            WHERE failure_type = 'parse_error' AND resolved = 0
            """
        ).fetchone()
        return row["cnt"] >= 3
