"""Tests for skill_error_logger module."""
import json
import sqlite3
import pytest
from steam_crawler.skill_error_logger import log_skill_error, resolve_skill_error


@pytest.fixture
def fresh_db(tmp_path):
    """Empty DB with no tables — tests fallback auto-create."""
    path = str(tmp_path / "empty.db")
    return path


@pytest.fixture
def initialized_db(db_path, db_conn):
    """DB with full schema initialized (uses conftest fixtures)."""
    return str(db_path)


class TestSchemaContainsSkillErrors:
    """T1: skill_errors table and indexes exist in SCHEMA_SQL."""

    def test_table_in_schema_sql(self):
        from steam_crawler.db.schema import SCHEMA_SQL
        assert "skill_errors" in SCHEMA_SQL

    def test_indexes_in_schema_sql(self):
        from steam_crawler.db.schema import SCHEMA_SQL
        assert "idx_skill_errors_unresolved" in SCHEMA_SQL
        assert "idx_skill_errors_skill" in SCHEMA_SQL

    def test_table_created_by_init_db(self, initialized_db):
        conn = sqlite3.connect(initialized_db)
        tables = [
            r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        ]
        conn.close()
        assert "skill_errors" in tables


class TestLogSkillError:
    """T2: log_skill_error() basic operation."""

    def test_returns_row_id(self, initialized_db):
        row_id = log_skill_error(
            db_path=initialized_db,
            skill_name="steam-insight",
            error_type="encoding",
            error_message="UnicodeEncodeError: 'cp949' codec",
        )
        assert isinstance(row_id, int)
        assert row_id > 0

    def test_all_columns_stored(self, initialized_db):
        ctx = {"appid": 286160, "step": "3B-review-analysis"}
        row_id = log_skill_error(
            db_path=initialized_db,
            skill_name="steam-insight",
            error_type="encoding",
            error_message="UnicodeEncodeError: 'cp949' codec",
            traceback="Traceback (most recent call last):\n  File ...",
            command='python -c "import sqlite3..."',
            context=ctx,
            fix_applied="PYTHONIOENCODING=utf-8",
        )
        conn = sqlite3.connect(initialized_db)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM skill_errors WHERE id = ?", (row_id,)
        ).fetchone()
        conn.close()

        assert row["skill_name"] == "steam-insight"
        assert row["error_type"] == "encoding"
        assert row["error_message"] == "UnicodeEncodeError: 'cp949' codec"
        assert row["traceback"].startswith("Traceback")
        assert row["command"] == 'python -c "import sqlite3..."'
        assert json.loads(row["context"]) == ctx
        assert row["fix_applied"] == "PYTHONIOENCODING=utf-8"
        assert row["resolved"] == 0
        assert row["created_at"] is not None


class TestFallbackAutoCreate:
    """T3: auto-create table on empty DB."""

    def test_creates_table_on_empty_db(self, fresh_db):
        row_id = log_skill_error(
            db_path=fresh_db,
            skill_name="steam-query",
            error_type="sql",
            error_message="no such column: foo",
        )
        assert isinstance(row_id, int)

        conn = sqlite3.connect(fresh_db)
        tables = [
            r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        ]
        conn.close()
        assert "skill_errors" in tables


class TestResolveSkillError:
    """T4: resolve_skill_error() operation."""

    def test_marks_resolved(self, initialized_db):
        row_id = log_skill_error(
            db_path=initialized_db,
            skill_name="steam-crawl",
            error_type="timeout",
            error_message="Read timed out",
        )
        resolve_skill_error(
            db_path=initialized_db,
            error_id=row_id,
            resolution="code_fixed",
            fix_applied="timeout 10s -> 20s",
        )
        conn = sqlite3.connect(initialized_db)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM skill_errors WHERE id = ?", (row_id,)
        ).fetchone()
        conn.close()

        assert row["resolved"] == 1
        assert row["resolution"] == "code_fixed"
        assert row["fix_applied"] == "timeout 10s -> 20s"


class TestErrorTypes:
    """T5: all 7 error_type values work."""

    @pytest.mark.parametrize(
        "error_type",
        ["encoding", "sql", "import", "timeout", "parse", "api", "unknown"],
    )
    def test_all_types_accepted(self, initialized_db, error_type):
        row_id = log_skill_error(
            db_path=initialized_db,
            skill_name="steam-insight",
            error_type=error_type,
            error_message=f"test {error_type} error",
        )
        conn = sqlite3.connect(initialized_db)
        row = conn.execute(
            "SELECT error_type FROM skill_errors WHERE id = ?", (row_id,)
        ).fetchone()
        conn.close()
        assert row[0] == error_type


class TestDiagnoseQueries:
    """T6: steam-diagnose queries return expected results."""

    def _seed(self, db_path):
        """Insert test data: 4 unresolved (2 duplicates), 2 resolved."""
        log_skill_error(db_path, "steam-insight", "encoding", "cp949 codec error")
        log_skill_error(db_path, "steam-insight", "encoding", "cp949 codec error")
        log_skill_error(db_path, "steam-query", "sql", "no such column")
        rid4 = log_skill_error(db_path, "steam-crawl", "timeout", "timed out")
        rid5 = log_skill_error(db_path, "steam-insight", "parse", "json decode")
        resolve_skill_error(db_path, rid4, "retried_ok")
        resolve_skill_error(db_path, rid5, "parser_fixed")

    def test_unresolved_by_type(self, initialized_db):
        self._seed(initialized_db)
        conn = sqlite3.connect(initialized_db)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """SELECT skill_name, error_type, count(*) as cnt
               FROM skill_errors WHERE resolved = 0
               GROUP BY skill_name, error_type ORDER BY cnt DESC"""
        ).fetchall()
        conn.close()

        assert len(rows) == 2
        assert rows[0]["skill_name"] == "steam-insight"
        assert rows[0]["error_type"] == "encoding"
        assert rows[0]["cnt"] == 2
        assert rows[1]["cnt"] == 1

    def test_repeated_patterns(self, initialized_db):
        self._seed(initialized_db)
        conn = sqlite3.connect(initialized_db)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """SELECT error_type, error_message, count(*) as cnt,
                      group_concat(DISTINCT fix_applied) as fixes
               FROM skill_errors WHERE resolved = 0
               GROUP BY error_type, error_message HAVING cnt >= 2"""
        ).fetchall()
        conn.close()

        assert len(rows) == 1
        assert rows[0]["error_type"] == "encoding"
        assert rows[0]["cnt"] == 2

    def test_recent_errors(self, initialized_db):
        self._seed(initialized_db)
        conn = sqlite3.connect(initialized_db)
        rows = conn.execute(
            """SELECT skill_name, error_type, error_message,
                      fix_applied, created_at
               FROM skill_errors ORDER BY created_at DESC LIMIT 10"""
        ).fetchall()
        conn.close()

        assert len(rows) == 5  # all 5 entries
