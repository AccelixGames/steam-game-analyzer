import pytest


@pytest.fixture(autouse=True)
def _seed_data_version(db_conn):
    """Insert a dummy data_versions row so FK constraints are satisfied."""
    db_conn.execute(
        "INSERT INTO data_versions (version, query_type, status) VALUES (1, 'test', 'done')"
    )
    db_conn.commit()


def test_classify_rate_limited():
    from steam_crawler.api.resilience import FailureTracker
    ft = FailureTracker()
    assert ft.classify(http_status=429) == "rate_limited"


def test_classify_server_error():
    from steam_crawler.api.resilience import FailureTracker
    ft = FailureTracker()
    assert ft.classify(http_status=500) == "server_error"
    assert ft.classify(http_status=503) == "server_error"


def test_classify_timeout():
    from steam_crawler.api.resilience import FailureTracker
    ft = FailureTracker()
    assert ft.classify(http_status=None, error_type="timeout") == "timeout"


def test_classify_parse_error():
    from steam_crawler.api.resilience import FailureTracker
    ft = FailureTracker()
    assert ft.classify(http_status=200, error_type="parse_error") == "parse_error"


def test_log_failure(db_conn):
    from steam_crawler.api.resilience import FailureTracker
    ft = FailureTracker()
    ft.log_failure(
        conn=db_conn, session_id=1, api_name="steamspy_tag",
        appid=730, step="step1", http_status=429,
        error_message="Too Many Requests",
        request_url="https://steamspy.com/api.php?request=tag&tag=FPS",
    )
    row = db_conn.execute("SELECT * FROM failure_logs WHERE appid=730").fetchone()
    assert row["failure_type"] == "rate_limited"
    assert row["resolved"] == 0


def test_log_failure_with_resolution(db_conn):
    from steam_crawler.api.resilience import FailureTracker
    ft = FailureTracker()
    failure_id = ft.log_failure(
        conn=db_conn, session_id=1, api_name="steam_reviews_crawl",
        appid=730, step="step3", http_status=500,
        error_message="Internal Server Error",
    )
    ft.resolve_failure(db_conn, failure_id, resolution="retried_ok")
    row = db_conn.execute("SELECT * FROM failure_logs WHERE id=?", (failure_id,)).fetchone()
    assert row["resolved"] == 1
    assert row["resolution"] == "retried_ok"


def test_get_unresolved_failures(db_conn):
    from steam_crawler.api.resilience import FailureTracker
    ft = FailureTracker()
    ft.log_failure(conn=db_conn, session_id=1, api_name="test",
                   step="step1", http_status=500, error_message="err1")
    ft.log_failure(conn=db_conn, session_id=1, api_name="test",
                   step="step1", http_status=500, error_message="err2")
    unresolved = ft.get_unresolved(db_conn)
    assert len(unresolved) == 2


def test_session_summary(db_conn):
    from steam_crawler.api.resilience import FailureTracker
    ft = FailureTracker()
    ft.log_failure(conn=db_conn, session_id=1, api_name="test",
                   step="step1", http_status=429, error_message="rate")
    ft.log_failure(conn=db_conn, session_id=1, api_name="test",
                   step="step1", http_status=500, error_message="err")
    fid = ft.log_failure(conn=db_conn, session_id=1, api_name="test",
                         step="step1", http_status=429, error_message="rate2")
    ft.resolve_failure(db_conn, fid, "retried_ok")
    summary = ft.get_session_summary(db_conn, session_id=1)
    assert summary["total"] == 3
    assert summary["resolved"] == 1
    assert summary["by_type"]["rate_limited"] == 2
