# Steam Analyzer MCP Server Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Steam 리뷰 데이터를 분석하고 게임 기획서에 대한 피드백을 제공하는 로컬 MCP stdio 서버 구현.

**Architecture:** Python MCP 서버가 SQLite DB에서 리뷰 데이터를 읽어 통계 가공 후 반환. `steam-crawler` 패키지의 모델과 스키마를 editable install로 재사용. 3개 tool: `search_reviews`, `analyze_design`, `get_analysis_logs`.

**Tech Stack:** Python 3.12+, mcp SDK, sqlite3, steam-crawler (editable install), pytest

**Spec:** `docs/superpowers/specs/2026-03-18-steam-analyzer-design.md`

---

## File Map

| Action | Path | Responsibility |
|--------|------|---------------|
| Modify | `steam-analyzer/pyproject.toml` | 의존성 + dev extras 추가 |
| Create | `steam-analyzer/src/steam_analyzer/__init__.py` | 패키지 초기화 |
| Create | `steam-analyzer/src/steam_analyzer/server.py` | MCP stdio 서버 메인 + analysis_logs 스키마 |
| Create | `steam-analyzer/src/steam_analyzer/db_queries.py` | analyzer 전용 SQL 읽기 쿼리 |
| Create | `steam-analyzer/src/steam_analyzer/error_logger.py` | 에러 로깅 + 자가 복구 헬퍼 |
| Create | `steam-analyzer/src/steam_analyzer/stats/__init__.py` | stats 패키지 |
| Create | `steam-analyzer/src/steam_analyzer/stats/review_stats.py` | 키워드 빈도, 긍부정 비율 |
| Create | `steam-analyzer/src/steam_analyzer/tools/__init__.py` | tools 패키지 |
| Create | `steam-analyzer/src/steam_analyzer/tools/search_reviews.py` | search_reviews tool |
| Create | `steam-analyzer/src/steam_analyzer/tools/analyze_design.py` | analyze_design tool |
| Create | `steam-analyzer/src/steam_analyzer/tools/analysis_logs.py` | get_analysis_logs tool |
| Create | `steam-analyzer/tests/conftest.py` | 테스트 픽스처 (DB + 샘플 데이터) |
| Create | `steam-analyzer/tests/test_db_queries.py` | DB 쿼리 테스트 |
| Create | `steam-analyzer/tests/test_review_stats.py` | 통계 로직 테스트 |
| Create | `steam-analyzer/tests/test_search_reviews.py` | search_reviews tool 테스트 |
| Create | `steam-analyzer/tests/test_analyze_design.py` | analyze_design tool 테스트 |
| Create | `.mcp.json` | MCP 서버 연동 설정 |

---

### Task 1: 프로젝트 뼈대 & pyproject.toml

**Files:**
- Modify: `steam-analyzer/pyproject.toml`
- Create: `steam-analyzer/src/steam_analyzer/__init__.py`
- Create: `steam-analyzer/src/steam_analyzer/stats/__init__.py`
- Create: `steam-analyzer/src/steam_analyzer/tools/__init__.py`

- [ ] **Step 1: pyproject.toml 업데이트**

```toml
[project]
name = "steam-analyzer"
version = "0.1.0"
description = "Steam game review analyzer — local MCP server"
requires-python = ">=3.12"
dependencies = [
    "mcp>=1.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]
```

- [ ] **Step 2: 패키지 __init__.py 파일 생성**

`src/steam_analyzer/__init__.py`:
```python
__version__ = "0.1.0"
```

`src/steam_analyzer/stats/__init__.py`: 빈 파일
`src/steam_analyzer/tools/__init__.py`: 빈 파일

- [ ] **Step 3: editable install 확인**

Run: `cd steam-crawler && pip install -e . && cd ../steam-analyzer && pip install -e ".[dev]"`
Expected: 둘 다 설치 성공

- [ ] **Step 4: import 확인**

Run: `python -c "from steam_crawler.db.schema import init_db; from steam_analyzer import __version__; print('OK', __version__)"`
Expected: `OK 0.1.0`

- [ ] **Step 5: Commit**

```bash
git add steam-analyzer/pyproject.toml steam-analyzer/src/
git commit -m "feat(analyzer): scaffold project with pyproject.toml and package structure"
```

---

### Task 2: DB 쿼리 모듈 (db_queries.py)

**Files:**
- Create: `steam-analyzer/src/steam_analyzer/db_queries.py`
- Create: `steam-analyzer/tests/conftest.py`
- Create: `steam-analyzer/tests/test_db_queries.py`

- [ ] **Step 1: conftest.py 작성 — 테스트 픽스처**

```python
import sqlite3
import json
import pytest
from steam_crawler.db.schema import init_db


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "test.db"


@pytest.fixture
def db_conn(db_path):
    conn = init_db(str(db_path))
    from steam_analyzer.error_logger import init_analysis_logs
    init_analysis_logs(conn)
    yield conn
    conn.close()


@pytest.fixture
def seeded_db(db_conn):
    """Insert sample games, tags, and reviews for testing."""
    # Games
    db_conn.execute(
        "INSERT INTO games (appid, name, source_tag) VALUES (?, ?, ?)",
        (100, "RogueGame Alpha", "tag:Roguelike"),
    )
    db_conn.execute(
        "INSERT INTO games (appid, name, source_tag) VALUES (?, ?, ?)",
        (200, "RogueGame Beta", "tag:Roguelike"),
    )
    db_conn.execute(
        "INSERT INTO games (appid, name, source_tag) VALUES (?, ?, ?)",
        (300, "ActionGame Gamma", "tag:Action"),
    )

    # Tags
    for appid, tag, votes in [
        (100, "Roguelike", 5000), (100, "RPG", 3000),
        (200, "Roguelike", 4000), (200, "Indie", 2000),
        (300, "Action", 6000), (300, "RPG", 1000),
    ]:
        db_conn.execute(
            "INSERT INTO game_tags (appid, tag_name, vote_count) VALUES (?, ?, ?)",
            (appid, tag, votes),
        )

    # Reviews
    reviews = [
        ("r1", 100, "english", "This game is so fun and addictive gameplay", 1, 500, 0.9),
        ("r2", 100, "english", "Too many bugs and crashes constantly", 0, 200, 0.8),
        ("r3", 100, "korean", "정말 재미있는 로그라이크 게임입니다", 1, 300, 0.7),
        ("r4", 200, "english", "Great roguelike with fun mechanics and replay value", 1, 800, 0.95),
        ("r5", 200, "english", "Terrible balance and unfair difficulty spike", 0, 150, 0.6),
        ("r6", 300, "english", "Amazing action game with smooth controls", 1, 1000, 0.85),
    ]
    for rid, appid, lang, text, voted_up, playtime, score in reviews:
        db_conn.execute(
            """INSERT INTO reviews
               (recommendation_id, appid, language, review_text, voted_up,
                playtime_forever, weighted_vote_score)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (rid, appid, lang, text, voted_up, playtime, score),
        )

    db_conn.commit()
    return db_conn
```

- [ ] **Step 2: test_db_queries.py — 실패하는 테스트 작성**

```python
from steam_analyzer.db_queries import (
    get_games_by_tag,
    get_reviews_for_games,
    get_review_samples,
    get_available_tags,
)


def test_get_games_by_tag(seeded_db):
    games = get_games_by_tag(seeded_db, "Roguelike")
    appids = [g["appid"] for g in games]
    assert set(appids) == {100, 200}


def test_get_games_by_tag_no_results(seeded_db):
    games = get_games_by_tag(seeded_db, "NonexistentTag")
    assert games == []


def test_get_reviews_for_games(seeded_db):
    reviews = get_reviews_for_games(seeded_db, [100, 200])
    assert len(reviews) == 5
    assert all("game_name" in r for r in reviews)


def test_get_reviews_for_games_language_filter(seeded_db):
    reviews = get_reviews_for_games(seeded_db, [100], language="korean")
    assert len(reviews) == 1
    assert reviews[0]["language"] == "korean"


def test_get_review_samples_positive(seeded_db):
    samples = get_review_samples(seeded_db, [100, 200], voted_up=True, limit=2)
    assert len(samples) == 2
    assert all(s["voted_up"] for s in samples)
    # Ordered by weighted_vote_score DESC
    assert samples[0]["weighted_vote_score"] >= samples[1]["weighted_vote_score"]


def test_get_review_samples_negative(seeded_db):
    samples = get_review_samples(seeded_db, [100, 200], voted_up=False, limit=10)
    assert len(samples) == 2
    assert all(not s["voted_up"] for s in samples)


def test_get_review_samples_truncates_text(seeded_db):
    # Insert a review with >500 chars
    long_text = "x" * 1000
    seeded_db.execute(
        """INSERT INTO reviews
           (recommendation_id, appid, language, review_text, voted_up,
            playtime_forever, weighted_vote_score)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        ("r_long", 100, "english", long_text, True, 100, 0.5),
    )
    seeded_db.commit()
    samples = get_review_samples(seeded_db, [100], voted_up=True, limit=10)
    for s in samples:
        assert len(s["review_text"]) <= 500


def test_get_available_tags(seeded_db):
    tags = get_available_tags(seeded_db)
    tag_names = [t["tag_name"] for t in tags]
    assert "Roguelike" in tag_names
    assert "Action" in tag_names
```

- [ ] **Step 3: 테스트 실패 확인**

Run: `cd steam-analyzer && python -m pytest tests/test_db_queries.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'steam_analyzer.db_queries'`

- [ ] **Step 4: db_queries.py 구현**

```python
"""Analyzer-specific read-only SQL queries against the steam-crawler DB."""

from __future__ import annotations

import sqlite3

MAX_REVIEW_TEXT_LENGTH = 500


def get_games_by_tag(conn: sqlite3.Connection, tag: str) -> list[dict]:
    """Return games that have the given tag via game_tags table."""
    rows = conn.execute(
        """SELECT g.appid, g.name, g.positive, g.negative, g.source_tag
           FROM games g
           JOIN game_tags gt ON g.appid = gt.appid
           WHERE gt.tag_name = ?
           ORDER BY g.positive DESC""",
        (tag,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_reviews_for_games(
    conn: sqlite3.Connection,
    appids: list[int],
    language: str | None = None,
) -> list[dict]:
    """Return reviews for given game IDs, with game_name from JOIN."""
    placeholders = ",".join("?" for _ in appids)
    query = f"""
        SELECT r.recommendation_id, r.appid, g.name AS game_name,
               r.language, r.review_text, r.voted_up,
               r.playtime_forever, r.weighted_vote_score
        FROM reviews r
        JOIN games g ON r.appid = g.appid
        WHERE r.appid IN ({placeholders})
    """
    params: list = list(appids)
    if language:
        query += " AND r.language = ?"
        params.append(language)
    rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def get_review_samples(
    conn: sqlite3.Connection,
    appids: list[int],
    voted_up: bool,
    limit: int,
    language: str | None = None,
) -> list[dict]:
    """Return top reviews by weighted_vote_score, text truncated to 500 chars."""
    placeholders = ",".join("?" for _ in appids)
    query = f"""
        SELECT r.recommendation_id, r.appid, g.name AS game_name,
               r.language, r.review_text, r.voted_up,
               r.playtime_forever, r.weighted_vote_score
        FROM reviews r
        JOIN games g ON r.appid = g.appid
        WHERE r.appid IN ({placeholders}) AND r.voted_up = ?
    """
    params: list = list(appids) + [voted_up]
    if language:
        query += " AND r.language = ?"
        params.append(language)
    query += " ORDER BY r.weighted_vote_score DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    results = []
    for r in rows:
        d = dict(r)
        text = d.get("review_text") or ""
        if len(text) > MAX_REVIEW_TEXT_LENGTH:
            d["review_text"] = text[:MAX_REVIEW_TEXT_LENGTH]
        results.append(d)
    return results


def get_available_tags(conn: sqlite3.Connection) -> list[dict]:
    """Return all distinct tags with game counts, sorted by count DESC."""
    rows = conn.execute(
        """SELECT tag_name, COUNT(*) AS game_count
           FROM game_tags
           GROUP BY tag_name
           ORDER BY game_count DESC"""
    ).fetchall()
    return [dict(r) for r in rows]
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `cd steam-analyzer && python -m pytest tests/test_db_queries.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add steam-analyzer/src/steam_analyzer/db_queries.py steam-analyzer/tests/
git commit -m "feat(analyzer): add db_queries with tag search, review sampling, and tests"
```

---

### Task 3: 에러 로거 (error_logger.py)

**Files:**
- Create: `steam-analyzer/src/steam_analyzer/error_logger.py`
- Create: `steam-analyzer/tests/test_error_logger.py`

- [ ] **Step 1: test_error_logger.py — 실패하는 테스트 작성**

```python
import sqlite3
from steam_analyzer.error_logger import (
    init_analysis_logs,
    log_error,
    resolve_error,
    get_unresolved_logs,
    make_error_response,
)


def _make_conn(tmp_path):
    conn = sqlite3.connect(str(tmp_path / "test.db"))
    conn.row_factory = sqlite3.Row
    init_analysis_logs(conn)
    return conn


def test_init_creates_table(tmp_path):
    conn = _make_conn(tmp_path)
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='analysis_logs'"
    ).fetchone()
    assert tables is not None
    conn.close()


def test_log_and_retrieve(tmp_path):
    conn = _make_conn(tmp_path)
    eid = log_error(
        conn,
        tool_name="search_reviews",
        params='{"tag": "Roguelike"}',
        error_type="no_data",
        error_message="No games found",
        suggestion="Try a different tag",
    )
    assert eid >= 1
    logs = get_unresolved_logs(conn, limit=10)
    assert len(logs) == 1
    assert logs[0]["error_type"] == "no_data"
    conn.close()


def test_resolve_error(tmp_path):
    conn = _make_conn(tmp_path)
    eid = log_error(conn, "test_tool", "{}", "unknown", "err", "fix it")
    resolve_error(conn, eid, "Fixed by retrying with different params")
    logs = get_unresolved_logs(conn, limit=10)
    assert len(logs) == 0
    conn.close()


def test_make_error_response(tmp_path):
    conn = _make_conn(tmp_path)
    resp = make_error_response(
        conn,
        tool_name="search_reviews",
        params='{"tag": "X"}',
        error_type="no_data",
        error_message="No games found for tag 'X'",
        suggestion="Try tag 'Roguelike'",
        extra={"available_tags": ["Roguelike", "RPG"]},
    )
    assert resp["error"] is True
    assert resp["error_id"] >= 1
    assert resp["suggestion"] == "Try tag 'Roguelike'"
    assert resp["available_tags"] == ["Roguelike", "RPG"]
    conn.close()
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd steam-analyzer && python -m pytest tests/test_error_logger.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: error_logger.py 구현**

```python
"""Error logging and self-healing helpers for steam-analyzer."""

from __future__ import annotations

import json
import sqlite3

ANALYSIS_LOGS_SQL = """
CREATE TABLE IF NOT EXISTS analysis_logs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    tool_name     TEXT NOT NULL,
    params        TEXT,
    error_type    TEXT NOT NULL,
    error_message TEXT,
    suggestion    TEXT,
    resolved      INTEGER DEFAULT 0,
    resolution    TEXT,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def init_analysis_logs(conn: sqlite3.Connection) -> None:
    """Create analysis_logs table if it doesn't exist."""
    conn.executescript(ANALYSIS_LOGS_SQL)


def log_error(
    conn: sqlite3.Connection,
    tool_name: str,
    params: str,
    error_type: str,
    error_message: str,
    suggestion: str,
) -> int:
    """Insert error log and return the error ID."""
    cursor = conn.execute(
        """INSERT INTO analysis_logs (tool_name, params, error_type, error_message, suggestion)
           VALUES (?, ?, ?, ?, ?)""",
        (tool_name, params, error_type, error_message, suggestion),
    )
    conn.commit()
    return cursor.lastrowid


def resolve_error(conn: sqlite3.Connection, error_id: int, resolution: str) -> None:
    """Mark an error as resolved."""
    conn.execute(
        "UPDATE analysis_logs SET resolved = 1, resolution = ? WHERE id = ?",
        (resolution, error_id),
    )
    conn.commit()


def get_unresolved_logs(
    conn: sqlite3.Connection, limit: int = 10
) -> list[dict]:
    """Return unresolved error logs."""
    rows = conn.execute(
        """SELECT id, tool_name, params, error_type, error_message, suggestion, created_at
           FROM analysis_logs
           WHERE resolved = 0
           ORDER BY created_at DESC
           LIMIT ?""",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_all_logs(
    conn: sqlite3.Connection, unresolved_only: bool = True, limit: int = 10
) -> list[dict]:
    """Return error logs, optionally filtered to unresolved only."""
    if unresolved_only:
        return get_unresolved_logs(conn, limit)
    rows = conn.execute(
        """SELECT id, tool_name, params, error_type, error_message,
                  suggestion, resolved, resolution, created_at
           FROM analysis_logs
           ORDER BY created_at DESC
           LIMIT ?""",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def make_error_response(
    conn: sqlite3.Connection,
    tool_name: str,
    params: str,
    error_type: str,
    error_message: str,
    suggestion: str,
    extra: dict | None = None,
) -> dict:
    """Log error and return structured error response for MCP."""
    error_id = log_error(conn, tool_name, params, error_type, error_message, suggestion)
    response = {
        "error": True,
        "error_id": error_id,
        "error_type": error_type,
        "error_message": error_message,
        "suggestion": suggestion,
    }
    if extra:
        response.update(extra)
    return response
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd steam-analyzer && python -m pytest tests/test_error_logger.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add steam-analyzer/src/steam_analyzer/error_logger.py steam-analyzer/tests/test_error_logger.py
git commit -m "feat(analyzer): add error_logger with logging, resolving, and structured responses"
```

---

### Task 4: 리뷰 통계 모듈 (stats/review_stats.py)

**Files:**
- Create: `steam-analyzer/src/steam_analyzer/stats/review_stats.py`
- Create: `steam-analyzer/tests/test_review_stats.py`

- [ ] **Step 1: test_review_stats.py — 실패하는 테스트 작성**

```python
import pytest

from steam_analyzer.stats.review_stats import (
    extract_keywords,
    compute_review_stats,
)


def test_extract_keywords_english():
    texts = [
        "This game is really fun and addictive",
        "The gameplay is fun but has some bugs",
    ]
    keywords = extract_keywords(texts, top_n=5)
    words = [kw["word"] for kw in keywords]
    assert "fun" in words
    # Stopwords excluded
    assert "is" not in words
    assert "the" not in words


def test_extract_keywords_filters_short_words():
    texts = ["I go to a fun big map"]
    keywords = extract_keywords(texts, top_n=10)
    words = [kw["word"] for kw in keywords]
    # 2글자 이하 제거
    assert "go" not in words
    assert "to" not in words
    assert "fun" in words
    assert "map" in words


def test_extract_keywords_filters_numbers():
    texts = ["player 123 scored 456 points in game"]
    keywords = extract_keywords(texts, top_n=10)
    words = [kw["word"] for kw in keywords]
    assert "123" not in words
    assert "456" not in words


def test_extract_keywords_korean():
    texts = ["정말 재미있는 로그라이크 게임입니다", "로그라이크 장르의 최고 게임"]
    keywords = extract_keywords(texts, top_n=5)
    words = [kw["word"] for kw in keywords]
    assert "로그라이크" in words


def test_extract_keywords_empty():
    assert extract_keywords([], top_n=5) == []


def test_compute_review_stats():
    reviews = [
        {"voted_up": True, "review_text": "Great fun gameplay"},
        {"voted_up": True, "review_text": "Really fun and addictive"},
        {"voted_up": False, "review_text": "Too many bugs and crashes"},
    ]
    stats = compute_review_stats(reviews, top_n=5)
    assert stats["total_reviews"] == 3
    assert stats["positive_ratio"] == pytest.approx(2 / 3, abs=0.01)
    assert any(kw["word"] == "fun" for kw in stats["top_keywords_positive"])
    assert any(kw["word"] == "bugs" for kw in stats["top_keywords_negative"])


def test_compute_review_stats_empty():
    stats = compute_review_stats([], top_n=5)
    assert stats["total_reviews"] == 0
    assert stats["positive_ratio"] == 0.0
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd steam-analyzer && python -m pytest tests/test_review_stats.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: review_stats.py 구현**

```python
"""Review statistics: keyword extraction and summary computation."""

from __future__ import annotations

import re
from collections import Counter

ENGLISH_STOPWORDS = frozenset({
    "the", "be", "to", "of", "and", "a", "in", "that", "have", "i",
    "it", "for", "not", "on", "with", "he", "as", "you", "do", "at",
    "this", "but", "his", "by", "from", "they", "we", "say", "her",
    "she", "or", "an", "will", "my", "one", "all", "would", "there",
    "their", "what", "so", "up", "out", "if", "about", "who", "get",
    "which", "go", "me", "when", "make", "can", "like", "time", "no",
    "just", "him", "know", "take", "people", "into", "year", "your",
    "good", "some", "could", "them", "see", "other", "than", "then",
    "now", "look", "only", "come", "its", "over", "think", "also",
    "back", "after", "use", "two", "how", "our", "work", "first",
    "well", "way", "even", "new", "want", "because", "any", "these",
    "give", "day", "most", "us", "very", "was", "is", "are", "been",
    "has", "had", "did", "does", "being", "am", "were", "more",
    "much", "really", "game", "games", "play", "played", "playing",
})

KOREAN_STOPWORDS = frozenset({
    "이", "그", "저", "것", "수", "등", "들", "및", "에", "의",
    "는", "은", "를", "을", "가", "와", "과", "도", "로", "에서",
    "하다", "있다", "되다", "이다", "않다",
})

_WORD_RE = re.compile(r"[a-zA-Z\uAC00-\uD7A3]+")
_NUMBER_RE = re.compile(r"^\d+$")


def _tokenize(text: str) -> list[str]:
    """Split text into tokens, lowercase, filter short/number tokens."""
    tokens = _WORD_RE.findall(text.lower())
    return [
        t for t in tokens
        if len(t) > 2 and not _NUMBER_RE.match(t)
    ]


def extract_keywords(
    texts: list[str], top_n: int = 30
) -> list[dict[str, int]]:
    """Extract top keyword frequencies from review texts."""
    if not texts:
        return []
    counter: Counter[str] = Counter()
    stopwords = ENGLISH_STOPWORDS | KOREAN_STOPWORDS
    for text in texts:
        tokens = _tokenize(text)
        counter.update(t for t in tokens if t not in stopwords)
    return [{"word": word, "count": count} for word, count in counter.most_common(top_n)]


def compute_review_stats(
    reviews: list[dict], top_n: int = 30
) -> dict:
    """Compute aggregate review statistics."""
    total = len(reviews)
    if total == 0:
        return {
            "total_reviews": 0,
            "positive_ratio": 0.0,
            "top_keywords_positive": [],
            "top_keywords_negative": [],
        }

    positive_texts = [r["review_text"] for r in reviews if r.get("voted_up") and r.get("review_text")]
    negative_texts = [r["review_text"] for r in reviews if not r.get("voted_up") and r.get("review_text")]

    positive_count = sum(1 for r in reviews if r.get("voted_up"))

    return {
        "total_reviews": total,
        "positive_ratio": round(positive_count / total, 4),
        "top_keywords_positive": extract_keywords(positive_texts, top_n),
        "top_keywords_negative": extract_keywords(negative_texts, top_n),
    }
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd steam-analyzer && python -m pytest tests/test_review_stats.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add steam-analyzer/src/steam_analyzer/stats/ steam-analyzer/tests/test_review_stats.py
git commit -m "feat(analyzer): add review_stats with keyword extraction and stats computation"
```

---

### Task 5: search_reviews tool

**Files:**
- Create: `steam-analyzer/src/steam_analyzer/tools/search_reviews.py`
- Create: `steam-analyzer/tests/test_search_reviews.py`

- [ ] **Step 1: test_search_reviews.py — 실패하는 테스트 작성**

```python
import json
from steam_analyzer.tools.search_reviews import handle_search_reviews


def test_search_by_tag(seeded_db):
    result = handle_search_reviews(seeded_db, tag="Roguelike")
    assert result["games_count"] == 2
    assert result["total_reviews"] == 5
    assert len(result["sample_reviews"]) <= 20
    assert result["positive_ratio"] > 0


def test_search_by_appid(seeded_db):
    result = handle_search_reviews(seeded_db, appid=100)
    assert result["games_count"] == 1
    assert result["total_reviews"] == 3


def test_search_with_language(seeded_db):
    result = handle_search_reviews(seeded_db, appid=100, language="korean")
    assert result["total_reviews"] == 1


def test_search_with_sample_count(seeded_db):
    result = handle_search_reviews(seeded_db, tag="Roguelike", sample_count=2)
    assert len(result["sample_reviews"]) <= 2


def test_search_no_params(seeded_db):
    result = handle_search_reviews(seeded_db)
    assert result["error"] is True
    assert result["error_type"] == "no_data"


def test_search_no_data(seeded_db):
    result = handle_search_reviews(seeded_db, tag="NonexistentTag")
    assert result["games_count"] == 0
    assert result["total_reviews"] == 0


def test_search_sample_count_capped(seeded_db):
    result = handle_search_reviews(seeded_db, tag="Roguelike", sample_count=100)
    # sample_count capped to 50
    assert len(result["sample_reviews"]) <= 50
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd steam-analyzer && python -m pytest tests/test_search_reviews.py -v`
Expected: FAIL

- [ ] **Step 3: search_reviews.py 구현**

```python
"""search_reviews MCP tool handler."""

from __future__ import annotations

import json
import sqlite3

from steam_analyzer.db_queries import (
    get_games_by_tag,
    get_reviews_for_games,
    get_review_samples,
    get_available_tags,
)
from steam_analyzer.stats.review_stats import compute_review_stats
from steam_analyzer.error_logger import make_error_response

MAX_SAMPLE_COUNT = 50
DEFAULT_SAMPLE_COUNT = 20


def handle_search_reviews(
    conn: sqlite3.Connection,
    tag: str | None = None,
    appid: int | None = None,
    language: str | None = None,
    sample_count: int | None = None,
) -> dict:
    """Execute search_reviews and return stats + samples."""
    if not tag and appid is None:
        return make_error_response(
            conn,
            tool_name="search_reviews",
            params=json.dumps({"tag": tag, "appid": appid}),
            error_type="no_data",
            error_message="Either 'tag' or 'appid' parameter is required.",
            suggestion="Provide a tag (e.g., 'Roguelike') or appid (e.g., 730).",
        )

    sample_count = min(sample_count or DEFAULT_SAMPLE_COUNT, MAX_SAMPLE_COUNT)

    # Resolve appids
    if tag:
        games = get_games_by_tag(conn, tag)
        appids = [g["appid"] for g in games]
    else:
        appids = [appid]
        games = conn.execute(
            "SELECT appid, name FROM games WHERE appid = ?", (appid,)
        ).fetchall()
        games = [dict(g) for g in games]

    games_count = len(games)

    if games_count == 0:
        available = get_available_tags(conn)
        tag_names = [t["tag_name"] for t in available[:20]]
        return {
            "games_count": 0,
            "total_reviews": 0,
            "positive_ratio": 0.0,
            "top_keywords_positive": [],
            "top_keywords_negative": [],
            "sample_reviews": [],
            "available_tags": tag_names,
        }

    # Get all reviews for stats computation
    reviews = get_reviews_for_games(conn, appids, language)

    # Compute stats
    stats = compute_review_stats(
        [dict(r) for r in reviews], top_n=30
    )

    # Get sample reviews
    samples = get_review_samples(conn, appids, voted_up=True, limit=sample_count, language=language)
    samples += get_review_samples(conn, appids, voted_up=False, limit=sample_count, language=language)
    # Sort by score and limit total
    samples.sort(key=lambda x: x.get("weighted_vote_score", 0) or 0, reverse=True)
    samples = samples[:sample_count]

    return {
        "games_count": games_count,
        "total_reviews": stats["total_reviews"],
        "positive_ratio": stats["positive_ratio"],
        "top_keywords_positive": stats["top_keywords_positive"],
        "top_keywords_negative": stats["top_keywords_negative"],
        "sample_reviews": samples,
    }
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd steam-analyzer && python -m pytest tests/test_search_reviews.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add steam-analyzer/src/steam_analyzer/tools/search_reviews.py steam-analyzer/tests/test_search_reviews.py
git commit -m "feat(analyzer): add search_reviews tool with tag/appid search, stats, and samples"
```

---

### Task 6: analyze_design tool

**Files:**
- Create: `steam-analyzer/src/steam_analyzer/tools/analyze_design.py`
- Create: `steam-analyzer/tests/test_analyze_design.py`

- [ ] **Step 1: test_analyze_design.py — 실패하는 테스트 작성**

```python
import json
from pathlib import Path
from steam_analyzer.tools.analyze_design import handle_analyze_design


def test_analyze_with_text(seeded_db):
    result = handle_analyze_design(
        seeded_db,
        design_text="My roguelike game features permadeath and procedural levels.",
        tag="Roguelike",
    )
    assert "design_content" in result
    assert result["design_content"].startswith("My roguelike")
    assert result["competitor_summary"]["games_count"] == 2
    assert len(result["sample_reviews_positive"]) > 0


def test_analyze_with_file(seeded_db, tmp_path):
    design_file = tmp_path / "design.md"
    design_file.write_text("# Game Design\nA roguelike with crafting.", encoding="utf-8")
    result = handle_analyze_design(
        seeded_db,
        design_file=str(design_file),
        tag="Roguelike",
    )
    assert "# Game Design" in result["design_content"]


def test_analyze_with_appids(seeded_db):
    result = handle_analyze_design(
        seeded_db,
        design_text="My game design.",
        appids=[100, 200],
    )
    assert result["competitor_summary"]["games_count"] == 2


def test_analyze_missing_design(seeded_db):
    result = handle_analyze_design(seeded_db, tag="Roguelike")
    assert result["error"] is True
    assert result["error_type"] == "no_data"


def test_analyze_missing_competitors(seeded_db):
    result = handle_analyze_design(seeded_db, design_text="My design.")
    assert result["error"] is True


def test_analyze_file_not_found(seeded_db):
    result = handle_analyze_design(
        seeded_db,
        design_file="/nonexistent/path.md",
        tag="Roguelike",
    )
    assert result["error"] is True
    assert result["error_type"] == "file_error"


def test_analyze_file_too_large(seeded_db, tmp_path):
    big_file = tmp_path / "big.md"
    big_file.write_text("x" * (1024 * 1024 + 1), encoding="utf-8")
    result = handle_analyze_design(
        seeded_db,
        design_file=str(big_file),
        tag="Roguelike",
    )
    assert result["error"] is True
    assert "too large" in result["error_message"].lower()
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd steam-analyzer && python -m pytest tests/test_analyze_design.py -v`
Expected: FAIL

- [ ] **Step 3: analyze_design.py 구현**

```python
"""analyze_design MCP tool handler."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from steam_analyzer.db_queries import (
    get_games_by_tag,
    get_reviews_for_games,
    get_review_samples,
)
from steam_analyzer.stats.review_stats import compute_review_stats
from steam_analyzer.error_logger import make_error_response

MAX_DESIGN_FILE_SIZE = 1024 * 1024  # 1MB
DEFAULT_SAMPLE_COUNT = 10


def _read_design_file(file_path: str) -> tuple[str | None, dict | None]:
    """Read design file, return (content, error_dict)."""
    p = Path(file_path)
    if not p.exists():
        return None, {
            "error_type": "file_error",
            "error_message": f"Cannot read design file: {file_path}",
            "suggestion": f"File '{file_path}' not found. Check the path or use design_text parameter.",
        }
    if p.stat().st_size > MAX_DESIGN_FILE_SIZE:
        return None, {
            "error_type": "file_error",
            "error_message": f"Design file too large (max 1MB): {file_path}",
            "suggestion": "Reduce file size or paste key sections via design_text parameter.",
        }
    try:
        return p.read_text(encoding="utf-8"), None
    except Exception as e:
        return None, {
            "error_type": "file_error",
            "error_message": f"Cannot read design file: {e}",
            "suggestion": "Ensure file is text-based (md/txt). Try design_text parameter.",
        }


def handle_analyze_design(
    conn: sqlite3.Connection,
    design_file: str | None = None,
    design_text: str | None = None,
    tag: str | None = None,
    appids: list[int] | None = None,
) -> dict:
    """Execute analyze_design and return design + competitor context."""
    params = json.dumps({
        "design_file": design_file, "design_text": design_text,
        "tag": tag, "appids": appids,
    })

    # Validate design input
    if not design_file and not design_text:
        return make_error_response(
            conn, "analyze_design", params, "no_data",
            "Either 'design_file' or 'design_text' is required.",
            "Provide a file path or paste design text directly.",
        )

    # Validate competitor input
    if not tag and not appids:
        return make_error_response(
            conn, "analyze_design", params, "no_data",
            "Either 'tag' or 'appids' is required for competitor analysis.",
            "Provide a tag (e.g., 'Roguelike') or specific appids.",
        )

    # Read design content
    if design_file:
        content, err = _read_design_file(design_file)
        if err:
            return make_error_response(
                conn, "analyze_design", params,
                err["error_type"], err["error_message"], err["suggestion"],
            )
    else:
        content = design_text

    # Resolve competitor appids
    if tag:
        games = get_games_by_tag(conn, tag)
        competitor_appids = [g["appid"] for g in games]
    else:
        competitor_appids = appids
        games = []
        for aid in appids:
            row = conn.execute("SELECT appid, name FROM games WHERE appid = ?", (aid,)).fetchone()
            if row:
                games.append(dict(row))

    # Get reviews and compute stats
    reviews = get_reviews_for_games(conn, competitor_appids) if competitor_appids else []
    stats = compute_review_stats([dict(r) for r in reviews], top_n=30)

    # Get sample reviews (positive and negative separately)
    sample_pos = get_review_samples(
        conn, competitor_appids, voted_up=True, limit=DEFAULT_SAMPLE_COUNT
    ) if competitor_appids else []
    sample_neg = get_review_samples(
        conn, competitor_appids, voted_up=False, limit=DEFAULT_SAMPLE_COUNT
    ) if competitor_appids else []

    return {
        "design_content": content,
        "competitor_summary": {
            "games_count": len(games),
            "positive_ratio": stats["positive_ratio"],
            "top_keywords_positive": stats["top_keywords_positive"],
            "top_keywords_negative": stats["top_keywords_negative"],
        },
        "sample_reviews_positive": sample_pos,
        "sample_reviews_negative": sample_neg,
    }
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd steam-analyzer && python -m pytest tests/test_analyze_design.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add steam-analyzer/src/steam_analyzer/tools/analyze_design.py steam-analyzer/tests/test_analyze_design.py
git commit -m "feat(analyzer): add analyze_design tool with file/text input and competitor analysis"
```

---

### Task 7: get_analysis_logs tool

**Files:**
- Create: `steam-analyzer/src/steam_analyzer/tools/analysis_logs.py`

- [ ] **Step 1: analysis_logs.py 구현**

```python
"""get_analysis_logs MCP tool handler."""

from __future__ import annotations

import sqlite3

from steam_analyzer.error_logger import get_all_logs


def handle_get_analysis_logs(
    conn: sqlite3.Connection,
    unresolved_only: bool = True,
    limit: int = 10,
) -> dict:
    """Return analysis error logs for diagnosis."""
    logs = get_all_logs(conn, unresolved_only=unresolved_only, limit=limit)
    return {
        "logs": logs,
        "count": len(logs),
        "unresolved_only": unresolved_only,
    }
```

- [ ] **Step 2: Commit**

```bash
git add steam-analyzer/src/steam_analyzer/tools/analysis_logs.py
git commit -m "feat(analyzer): add get_analysis_logs diagnostic tool"
```

---

### Task 8: MCP 서버 (server.py) & .mcp.json

**Files:**
- Create: `steam-analyzer/src/steam_analyzer/server.py`
- Create: `.mcp.json`

- [ ] **Step 1: server.py 구현**

```python
"""Steam Analyzer MCP stdio server."""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from steam_analyzer.error_logger import init_analysis_logs
from steam_analyzer.tools.search_reviews import handle_search_reviews
from steam_analyzer.tools.analyze_design import handle_analyze_design
from steam_analyzer.tools.analysis_logs import handle_get_analysis_logs

DEFAULT_DB_PATH = "../data/steam.db"

server = Server("steam-analyzer")


def _get_db_path() -> str:
    return os.environ.get("STEAM_DB_PATH", DEFAULT_DB_PATH)


def _get_connection() -> sqlite3.Connection:
    db_path = _get_db_path()
    if not Path(db_path).exists():
        raise FileNotFoundError(f"Database not found at {db_path}")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    init_analysis_logs(conn)
    return conn


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="search_reviews",
            description="Search Steam reviews by tag or appid. Returns keyword stats and sample reviews.",
            inputSchema={
                "type": "object",
                "properties": {
                    "tag": {"type": "string", "description": "Tag name (e.g., 'Roguelike')"},
                    "appid": {"type": "integer", "description": "Steam App ID"},
                    "language": {"type": "string", "description": "Review language filter"},
                    "sample_count": {"type": "integer", "description": "Number of sample reviews (default: 20, max: 50)"},
                },
            },
        ),
        Tool(
            name="analyze_design",
            description="Analyze a game design document against competitor reviews. Returns design + competitor stats for feedback generation.",
            inputSchema={
                "type": "object",
                "properties": {
                    "design_file": {"type": "string", "description": "Path to design document"},
                    "design_text": {"type": "string", "description": "Design document text"},
                    "tag": {"type": "string", "description": "Competitor tag"},
                    "appids": {"type": "array", "items": {"type": "integer"}, "description": "Specific competitor app IDs"},
                },
            },
        ),
        Tool(
            name="get_analysis_logs",
            description="View error logs for diagnosing issues. Shows recent errors with suggestions.",
            inputSchema={
                "type": "object",
                "properties": {
                    "unresolved_only": {"type": "boolean", "description": "Only show unresolved errors (default: true)"},
                    "limit": {"type": "integer", "description": "Max results (default: 10)"},
                },
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        conn = _get_connection()
    except FileNotFoundError as e:
        result = {
            "error": True,
            "error_type": "db_not_found",
            "error_message": str(e),
            "suggestion": f"Run steam-crawler to collect data first. DB expected at: {_get_db_path()}",
        }
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]

    try:
        if name == "search_reviews":
            result = handle_search_reviews(conn, **arguments)
        elif name == "analyze_design":
            result = handle_analyze_design(conn, **arguments)
        elif name == "get_analysis_logs":
            result = handle_get_analysis_logs(conn, **arguments)
        else:
            result = {"error": True, "error_message": f"Unknown tool: {name}"}
    except Exception as e:
        from steam_analyzer.error_logger import make_error_response
        result = make_error_response(
            conn, name, json.dumps(arguments, ensure_ascii=False),
            "unknown", str(e),
            f"Unexpected error. Check analysis_logs for details.",
        )
    finally:
        conn.close()

    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, default=str))]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

- [ ] **Step 2: .mcp.json 생성 (프로젝트 루트)**

```json
{
  "mcpServers": {
    "steam-analyzer": {
      "command": "python",
      "args": ["-m", "steam_analyzer.server"],
      "cwd": "./steam-analyzer",
      "env": {
        "STEAM_DB_PATH": "../data/steam.db"
      }
    }
  }
}
```

- [ ] **Step 3: 서버 import 테스트**

Run: `cd steam-analyzer && python -c "from steam_analyzer.server import server; print('Server OK:', server.name)"`
Expected: `Server OK: steam-analyzer`

- [ ] **Step 4: Commit**

```bash
git add steam-analyzer/src/steam_analyzer/server.py .mcp.json
git commit -m "feat(analyzer): add MCP stdio server with tool routing and .mcp.json config"
```

---

### Task 9: 통합 테스트 & 최종 확인

- [ ] **Step 1: 전체 테스트 실행**

Run: `cd steam-analyzer && python -m pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 2: steam-crawler 테스트도 깨지지 않았는지 확인**

Run: `cd steam-crawler && python -m pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 3: MCP 서버 수동 실행 확인**

Run: `cd steam-analyzer && python -m steam_analyzer.server`
Expected: 서버가 시작되고 stdin 대기 (Ctrl+C로 종료)

- [ ] **Step 4: Commit (필요시 수정사항)**

```bash
git add -A
git commit -m "test(analyzer): verify all tests pass and server starts"
```
