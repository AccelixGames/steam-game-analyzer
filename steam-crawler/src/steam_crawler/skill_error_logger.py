"""Log skill execution errors to SQLite for diagnosis by steam-diagnose."""

import json
import sqlite3

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS skill_errors (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_name      TEXT NOT NULL,
    error_type      TEXT NOT NULL,
    error_message   TEXT NOT NULL,
    traceback       TEXT,
    command         TEXT,
    context         TEXT,
    fix_applied     TEXT,
    resolved        INTEGER DEFAULT 0,
    resolution      TEXT,
    created_at      TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_skill_errors_unresolved
    ON skill_errors(resolved) WHERE resolved = 0;
CREATE INDEX IF NOT EXISTS idx_skill_errors_skill
    ON skill_errors(skill_name);
"""


def _get_conn(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.executescript(_CREATE_TABLE_SQL)
    return conn


def log_skill_error(
    db_path: str,
    skill_name: str,
    error_type: str,
    error_message: str,
    traceback: str = None,
    command: str = None,
    context: dict = None,
    fix_applied: str = None,
) -> int:
    """Log a skill execution error to DB. Returns inserted row id."""
    conn = _get_conn(db_path)
    cursor = conn.execute(
        """INSERT INTO skill_errors
           (skill_name, error_type, error_message, traceback,
            command, context, fix_applied)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            skill_name,
            error_type,
            error_message,
            traceback,
            command,
            json.dumps(context) if context else None,
            fix_applied,
        ),
    )
    conn.commit()
    row_id = cursor.lastrowid
    conn.close()
    return row_id


def resolve_skill_error(
    db_path: str,
    error_id: int,
    resolution: str,
    fix_applied: str = None,
) -> None:
    """Mark a skill error as resolved."""
    conn = _get_conn(db_path)
    if fix_applied:
        conn.execute(
            """UPDATE skill_errors
               SET resolved = 1, resolution = ?, fix_applied = ?
               WHERE id = ?""",
            (resolution, fix_applied, error_id),
        )
    else:
        conn.execute(
            """UPDATE skill_errors SET resolved = 1, resolution = ?
               WHERE id = ?""",
            (resolution, error_id),
        )
    conn.commit()
    conn.close()
