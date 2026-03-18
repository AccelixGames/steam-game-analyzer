"""Tests for error_logger.py — TDD first pass."""

import sqlite3
import pytest
from steam_analyzer.error_logger import (
    ANALYSIS_LOGS_SQL,
    init_analysis_logs,
    log_error,
    resolve_error,
    get_unresolved_logs,
    get_all_logs,
    make_error_response,
)


@pytest.fixture
def conn(tmp_path):
    db_path = tmp_path / "test.db"
    c = sqlite3.connect(str(db_path))
    c.row_factory = sqlite3.Row
    yield c
    c.close()


@pytest.fixture
def init_conn(conn):
    init_analysis_logs(conn)
    return conn


# ---------------------------------------------------------------------------
# ANALYSIS_LOGS_SQL
# ---------------------------------------------------------------------------

class TestAnalysisLogsSql:
    def test_sql_constant_is_string(self):
        assert isinstance(ANALYSIS_LOGS_SQL, str)

    def test_sql_contains_create_table(self):
        assert "CREATE TABLE IF NOT EXISTS" in ANALYSIS_LOGS_SQL.upper()

    def test_sql_contains_analysis_logs(self):
        assert "analysis_logs" in ANALYSIS_LOGS_SQL

    def test_sql_contains_required_columns(self):
        sql = ANALYSIS_LOGS_SQL.lower()
        for col in ("id", "tool_name", "params", "error_type", "error_message",
                    "suggestion", "resolved", "resolution", "created_at"):
            assert col in sql, f"Missing column: {col}"


# ---------------------------------------------------------------------------
# init_analysis_logs
# ---------------------------------------------------------------------------

class TestInitAnalysisLogs:
    def test_creates_table(self, conn):
        init_analysis_logs(conn)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='analysis_logs'"
        )
        assert cursor.fetchone() is not None

    def test_idempotent(self, conn):
        init_analysis_logs(conn)
        init_analysis_logs(conn)  # must not raise


# ---------------------------------------------------------------------------
# log_error
# ---------------------------------------------------------------------------

class TestLogError:
    def test_returns_int(self, init_conn):
        error_id = log_error(
            init_conn,
            tool_name="some_tool",
            params={"key": "value"},
            error_type="ValueError",
            error_message="Something went wrong",
            suggestion="Try again",
        )
        assert isinstance(error_id, int)
        assert error_id > 0

    def test_inserts_row(self, init_conn):
        log_error(
            init_conn,
            tool_name="tool_a",
            params={"x": 1},
            error_type="TypeError",
            error_message="bad type",
            suggestion="fix it",
        )
        row = init_conn.execute("SELECT * FROM analysis_logs").fetchone()
        assert row is not None
        assert row["tool_name"] == "tool_a"
        assert row["error_type"] == "TypeError"
        assert row["error_message"] == "bad type"
        assert row["suggestion"] == "fix it"

    def test_resolved_defaults_to_zero(self, init_conn):
        log_error(
            init_conn,
            tool_name="t",
            params={},
            error_type="E",
            error_message="m",
            suggestion="s",
        )
        row = init_conn.execute("SELECT resolved FROM analysis_logs").fetchone()
        assert row["resolved"] == 0

    def test_params_stored_as_json_string(self, init_conn):
        log_error(
            init_conn,
            tool_name="t",
            params={"appid": 123},
            error_type="E",
            error_message="m",
            suggestion="s",
        )
        row = init_conn.execute("SELECT params FROM analysis_logs").fetchone()
        # params should be stored as a JSON-serializable string
        import json
        data = json.loads(row["params"])
        assert data["appid"] == 123

    def test_multiple_inserts_return_different_ids(self, init_conn):
        id1 = log_error(init_conn, "t", {}, "E", "m1", "s")
        id2 = log_error(init_conn, "t", {}, "E", "m2", "s")
        assert id1 != id2


# ---------------------------------------------------------------------------
# resolve_error
# ---------------------------------------------------------------------------

class TestResolveError:
    def test_marks_resolved(self, init_conn):
        error_id = log_error(init_conn, "t", {}, "E", "m", "s")
        resolve_error(init_conn, error_id, "fixed by doing X")
        row = init_conn.execute(
            "SELECT resolved, resolution FROM analysis_logs WHERE id=?", (error_id,)
        ).fetchone()
        assert row["resolved"] == 1
        assert row["resolution"] == "fixed by doing X"

    def test_does_not_affect_other_rows(self, init_conn):
        id1 = log_error(init_conn, "t", {}, "E", "m1", "s")
        id2 = log_error(init_conn, "t", {}, "E", "m2", "s")
        resolve_error(init_conn, id1, "done")
        row2 = init_conn.execute(
            "SELECT resolved FROM analysis_logs WHERE id=?", (id2,)
        ).fetchone()
        assert row2["resolved"] == 0


# ---------------------------------------------------------------------------
# get_unresolved_logs
# ---------------------------------------------------------------------------

class TestGetUnresolvedLogs:
    def test_returns_list(self, init_conn):
        result = get_unresolved_logs(init_conn)
        assert isinstance(result, list)

    def test_empty_when_no_logs(self, init_conn):
        assert get_unresolved_logs(init_conn) == []

    def test_returns_unresolved_only(self, init_conn):
        id1 = log_error(init_conn, "t", {}, "E", "m1", "s")
        id2 = log_error(init_conn, "t", {}, "E", "m2", "s")
        resolve_error(init_conn, id1, "done")
        result = get_unresolved_logs(init_conn)
        ids = [r["id"] for r in result]
        assert id1 not in ids
        assert id2 in ids

    def test_result_is_list_of_dicts(self, init_conn):
        log_error(init_conn, "t", {}, "E", "m", "s")
        result = get_unresolved_logs(init_conn)
        assert isinstance(result[0], dict)

    def test_limit_respected(self, init_conn):
        for i in range(5):
            log_error(init_conn, "t", {}, "E", f"m{i}", "s")
        result = get_unresolved_logs(init_conn, limit=3)
        assert len(result) <= 3


# ---------------------------------------------------------------------------
# get_all_logs
# ---------------------------------------------------------------------------

class TestGetAllLogs:
    def test_returns_list(self, init_conn):
        assert isinstance(get_all_logs(init_conn), list)

    def test_unresolved_only_true_filters(self, init_conn):
        id1 = log_error(init_conn, "t", {}, "E", "m1", "s")
        id2 = log_error(init_conn, "t", {}, "E", "m2", "s")
        resolve_error(init_conn, id1, "done")
        result = get_all_logs(init_conn, unresolved_only=True)
        ids = [r["id"] for r in result]
        assert id1 not in ids
        assert id2 in ids

    def test_unresolved_only_false_returns_all(self, init_conn):
        id1 = log_error(init_conn, "t", {}, "E", "m1", "s")
        id2 = log_error(init_conn, "t", {}, "E", "m2", "s")
        resolve_error(init_conn, id1, "done")
        result = get_all_logs(init_conn, unresolved_only=False)
        ids = [r["id"] for r in result]
        assert id1 in ids
        assert id2 in ids

    def test_limit_respected(self, init_conn):
        for i in range(5):
            log_error(init_conn, "t", {}, "E", f"m{i}", "s")
        result = get_all_logs(init_conn, unresolved_only=False, limit=2)
        assert len(result) <= 2

    def test_result_is_list_of_dicts(self, init_conn):
        log_error(init_conn, "t", {}, "E", "m", "s")
        result = get_all_logs(init_conn)
        assert isinstance(result[0], dict)


# ---------------------------------------------------------------------------
# make_error_response
# ---------------------------------------------------------------------------

class TestMakeErrorResponse:
    def test_returns_dict(self, init_conn):
        resp = make_error_response(
            init_conn, "tool", {}, "ValueError", "bad value", "check input"
        )
        assert isinstance(resp, dict)

    def test_error_key_is_true(self, init_conn):
        resp = make_error_response(
            init_conn, "tool", {}, "ValueError", "bad value", "check input"
        )
        assert resp["error"] is True

    def test_contains_required_keys(self, init_conn):
        resp = make_error_response(
            init_conn, "tool", {}, "ValueError", "bad value", "check input"
        )
        for key in ("error", "error_id", "error_type", "error_message", "suggestion"):
            assert key in resp, f"Missing key: {key}"

    def test_error_id_is_positive_int(self, init_conn):
        resp = make_error_response(
            init_conn, "tool", {}, "ValueError", "bad value", "check input"
        )
        assert isinstance(resp["error_id"], int)
        assert resp["error_id"] > 0

    def test_values_match_input(self, init_conn):
        resp = make_error_response(
            init_conn, "my_tool", {"a": 1}, "KeyError", "key missing", "add key"
        )
        assert resp["error_type"] == "KeyError"
        assert resp["error_message"] == "key missing"
        assert resp["suggestion"] == "add key"

    def test_extra_keys_merged(self, init_conn):
        resp = make_error_response(
            init_conn, "tool", {}, "E", "m", "s",
            extra={"appid": 730, "detail": "extra detail"},
        )
        assert resp["appid"] == 730
        assert resp["detail"] == "extra detail"

    def test_extra_none_no_error(self, init_conn):
        resp = make_error_response(init_conn, "tool", {}, "E", "m", "s", extra=None)
        assert resp["error"] is True

    def test_logs_error_to_db(self, init_conn):
        make_error_response(
            init_conn, "tool_x", {"z": 9}, "RuntimeError", "crash", "restart"
        )
        rows = get_all_logs(init_conn, unresolved_only=False)
        assert len(rows) == 1
        assert rows[0]["tool_name"] == "tool_x"
