import time


def test_rate_limiter_initial_delay():
    from steam_crawler.api.rate_limiter import AdaptiveRateLimiter
    rl = AdaptiveRateLimiter(api_name="test", default_delay_ms=1000)
    assert rl.current_delay_ms == 1000


def test_rate_limiter_decrease_on_fast_response():
    from steam_crawler.api.rate_limiter import AdaptiveRateLimiter
    rl = AdaptiveRateLimiter(api_name="test", default_delay_ms=1000, min_delay_ms=500)
    rl.record_success(response_time_ms=200)
    assert rl.current_delay_ms < 1000


def test_rate_limiter_hold_on_slow_response():
    from steam_crawler.api.rate_limiter import AdaptiveRateLimiter
    rl = AdaptiveRateLimiter(api_name="test", default_delay_ms=1000)
    rl.record_success(response_time_ms=3000)
    assert rl.current_delay_ms == 1000


def test_rate_limiter_increase_on_429():
    from steam_crawler.api.rate_limiter import AdaptiveRateLimiter
    rl = AdaptiveRateLimiter(api_name="test", default_delay_ms=1000)
    rl.record_rate_limited()
    assert rl.current_delay_ms == 1500


def test_rate_limiter_backoff_sequence():
    from steam_crawler.api.rate_limiter import AdaptiveRateLimiter
    rl = AdaptiveRateLimiter(api_name="test", default_delay_ms=1000)
    backoffs = rl.get_backoff_sequence()
    assert backoffs == [5000, 15000, 45000]


def test_rate_limiter_stats(db_conn):
    from steam_crawler.api.rate_limiter import AdaptiveRateLimiter
    rl = AdaptiveRateLimiter(api_name="steamspy", default_delay_ms=1000)
    rl.record_success(response_time_ms=200)
    rl.record_success(response_time_ms=300)
    rl.record_rate_limited()
    stats = rl.get_stats()
    assert stats["requests_made"] == 3
    assert stats["errors_429"] == 1


def test_rate_limiter_load_from_db(db_conn):
    from steam_crawler.api.rate_limiter import AdaptiveRateLimiter, save_rate_stats, load_optimal_delay

    # Insert a dummy data_versions row to satisfy FK constraint (PRAGMA foreign_keys=ON)
    db_conn.execute(
        "INSERT INTO data_versions (version, query_type, status) VALUES (1, 'test', 'done')"
    )
    db_conn.commit()

    rl = AdaptiveRateLimiter(api_name="steamspy", default_delay_ms=1000)
    rl.record_success(response_time_ms=200)
    save_rate_stats(db_conn, rl, session_id=1)
    loaded = load_optimal_delay(db_conn, "steamspy")
    assert loaded is not None
    assert loaded == rl.current_delay_ms
