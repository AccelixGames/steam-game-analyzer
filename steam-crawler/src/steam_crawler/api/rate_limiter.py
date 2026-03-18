"""Adaptive rate limiter for Steam API requests."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional
import sqlite3


@dataclass
class AdaptiveRateLimiter:
    """Adaptive rate limiter that adjusts delay based on API response patterns."""

    api_name: str
    default_delay_ms: float
    min_delay_ms: float = 300
    max_delay_ms: float = 60000
    current_delay_ms: float = 0

    # Internal tracking (not part of constructor signature for users)
    _requests_made: int = field(default=0, init=False, repr=False)
    _errors_429: int = field(default=0, init=False, repr=False)
    _errors_5xx: int = field(default=0, init=False, repr=False)
    _response_times: list = field(default_factory=list, init=False, repr=False)
    _last_request_time: float = field(default=0.0, init=False, repr=False)

    def __post_init__(self):
        if self.current_delay_ms == 0:
            self.current_delay_ms = self.default_delay_ms

    def wait(self) -> None:
        """Sleep remaining time since last request to enforce rate limit."""
        if self._last_request_time > 0:
            elapsed_ms = (time.time() - self._last_request_time) * 1000
            remaining_ms = self.current_delay_ms - elapsed_ms
            if remaining_ms > 0:
                time.sleep(remaining_ms / 1000)
        self._last_request_time = time.time()

    def record_success(self, response_time_ms: float) -> None:
        """Record a successful response. Decrease delay if fast, hold if slow."""
        self._requests_made += 1
        self._response_times.append(response_time_ms)

        if response_time_ms < 500:
            # Fast response — decrease delay by 5%, respecting min
            new_delay = self.current_delay_ms * 0.95
            self.current_delay_ms = max(new_delay, self.min_delay_ms)
        # Slow response (>= 500ms) — hold current delay

    def record_rate_limited(self) -> None:
        """Record a 429 rate limit response. Increase delay by 1.5x."""
        self._requests_made += 1
        self._errors_429 += 1
        new_delay = self.current_delay_ms * 1.5
        self.current_delay_ms = min(new_delay, self.max_delay_ms)

    def record_server_error(self) -> None:
        """Record a 5xx server error."""
        self._requests_made += 1
        self._errors_5xx += 1

    def get_backoff_sequence(self) -> list[float]:
        """Return backoff sequence in milliseconds: [5000, 15000, 45000]."""
        return [5000, 15000, 45000]

    def get_stats(self) -> dict:
        """Return current statistics."""
        avg_response = (
            sum(self._response_times) / len(self._response_times)
            if self._response_times
            else 0.0
        )
        return {
            "api_name": self.api_name,
            "requests_made": self._requests_made,
            "errors_429": self._errors_429,
            "errors_5xx": self._errors_5xx,
            "avg_response_ms": avg_response,
            "optimal_delay_ms": self.current_delay_ms,
        }


def save_rate_stats(
    conn: sqlite3.Connection,
    limiter: AdaptiveRateLimiter,
    session_id: int,
) -> None:
    """Persist rate limiter statistics to the rate_limit_stats table."""
    stats = limiter.get_stats()
    conn.execute(
        """
        INSERT INTO rate_limit_stats
            (api_name, session_id, requests_made, errors_429, errors_5xx,
             avg_response_ms, optimal_delay_ms)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            limiter.api_name,
            session_id,
            stats["requests_made"],
            stats["errors_429"],
            stats["errors_5xx"],
            stats["avg_response_ms"],
            stats["optimal_delay_ms"],
        ),
    )
    conn.commit()


def load_optimal_delay(
    conn: sqlite3.Connection,
    api_name: str,
) -> Optional[float]:
    """Load the most recently recorded optimal delay for an API."""
    row = conn.execute(
        """
        SELECT optimal_delay_ms
        FROM rate_limit_stats
        WHERE api_name = ?
        ORDER BY recorded_at DESC, id DESC
        LIMIT 1
        """,
        (api_name,),
    ).fetchone()
    if row is None:
        return None
    return row["optimal_delay_ms"]
