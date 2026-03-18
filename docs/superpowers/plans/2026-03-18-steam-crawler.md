# Steam Crawler Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** SteamSpy + Steam Reviews API를 사용하여 태그/장르별 게임 데이터 및 리뷰를 수집하는 CLI 도구 구현

**Architecture:** 3단계 파이프라인(게임목록→리뷰요약→리뷰본문) + Adaptive Resilience(실패 로깅·학습·자동복구) + SQLite 변경 로그. 각 단계 독립 실행 가능, 중단/재개 지원.

**Tech Stack:** Python 3.12+, httpx, click, rich, SQLite, pytest

**Spec:** `PLAN.md` (루트)

---

## File Map

```
steam-game-analyzer/
├── .gitignore
├── CLAUDE.md
├── README.md
├── PLAN.md                              (existing)
├── REFERENCES.md                        (existing)
│
├── steam-crawler/
│   ├── pyproject.toml
│   ├── src/steam_crawler/
│   │   ├── __init__.py
│   │   ├── cli.py
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── game.py
│   │   │   └── review.py
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   ├── rate_limiter.py
│   │   │   ├── resilience.py
│   │   │   ├── steamspy.py
│   │   │   └── steam_reviews.py
│   │   ├── pipeline/
│   │   │   ├── __init__.py
│   │   │   ├── runner.py
│   │   │   ├── step1_collect.py
│   │   │   ├── step1b_enrich.py
│   │   │   ├── step2_scan.py
│   │   │   └── step3_crawl.py
│   │   └── db/
│   │       ├── __init__.py
│   │       ├── schema.py
│   │       ├── repository.py
│   │       └── changelog.py
│   └── tests/
│       ├── conftest.py
│       ├── test_schema.py
│       ├── test_models.py
│       ├── test_repository.py
│       ├── test_changelog.py
│       ├── test_rate_limiter.py
│       ├── test_resilience.py
│       ├── test_steamspy.py
│       ├── test_steam_reviews.py
│       ├── test_pipeline.py
│       ├── test_runner.py
│       └── test_cli.py
│
├── steam-analyzer/
│   ├── README.md
│   └── pyproject.toml
│
└── data/
    └── (steam.db — gitignored)
```

---

## Task 1: Project Scaffold

**Files:**
- Create: `.gitignore`
- Create: `README.md`
- Create: `CLAUDE.md`
- Create: `steam-crawler/pyproject.toml`
- Create: `steam-crawler/src/steam_crawler/__init__.py`
- Create: `steam-analyzer/README.md`
- Create: `steam-analyzer/pyproject.toml`

- [ ] **Step 1: Initialize git repo**

```bash
cd /c/WorkSpace/github.com/AccelixGames/steam-game-analyzer
git init
```

- [ ] **Step 2: Create .gitignore**

```gitignore
# Data
data/
*.db

# Python
__pycache__/
*.py[cod]
*$py.class
*.egg-info/
dist/
build/
.venv/
venv/

# IDE
.idea/
.vscode/
*.swp

# OS
.DS_Store
Thumbs.db
```

- [ ] **Step 3: Create README.md**

```markdown
# Steam Game Analyzer

Steam 게임 데이터 수집 및 분석 도구.

## 프로젝트 구조

- `steam-crawler/` — 데이터 수집기 (SteamSpy + Steam Reviews API)
- `steam-analyzer/` — 데이터 분석기 (추후 구현)
- `data/` — 공유 데이터 (SQLite DB, gitignored)

## 시작하기

```bash
cd steam-crawler
pip install -e ".[dev]"
steam-crawler collect --tag Roguelike --limit 5
```
```

- [ ] **Step 4: Create CLAUDE.md**

```markdown
# Steam Game Analyzer

## 프로젝트 개요
Steam 게임을 태그/장르별로 필터링하고, 리뷰 데이터를 수집하는 CLI 도구.

## 모노레포 구조
- `steam-crawler/` — Python CLI (click + rich + httpx)
- `steam-analyzer/` — placeholder (추후 구현)
- `data/` — SQLite DB (gitignored)

## 개발 환경
- Python 3.12+
- 테스트: `cd steam-crawler && pytest`
- 설치: `cd steam-crawler && pip install -e ".[dev]"`

## 핵심 규칙
- DB는 SQLite, ORM 없이 raw SQL 사용
- API 호출은 반드시 AdaptiveRateLimiter를 통해 수행
- 모든 실패는 failure_logs 테이블에 기록
- 리뷰 API는 `filter=recent`, `purchase_type=all`, `num_per_page=80` 고정
```

- [ ] **Step 5: Create steam-crawler/pyproject.toml**

```toml
[project]
name = "steam-crawler"
version = "0.1.0"
description = "Steam game data crawler using SteamSpy + Steam Reviews API"
requires-python = ">=3.12"

dependencies = [
    "httpx>=0.27",
    "click>=8.1",
    "rich>=13.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-httpx>=0.30",
]

[project.scripts]
steam-crawler = "steam_crawler.cli:main"

[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]
```

- [ ] **Step 6: Create steam-crawler/src/steam_crawler/__init__.py**

```python
__version__ = "0.1.0"
```

- [ ] **Step 7: Create steam-analyzer placeholder**

`steam-analyzer/README.md`:
```markdown
# Steam Analyzer

Steam 게임 데이터 분석기. 추후 구현 예정.

## 예상 기능
- 리뷰 키워드 빈도 분석
- 감성 분석 (영어 + 한국어)
- 경쟁작 비교 리포트
```

`steam-analyzer/pyproject.toml`:
```toml
[project]
name = "steam-analyzer"
version = "0.1.0"
description = "Steam game data analyzer (placeholder)"
requires-python = ">=3.12"
```

- [ ] **Step 8: Create directory structure + __init__.py files**

```bash
mkdir -p steam-crawler/src/steam_crawler/{models,api,pipeline,db}
mkdir -p steam-crawler/tests
touch steam-crawler/src/steam_crawler/models/__init__.py
touch steam-crawler/src/steam_crawler/api/__init__.py
touch steam-crawler/src/steam_crawler/pipeline/__init__.py
touch steam-crawler/src/steam_crawler/db/__init__.py
mkdir -p data
```

- [ ] **Step 9: Commit**

```bash
git add .gitignore README.md CLAUDE.md PLAN.md REFERENCES.md
git add steam-crawler/ steam-analyzer/ docs/
git commit -m "chore: initialize monorepo scaffold with steam-crawler and steam-analyzer placeholder"
```

---

## Task 2: DB Schema

**Files:**
- Create: `steam-crawler/src/steam_crawler/db/schema.py`
- Create: `steam-crawler/tests/conftest.py`
- Create: `steam-crawler/tests/test_schema.py`

- [ ] **Step 1: Write the failing test**

`steam-crawler/tests/conftest.py`:
```python
import sqlite3
import pytest
from pathlib import Path


@pytest.fixture
def db_path(tmp_path):
    """Provides a temporary database path."""
    return tmp_path / "test.db"


@pytest.fixture
def db_conn(db_path):
    """Provides a fresh database connection with schema initialized."""
    from steam_crawler.db.schema import init_db

    conn = init_db(str(db_path))
    yield conn
    conn.close()
```

`steam-crawler/tests/test_schema.py`:
```python
def test_init_db_creates_all_tables(db_conn):
    cursor = db_conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = {row[0] for row in cursor.fetchall()}
    expected = {
        "games",
        "reviews",
        "data_versions",
        "changelog",
        "rate_limit_stats",
        "failure_logs",
        "game_collection_status",
    }
    assert expected.issubset(tables)


def test_init_db_creates_indexes(db_conn):
    cursor = db_conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
    )
    indexes = {row[0] for row in cursor.fetchall()}
    assert "idx_reviews_appid" in indexes
    assert "idx_changelog_version" in indexes
    assert "idx_failure_logs_type" in indexes


def test_init_db_is_idempotent(db_path):
    from steam_crawler.db.schema import init_db

    conn1 = init_db(str(db_path))
    conn1.close()
    # Should not raise on second call
    conn2 = init_db(str(db_path))
    tables = conn2.execute(
        "SELECT count(*) FROM sqlite_master WHERE type='table'"
    ).fetchone()[0]
    conn2.close()
    assert tables >= 7
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd steam-crawler
pip install -e ".[dev]"
pytest tests/test_schema.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'steam_crawler.db.schema'`

- [ ] **Step 3: Write implementation**

`steam-crawler/src/steam_crawler/db/schema.py`:
```python
"""SQLite schema initialization for steam-crawler."""

import sqlite3
from pathlib import Path

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS games (
    appid          INTEGER PRIMARY KEY,
    name           TEXT NOT NULL,
    positive       INTEGER,
    negative       INTEGER,
    owners         TEXT,
    price          INTEGER,
    tags           TEXT,
    avg_playtime   INTEGER,
    score_rank     TEXT,
    steam_positive INTEGER,
    steam_negative INTEGER,
    review_score   TEXT,
    source_tag     TEXT,
    first_seen_ver INTEGER,
    updated_at     TIMESTAMP
);

CREATE TABLE IF NOT EXISTS reviews (
    recommendation_id TEXT PRIMARY KEY,
    appid            INTEGER REFERENCES games(appid),
    language         TEXT,
    review_text      TEXT,
    voted_up         BOOLEAN,
    playtime_forever INTEGER,
    playtime_at_review INTEGER,
    early_access     BOOLEAN,
    steam_purchase   BOOLEAN,
    received_for_free BOOLEAN,
    dev_response     TEXT,
    timestamp_created INTEGER,
    votes_up         INTEGER,
    votes_funny      INTEGER,
    weighted_vote_score REAL,
    comment_count    INTEGER,
    author_steamid   TEXT,
    author_num_reviews INTEGER,
    author_playtime_forever INTEGER,
    collected_ver    INTEGER,
    collected_at     TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_reviews_appid ON reviews(appid);
CREATE INDEX IF NOT EXISTS idx_reviews_language ON reviews(language);
CREATE INDEX IF NOT EXISTS idx_reviews_voted_up ON reviews(voted_up);

CREATE TABLE IF NOT EXISTS data_versions (
    version       INTEGER PRIMARY KEY AUTOINCREMENT,
    query_type    TEXT NOT NULL,
    query_value   TEXT,
    status        TEXT NOT NULL,
    games_total   INTEGER,
    reviews_total INTEGER,
    config        TEXT,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    note          TEXT
);

CREATE TABLE IF NOT EXISTS changelog (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    version       INTEGER REFERENCES data_versions(version),
    change_type   TEXT NOT NULL,
    appid         INTEGER,
    field_name    TEXT,
    old_value     TEXT,
    new_value     TEXT,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_changelog_version ON changelog(version);
CREATE INDEX IF NOT EXISTS idx_changelog_appid ON changelog(appid);

CREATE TABLE IF NOT EXISTS rate_limit_stats (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    api_name        TEXT NOT NULL,
    session_id      INTEGER REFERENCES data_versions(version),
    requests_made   INTEGER,
    errors_429      INTEGER DEFAULT 0,
    errors_5xx      INTEGER DEFAULT 0,
    avg_response_ms REAL,
    optimal_delay_ms REAL,
    recorded_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS failure_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      INTEGER REFERENCES data_versions(version),
    api_name        TEXT NOT NULL,
    appid           INTEGER,
    step            TEXT,
    failure_type    TEXT NOT NULL,
    http_status     INTEGER,
    error_message   TEXT,
    request_url     TEXT,
    response_body   TEXT,
    retry_count     INTEGER DEFAULT 0,
    resolved        BOOLEAN DEFAULT 0,
    resolution      TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_failure_logs_type ON failure_logs(failure_type);
CREATE INDEX IF NOT EXISTS idx_failure_logs_session ON failure_logs(session_id);
CREATE INDEX IF NOT EXISTS idx_failure_logs_unresolved ON failure_logs(resolved) WHERE resolved = 0;

CREATE TABLE IF NOT EXISTS game_collection_status (
    appid           INTEGER,
    version         INTEGER REFERENCES data_versions(version),
    steamspy_done   BOOLEAN DEFAULT 0,
    summary_done    BOOLEAN DEFAULT 0,
    reviews_done    BOOLEAN DEFAULT 0,
    last_cursor     TEXT,
    reviews_collected INTEGER DEFAULT 0,
    reviews_total     INTEGER,
    languages_done  TEXT,
    review_types_done TEXT,
    updated_at      TIMESTAMP,
    PRIMARY KEY (appid, version)
);
"""


def init_db(db_path: str) -> sqlite3.Connection:
    """Initialize the database with schema. Returns connection."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA_SQL)
    return conn
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_schema.py -v
```
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/steam_crawler/db/schema.py tests/conftest.py tests/test_schema.py
git commit -m "feat: add SQLite schema with 7 tables including failure_logs for adaptive resilience"
```

---

## Task 3: Data Models

**Files:**
- Create: `steam-crawler/src/steam_crawler/models/game.py`
- Create: `steam-crawler/src/steam_crawler/models/review.py`
- Create: `steam-crawler/tests/test_models.py`

- [ ] **Step 1: Write the failing test**

`steam-crawler/tests/test_models.py`:
```python
import json


def test_game_summary_from_steamspy_tag_response():
    """SteamSpy tag endpoint returns reduced fields (no tags)."""
    from steam_crawler.models.game import GameSummary

    raw = {
        "appid": 1091500,
        "name": "Cyberpunk 2077",
        "developer": "CD PROJEKT RED",
        "publisher": "CD PROJEKT RED",
        "score_rank": "",
        "positive": 500000,
        "negative": 100000,
        "userscore": 0,
        "owners": "10,000,000 .. 20,000,000",
        "average_forever": 3000,
        "average_2weeks": 500,
        "median_forever": 2000,
        "median_2weeks": 300,
        "price": "5999",
        "initialprice": "5999",
        "discount": "0",
        "ccu": 50000,
    }
    game = GameSummary.from_steamspy(raw, source_tag="tag:RPG")
    assert game.appid == 1091500
    assert game.name == "Cyberpunk 2077"
    assert game.positive == 500000
    assert game.price == 5999
    assert game.source_tag == "tag:RPG"
    assert game.tags is None  # tag endpoint doesn't include tags


def test_game_summary_from_steamspy_appdetails():
    """SteamSpy appdetails includes tags."""
    from steam_crawler.models.game import GameSummary

    raw = {
        "appid": 1091500,
        "name": "Cyberpunk 2077",
        "developer": "CD PROJEKT RED",
        "publisher": "CD PROJEKT RED",
        "score_rank": "90",
        "positive": 500000,
        "negative": 100000,
        "userscore": 0,
        "owners": "10,000,000 .. 20,000,000",
        "average_forever": 3000,
        "average_2weeks": 500,
        "median_forever": 2000,
        "median_2weeks": 300,
        "price": "5999",
        "initialprice": "5999",
        "discount": "0",
        "ccu": 50000,
        "tags": {"RPG": 5000, "Open World": 4000},
    }
    game = GameSummary.from_steamspy(raw, source_tag="tag:RPG")
    assert game.tags == {"RPG": 5000, "Open World": 4000}


def test_review_from_steam_api():
    from steam_crawler.models.review import Review

    raw = {
        "recommendationid": "12345",
        "language": "english",
        "review": "Great game!",
        "voted_up": True,
        "steam_purchase": True,
        "received_for_free": False,
        "written_during_early_access": False,
        "timestamp_created": 1700000000,
        "votes_up": 10,
        "votes_funny": 2,
        "weighted_vote_score": "0.95",
        "comment_count": 3,
        "developer_response": "Thanks!",
        "author": {
            "steamid": "76561198000000000",
            "num_reviews": 50,
            "playtime_forever": 6000,
            "playtime_at_review": 3000,
        },
    }
    review = Review.from_steam_api(raw, appid=1091500)
    assert review.recommendation_id == "12345"
    assert review.appid == 1091500
    assert review.review_text == "Great game!"
    assert review.voted_up is True
    assert review.weighted_vote_score == 0.95
    assert review.author_steamid == "76561198000000000"
    assert review.playtime_at_review == 3000
    assert review.dev_response == "Thanks!"


def test_review_summary_from_query_summary():
    from steam_crawler.models.review import ReviewSummary

    raw = {
        "num_reviews": 20,
        "review_score": 8,
        "review_score_desc": "Very Positive",
        "total_positive": 5000,
        "total_negative": 500,
        "total_reviews": 5500,
    }
    summary = ReviewSummary.from_query_summary(raw)
    assert summary.total_positive == 5000
    assert summary.total_negative == 500
    assert summary.review_score_desc == "Very Positive"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_models.py -v
```
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write GameSummary model**

`steam-crawler/src/steam_crawler/models/game.py`:
```python
"""Game data models."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class GameSummary:
    appid: int
    name: str
    positive: int | None = None
    negative: int | None = None
    owners: str | None = None
    price: int | None = None
    tags: dict[str, int] | None = None
    avg_playtime: int | None = None
    score_rank: str | None = None
    source_tag: str | None = None

    @classmethod
    def from_steamspy(cls, data: dict[str, Any], source_tag: str | None = None) -> GameSummary:
        tags_raw = data.get("tags")
        tags = tags_raw if isinstance(tags_raw, dict) else None

        price_raw = data.get("price")
        price = int(price_raw) if price_raw is not None else None

        return cls(
            appid=int(data["appid"]),
            name=data["name"],
            positive=data.get("positive"),
            negative=data.get("negative"),
            owners=data.get("owners"),
            price=price,
            tags=tags,
            avg_playtime=data.get("average_forever"),
            score_rank=data.get("score_rank") or None,
            source_tag=source_tag,
        )

    def tags_json(self) -> str | None:
        return json.dumps(self.tags) if self.tags else None
```

- [ ] **Step 4: Write Review and ReviewSummary models**

`steam-crawler/src/steam_crawler/models/review.py`:
```python
"""Review data models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Review:
    recommendation_id: str
    appid: int
    language: str | None = None
    review_text: str | None = None
    voted_up: bool | None = None
    playtime_forever: int | None = None
    playtime_at_review: int | None = None
    early_access: bool | None = None
    steam_purchase: bool | None = None
    received_for_free: bool | None = None
    dev_response: str | None = None
    timestamp_created: int | None = None
    votes_up: int | None = None
    votes_funny: int | None = None
    weighted_vote_score: float | None = None
    comment_count: int | None = None
    author_steamid: str | None = None
    author_num_reviews: int | None = None
    author_playtime_forever: int | None = None

    @classmethod
    def from_steam_api(cls, data: dict[str, Any], appid: int) -> Review:
        author = data.get("author", {})
        wvs = data.get("weighted_vote_score")

        return cls(
            recommendation_id=data["recommendationid"],
            appid=appid,
            language=data.get("language"),
            review_text=data.get("review"),
            voted_up=data.get("voted_up"),
            playtime_forever=author.get("playtime_forever"),
            playtime_at_review=author.get("playtime_at_review"),
            early_access=data.get("written_during_early_access"),
            steam_purchase=data.get("steam_purchase"),
            received_for_free=data.get("received_for_free"),
            dev_response=data.get("developer_response"),
            timestamp_created=data.get("timestamp_created"),
            votes_up=data.get("votes_up"),
            votes_funny=data.get("votes_funny"),
            weighted_vote_score=float(wvs) if wvs is not None else None,
            comment_count=data.get("comment_count"),
            author_steamid=author.get("steamid"),
            author_num_reviews=author.get("num_reviews"),
            author_playtime_forever=author.get("playtime_forever"),
        )


@dataclass
class ReviewSummary:
    total_positive: int
    total_negative: int
    total_reviews: int
    review_score: int | None = None
    review_score_desc: str | None = None

    @classmethod
    def from_query_summary(cls, data: dict[str, Any]) -> ReviewSummary:
        return cls(
            total_positive=data["total_positive"],
            total_negative=data["total_negative"],
            total_reviews=data["total_reviews"],
            review_score=data.get("review_score"),
            review_score_desc=data.get("review_score_desc"),
        )
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_models.py -v
```
Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
git add src/steam_crawler/models/ tests/test_models.py
git commit -m "feat: add GameSummary and Review dataclasses with SteamSpy/Steam API parsing"
```

---

## Task 4: Repository (DB CRUD)

**Files:**
- Create: `steam-crawler/src/steam_crawler/db/repository.py`
- Create: `steam-crawler/tests/test_repository.py`

- [ ] **Step 1: Write the failing test**

`steam-crawler/tests/test_repository.py`:
```python
from steam_crawler.models.game import GameSummary
from steam_crawler.models.review import Review


def test_upsert_game_insert(db_conn):
    from steam_crawler.db.repository import upsert_game

    game = GameSummary(appid=730, name="CS2", positive=100, negative=10, source_tag="tag:FPS")
    is_new, changes = upsert_game(db_conn, game, version=1)
    assert is_new is True
    assert changes == {}

    row = db_conn.execute("SELECT * FROM games WHERE appid=730").fetchone()
    assert row["name"] == "CS2"
    assert row["source_tag"] == "tag:FPS"


def test_upsert_game_update_detects_changes(db_conn):
    from steam_crawler.db.repository import upsert_game

    game1 = GameSummary(appid=730, name="CS2", positive=100, negative=10)
    upsert_game(db_conn, game1, version=1)

    game2 = GameSummary(appid=730, name="CS2", positive=200, negative=10)
    is_new, changes = upsert_game(db_conn, game2, version=2)
    assert is_new is False
    assert "positive" in changes
    assert changes["positive"] == ("100", "200")


def test_insert_reviews_batch(db_conn):
    from steam_crawler.db.repository import upsert_game, insert_reviews_batch

    upsert_game(db_conn, GameSummary(appid=730, name="CS2"), version=1)

    reviews = [
        Review(recommendation_id="r1", appid=730, review_text="Good", voted_up=True),
        Review(recommendation_id="r2", appid=730, review_text="Bad", voted_up=False),
    ]
    inserted = insert_reviews_batch(db_conn, reviews, version=1)
    assert inserted == 2

    row = db_conn.execute("SELECT collected_ver FROM reviews WHERE recommendation_id='r1'").fetchone()
    assert row["collected_ver"] == 1

    count = db_conn.execute("SELECT count(*) FROM reviews WHERE appid=730").fetchone()[0]
    assert count == 2


def test_insert_reviews_ignores_duplicates(db_conn):
    from steam_crawler.db.repository import upsert_game, insert_reviews_batch

    upsert_game(db_conn, GameSummary(appid=730, name="CS2"), version=1)

    reviews = [Review(recommendation_id="r1", appid=730, review_text="Good")]
    insert_reviews_batch(db_conn, reviews, version=1)
    inserted = insert_reviews_batch(db_conn, reviews, version=1)  # duplicate
    assert inserted == 0


def test_create_version(db_conn):
    from steam_crawler.db.repository import create_version

    ver = create_version(db_conn, query_type="tag", query_value="Roguelike", config="{}")
    assert ver == 1

    row = db_conn.execute("SELECT * FROM data_versions WHERE version=1").fetchone()
    assert row["query_type"] == "tag"
    assert row["status"] == "running"


def test_update_game_review_stats(db_conn):
    from steam_crawler.db.repository import upsert_game, update_game_review_stats

    upsert_game(db_conn, GameSummary(appid=730, name="CS2"), version=1)
    update_game_review_stats(db_conn, appid=730, steam_positive=5000, steam_negative=500, review_score="Very Positive")

    row = db_conn.execute("SELECT steam_positive, review_score FROM games WHERE appid=730").fetchone()
    assert row["steam_positive"] == 5000
    assert row["review_score"] == "Very Positive"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_repository.py -v
```
Expected: FAIL

- [ ] **Step 3: Write implementation**

`steam-crawler/src/steam_crawler/db/repository.py`:
```python
"""CRUD operations for games, reviews, and versions."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from steam_crawler.models.game import GameSummary
from steam_crawler.models.review import Review


def upsert_game(
    conn: sqlite3.Connection, game: GameSummary, version: int
) -> tuple[bool, dict[str, tuple[str, str]]]:
    """Insert or update a game. Returns (is_new, changed_fields).
    changed_fields maps field_name -> (old_value, new_value).
    """
    existing = conn.execute(
        "SELECT * FROM games WHERE appid = ?", (game.appid,)
    ).fetchone()

    now = datetime.now(timezone.utc).isoformat()

    if existing is None:
        conn.execute(
            """INSERT INTO games
            (appid, name, positive, negative, owners, price, tags,
             avg_playtime, score_rank, source_tag, first_seen_ver, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                game.appid, game.name, game.positive, game.negative,
                game.owners, game.price, game.tags_json(),
                game.avg_playtime, game.score_rank, game.source_tag,
                version, now,
            ),
        )
        conn.commit()
        return True, {}

    # Detect changes
    changes: dict[str, tuple[str, str]] = {}
    track_fields = ["positive", "negative", "owners", "price", "avg_playtime", "score_rank"]
    for field_name in track_fields:
        old_val = str(existing[field_name]) if existing[field_name] is not None else None
        new_val = str(getattr(game, field_name)) if getattr(game, field_name) is not None else None
        if new_val is not None and old_val != new_val:
            changes[field_name] = (old_val or "", new_val)

    update_fields = {
        "name": game.name,
        "positive": game.positive,
        "negative": game.negative,
        "owners": game.owners,
        "price": game.price,
        "avg_playtime": game.avg_playtime,
        "score_rank": game.score_rank,
        "updated_at": now,
    }
    if game.tags is not None:
        update_fields["tags"] = game.tags_json()

    set_clause = ", ".join(f"{k} = ?" for k in update_fields)
    values = list(update_fields.values()) + [game.appid]
    conn.execute(f"UPDATE games SET {set_clause} WHERE appid = ?", values)
    conn.commit()
    return False, changes


def insert_reviews_batch(
    conn: sqlite3.Connection, reviews: list[Review], version: int = 0
) -> int:
    """Insert reviews, ignoring duplicates. Returns count of newly inserted."""
    inserted = 0
    for review in reviews:
        try:
            conn.execute(
                """INSERT OR IGNORE INTO reviews
                (recommendation_id, appid, language, review_text, voted_up,
                 playtime_forever, playtime_at_review, early_access,
                 steam_purchase, received_for_free, dev_response,
                 timestamp_created, votes_up, votes_funny,
                 weighted_vote_score, comment_count,
                 author_steamid, author_num_reviews, author_playtime_forever,
                 collected_ver, collected_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    review.recommendation_id, review.appid, review.language,
                    review.review_text, review.voted_up,
                    review.playtime_forever, review.playtime_at_review,
                    review.early_access, review.steam_purchase,
                    review.received_for_free, review.dev_response,
                    review.timestamp_created, review.votes_up,
                    review.votes_funny, review.weighted_vote_score,
                    review.comment_count, review.author_steamid,
                    review.author_num_reviews, review.author_playtime_forever,
                    version, datetime.now(timezone.utc).isoformat(),
                ),
            )
            if conn.execute("SELECT changes()").fetchone()[0] > 0:
                inserted += 1
        except sqlite3.Error:
            continue
    conn.commit()
    return inserted


def create_version(
    conn: sqlite3.Connection,
    query_type: str,
    query_value: str | None = None,
    config: str | None = None,
    note: str | None = None,
) -> int:
    """Create a new data_versions entry. Returns version number."""
    cursor = conn.execute(
        """INSERT INTO data_versions (query_type, query_value, status, config, note)
        VALUES (?, ?, 'running', ?, ?)""",
        (query_type, query_value, config, note),
    )
    conn.commit()
    return cursor.lastrowid


def update_version_status(
    conn: sqlite3.Connection,
    version: int,
    status: str,
    games_total: int | None = None,
    reviews_total: int | None = None,
) -> None:
    conn.execute(
        """UPDATE data_versions
        SET status=?, games_total=?, reviews_total=?
        WHERE version=?""",
        (status, games_total, reviews_total, version),
    )
    conn.commit()


def update_game_review_stats(
    conn: sqlite3.Connection,
    appid: int,
    steam_positive: int,
    steam_negative: int,
    review_score: str | None,
) -> None:
    conn.execute(
        """UPDATE games
        SET steam_positive=?, steam_negative=?, review_score=?, updated_at=?
        WHERE appid=?""",
        (steam_positive, steam_negative, review_score,
         datetime.now(timezone.utc).isoformat(), appid),
    )
    conn.commit()


def get_games_by_version(conn: sqlite3.Connection, source_tag: str | None = None) -> list[dict]:
    """Get games, optionally filtered by source_tag, sorted by positive desc."""
    if source_tag:
        rows = conn.execute(
            "SELECT * FROM games WHERE source_tag = ? ORDER BY positive DESC",
            (source_tag,),
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM games ORDER BY positive DESC").fetchall()
    return [dict(r) for r in rows]


def update_collection_status(
    conn: sqlite3.Connection,
    appid: int,
    version: int,
    **kwargs,
) -> None:
    """Upsert game_collection_status."""
    now = datetime.now(timezone.utc).isoformat()
    existing = conn.execute(
        "SELECT 1 FROM game_collection_status WHERE appid=? AND version=?",
        (appid, version),
    ).fetchone()

    if existing is None:
        cols = ["appid", "version", "updated_at"] + list(kwargs.keys())
        vals = [appid, version, now] + list(kwargs.values())
        placeholders = ",".join("?" * len(cols))
        conn.execute(
            f"INSERT INTO game_collection_status ({','.join(cols)}) VALUES ({placeholders})",
            vals,
        )
    else:
        kwargs["updated_at"] = now
        set_clause = ", ".join(f"{k}=?" for k in kwargs)
        vals = list(kwargs.values()) + [appid, version]
        conn.execute(
            f"UPDATE game_collection_status SET {set_clause} WHERE appid=? AND version=?",
            vals,
        )
    conn.commit()
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_repository.py -v
```
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add src/steam_crawler/db/repository.py tests/test_repository.py
git commit -m "feat: add repository with game upsert, review batch insert, and version management"
```

---

## Task 5: Changelog

**Files:**
- Create: `steam-crawler/src/steam_crawler/db/changelog.py`
- Create: `steam-crawler/tests/test_changelog.py`

- [ ] **Step 1: Write the failing test**

`steam-crawler/tests/test_changelog.py`:
```python
def test_log_game_added(db_conn):
    from steam_crawler.db.changelog import log_game_added

    log_game_added(db_conn, version=1, appid=730)
    row = db_conn.execute("SELECT * FROM changelog WHERE appid=730").fetchone()
    assert row["change_type"] == "game_added"
    assert row["version"] == 1


def test_log_game_updated(db_conn):
    from steam_crawler.db.changelog import log_game_updated

    log_game_updated(db_conn, version=1, appid=730, field_name="positive",
                     old_value="100", new_value="200")
    row = db_conn.execute("SELECT * FROM changelog WHERE appid=730").fetchone()
    assert row["change_type"] == "game_updated"
    assert row["field_name"] == "positive"


def test_log_reviews_batch(db_conn):
    from steam_crawler.db.changelog import log_reviews_batch_added

    log_reviews_batch_added(db_conn, version=1, appid=730, count=50)
    row = db_conn.execute("SELECT * FROM changelog WHERE appid=730").fetchone()
    assert row["change_type"] == "reviews_batch_added"
    assert row["new_value"] == "50"


def test_get_diff_between_versions(db_conn):
    from steam_crawler.db.changelog import (
        log_game_added, log_game_updated, get_version_diff,
    )

    log_game_added(db_conn, version=1, appid=730)
    log_game_added(db_conn, version=1, appid=570)
    log_game_updated(db_conn, version=2, appid=730,
                     field_name="positive", old_value="100", new_value="200")

    diff = get_version_diff(db_conn, version=2)
    assert len(diff) == 1
    assert diff[0]["change_type"] == "game_updated"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_changelog.py -v
```

- [ ] **Step 3: Write implementation**

`steam-crawler/src/steam_crawler/db/changelog.py`:
```python
"""Changelog recording and querying."""

from __future__ import annotations

import sqlite3


def _log(
    conn: sqlite3.Connection,
    version: int,
    change_type: str,
    appid: int | None = None,
    field_name: str | None = None,
    old_value: str | None = None,
    new_value: str | None = None,
) -> None:
    conn.execute(
        """INSERT INTO changelog (version, change_type, appid, field_name, old_value, new_value)
        VALUES (?, ?, ?, ?, ?, ?)""",
        (version, change_type, appid, field_name, old_value, new_value),
    )
    conn.commit()


def log_game_added(conn: sqlite3.Connection, version: int, appid: int) -> None:
    _log(conn, version, "game_added", appid=appid)


def log_game_updated(
    conn: sqlite3.Connection,
    version: int,
    appid: int,
    field_name: str,
    old_value: str,
    new_value: str,
) -> None:
    _log(conn, version, "game_updated", appid=appid,
         field_name=field_name, old_value=old_value, new_value=new_value)


def log_reviews_count_changed(
    conn: sqlite3.Connection,
    version: int,
    appid: int,
    old_value: str,
    new_value: str,
) -> None:
    _log(conn, version, "reviews_count_changed", appid=appid,
         field_name="review_count", old_value=old_value, new_value=new_value)


def log_reviews_batch_added(
    conn: sqlite3.Connection,
    version: int,
    appid: int,
    count: int,
) -> None:
    _log(conn, version, "reviews_batch_added", appid=appid, new_value=str(count))


def get_version_diff(conn: sqlite3.Connection, version: int) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM changelog WHERE version = ? ORDER BY id",
        (version,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_version_summary(conn: sqlite3.Connection, version: int) -> dict:
    """Summary of changes for a version."""
    rows = conn.execute(
        """SELECT change_type, count(*) as cnt
        FROM changelog WHERE version = ?
        GROUP BY change_type""",
        (version,),
    ).fetchall()
    return {row["change_type"]: row["cnt"] for row in rows}
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_changelog.py -v
```
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/steam_crawler/db/changelog.py tests/test_changelog.py
git commit -m "feat: add changelog recording and version diff querying"
```

---

## Task 6: AdaptiveRateLimiter

**Files:**
- Create: `steam-crawler/src/steam_crawler/api/rate_limiter.py`
- Create: `steam-crawler/tests/test_rate_limiter.py`

- [ ] **Step 1: Write the failing test**

`steam-crawler/tests/test_rate_limiter.py`:
```python
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
    assert rl.current_delay_ms == 1500  # 1.5x


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

    rl = AdaptiveRateLimiter(api_name="steamspy", default_delay_ms=1000)
    rl.record_success(response_time_ms=200)
    save_rate_stats(db_conn, rl, session_id=1)

    loaded = load_optimal_delay(db_conn, "steamspy")
    assert loaded is not None
    assert loaded == rl.current_delay_ms
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_rate_limiter.py -v
```

- [ ] **Step 3: Write implementation**

`steam-crawler/src/steam_crawler/api/rate_limiter.py`:
```python
"""Adaptive rate limiter that learns optimal request delays."""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass, field


@dataclass
class AdaptiveRateLimiter:
    api_name: str
    default_delay_ms: float
    min_delay_ms: float = 300
    max_delay_ms: float = 60_000
    current_delay_ms: float = 0
    _requests_made: int = field(default=0, repr=False)
    _errors_429: int = field(default=0, repr=False)
    _errors_5xx: int = field(default=0, repr=False)
    _total_response_ms: float = field(default=0, repr=False)
    _last_request_time: float = field(default=0, repr=False)

    def __post_init__(self):
        if self.current_delay_ms == 0:
            self.current_delay_ms = self.default_delay_ms

    def wait(self) -> None:
        """Wait the appropriate delay before next request."""
        if self._last_request_time > 0:
            elapsed_ms = (time.monotonic() - self._last_request_time) * 1000
            remaining_ms = self.current_delay_ms - elapsed_ms
            if remaining_ms > 0:
                time.sleep(remaining_ms / 1000)
        self._last_request_time = time.monotonic()

    def record_success(self, response_time_ms: float) -> None:
        self._requests_made += 1
        self._total_response_ms += response_time_ms

        if response_time_ms < 500:
            # Fast response — decrease delay by 5%
            self.current_delay_ms = max(
                self.min_delay_ms,
                self.current_delay_ms * 0.95,
            )
        # Slow response (>2000ms) — hold current delay

    def record_rate_limited(self) -> None:
        self._requests_made += 1
        self._errors_429 += 1
        self.current_delay_ms = min(
            self.max_delay_ms,
            self.current_delay_ms * 1.5,
        )

    def record_server_error(self) -> None:
        self._requests_made += 1
        self._errors_5xx += 1

    def get_backoff_sequence(self) -> list[int]:
        """Exponential backoff delays for retries: 5s, 15s, 45s."""
        return [5000, 15000, 45000]

    def get_stats(self) -> dict:
        avg_ms = (
            self._total_response_ms / max(1, self._requests_made - self._errors_429 - self._errors_5xx)
        )
        return {
            "api_name": self.api_name,
            "requests_made": self._requests_made,
            "errors_429": self._errors_429,
            "errors_5xx": self._errors_5xx,
            "avg_response_ms": round(avg_ms, 2),
            "optimal_delay_ms": round(self.current_delay_ms, 2),
        }


def save_rate_stats(conn: sqlite3.Connection, limiter: AdaptiveRateLimiter, session_id: int) -> None:
    stats = limiter.get_stats()
    conn.execute(
        """INSERT INTO rate_limit_stats
        (api_name, session_id, requests_made, errors_429, errors_5xx, avg_response_ms, optimal_delay_ms)
        VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (stats["api_name"], session_id, stats["requests_made"],
         stats["errors_429"], stats["errors_5xx"],
         stats["avg_response_ms"], stats["optimal_delay_ms"]),
    )
    conn.commit()


def load_optimal_delay(conn: sqlite3.Connection, api_name: str) -> float | None:
    row = conn.execute(
        """SELECT optimal_delay_ms FROM rate_limit_stats
        WHERE api_name = ? ORDER BY recorded_at DESC LIMIT 1""",
        (api_name,),
    ).fetchone()
    return row["optimal_delay_ms"] if row else None
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_rate_limiter.py -v
```
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add src/steam_crawler/api/rate_limiter.py tests/test_rate_limiter.py
git commit -m "feat: add AdaptiveRateLimiter with delay tuning and DB persistence"
```

---

## Task 7: FailureTracker (Resilience)

**Files:**
- Create: `steam-crawler/src/steam_crawler/api/resilience.py`
- Create: `steam-crawler/tests/test_resilience.py`

- [ ] **Step 1: Write the failing test**

`steam-crawler/tests/test_resilience.py`:
```python
def test_classify_rate_limited():
    from steam_crawler.api.resilience import FailureTracker

    ft = FailureTracker()
    ftype = ft.classify(http_status=429)
    assert ftype == "rate_limited"


def test_classify_server_error():
    from steam_crawler.api.resilience import FailureTracker

    ft = FailureTracker()
    assert ft.classify(http_status=500) == "server_error"
    assert ft.classify(http_status=503) == "server_error"


def test_classify_timeout():
    from steam_crawler.api.resilience import FailureTracker

    ft = FailureTracker()
    ftype = ft.classify(http_status=None, error_type="timeout")
    assert ftype == "timeout"


def test_classify_parse_error():
    from steam_crawler.api.resilience import FailureTracker

    ft = FailureTracker()
    ftype = ft.classify(http_status=200, error_type="parse_error")
    assert ftype == "parse_error"


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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_resilience.py -v
```

- [ ] **Step 3: Write implementation**

`steam-crawler/src/steam_crawler/api/resilience.py`:
```python
"""Failure tracking, classification, and auto-recovery for adaptive resilience."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass
class FailureTracker:
    """Tracks, classifies, and helps recover from API failures."""

    def classify(
        self,
        http_status: int | None = None,
        error_type: str | None = None,
    ) -> str:
        """Classify a failure into a failure_type."""
        if error_type:
            valid = {"timeout", "parse_error", "connection_error", "cursor_invalid", "data_quality", "empty_response"}
            if error_type in valid:
                return error_type

        if http_status is not None:
            if http_status == 429:
                return "rate_limited"
            if 500 <= http_status < 600:
                return "server_error"

        return "unknown"

    def log_failure(
        self,
        conn: sqlite3.Connection,
        session_id: int,
        api_name: str,
        step: str,
        http_status: int | None = None,
        error_message: str | None = None,
        request_url: str | None = None,
        response_body: str | None = None,
        appid: int | None = None,
        retry_count: int = 0,
        error_type: str | None = None,
    ) -> int:
        """Log a failure and return its ID."""
        failure_type = self.classify(http_status, error_type)
        # Truncate response body
        if response_body and len(response_body) > 1000:
            response_body = response_body[:1000]

        cursor = conn.execute(
            """INSERT INTO failure_logs
            (session_id, api_name, appid, step, failure_type,
             http_status, error_message, request_url, response_body, retry_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (session_id, api_name, appid, step, failure_type,
             http_status, error_message, request_url, response_body, retry_count),
        )
        conn.commit()
        return cursor.lastrowid

    def resolve_failure(
        self, conn: sqlite3.Connection, failure_id: int, resolution: str
    ) -> None:
        conn.execute(
            "UPDATE failure_logs SET resolved=1, resolution=? WHERE id=?",
            (resolution, failure_id),
        )
        conn.commit()

    def get_unresolved(
        self, conn: sqlite3.Connection, session_id: int | None = None
    ) -> list[dict]:
        if session_id:
            rows = conn.execute(
                "SELECT * FROM failure_logs WHERE resolved=0 AND session_id=? ORDER BY id",
                (session_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM failure_logs WHERE resolved=0 ORDER BY id"
            ).fetchall()
        return [dict(r) for r in rows]

    def get_session_summary(self, conn: sqlite3.Connection, session_id: int) -> dict:
        total = conn.execute(
            "SELECT count(*) FROM failure_logs WHERE session_id=?", (session_id,)
        ).fetchone()[0]

        resolved = conn.execute(
            "SELECT count(*) FROM failure_logs WHERE session_id=? AND resolved=1",
            (session_id,),
        ).fetchone()[0]

        by_type_rows = conn.execute(
            """SELECT failure_type, count(*) as cnt
            FROM failure_logs WHERE session_id=?
            GROUP BY failure_type""",
            (session_id,),
        ).fetchall()
        by_type = {row["failure_type"]: row["cnt"] for row in by_type_rows}

        return {"total": total, "resolved": resolved, "by_type": by_type}

    def get_retry_targets(self, conn: sqlite3.Connection) -> list[dict]:
        """Get unresolved server_error/timeout failures as retry targets."""
        rows = conn.execute(
            """SELECT * FROM failure_logs
            WHERE resolved=0 AND failure_type IN ('server_error', 'timeout')
            ORDER BY id""",
        ).fetchall()
        return [dict(r) for r in rows]

    def check_schema_change_risk(self, conn: sqlite3.Connection) -> bool:
        """Returns True if parse_error count suggests API schema change."""
        count = conn.execute(
            "SELECT count(*) FROM failure_logs WHERE resolved=0 AND failure_type='parse_error'"
        ).fetchone()[0]
        return count >= 3
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_resilience.py -v
```
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add src/steam_crawler/api/resilience.py tests/test_resilience.py
git commit -m "feat: add FailureTracker with failure classification, logging, and session summaries"
```

---

## Task 8: BaseClient + SteamSpy Client

**Files:**
- Create: `steam-crawler/src/steam_crawler/api/base.py`
- Create: `steam-crawler/src/steam_crawler/api/steamspy.py`
- Create: `steam-crawler/tests/test_steamspy.py`

- [ ] **Step 1: Write the failing test**

`steam-crawler/tests/test_steamspy.py`:
```python
import json
import pytest
import httpx


MOCK_TAG_RESPONSE = {
    "730": {
        "appid": 730, "name": "Counter-Strike 2",
        "positive": 7000000, "negative": 1000000,
        "owners": "50,000,000 .. 100,000,000",
        "average_forever": 30000, "price": "0",
        "score_rank": "", "userscore": 0,
        "developer": "Valve", "publisher": "Valve",
    },
    "570": {
        "appid": 570, "name": "Dota 2",
        "positive": 1500000, "negative": 400000,
        "owners": "100,000,000 .. 200,000,000",
        "average_forever": 50000, "price": "0",
        "score_rank": "", "userscore": 0,
        "developer": "Valve", "publisher": "Valve",
    },
}

MOCK_APPDETAILS_RESPONSE = {
    "appid": 730, "name": "Counter-Strike 2",
    "positive": 7000000, "negative": 1000000,
    "owners": "50,000,000 .. 100,000,000",
    "average_forever": 30000, "price": "0",
    "tags": {"FPS": 90000, "Shooter": 65000, "Multiplayer": 55000},
}


def test_fetch_games_by_tag(httpx_mock):
    from steam_crawler.api.steamspy import SteamSpyClient

    httpx_mock.add_response(json=MOCK_TAG_RESPONSE)

    client = SteamSpyClient()
    games = client.fetch_by_tag("FPS")
    assert len(games) == 2
    assert games[0].positive >= games[1].positive  # sorted desc
    assert games[0].source_tag == "tag:FPS"


def test_fetch_games_by_tag_with_limit(httpx_mock):
    from steam_crawler.api.steamspy import SteamSpyClient

    httpx_mock.add_response(json=MOCK_TAG_RESPONSE)

    client = SteamSpyClient()
    games = client.fetch_by_tag("FPS", limit=1)
    assert len(games) == 1
    assert games[0].appid == 730  # highest positive


def test_fetch_app_details(httpx_mock):
    from steam_crawler.api.steamspy import SteamSpyClient

    httpx_mock.add_response(json=MOCK_APPDETAILS_RESPONSE)

    client = SteamSpyClient()
    game = client.fetch_app_details(730)
    assert game.tags == {"FPS": 90000, "Shooter": 65000, "Multiplayer": 55000}


def test_fetch_by_genre(httpx_mock):
    from steam_crawler.api.steamspy import SteamSpyClient

    httpx_mock.add_response(json=MOCK_TAG_RESPONSE)

    client = SteamSpyClient()
    games = client.fetch_by_genre("Racing")
    assert len(games) == 2
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_steamspy.py -v
```

- [ ] **Step 3: Write BaseClient**

`steam-crawler/src/steam_crawler/api/base.py`:
```python
"""Base HTTP client with rate limiting and failure tracking integration."""

from __future__ import annotations

import time
import httpx

from steam_crawler.api.rate_limiter import AdaptiveRateLimiter


class BaseClient:
    def __init__(
        self,
        rate_limiter: AdaptiveRateLimiter | None = None,
        timeout: float = 10.0,
    ):
        self._client = httpx.Client(timeout=timeout)
        self._rate_limiter = rate_limiter

    def get(self, url: str, params: dict | None = None) -> httpx.Response:
        """Make a GET request with rate limiting."""
        if self._rate_limiter:
            self._rate_limiter.wait()

        start = time.monotonic()
        response = self._client.get(url, params=params)
        elapsed_ms = (time.monotonic() - start) * 1000

        if self._rate_limiter:
            if response.status_code == 429:
                self._rate_limiter.record_rate_limited()
            elif response.status_code >= 500:
                self._rate_limiter.record_server_error()
            else:
                self._rate_limiter.record_success(elapsed_ms)

        return response

    def close(self) -> None:
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
```

- [ ] **Step 4: Write SteamSpy client**

`steam-crawler/src/steam_crawler/api/steamspy.py`:
```python
"""SteamSpy API client."""

from __future__ import annotations

from steam_crawler.api.base import BaseClient
from steam_crawler.api.rate_limiter import AdaptiveRateLimiter
from steam_crawler.models.game import GameSummary

STEAMSPY_BASE = "https://steamspy.com/api.php"


class SteamSpyClient:
    def __init__(self, rate_limiter: AdaptiveRateLimiter | None = None):
        self._client = BaseClient(
            rate_limiter=rate_limiter or AdaptiveRateLimiter(
                api_name="steamspy", default_delay_ms=1000,
            ),
        )

    def fetch_by_tag(
        self, tag: str, limit: int | None = None, source_prefix: str = "tag"
    ) -> list[GameSummary]:
        """Fetch games by SteamSpy tag. Returns sorted by positive desc."""
        response = self._client.get(
            STEAMSPY_BASE, params={"request": "tag", "tag": tag}
        )
        response.raise_for_status()
        return self._parse_game_list(response.json(), f"{source_prefix}:{tag}", limit)

    def fetch_by_genre(
        self, genre: str, limit: int | None = None
    ) -> list[GameSummary]:
        response = self._client.get(
            STEAMSPY_BASE, params={"request": "genre", "genre": genre}
        )
        response.raise_for_status()
        return self._parse_game_list(response.json(), f"genre:{genre}", limit)

    def fetch_top100(self, limit: int | None = None) -> list[GameSummary]:
        response = self._client.get(
            STEAMSPY_BASE, params={"request": "top100in2weeks"}
        )
        response.raise_for_status()
        return self._parse_game_list(response.json(), "top100", limit)

    def fetch_app_details(self, appid: int) -> GameSummary:
        """Fetch full details for a single app (includes tags)."""
        response = self._client.get(
            STEAMSPY_BASE, params={"request": "appdetails", "appid": str(appid)}
        )
        response.raise_for_status()
        data = response.json()
        return GameSummary.from_steamspy(data)

    def _parse_game_list(
        self, data: dict, source_tag: str, limit: int | None
    ) -> list[GameSummary]:
        games = [
            GameSummary.from_steamspy(v, source_tag=source_tag)
            for v in data.values()
            if isinstance(v, dict) and "appid" in v
        ]
        games.sort(key=lambda g: g.positive or 0, reverse=True)
        if limit:
            games = games[:limit]
        return games

    def close(self):
        self._client.close()
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_steamspy.py -v
```
Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
git add src/steam_crawler/api/base.py src/steam_crawler/api/steamspy.py tests/test_steamspy.py
git commit -m "feat: add BaseClient and SteamSpy API client with tag/genre/top100/appdetails support"
```

---

## Task 9: Steam Reviews Client

**Files:**
- Create: `steam-crawler/src/steam_crawler/api/steam_reviews.py`
- Create: `steam-crawler/tests/test_steam_reviews.py`

- [ ] **Step 1: Write the failing test**

`steam-crawler/tests/test_steam_reviews.py`:
```python
import pytest


MOCK_FIRST_PAGE = {
    "success": 1,
    "query_summary": {
        "num_reviews": 2,
        "review_score": 8,
        "review_score_desc": "Very Positive",
        "total_positive": 5000,
        "total_negative": 500,
        "total_reviews": 5500,
    },
    "reviews": [
        {
            "recommendationid": "r1",
            "language": "english",
            "review": "Amazing game!",
            "voted_up": True,
            "steam_purchase": True,
            "received_for_free": False,
            "written_during_early_access": False,
            "timestamp_created": 1700000000,
            "votes_up": 10,
            "votes_funny": 2,
            "weighted_vote_score": "0.95",
            "comment_count": 1,
            "author": {
                "steamid": "76561198000000001",
                "num_reviews": 30,
                "playtime_forever": 5000,
                "playtime_at_review": 2000,
            },
        },
        {
            "recommendationid": "r2",
            "language": "english",
            "review": "Not bad",
            "voted_up": True,
            "steam_purchase": True,
            "received_for_free": False,
            "written_during_early_access": False,
            "timestamp_created": 1700000001,
            "votes_up": 5,
            "votes_funny": 0,
            "weighted_vote_score": "0.80",
            "comment_count": 0,
            "author": {
                "steamid": "76561198000000002",
                "num_reviews": 10,
                "playtime_forever": 3000,
                "playtime_at_review": 1000,
            },
        },
    ],
    "cursor": "AoMFQFQ3YCAAAAAFP+6dmQAAAAB3gvzABg==",
}

MOCK_EMPTY_PAGE = {
    "success": 1,
    "reviews": [],
    "cursor": "AoMFQFQ3YCAAAAAFP+6dmQAAAAB3gvzABg==",
}


def test_fetch_review_summary(httpx_mock):
    from steam_crawler.api.steam_reviews import SteamReviewsClient

    httpx_mock.add_response(json=MOCK_FIRST_PAGE)

    client = SteamReviewsClient()
    summary = client.fetch_summary(appid=730)
    assert summary.total_positive == 5000
    assert summary.total_negative == 500
    assert summary.review_score_desc == "Very Positive"


def test_fetch_reviews_page(httpx_mock):
    from steam_crawler.api.steam_reviews import SteamReviewsClient

    httpx_mock.add_response(json=MOCK_FIRST_PAGE)

    client = SteamReviewsClient()
    reviews, next_cursor, has_more = client.fetch_reviews_page(appid=730, cursor="*")
    assert len(reviews) == 2
    assert reviews[0].recommendation_id == "r1"
    assert reviews[0].appid == 730
    assert next_cursor == "AoMFQFQ3YCAAAAAFP+6dmQAAAAB3gvzABg=="
    assert has_more is True


def test_fetch_reviews_page_empty_means_done(httpx_mock):
    from steam_crawler.api.steam_reviews import SteamReviewsClient

    httpx_mock.add_response(json=MOCK_EMPTY_PAGE)

    client = SteamReviewsClient()
    reviews, next_cursor, has_more = client.fetch_reviews_page(appid=730, cursor="somecursor")
    assert len(reviews) == 0
    assert has_more is False


def test_reviews_client_uses_correct_params(httpx_mock):
    from steam_crawler.api.steam_reviews import SteamReviewsClient

    httpx_mock.add_response(json=MOCK_FIRST_PAGE)

    client = SteamReviewsClient()
    client.fetch_reviews_page(appid=730, cursor="*", language="korean", review_type="positive")

    request = httpx_mock.get_request()
    assert "filter=recent" in str(request.url)
    assert "purchase_type=all" in str(request.url)
    assert "num_per_page=80" in str(request.url)
    assert "language=korean" in str(request.url)
    assert "review_type=positive" in str(request.url)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_steam_reviews.py -v
```

- [ ] **Step 3: Write implementation**

`steam-crawler/src/steam_crawler/api/steam_reviews.py`:
```python
"""Steam Store Reviews API client."""

from __future__ import annotations

from urllib.parse import quote

from steam_crawler.api.base import BaseClient
from steam_crawler.api.rate_limiter import AdaptiveRateLimiter
from steam_crawler.models.review import Review, ReviewSummary

REVIEWS_BASE = "https://store.steampowered.com/appreviews"


class SteamReviewsClient:
    def __init__(self, rate_limiter: AdaptiveRateLimiter | None = None):
        self._client = BaseClient(
            rate_limiter=rate_limiter or AdaptiveRateLimiter(
                api_name="steam_reviews", default_delay_ms=1500,
            ),
        )

    def fetch_summary(self, appid: int) -> ReviewSummary:
        """Fetch only query_summary (first request with cursor=*)."""
        response = self._client.get(
            f"{REVIEWS_BASE}/{appid}",
            params={
                "json": "1",
                "cursor": "*",
                "filter": "recent",
                "purchase_type": "all",
                "num_per_page": "0",
            },
        )
        response.raise_for_status()
        data = response.json()
        return ReviewSummary.from_query_summary(data["query_summary"])

    def fetch_reviews_page(
        self,
        appid: int,
        cursor: str = "*",
        language: str = "all",
        review_type: str = "all",
    ) -> tuple[list[Review], str, bool]:
        """Fetch a page of reviews.

        Returns (reviews, next_cursor, has_more).
        """
        response = self._client.get(
            f"{REVIEWS_BASE}/{appid}",
            params={
                "json": "1",
                "cursor": cursor,
                "filter": "recent",
                "purchase_type": "all",
                "num_per_page": "80",
                "language": language,
                "review_type": review_type,
            },
        )
        response.raise_for_status()
        data = response.json()

        reviews_data = data.get("reviews", [])
        reviews = [Review.from_steam_api(r, appid=appid) for r in reviews_data]
        next_cursor = data.get("cursor", "")
        has_more = len(reviews_data) > 0

        return reviews, next_cursor, has_more

    def close(self):
        self._client.close()
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_steam_reviews.py -v
```
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/steam_crawler/api/steam_reviews.py tests/test_steam_reviews.py
git commit -m "feat: add Steam Reviews API client with summary and cursor-based pagination"
```

---

## Task 10: Pipeline Steps (1, 1b, 2, 3)

**Files:**
- Create: `steam-crawler/src/steam_crawler/pipeline/step1_collect.py`
- Create: `steam-crawler/src/steam_crawler/pipeline/step1b_enrich.py`
- Create: `steam-crawler/src/steam_crawler/pipeline/step2_scan.py`
- Create: `steam-crawler/src/steam_crawler/pipeline/step3_crawl.py`
- Create: `steam-crawler/tests/test_pipeline.py`

- [ ] **Step 1: Write failing tests for Step 1 + Step 1b**

`steam-crawler/tests/test_pipeline.py`:
```python
import json
import pytest

# --- Mock data ---

MOCK_TAG_RESPONSE = {
    "730": {"appid": 730, "name": "CS2", "positive": 7000000, "negative": 1000000,
            "owners": "50,000,000 .. 100,000,000", "average_forever": 30000,
            "price": "0", "score_rank": "", "userscore": 0,
            "developer": "Valve", "publisher": "Valve"},
    "570": {"appid": 570, "name": "Dota 2", "positive": 1500000, "negative": 400000,
            "owners": "100,000,000 .. 200,000,000", "average_forever": 50000,
            "price": "0", "score_rank": "", "userscore": 0,
            "developer": "Valve", "publisher": "Valve"},
}

MOCK_APPDETAILS_730 = {
    "appid": 730, "name": "CS2", "positive": 7000000, "negative": 1000000,
    "owners": "50,000,000 .. 100,000,000", "average_forever": 30000,
    "price": "0", "score_rank": "", "userscore": 0,
    "tags": {"FPS": 90000, "Shooter": 65000},
}

MOCK_SUMMARY_RESPONSE = {
    "success": 1,
    "query_summary": {
        "num_reviews": 0, "review_score": 9,
        "review_score_desc": "Overwhelmingly Positive",
        "total_positive": 7100000, "total_negative": 1050000,
        "total_reviews": 8150000,
    },
    "reviews": [],
    "cursor": "*",
}

MOCK_REVIEWS_PAGE = {
    "success": 1,
    "reviews": [
        {
            "recommendationid": "r1", "language": "english",
            "review": "Great!", "voted_up": True, "steam_purchase": True,
            "received_for_free": False, "written_during_early_access": False,
            "timestamp_created": 1700000000, "votes_up": 10, "votes_funny": 0,
            "weighted_vote_score": "0.9", "comment_count": 0,
            "author": {"steamid": "123", "num_reviews": 5,
                       "playtime_forever": 1000, "playtime_at_review": 500},
        },
    ],
    "cursor": "nextcursor==",
}

MOCK_EMPTY_PAGE = {"success": 1, "reviews": [], "cursor": "nextcursor=="}


def test_step1_collect(httpx_mock, db_conn):
    from steam_crawler.pipeline.step1_collect import run_step1

    httpx_mock.add_response(json=MOCK_TAG_RESPONSE)

    result = run_step1(db_conn, query_type="tag", query_value="FPS", limit=2, version=1)
    assert result == 2

    games = db_conn.execute("SELECT * FROM games ORDER BY positive DESC").fetchall()
    assert len(games) == 2
    assert games[0]["appid"] == 730

    changelog = db_conn.execute("SELECT * FROM changelog WHERE change_type='game_added'").fetchall()
    assert len(changelog) == 2


def test_step1b_enrich(httpx_mock, db_conn):
    from steam_crawler.pipeline.step1_collect import run_step1
    from steam_crawler.pipeline.step1b_enrich import run_step1b

    httpx_mock.add_response(json=MOCK_TAG_RESPONSE)
    run_step1(db_conn, query_type="tag", query_value="FPS", limit=1, version=1)

    httpx_mock.add_response(json=MOCK_APPDETAILS_730)
    run_step1b(db_conn, version=1, source_tag="tag:FPS")

    row = db_conn.execute("SELECT tags FROM games WHERE appid=730").fetchone()
    tags = json.loads(row["tags"])
    assert "FPS" in tags


def test_step2_scan(httpx_mock, db_conn):
    from steam_crawler.pipeline.step1_collect import run_step1
    from steam_crawler.pipeline.step2_scan import run_step2

    httpx_mock.add_response(json=MOCK_TAG_RESPONSE)
    run_step1(db_conn, query_type="tag", query_value="FPS", limit=1, version=1)

    httpx_mock.add_response(json=MOCK_SUMMARY_RESPONSE)
    run_step2(db_conn, version=1, source_tag="tag:FPS")

    row = db_conn.execute("SELECT steam_positive, review_score FROM games WHERE appid=730").fetchone()
    assert row["steam_positive"] == 7100000
    assert row["review_score"] == "Overwhelmingly Positive"


def test_step3_crawl(httpx_mock, db_conn):
    from steam_crawler.pipeline.step1_collect import run_step1
    from steam_crawler.pipeline.step3_crawl import run_step3

    httpx_mock.add_response(json=MOCK_TAG_RESPONSE)
    run_step1(db_conn, query_type="tag", query_value="FPS", limit=1, version=1)

    httpx_mock.add_response(json=MOCK_REVIEWS_PAGE)
    httpx_mock.add_response(json=MOCK_EMPTY_PAGE)

    run_step3(db_conn, version=1, source_tag="tag:FPS", top_n=1, max_reviews=10)

    reviews = db_conn.execute("SELECT * FROM reviews WHERE appid=730").fetchall()
    assert len(reviews) == 1

    changelog = db_conn.execute(
        "SELECT * FROM changelog WHERE change_type='reviews_batch_added'"
    ).fetchall()
    assert len(changelog) == 1
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_pipeline.py -v
```

- [ ] **Step 3: Implement step1_collect.py**

`steam-crawler/src/steam_crawler/pipeline/step1_collect.py`:
```python
"""Step 1: Collect game list from SteamSpy by tag/genre/top100."""

from __future__ import annotations

import sqlite3

from rich.console import Console

from steam_crawler.api.steamspy import SteamSpyClient
from steam_crawler.db.changelog import log_game_added, log_game_updated
from steam_crawler.db.repository import upsert_game

console = Console()


def run_step1(
    conn: sqlite3.Connection,
    query_type: str,
    query_value: str | None,
    limit: int,
    version: int,
    steamspy_client: SteamSpyClient | None = None,
) -> int:
    """Collect games from SteamSpy. Returns number of games collected."""
    client = steamspy_client or SteamSpyClient()

    try:
        if query_type == "tag":
            games = client.fetch_by_tag(query_value, limit=limit)
        elif query_type == "genre":
            games = client.fetch_by_genre(query_value, limit=limit)
        elif query_type == "top100":
            games = client.fetch_top100(limit=limit)
        else:
            raise ValueError(f"Unknown query_type: {query_type}")

        for game in games:
            is_new, changes = upsert_game(conn, game, version=version)
            if is_new:
                log_game_added(conn, version=version, appid=game.appid)
            else:
                for field_name, (old_val, new_val) in changes.items():
                    log_game_updated(conn, version=version, appid=game.appid,
                                     field_name=field_name, old_value=old_val, new_value=new_val)

        console.print(f"[green]Step 1 complete:[/green] {len(games)} games collected")
        return len(games)
    finally:
        if steamspy_client is None:
            client.close()
```

- [ ] **Step 4: Implement step1b_enrich.py**

`steam-crawler/src/steam_crawler/pipeline/step1b_enrich.py`:
```python
"""Step 1.5: Enrich games with SteamSpy appdetails (tags field)."""

from __future__ import annotations

import json
import sqlite3

from rich.console import Console

from steam_crawler.api.steamspy import SteamSpyClient
from steam_crawler.db.repository import get_games_by_version, update_collection_status

console = Console()


def run_step1b(
    conn: sqlite3.Connection,
    version: int,
    source_tag: str | None = None,
    steamspy_client: SteamSpyClient | None = None,
) -> int:
    """Enrich games with tags from SteamSpy appdetails. Returns enriched count."""
    client = steamspy_client or SteamSpyClient()
    games = get_games_by_version(conn, source_tag=source_tag)
    enriched = 0

    try:
        for game_row in games:
            appid = game_row["appid"]
            detail = client.fetch_app_details(appid)
            if detail.tags:
                tags_json = json.dumps(detail.tags)
                conn.execute(
                    "UPDATE games SET tags = ? WHERE appid = ?",
                    (tags_json, appid),
                )
                conn.commit()
                enriched += 1

            update_collection_status(conn, appid=appid, version=version, steamspy_done=True)

        console.print(f"[green]Step 1.5 complete:[/green] {enriched}/{len(games)} games enriched with tags")
        return enriched
    finally:
        if steamspy_client is None:
            client.close()
```

- [ ] **Step 5: Implement step2_scan.py**

`steam-crawler/src/steam_crawler/pipeline/step2_scan.py`:
```python
"""Step 2: Scan review summaries from Steam Reviews API."""

from __future__ import annotations

import sqlite3

from rich.console import Console

from steam_crawler.api.resilience import FailureTracker
from steam_crawler.api.steam_reviews import SteamReviewsClient
from steam_crawler.db.changelog import log_reviews_count_changed
from steam_crawler.db.repository import (
    get_games_by_version,
    update_collection_status,
    update_game_review_stats,
)

console = Console()


def run_step2(
    conn: sqlite3.Connection,
    version: int,
    source_tag: str | None = None,
    reviews_client: SteamReviewsClient | None = None,
    failure_tracker: FailureTracker | None = None,
) -> int:
    """Scan review summaries for all games. Returns scanned count."""
    client = reviews_client or SteamReviewsClient()
    tracker = failure_tracker or FailureTracker()
    games = get_games_by_version(conn, source_tag=source_tag)
    scanned = 0

    try:
        for game_row in games:
            appid = game_row["appid"]
            summary = client.fetch_summary(appid)

            # Check SteamSpy vs Steam API data quality (10% deviation)
            spy_positive = game_row.get("positive")
            if spy_positive and spy_positive > 0:
                deviation = abs(summary.total_positive - spy_positive) / spy_positive
                if deviation > 0.1:
                    tracker.log_failure(
                        conn=conn, session_id=version, api_name="steam_reviews_summary",
                        appid=appid, step="step2", http_status=200,
                        error_type="data_quality",
                        error_message=(
                            f"SteamSpy positive={spy_positive} vs "
                            f"Steam API positive={summary.total_positive} "
                            f"(deviation={deviation:.1%})"
                        ),
                    )

            old_positive = game_row.get("steam_positive")
            update_game_review_stats(
                conn, appid=appid,
                steam_positive=summary.total_positive,
                steam_negative=summary.total_negative,
                review_score=summary.review_score_desc,
            )

            if old_positive is not None and old_positive != summary.total_positive:
                log_reviews_count_changed(
                    conn, version=version, appid=appid,
                    old_value=str(old_positive),
                    new_value=str(summary.total_positive),
                )

            update_collection_status(conn, appid=appid, version=version, summary_done=True)
            scanned += 1

        console.print(f"[green]Step 2 complete:[/green] {scanned} games scanned")
        return scanned
    finally:
        if reviews_client is None:
            client.close()
```

- [ ] **Step 6: Implement step3_crawl.py**

`steam-crawler/src/steam_crawler/pipeline/step3_crawl.py`:
```python
"""Step 3: Crawl review text from Steam Reviews API."""

from __future__ import annotations

import json
import sqlite3

from rich.console import Console

from steam_crawler.api.steam_reviews import SteamReviewsClient
from steam_crawler.db.changelog import log_reviews_batch_added
from steam_crawler.db.repository import (
    get_games_by_version,
    insert_reviews_batch,
    update_collection_status,
)

console = Console()


def run_step3(
    conn: sqlite3.Connection,
    version: int,
    source_tag: str | None = None,
    top_n: int = 10,
    max_reviews: int = 500,
    language: str = "all",
    review_type: str = "all",
    reviews_client: SteamReviewsClient | None = None,
) -> int:
    """Crawl review text for top N games. Returns total reviews collected."""
    client = reviews_client or SteamReviewsClient()
    games = get_games_by_version(conn, source_tag=source_tag)[:top_n]
    total_collected = 0

    try:
        for game_row in games:
            appid = game_row["appid"]
            name = game_row["name"]

            # Check if already done or has a resume cursor
            status = conn.execute(
                "SELECT * FROM game_collection_status WHERE appid=? AND version=?",
                (appid, version),
            ).fetchone()

            if status and status["reviews_done"]:
                continue

            cursor = (status["last_cursor"] if status and status["last_cursor"] else "*")
            collected_for_game = status["reviews_collected"] if status else 0
            has_more = True  # Initialize before loop

            console.print(f"[blue]Crawling reviews for {name} (appid={appid})...[/blue]")

            while collected_for_game < max_reviews and has_more:
                reviews, next_cursor, has_more = client.fetch_reviews_page(
                    appid=appid, cursor=cursor,
                    language=language, review_type=review_type,
                )

                if not reviews:
                    has_more = False
                    break

                inserted = insert_reviews_batch(conn, reviews, version=version)
                collected_for_game += inserted
                total_collected += inserted

                update_collection_status(
                    conn, appid=appid, version=version,
                    last_cursor=next_cursor,
                    reviews_collected=collected_for_game,
                )

                cursor = next_cursor

            # Mark done + record languages/review_types
            is_done = collected_for_game >= max_reviews or not has_more
            if is_done:
                update_collection_status(
                    conn, appid=appid, version=version,
                    reviews_done=True,
                    languages_done=json.dumps([language]),
                    review_types_done=json.dumps([review_type]),
                )

            if collected_for_game > 0:
                log_reviews_batch_added(conn, version=version, appid=appid, count=collected_for_game)

            console.print(f"  → {collected_for_game} reviews collected")

        console.print(f"[green]Step 3 complete:[/green] {total_collected} total reviews")
        return total_collected
    finally:
        if reviews_client is None:
            client.close()
```

- [ ] **Step 7: Run all pipeline tests**

```bash
pytest tests/test_pipeline.py -v
```
Expected: 4 passed

- [ ] **Step 8: Commit**

```bash
git add src/steam_crawler/pipeline/ tests/test_pipeline.py
git commit -m "feat: add pipeline steps 1, 1b, 2, 3 for game collection, enrichment, review scan, and crawl"
```

---

## Task 11: Pipeline Runner (Orchestrator)

**Files:**
- Create: `steam-crawler/src/steam_crawler/pipeline/runner.py`
- Create: `steam-crawler/tests/test_runner.py`

- [ ] **Step 1: Write the failing test**

`steam-crawler/tests/test_runner.py`:
```python
import json

MOCK_TAG_RESPONSE = {
    "730": {"appid": 730, "name": "CS2", "positive": 7000000, "negative": 1000000,
            "owners": "50M", "average_forever": 30000, "price": "0",
            "score_rank": "", "userscore": 0, "developer": "Valve", "publisher": "Valve"},
}

MOCK_APPDETAILS = {
    "appid": 730, "name": "CS2", "positive": 7000000, "negative": 1000000,
    "owners": "50M", "average_forever": 30000, "price": "0",
    "tags": {"FPS": 90000}, "score_rank": "", "userscore": 0,
}

MOCK_SUMMARY = {
    "success": 1,
    "query_summary": {"num_reviews": 0, "review_score": 9,
                       "review_score_desc": "Overwhelmingly Positive",
                       "total_positive": 7100000, "total_negative": 1050000,
                       "total_reviews": 8150000},
    "reviews": [], "cursor": "*",
}

MOCK_REVIEWS = {
    "success": 1,
    "reviews": [{"recommendationid": "r1", "language": "english",
                 "review": "Great!", "voted_up": True, "steam_purchase": True,
                 "received_for_free": False, "written_during_early_access": False,
                 "timestamp_created": 1700000000, "votes_up": 10, "votes_funny": 0,
                 "weighted_vote_score": "0.9", "comment_count": 0,
                 "author": {"steamid": "123", "num_reviews": 5,
                            "playtime_forever": 1000, "playtime_at_review": 500}}],
    "cursor": "next==",
}

MOCK_EMPTY = {"success": 1, "reviews": [], "cursor": "next=="}


def test_run_pipeline_full(httpx_mock, db_conn):
    from steam_crawler.pipeline.runner import run_pipeline

    # Step 1: tag query
    httpx_mock.add_response(json=MOCK_TAG_RESPONSE)
    # Step 1b: appdetails
    httpx_mock.add_response(json=MOCK_APPDETAILS)
    # Step 2: review summary
    httpx_mock.add_response(json=MOCK_SUMMARY)
    # Step 3: reviews page + empty page
    httpx_mock.add_response(json=MOCK_REVIEWS)
    httpx_mock.add_response(json=MOCK_EMPTY)

    run_pipeline(db_conn, query_type="tag", query_value="FPS",
                 limit=1, top_n=1, max_reviews=10)

    ver = db_conn.execute("SELECT * FROM data_versions WHERE version=1").fetchone()
    assert ver["status"] == "completed"

    # Rate stats saved
    stats = db_conn.execute("SELECT * FROM rate_limit_stats").fetchall()
    assert len(stats) >= 2  # steamspy + steam_reviews


def test_run_pipeline_uses_learned_delays(httpx_mock, db_conn):
    from steam_crawler.api.rate_limiter import AdaptiveRateLimiter, save_rate_stats
    from steam_crawler.db.repository import create_version

    # Simulate previous session with learned delay
    prev_ver = create_version(db_conn, "tag", "FPS")
    rl = AdaptiveRateLimiter(api_name="steamspy", default_delay_ms=800)
    save_rate_stats(db_conn, rl, session_id=prev_ver)

    from steam_crawler.pipeline.runner import run_pipeline

    httpx_mock.add_response(json=MOCK_TAG_RESPONSE)
    httpx_mock.add_response(json=MOCK_APPDETAILS)
    httpx_mock.add_response(json=MOCK_SUMMARY)
    httpx_mock.add_response(json=MOCK_REVIEWS)
    httpx_mock.add_response(json=MOCK_EMPTY)

    run_pipeline(db_conn, query_type="tag", query_value="FPS",
                 limit=1, top_n=1, max_reviews=10)

    # Should have used learned delay (800ms) not default (1000ms)
    stats = db_conn.execute(
        "SELECT optimal_delay_ms FROM rate_limit_stats WHERE api_name='steamspy' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert stats is not None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_runner.py -v
```

- [ ] **Step 3: Write implementation**

`steam-crawler/src/steam_crawler/pipeline/runner.py`:
```python
"""Pipeline orchestrator — runs steps in sequence with resilience."""

from __future__ import annotations

import json
import sqlite3

from rich.console import Console

from steam_crawler.api.rate_limiter import (
    AdaptiveRateLimiter, load_optimal_delay, save_rate_stats,
)
from steam_crawler.api.resilience import FailureTracker
from steam_crawler.api.steamspy import SteamSpyClient
from steam_crawler.api.steam_reviews import SteamReviewsClient
from steam_crawler.db.repository import create_version, update_version_status
from steam_crawler.pipeline.step1_collect import run_step1
from steam_crawler.pipeline.step1b_enrich import run_step1b
from steam_crawler.pipeline.step2_scan import run_step2
from steam_crawler.pipeline.step3_crawl import run_step3

console = Console()


def build_source_tag(query_type: str, query_value: str | None) -> str | None:
    if query_type == "top100":
        return "top100"
    return f"{query_type}:{query_value}" if query_value else None


def run_pipeline(
    conn: sqlite3.Connection,
    query_type: str,
    query_value: str | None = None,
    limit: int = 50,
    top_n: int = 10,
    max_reviews: int = 500,
    language: str = "all",
    review_type: str = "all",
    step: int | None = None,
    resume: bool = False,
    note: str | None = None,
) -> None:
    """Run the full collection pipeline (or a specific step)."""
    tracker = FailureTracker()

    # Check for unresolved failures from previous sessions
    unresolved = tracker.get_unresolved(conn)
    if unresolved:
        console.print(f"[yellow]Warning: {len(unresolved)} unresolved failures from previous sessions[/yellow]")
        if tracker.check_schema_change_risk(conn):
            console.print("[red]Warning: Multiple parse errors detected — API schema may have changed[/red]")

    # Build rate limiters with learned delays
    spy_delay = load_optimal_delay(conn, "steamspy") or 1000
    rev_delay = load_optimal_delay(conn, "steam_reviews") or 1500

    spy_limiter = AdaptiveRateLimiter(api_name="steamspy", default_delay_ms=spy_delay)
    rev_limiter = AdaptiveRateLimiter(api_name="steam_reviews", default_delay_ms=rev_delay)

    spy_client = SteamSpyClient(rate_limiter=spy_limiter)
    rev_client = SteamReviewsClient(rate_limiter=rev_limiter)

    # Resume: find last interrupted version instead of creating new one
    if resume:
        row = conn.execute(
            """SELECT version, config FROM data_versions
            WHERE status='interrupted' ORDER BY version DESC LIMIT 1"""
        ).fetchone()
        if row is None:
            console.print("[yellow]No interrupted version found. Starting fresh.[/yellow]")
            resume = False
        else:
            version = row["version"]
            cfg = json.loads(row["config"]) if row["config"] else {}
            query_type = cfg.get("query_type", query_type)
            query_value = cfg.get("query_value", query_value)
            source_tag = build_source_tag(query_type, query_value)
            conn.execute(
                "UPDATE data_versions SET status='running' WHERE version=?",
                (version,),
            )
            conn.commit()
            console.print(f"[bold]Resuming pipeline v{version}[/bold]")

    if not resume:
        config = json.dumps({
            "query_type": query_type, "query_value": query_value,
            "limit": limit, "top_n": top_n, "max_reviews": max_reviews,
            "language": language, "review_type": review_type,
        })
        version = create_version(conn, query_type, query_value, config=config, note=note)

    source_tag = build_source_tag(query_type, query_value)

    console.print(f"[bold]Pipeline v{version} started[/bold] ({query_type}:{query_value or ''})")

    games_total = 0
    reviews_total = 0

    try:
        if step is None or step == 1:
            games_total = run_step1(conn, query_type, query_value, limit, version,
                                    steamspy_client=spy_client)
            run_step1b(conn, version, source_tag=source_tag, steamspy_client=spy_client)

        if step is None or step == 2:
            run_step2(conn, version, source_tag=source_tag,
                      reviews_client=rev_client, failure_tracker=tracker)

        if step is None or step == 3:
            reviews_total = run_step3(
                conn, version, source_tag=source_tag, top_n=top_n,
                max_reviews=max_reviews, language=language,
                review_type=review_type, reviews_client=rev_client,
            )

        update_version_status(conn, version, "completed",
                              games_total=games_total, reviews_total=reviews_total)
        console.print(f"[bold green]Pipeline v{version} completed[/bold green]")

    except KeyboardInterrupt:
        update_version_status(conn, version, "interrupted",
                              games_total=games_total, reviews_total=reviews_total)
        console.print(f"\n[yellow]Pipeline v{version} interrupted. Use --resume to continue.[/yellow]")

    except Exception as e:
        update_version_status(conn, version, "interrupted",
                              games_total=games_total, reviews_total=reviews_total)
        console.print(f"[red]Pipeline v{version} failed: {e}[/red]")
        raise

    finally:
        # Save rate stats
        save_rate_stats(conn, spy_limiter, session_id=version)
        save_rate_stats(conn, rev_limiter, session_id=version)

        # Print failure summary
        summary = tracker.get_session_summary(conn, session_id=version)
        if summary["total"] > 0:
            console.print(f"\n[yellow]Failure summary: {summary['total']} total, "
                          f"{summary['resolved']} resolved[/yellow]")
            for ftype, count in summary["by_type"].items():
                console.print(f"  {ftype}: {count}")

        spy_client.close()
        rev_client.close()
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_runner.py -v
```
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add src/steam_crawler/pipeline/runner.py tests/test_runner.py
git commit -m "feat: add pipeline runner with adaptive resilience, learned delays, resume, and failure summaries"
```

---

## Task 12: CLI

**Files:**
- Create: `steam-crawler/src/steam_crawler/cli.py`
- Create: `steam-crawler/tests/test_cli.py`

- [ ] **Step 1: Write the failing test**

`steam-crawler/tests/test_cli.py`:
```python
from click.testing import CliRunner


def test_cli_help():
    from steam_crawler.cli import main

    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "collect" in result.output


def test_collect_help():
    from steam_crawler.cli import main

    runner = CliRunner()
    result = runner.invoke(main, ["collect", "--help"])
    assert result.exit_code == 0
    assert "--tag" in result.output
    assert "--genre" in result.output
    assert "--review-type" in result.output


def test_versions_empty(tmp_path):
    from steam_crawler.cli import main

    runner = CliRunner()
    result = runner.invoke(main, ["versions", "--db", str(tmp_path / "test.db")])
    assert result.exit_code == 0


def test_status_empty(tmp_path):
    from steam_crawler.cli import main

    runner = CliRunner()
    result = runner.invoke(main, ["status", "--db", str(tmp_path / "test.db")])
    assert result.exit_code == 0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_cli.py -v
```

- [ ] **Step 3: Write implementation**

`steam-crawler/src/steam_crawler/cli.py`:
```python
"""CLI entry point for steam-crawler."""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from steam_crawler.db.schema import init_db

console = Console()
DEFAULT_DB = str(Path.cwd().parent / "data" / "steam.db")


@click.group()
def main():
    """Steam game data crawler."""
    pass


@main.command()
@click.option("--tag", default=None, help='Tag filter (e.g., "Roguelike")')
@click.option("--genre", default=None, help='Genre filter (e.g., "Simulation")')
@click.option("--top100", is_flag=True, help="Top 100 in last 2 weeks")
@click.option("--limit", default=50, help="Max games to collect in Step 1")
@click.option("--top-n", default=10, help="Top N games for review crawling")
@click.option("--max-reviews", default=500, help="Max reviews per game")
@click.option("--language", default="all", help="Review language filter")
@click.option("--review-type", default="all", type=click.Choice(["all", "positive", "negative"]))
@click.option("--resume", is_flag=True, help="Resume interrupted collection")
@click.option("--step", default=None, type=click.IntRange(1, 3), help="Run specific step only")
@click.option("--note", default=None, help="Note for this version")
@click.option("--db", default=DEFAULT_DB, help="Database path")
def collect(tag, genre, top100, limit, top_n, max_reviews, language, review_type, resume, step, note, db):
    """Collect game data and reviews from Steam."""
    if not any([tag, genre, top100]):
        raise click.UsageError("Specify one of: --tag, --genre, --top100")

    if sum(bool(x) for x in [tag, genre, top100]) > 1:
        raise click.UsageError("Specify only one of: --tag, --genre, --top100")

    conn = init_db(db)

    query_type = "tag" if tag else ("genre" if genre else "top100")
    query_value = tag or genre

    from steam_crawler.pipeline.runner import run_pipeline
    try:
        run_pipeline(
            conn, query_type=query_type, query_value=query_value,
            limit=limit, top_n=top_n, max_reviews=max_reviews,
            language=language, review_type=review_type,
            step=step, resume=resume, note=note,
        )
    finally:
        conn.close()


@main.command()
@click.option("--db", default=DEFAULT_DB, help="Database path")
def versions(db):
    """List collection versions."""
    conn = init_db(db)
    rows = conn.execute(
        "SELECT * FROM data_versions ORDER BY version DESC"
    ).fetchall()

    if not rows:
        console.print("No versions found.")
        conn.close()
        return

    table = Table(title="Collection Versions")
    table.add_column("Ver", style="bold")
    table.add_column("Type")
    table.add_column("Value")
    table.add_column("Status")
    table.add_column("Games")
    table.add_column("Reviews")
    table.add_column("Created")
    table.add_column("Note")

    for r in rows:
        table.add_row(
            str(r["version"]), r["query_type"], r["query_value"] or "",
            r["status"], str(r["games_total"] or ""), str(r["reviews_total"] or ""),
            r["created_at"] or "", r["note"] or "",
        )

    console.print(table)
    conn.close()


@main.command()
@click.argument("v1", type=int)
@click.argument("v2", type=int)
@click.option("--db", default=DEFAULT_DB, help="Database path")
def diff(v1, v2, db):
    """Show changes between two versions."""
    from steam_crawler.db.changelog import get_version_diff, get_version_summary

    conn = init_db(db)

    for ver in [v1, v2]:
        summary = get_version_summary(conn, ver)
        console.print(f"\n[bold]Version {ver}:[/bold]")
        if not summary:
            console.print("  No changes recorded.")
        for change_type, count in summary.items():
            console.print(f"  {change_type}: {count}")

    conn.close()


@main.command()
@click.option("--db", default=DEFAULT_DB, help="Database path")
def status(db):
    """Show current collection status."""
    conn = init_db(db)

    # Latest version
    latest = conn.execute(
        "SELECT * FROM data_versions ORDER BY version DESC LIMIT 1"
    ).fetchone()

    if not latest:
        console.print("No collection data found.")
        conn.close()
        return

    console.print(f"[bold]Latest version: {latest['version']}[/bold] ({latest['status']})")
    console.print(f"  Type: {latest['query_type']}:{latest['query_value'] or ''}")

    # Game progress
    total_games = conn.execute("SELECT count(*) FROM games").fetchone()[0]
    total_reviews = conn.execute("SELECT count(*) FROM reviews").fetchone()[0]
    console.print(f"  Games: {total_games}, Reviews: {total_reviews}")

    # Failure summary
    from steam_crawler.api.resilience import FailureTracker
    tracker = FailureTracker()
    unresolved = tracker.get_unresolved(conn)
    if unresolved:
        console.print(f"  [yellow]Unresolved failures: {len(unresolved)}[/yellow]")

    conn.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_cli.py -v
```
Expected: 4 passed

- [ ] **Step 5: Run all tests**

```bash
pytest tests/ -v
```
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add src/steam_crawler/cli.py tests/test_cli.py
git commit -m "feat: add CLI with collect, versions, diff, and status commands"
```

---

## Task 13: Integration Smoke Test

- [ ] **Step 1: Install and verify CLI entry point**

```bash
cd steam-crawler
pip install -e ".[dev]"
steam-crawler --help
steam-crawler collect --help
```

- [ ] **Step 2: Run full test suite**

```bash
pytest tests/ -v --tb=short
```
Expected: All tests pass

- [ ] **Step 3: Final commit**

```bash
cd ..
git add -A
git commit -m "chore: finalize steam-crawler v0.1.0 with full test coverage"
```
