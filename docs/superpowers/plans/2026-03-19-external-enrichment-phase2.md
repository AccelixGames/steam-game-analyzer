# External Enrichment Phase 2: curl_cffi + 외부 평가 소스 통합

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** curl_cffi로 HTTP 클라이언트를 업그레이드하고, ProtonDB / HowLongToBeat / CheapShark / OpenCritic / PCGamingWiki 5개 외부 소스를 파이프라인에 통합하여 게임 기획 인사이트 분석을 강화한다.

**Architecture:** BaseClient의 httpx를 curl_cffi로 교체 (TLS 핑거프린트 위장). 각 외부 소스는 독립적인 step1g~step1k 파이프라인 스텝으로 구현. 단일 레코드 소스는 games 테이블 컬럼, 다중 레코드 소스(OpenCritic 개별 리뷰)는 external_reviews 테이블 사용.

**Tech Stack:** Python 3.12+, curl_cffi, SQLite, howlongtobeatpy, rich

---

## 선행 조건

- `feat/external-sources` 브랜치의 기존 작업(RAWG retention, Twitch, IGDB themes/keywords)이 완료되어야 함
- `.env`에 `RAPIDAPI_KEY` 추가 필요 (OpenCritic용, Phase 2에서)

## 참고 문서

- `docs/research-external-sources.md` — 전체 외부 소스 리서치 결과
- `C:\Users\splus\.claude\plans\clever-yawning-liskov.md` — 안티-디텍션 라이브러리 리서치

---

## File Structure

| Action | File | Responsibility |
|--------|------|---------------|
| Modify | `steam-crawler/pyproject.toml` | curl_cffi, howlongtobeatpy 의존성 추가 |
| Modify | `steam-crawler/src/steam_crawler/api/base.py` | httpx → curl_cffi 교체 |
| Modify | `steam-crawler/src/steam_crawler/db/schema.py` | 5개 소스용 컬럼 + external_reviews 테이블 |
| Modify | `steam-crawler/src/steam_crawler/db/repository.py` | 5개 소스 update 함수 + external_reviews CRUD |
| Create | `steam-crawler/src/steam_crawler/api/protondb.py` | ProtonDB JSON API 클라이언트 |
| Create | `steam-crawler/src/steam_crawler/api/hltb.py` | HowLongToBeat 래퍼 |
| Create | `steam-crawler/src/steam_crawler/api/cheapshark.py` | CheapShark API 클라이언트 |
| Create | `steam-crawler/src/steam_crawler/api/opencritic.py` | OpenCritic RapidAPI 클라이언트 |
| Create | `steam-crawler/src/steam_crawler/api/pcgamingwiki.py` | PCGamingWiki Cargo API 클라이언트 |
| Create | `steam-crawler/src/steam_crawler/pipeline/step1g_protondb.py` | ProtonDB enrichment step |
| Create | `steam-crawler/src/steam_crawler/pipeline/step1h_hltb.py` | HowLongToBeat enrichment step |
| Create | `steam-crawler/src/steam_crawler/pipeline/step1i_cheapshark.py` | CheapShark enrichment step |
| Create | `steam-crawler/src/steam_crawler/pipeline/step1j_opencritic.py` | OpenCritic enrichment step |
| Create | `steam-crawler/src/steam_crawler/pipeline/step1k_pcgamingwiki.py` | PCGamingWiki enrichment step |
| Modify | `steam-crawler/src/steam_crawler/pipeline/runner.py` | step1g~1k 통합 |
| Create | `steam-crawler/tests/test_protondb.py` | ProtonDB 테스트 |
| Create | `steam-crawler/tests/test_hltb.py` | HowLongToBeat 테스트 |
| Create | `steam-crawler/tests/test_cheapshark.py` | CheapShark 테스트 |
| Create | `steam-crawler/tests/test_opencritic.py` | OpenCritic 테스트 |
| Create | `steam-crawler/tests/test_pcgamingwiki.py` | PCGamingWiki 테스트 |

---

## Task 1: curl_cffi 마이그레이션 — httpx 교체

**Files:**
- Modify: `steam-crawler/pyproject.toml`
- Modify: `steam-crawler/src/steam_crawler/api/base.py`
- Modify: `steam-crawler/src/steam_crawler/api/igdb.py` (POST `content=` → `data=`)
- Modify: `steam-crawler/src/steam_crawler/api/twitch.py` (httpx.Client → Session)
- Modify: `steam-crawler/src/steam_crawler/pipeline/step1b_enrich.py` (httpx.ConnectError → ConnectionError)
- Modify: `steam-crawler/src/steam_crawler/pipeline/step1c_store.py` (httpx.ConnectError → ConnectionError)
- Modify: `steam-crawler/src/steam_crawler/pipeline/step2_scan.py` (httpx.ConnectError → ConnectionError)
- Modify: `steam-crawler/src/steam_crawler/pipeline/step3_crawl.py` (httpx.ConnectError → ConnectionError)

`★ Insight: curl_cffi는 httpx와 거의 동일한 requests-like API를 제공하면서 TLS/JA3 핑거프린트를 Chrome으로 위장합니다. impersonate="chrome" 한 줄로 봇 탐지 대부분을 우회할 수 있습니다.`

- [ ] **Step 1: pyproject.toml 의존성 업데이트**

```toml
dependencies = [
    "curl_cffi>=0.7",
    "click>=8.1",
    "rich>=13.0",
    "python-dotenv>=1.0",
    "howlongtobeatpy>=1.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-httpx>=0.30",
    "httpx>=0.27",
]
```

핵심 변경: `httpx`를 core에서 제거하고 dev에만 유지 (기존 테스트 호환). `curl_cffi`와 `howlongtobeatpy` 추가.

- [ ] **Step 2: base.py에서 httpx → curl_cffi 교체**

```python
"""Base HTTP client with rate limiting and TLS fingerprint impersonation."""

from __future__ import annotations

import time
from curl_cffi.requests import Session, Response

from steam_crawler.api.rate_limiter import AdaptiveRateLimiter


class BaseClient:
    def __init__(
        self,
        rate_limiter: AdaptiveRateLimiter | None = None,
        timeout: float = 10.0,
        impersonate: str = "chrome",
    ):
        self._client = Session(timeout=timeout, impersonate=impersonate)
        self._rate_limiter = rate_limiter

    def get(self, url: str, params: dict | None = None, headers: dict | None = None) -> Response:
        """Make a GET request with rate limiting and retry on 429/5xx."""
        if self._rate_limiter:
            self._rate_limiter.wait()

        start = time.monotonic()
        response = self._client.get(url, params=params, headers=headers)
        elapsed_ms = (time.monotonic() - start) * 1000

        if self._rate_limiter:
            if response.status_code == 429 or response.status_code >= 500:
                backoffs = self._rate_limiter.get_backoff_sequence()
                for delay_ms in backoffs:
                    if response.status_code == 429:
                        self._rate_limiter.record_rate_limited()
                    else:
                        self._rate_limiter.record_server_error()
                    time.sleep(delay_ms / 1000)
                    start = time.monotonic()
                    response = self._client.get(url, params=params, headers=headers)
                    elapsed_ms = (time.monotonic() - start) * 1000
                    if response.status_code < 400:
                        break
                if response.status_code == 429:
                    self._rate_limiter.record_rate_limited()
                elif response.status_code >= 500:
                    self._rate_limiter.record_server_error()
                else:
                    self._rate_limiter.record_success(elapsed_ms)
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

**변경 포인트:**
- `httpx.Client` → `curl_cffi.requests.Session`
- `impersonate="chrome"` 파라미터 추가 (TLS 핑거프린트 위장)
- `headers` 파라미터를 `get()`에 추가 (OpenCritic 등 커스텀 헤더 필요)
- API는 동일: `.get()`, `.status_code`, `.json()`, `.raise_for_status()`

- [ ] **Step 3: `import httpx`를 사용하는 모든 파일 수정**

**총 7개 파일** 에서 httpx 의존성 제거 필요:

**API 클라이언트 (2개 — 독자 httpx.Client 사용):**

`igdb.py` — POST 기반 API, **`content=` → `data=` 파라미터 변경 필수**:
```python
# Before (httpx)
import httpx
self._http = httpx.Client(timeout=timeout)
response = self._http.post(url, content=query, headers=headers)

# After (curl_cffi)
from curl_cffi.requests import Session
self._http = Session(timeout=timeout, impersonate="chrome")
response = self._http.post(url, data=query, headers=headers)  # content → data
```

`twitch.py` — GET 기반, 단순 교체:
```python
# Before → After: httpx.Client → Session, 나머지 동일
from curl_cffi.requests import Session
self._http = Session(timeout=timeout, impersonate="chrome")
```

**파이프라인 스텝 (4개 — `httpx.ConnectError` 사용):**

`step1b_enrich.py`, `step1c_store.py`, `step2_scan.py`, `step3_crawl.py` 모두 동일 패턴:
```python
# Before
import httpx
error_type="connection_error" if isinstance(e, httpx.ConnectError) else None,

# After — httpx import 제거, 표준 라이브러리 ConnectionError 사용
# (import httpx 줄 삭제)
error_type="connection_error" if isinstance(e, (ConnectionError, OSError)) else None,
```

`ConnectionError`와 `OSError`는 Python 표준 라이브러리이므로 import 불필요. curl_cffi의 네트워크 오류는 이 계층의 하위 클래스로 전파됨.

**자동 적용 (수정 불필요):**
- `steam_reviews.py`, `steam_store.py` — BaseClient를 래핑 (composition), httpx를 직접 import 하지 않음
- `rawg.py` — BaseClient 상속, 자동 적용
- `steamspy.py` — BaseClient 상속, 자동 적용

- [ ] **Step 4: 설치 및 기본 테스트**

```bash
cd steam-crawler && pip install -e ".[dev]"
```

```bash
cd steam-crawler && python -c "
from curl_cffi.requests import Session
s = Session(impersonate='chrome')
r = s.get('https://store.steampowered.com/api/appdetails?appids=730')
print(f'Status: {r.status_code}, TLS: OK')
s.close()
"
```

Expected: `Status: 200, TLS: OK`

- [ ] **Step 5: 기존 테스트 실행 (실패 예상 — pytest-httpx는 httpx 전용)**

```bash
cd steam-crawler && pytest --tb=short 2>&1 | head -30
```

pytest-httpx 기반 테스트는 curl_cffi와 호환되지 않으므로 실패할 수 있음. **Task 2에서 즉시 수정** (CI를 깨뜨린 상태로 두지 않기 위해).

- [ ] **Step 6: Commit**

```bash
git add steam-crawler/pyproject.toml steam-crawler/src/steam_crawler/api/base.py
git add steam-crawler/src/steam_crawler/api/steam_reviews.py
git add steam-crawler/src/steam_crawler/api/steam_store.py
git add steam-crawler/src/steam_crawler/api/igdb.py
git add steam-crawler/src/steam_crawler/api/twitch.py
git add steam-crawler/src/steam_crawler/api/rawg.py
git commit -m "feat: migrate httpx to curl_cffi for TLS fingerprint impersonation"
```

---

## Task 2: 기존 테스트 curl_cffi 호환성 업데이트

> **중요: Task 1 직후에 실행해야 CI를 깨뜨린 상태로 두지 않음.**

**Files:**
- Modify: 기존 pytest-httpx 의존 테스트 파일 8개

- [ ] **Step 1: pytest-httpx 의존 테스트 파일 식별**

```bash
cd steam-crawler && grep -rl "pytest_httpx\|httpx_mock\|pytest-httpx" tests/
```

영향받는 파일: `test_runner.py`, `test_step1d.py`, `test_igdb.py`, `test_step1e.py`, `test_rawg.py`, `test_pipeline.py`, `test_steam_reviews.py`, `test_steamspy.py`

- [ ] **Step 2: 각 테스트에서 httpx_mock → unittest.mock.patch 전환**

패턴:
```python
# Before (pytest-httpx)
def test_something(httpx_mock):
    httpx_mock.add_response(url="...", json={...})
    client = SomeClient()
    result = client.fetch(...)

# After (unittest.mock — BaseClient 래핑 클라이언트용)
def test_something():
    client = SomeClient()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {...}
    with patch.object(client._client, "get", return_value=mock_resp):
        result = client.fetch(...)

# After (unittest.mock — 독자 Session 사용 클라이언트용, e.g. IGDB)
def test_something():
    client = IGDBClient(client_id="test", client_secret="test")
    client._token = "test_token"
    client._token_expires_at = float("inf")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {...}
    with patch.object(client._http, "post", return_value=mock_resp):
        result = client.search_by_name("Hades")
```

- [ ] **Step 3: 전체 테스트 통과 확인**

```bash
cd steam-crawler && pytest -v
```

Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add steam-crawler/tests/
git commit -m "test: migrate tests from pytest-httpx to unittest.mock for curl_cffi compat"
```

---

## Task 3: DB 스키마 확장 — 5개 외부 소스 컬럼 + external_reviews 테이블

**Files:**
- Modify: `steam-crawler/src/steam_crawler/db/schema.py`

- [ ] **Step 1: SCHEMA_SQL에 external_reviews 테이블 추가**

`SCHEMA_SQL` 문자열 끝(crawl_locks 테이블 이후)에 추가:

```sql
CREATE TABLE IF NOT EXISTS external_reviews (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    appid         INTEGER REFERENCES games(appid),
    source        TEXT NOT NULL,
    source_id     TEXT,
    title         TEXT,
    score         REAL,
    author        TEXT,
    outlet        TEXT,
    url           TEXT,
    snippet       TEXT,
    view_count    INTEGER,
    like_ratio    REAL,
    published_at  TIMESTAMP,
    fetched_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(appid, source, source_id)
);

CREATE INDEX IF NOT EXISTS idx_ext_reviews_appid ON external_reviews(appid);
CREATE INDEX IF NOT EXISTS idx_ext_reviews_source ON external_reviews(source);
```

- [ ] **Step 2: _migrate()에 새 컬럼 추가**

기존 `_migrate()` 함수의 migrations 리스트에 추가:

```python
        # ProtonDB
        ("protondb_tier", "TEXT"),
        ("protondb_confidence", "TEXT"),
        ("protondb_trending_tier", "TEXT"),
        ("protondb_report_count", "INTEGER"),
        # HowLongToBeat
        ("hltb_id", "INTEGER"),
        ("hltb_main_story", "REAL"),
        ("hltb_main_extra", "REAL"),
        ("hltb_completionist", "REAL"),
        # CheapShark
        ("cheapshark_deal_rating", "REAL"),
        ("cheapshark_lowest_price", "REAL"),
        ("cheapshark_lowest_price_date", "TEXT"),
        # OpenCritic
        ("opencritic_id", "INTEGER"),
        ("opencritic_score", "REAL"),
        ("opencritic_pct_recommend", "REAL"),
        ("opencritic_tier", "TEXT"),
        ("opencritic_review_count", "INTEGER"),
        # PCGamingWiki
        ("pcgw_engine", "TEXT"),
        ("pcgw_has_ultrawide", "INTEGER"),
        ("pcgw_has_hdr", "INTEGER"),
        ("pcgw_has_controller", "INTEGER"),
        ("pcgw_graphics_api", "TEXT"),
```

- [ ] **Step 3: games 테이블에 인덱스 추가**

SCHEMA_SQL에 추가:

```sql
CREATE INDEX IF NOT EXISTS idx_games_opencritic_id ON games(opencritic_id);
CREATE INDEX IF NOT EXISTS idx_games_hltb_id ON games(hltb_id);
```

- [ ] **Step 4: 마이그레이션 확인**

```bash
cd steam-crawler && python -c "
from steam_crawler.db.schema import init_db
conn=init_db('../data/steam.db')
cols = [r[1] for r in conn.execute('PRAGMA table_info(games)').fetchall()]
new_cols = [c for c in cols if c.startswith(('protondb_','hltb_','cheapshark_','opencritic_','pcgw_'))]
print(f'New columns ({len(new_cols)}):', new_cols)
tables = [r[0] for r in conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()]
print('external_reviews exists:', 'external_reviews' in tables)
"
```

Expected: 17개 새 컬럼 + external_reviews 테이블 존재

- [ ] **Step 5: Commit**

```bash
git add steam-crawler/src/steam_crawler/db/schema.py
git commit -m "feat: add schema for ProtonDB/HLTB/CheapShark/OpenCritic/PCGamingWiki"
```

---

## Task 4: Repository — 5개 소스 update 함수 + external_reviews CRUD

**Files:**
- Modify: `steam-crawler/src/steam_crawler/db/repository.py`

- [ ] **Step 1: ProtonDB update 함수**

```python
def update_game_protondb(
    conn: sqlite3.Connection,
    appid: int,
    tier: str,
    confidence: str | None = None,
    trending_tier: str | None = None,
    report_count: int | None = None,
) -> None:
    """Update ProtonDB compatibility data."""
    conn.execute(
        """UPDATE games SET protondb_tier=?, protondb_confidence=?,
           protondb_trending_tier=?, protondb_report_count=?,
           updated_at=? WHERE appid=?""",
        (tier, confidence, trending_tier, report_count, _now(), appid),
    )
    conn.commit()
```

- [ ] **Step 2: HowLongToBeat update 함수**

```python
def update_game_hltb(
    conn: sqlite3.Connection,
    appid: int,
    hltb_id: int,
    main_story: float | None = None,
    main_extra: float | None = None,
    completionist: float | None = None,
) -> None:
    """Update HowLongToBeat completion times."""
    conn.execute(
        """UPDATE games SET hltb_id=?, hltb_main_story=?,
           hltb_main_extra=?, hltb_completionist=?,
           updated_at=? WHERE appid=?""",
        (hltb_id, main_story, main_extra, completionist, _now(), appid),
    )
    conn.commit()
```

- [ ] **Step 3: CheapShark update 함수**

```python
def update_game_cheapshark(
    conn: sqlite3.Connection,
    appid: int,
    deal_rating: float | None = None,
    lowest_price: float | None = None,
    lowest_price_date: str | None = None,
) -> None:
    """Update CheapShark deal/price data."""
    conn.execute(
        """UPDATE games SET cheapshark_deal_rating=?,
           cheapshark_lowest_price=?, cheapshark_lowest_price_date=?,
           updated_at=? WHERE appid=?""",
        (deal_rating, lowest_price, lowest_price_date, _now(), appid),
    )
    conn.commit()
```

- [ ] **Step 4: OpenCritic update 함수**

```python
def update_game_opencritic(
    conn: sqlite3.Connection,
    appid: int,
    opencritic_id: int,
    score: float | None = None,
    pct_recommend: float | None = None,
    tier: str | None = None,
    review_count: int | None = None,
) -> None:
    """Update OpenCritic aggregate scores."""
    conn.execute(
        """UPDATE games SET opencritic_id=?, opencritic_score=?,
           opencritic_pct_recommend=?, opencritic_tier=?,
           opencritic_review_count=?,
           updated_at=? WHERE appid=?""",
        (opencritic_id, score, pct_recommend, tier, review_count, _now(), appid),
    )
    conn.commit()
```

- [ ] **Step 5: PCGamingWiki update 함수**

```python
def update_game_pcgamingwiki(
    conn: sqlite3.Connection,
    appid: int,
    engine: str | None = None,
    has_ultrawide: bool | None = None,
    has_hdr: bool | None = None,
    has_controller: bool | None = None,
    graphics_api: str | None = None,
) -> None:
    """Update PCGamingWiki technical data."""
    conn.execute(
        """UPDATE games SET pcgw_engine=?, pcgw_has_ultrawide=?,
           pcgw_has_hdr=?, pcgw_has_controller=?, pcgw_graphics_api=?,
           updated_at=? WHERE appid=?""",
        (engine, int(has_ultrawide) if has_ultrawide is not None else None,
         int(has_hdr) if has_hdr is not None else None,
         int(has_controller) if has_controller is not None else None,
         graphics_api, _now(), appid),
    )
    conn.commit()
```

- [ ] **Step 6: external_reviews CRUD**

```python
def upsert_external_review(
    conn: sqlite3.Connection,
    appid: int,
    source: str,
    source_id: str,
    title: str | None = None,
    score: float | None = None,
    author: str | None = None,
    outlet: str | None = None,
    url: str | None = None,
    snippet: str | None = None,
    view_count: int | None = None,
    like_ratio: float | None = None,
    published_at: str | None = None,
) -> None:
    """Insert or update an external review."""
    conn.execute(
        """INSERT INTO external_reviews
           (appid, source, source_id, title, score, author, outlet, url,
            snippet, view_count, like_ratio, published_at, fetched_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(appid, source, source_id) DO UPDATE SET
               title=excluded.title, score=excluded.score,
               snippet=excluded.snippet, view_count=excluded.view_count,
               like_ratio=excluded.like_ratio, fetched_at=excluded.fetched_at""",
        (appid, source, source_id, title, score, author, outlet, url,
         snippet, view_count, like_ratio, published_at, _now()),
    )
    conn.commit()


def get_external_reviews(
    conn: sqlite3.Connection,
    appid: int,
    source: str | None = None,
) -> list[dict]:
    """Get external reviews for a game, optionally filtered by source."""
    if source:
        rows = conn.execute(
            "SELECT * FROM external_reviews WHERE appid=? AND source=? ORDER BY score DESC",
            (appid, source),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM external_reviews WHERE appid=? ORDER BY source, score DESC",
            (appid,),
        ).fetchall()
    return [dict(r) for r in rows]
```

- [ ] **Step 7: get_games_needing_enrichment에 새 소스 추가**

`id_col_map` 확장:

```python
    id_col_map = {
        "igdb": "igdb_id",
        "rawg": "rawg_id",
        "twitch": "twitch_game_id",
        "protondb": "protondb_tier",
        "hltb": "hltb_id",
        "cheapshark": "cheapshark_deal_rating",
        "opencritic": "opencritic_id",
        "pcgamingwiki": "pcgw_engine",
    }
```

주의: ProtonDB, CheapShark, PCGamingWiki는 id 컬럼이 아닌 데이터 컬럼으로 enrichment 여부를 판단. `IS NULL`이 "아직 안 함"을 의미.

- [ ] **Step 8: Commit**

```bash
git add steam-crawler/src/steam_crawler/db/repository.py
git commit -m "feat: add repository functions for 5 external sources + external_reviews"
```

---

## Task 5: ProtonDB API 클라이언트 + 파이프라인 스텝

**Files:**
- Create: `steam-crawler/src/steam_crawler/api/protondb.py`
- Create: `steam-crawler/src/steam_crawler/pipeline/step1g_protondb.py`

`★ Insight: ProtonDB는 가장 단순한 외부 소스입니다. appid로 직접 조회 가능하고 인증도 불필요합니다. 단, 공식 API가 아니므로 rate limit에 주의해야 합니다.`

- [ ] **Step 1: ProtonDB 클라이언트 작성**

```python
"""ProtonDB API client — Linux/Steam Deck compatibility data."""

from __future__ import annotations

from steam_crawler.api.base import BaseClient
from steam_crawler.api.rate_limiter import AdaptiveRateLimiter


class ProtonDBClient(BaseClient):
    """Fetches ProtonDB compatibility summaries by Steam appid."""

    BASE_URL = "https://www.protondb.com/api/v1/reports/summaries"

    def __init__(self, rate_limiter: AdaptiveRateLimiter | None = None):
        super().__init__(rate_limiter=rate_limiter, timeout=10.0)

    def fetch_summary(self, appid: int) -> dict | None:
        """Fetch ProtonDB summary for a Steam appid.

        Returns dict with keys: tier, confidence, trendingTier, total, score, bestReportedTier
        Returns None if game not found (404).
        """
        url = f"{self.BASE_URL}/{appid}.json"
        response = self.get(url)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()
```

- [ ] **Step 2: step1g_protondb.py 작성**

```python
"""Step 1g: Enrich games with ProtonDB compatibility data."""
from __future__ import annotations

import sqlite3

from rich.console import Console

from steam_crawler.api.protondb import ProtonDBClient
from steam_crawler.api.rate_limiter import AdaptiveRateLimiter
from steam_crawler.api.resilience import FailureTracker
from steam_crawler.db.repository import (
    get_games_needing_enrichment,
    update_game_protondb,
)

console = Console()


def run_step1g(
    conn: sqlite3.Connection,
    version: int,
    source_tag: str | None = None,
    protondb_client: ProtonDBClient | None = None,
    failure_tracker: FailureTracker | None = None,
    lock_owner: str | None = None,
) -> int:
    """Enrich games with ProtonDB compatibility tiers. Returns count enriched."""
    client = protondb_client or ProtonDBClient(
        rate_limiter=AdaptiveRateLimiter(api_name="protondb", default_delay_ms=1500)
    )
    tracker = failure_tracker or FailureTracker()
    games = get_games_needing_enrichment(
        conn, source="protondb", source_tag=source_tag, lock_owner=lock_owner
    )
    enriched = 0

    if not games:
        console.print("[dim]Step 1g: No games need ProtonDB enrichment[/dim]")
        return 0

    console.print(f"[bold]Step 1g:[/bold] Enriching {len(games)} games from ProtonDB")

    try:
        for game_row in games:
            appid = game_row["appid"]
            name = game_row["name"]
            try:
                data = client.fetch_summary(appid)
                if data is None:
                    # Mark as checked but no data (use "unknown" as sentinel)
                    update_game_protondb(conn, appid=appid, tier="unknown")
                    continue

                update_game_protondb(
                    conn,
                    appid=appid,
                    tier=data.get("tier", "unknown"),
                    confidence=data.get("confidence"),
                    trending_tier=data.get("trendingTier"),
                    report_count=data.get("total"),
                )
                enriched += 1

            except Exception as e:
                tracker.log_failure(
                    conn=conn, session_id=version, api_name="protondb",
                    appid=appid, step="step1g", error_message=str(e),
                )
                console.print(f"  [red]ProtonDB error for {name} ({appid}): {e}[/red]")
                continue

        console.print(
            f"[green]Step 1g complete:[/green] {enriched}/{len(games)} games enriched from ProtonDB"
        )
        return enriched
    finally:
        if protondb_client is None:
            client.close()
```

- [ ] **Step 3: Commit**

```bash
git add steam-crawler/src/steam_crawler/api/protondb.py
git add steam-crawler/src/steam_crawler/pipeline/step1g_protondb.py
git commit -m "feat: add ProtonDB compatibility enrichment (step1g)"
```

---

## Task 6: HowLongToBeat 래퍼 + 파이프라인 스텝

**Files:**
- Create: `steam-crawler/src/steam_crawler/api/hltb.py`
- Create: `steam-crawler/src/steam_crawler/pipeline/step1h_hltb.py`

`★ Insight: HowLongToBeat는 게임 길이 데이터의 사실상 유일한 소스입니다. main_story vs completionist 비율로 "콘텐츠 깊이 vs 패딩"을 측정할 수 있고, Steam 리뷰의 "hours played"와 교차 검증이 가능합니다.`

- [ ] **Step 1: HLTB 래퍼 작성**

```python
"""HowLongToBeat wrapper — game completion time data."""

from __future__ import annotations

import asyncio
import time

from howlongtobeatpy import HowLongToBeat

from steam_crawler.api.rate_limiter import AdaptiveRateLimiter


def _run_async(coro):
    """Run an async coroutine from sync code, handling existing event loops."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        # Already in an async context — create a new loop in a thread
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


class HLTBClient:
    """Wrapper around howlongtobeatpy with rate limiting."""

    def __init__(self, rate_limiter: AdaptiveRateLimiter | None = None):
        self._rate_limiter = rate_limiter

    def search(self, game_name: str) -> dict | None:
        """Search HowLongToBeat by game name. Returns best match or None.

        Returns dict with keys: game_id, main_story, main_extra, completionist
        Times are in hours (float).
        """
        if self._rate_limiter:
            self._rate_limiter.wait()

        start = time.monotonic()
        results = _run_async(HowLongToBeat().async_search(game_name))
        elapsed_ms = (time.monotonic() - start) * 1000

        if self._rate_limiter:
            self._rate_limiter.record_success(elapsed_ms)

        if not results:
            return None

        best = max(results, key=lambda r: r.similarity)
        if best.similarity < 0.4:
            return None

        return {
            "game_id": best.game_id,
            "main_story": best.main_story if best.main_story > 0 else None,
            "main_extra": best.main_extra if best.main_extra > 0 else None,
            "completionist": best.completionist if best.completionist > 0 else None,
        }

    def close(self) -> None:
        pass  # No persistent connection

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
```

- [ ] **Step 2: step1h_hltb.py 작성**

```python
"""Step 1h: Enrich games with HowLongToBeat completion times."""
from __future__ import annotations

import sqlite3

from rich.console import Console

from steam_crawler.api.hltb import HLTBClient
from steam_crawler.api.rate_limiter import AdaptiveRateLimiter
from steam_crawler.api.resilience import FailureTracker
from steam_crawler.db.repository import (
    get_games_needing_enrichment,
    update_game_hltb,
)

console = Console()


def run_step1h(
    conn: sqlite3.Connection,
    version: int,
    source_tag: str | None = None,
    hltb_client: HLTBClient | None = None,
    failure_tracker: FailureTracker | None = None,
    lock_owner: str | None = None,
) -> int:
    """Enrich games with HowLongToBeat completion times. Returns count enriched."""
    client = hltb_client or HLTBClient(
        rate_limiter=AdaptiveRateLimiter(api_name="hltb", default_delay_ms=2000)
    )
    tracker = failure_tracker or FailureTracker()
    games = get_games_needing_enrichment(
        conn, source="hltb", source_tag=source_tag, lock_owner=lock_owner
    )
    enriched = 0

    if not games:
        console.print("[dim]Step 1h: No games need HLTB enrichment[/dim]")
        return 0

    console.print(f"[bold]Step 1h:[/bold] Enriching {len(games)} games from HowLongToBeat")

    try:
        for game_row in games:
            appid = game_row["appid"]
            name = game_row["name"]
            try:
                data = client.search(name)
                if data is None:
                    # Mark as unmatchable
                    update_game_hltb(conn, appid=appid, hltb_id=-1)
                    tracker.log_failure(
                        conn=conn, session_id=version, api_name="hltb",
                        appid=appid, step="step1h",
                        error_type="match_failed",
                        error_message=f"No HLTB match for '{name}'",
                    )
                    continue

                update_game_hltb(
                    conn,
                    appid=appid,
                    hltb_id=data["game_id"],
                    main_story=data["main_story"],
                    main_extra=data["main_extra"],
                    completionist=data["completionist"],
                )
                enriched += 1

            except Exception as e:
                tracker.log_failure(
                    conn=conn, session_id=version, api_name="hltb",
                    appid=appid, step="step1h", error_message=str(e),
                )
                console.print(f"  [red]HLTB error for {name} ({appid}): {e}[/red]")
                continue

        console.print(
            f"[green]Step 1h complete:[/green] {enriched}/{len(games)} games enriched from HLTB"
        )
        return enriched
    finally:
        if hltb_client is None:
            client.close()
```

- [ ] **Step 3: Commit**

```bash
git add steam-crawler/src/steam_crawler/api/hltb.py
git add steam-crawler/src/steam_crawler/pipeline/step1h_hltb.py
git commit -m "feat: add HowLongToBeat completion time enrichment (step1h)"
```

---

## Task 7: CheapShark API 클라이언트 + 파이프라인 스텝

**Files:**
- Create: `steam-crawler/src/steam_crawler/api/cheapshark.py`
- Create: `steam-crawler/src/steam_crawler/pipeline/step1i_cheapshark.py`

- [ ] **Step 1: CheapShark 클라이언트 작성**

```python
"""CheapShark API client — game deal/price data."""

from __future__ import annotations

from steam_crawler.api.base import BaseClient
from steam_crawler.api.rate_limiter import AdaptiveRateLimiter


class CheapSharkClient(BaseClient):
    """Fetches game deal ratings and price history from CheapShark."""

    BASE_URL = "https://www.cheapshark.com/api/1.0"

    def __init__(self, rate_limiter: AdaptiveRateLimiter | None = None):
        super().__init__(rate_limiter=rate_limiter, timeout=10.0)

    def search_by_steam_appid(self, appid: int) -> dict | None:
        """Search CheapShark by Steam appid via deals endpoint.

        CheapShark uses Steam store IDs. We search deals filtered by steamAppID.
        Returns best deal info or None.
        """
        response = self.get(
            f"{self.BASE_URL}/deals",
            params={"steamAppID": appid, "sortBy": "Rating", "pageSize": 1},
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        deals = response.json()
        if not deals:
            return None
        return deals[0]

    def fetch_game_details(self, cheapshark_game_id: str) -> dict | None:
        """Fetch full game details including price history.

        Returns dict with cheapestPriceEver, deals list.
        """
        response = self.get(
            f"{self.BASE_URL}/games",
            params={"id": cheapshark_game_id},
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()
```

- [ ] **Step 2: step1i_cheapshark.py 작성**

```python
"""Step 1i: Enrich games with CheapShark deal/price data."""
from __future__ import annotations

import sqlite3

from rich.console import Console

from steam_crawler.api.cheapshark import CheapSharkClient
from steam_crawler.api.rate_limiter import AdaptiveRateLimiter
from steam_crawler.api.resilience import FailureTracker
from steam_crawler.db.repository import (
    get_games_needing_enrichment,
    update_game_cheapshark,
)

console = Console()


def run_step1i(
    conn: sqlite3.Connection,
    version: int,
    source_tag: str | None = None,
    cheapshark_client: CheapSharkClient | None = None,
    failure_tracker: FailureTracker | None = None,
    lock_owner: str | None = None,
) -> int:
    """Enrich games with CheapShark deal ratings and price data. Returns count enriched."""
    client = cheapshark_client or CheapSharkClient(
        rate_limiter=AdaptiveRateLimiter(api_name="cheapshark", default_delay_ms=1000)
    )
    tracker = failure_tracker or FailureTracker()
    games = get_games_needing_enrichment(
        conn, source="cheapshark", source_tag=source_tag, lock_owner=lock_owner
    )
    enriched = 0

    if not games:
        console.print("[dim]Step 1i: No games need CheapShark enrichment[/dim]")
        return 0

    console.print(f"[bold]Step 1i:[/bold] Enriching {len(games)} games from CheapShark")

    try:
        for game_row in games:
            appid = game_row["appid"]
            name = game_row["name"]
            try:
                deal = client.search_by_steam_appid(appid)
                if deal is None:
                    # Mark as checked — store 0.0 as sentinel for "no deals found"
                    update_game_cheapshark(conn, appid=appid, deal_rating=0.0)
                    continue

                deal_rating = float(deal.get("dealRating", 0))
                lowest_price = None
                lowest_price_date = None

                # Try to get full game details for price history
                game_id = deal.get("gameID")
                if game_id:
                    details = client.fetch_game_details(game_id)
                    if details and "cheapestPriceEver" in details:
                        cpe = details["cheapestPriceEver"]
                        lowest_price = float(cpe.get("price", 0))
                        lowest_price_date = cpe.get("date")

                update_game_cheapshark(
                    conn,
                    appid=appid,
                    deal_rating=deal_rating,
                    lowest_price=lowest_price,
                    lowest_price_date=lowest_price_date,
                )
                enriched += 1

            except Exception as e:
                tracker.log_failure(
                    conn=conn, session_id=version, api_name="cheapshark",
                    appid=appid, step="step1i", error_message=str(e),
                )
                console.print(f"  [red]CheapShark error for {name} ({appid}): {e}[/red]")
                continue

        console.print(
            f"[green]Step 1i complete:[/green] {enriched}/{len(games)} games enriched from CheapShark"
        )
        return enriched
    finally:
        if cheapshark_client is None:
            client.close()
```

- [ ] **Step 3: Commit**

```bash
git add steam-crawler/src/steam_crawler/api/cheapshark.py
git add steam-crawler/src/steam_crawler/pipeline/step1i_cheapshark.py
git commit -m "feat: add CheapShark deal/price enrichment (step1i)"
```

---

## Task 8: OpenCritic API 클라이언트 + 파이프라인 스텝

**Files:**
- Create: `steam-crawler/src/steam_crawler/api/opencritic.py`
- Create: `steam-crawler/src/steam_crawler/pipeline/step1j_opencritic.py`

`★ Insight: OpenCritic은 Metacritic의 대안으로, 공식 API를 RapidAPI를 통해 제공합니다. 무료 티어는 일 25회 제한이지만, 배치 enrichment에 충분합니다. topCriticScore + percentRecommended + tier 3가지 지표로 전문가 평가를 삼각 검증할 수 있습니다.`

- [ ] **Step 1: OpenCritic 클라이언트 작성**

```python
"""OpenCritic API client via RapidAPI — critic review aggregation."""

from __future__ import annotations

from steam_crawler.api.base import BaseClient
from steam_crawler.api.rate_limiter import AdaptiveRateLimiter
from steam_crawler.api.matching import GameMatcher


class OpenCriticClient(BaseClient):
    """Fetches critic scores and reviews from OpenCritic via RapidAPI."""

    BASE_URL = "https://opencritic-api.p.rapidapi.com"

    def __init__(
        self,
        rapidapi_key: str,
        rate_limiter: AdaptiveRateLimiter | None = None,
    ):
        super().__init__(rate_limiter=rate_limiter, timeout=15.0)
        self._headers = {
            "X-RapidAPI-Key": rapidapi_key,
            "X-RapidAPI-Host": "opencritic-api.p.rapidapi.com",
        }

    def search(self, game_name: str) -> dict | None:
        """Search OpenCritic for a game. Returns best match or None."""
        response = self.get(
            f"{self.BASE_URL}/game/search",
            params={"criteria": game_name},
            headers=self._headers,
        )
        response.raise_for_status()
        results = response.json()
        if not results:
            return None

        # Use GameMatcher for name matching
        matcher = GameMatcher()
        return matcher.best_match(game_name, results, name_key="name")

    def fetch_game(self, opencritic_id: int) -> dict | None:
        """Fetch full game details from OpenCritic.

        Returns dict with: topCriticScore, percentRecommended, tier, numReviews, etc.
        """
        response = self.get(
            f"{self.BASE_URL}/game/{opencritic_id}",
            headers=self._headers,
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()

    def fetch_reviews(self, opencritic_id: int, sort: str = "score") -> list[dict]:
        """Fetch individual critic reviews for a game.

        Returns list of review dicts with: score, snippet, outlet, author, publishedDate.
        """
        response = self.get(
            f"{self.BASE_URL}/game/{opencritic_id}/reviews",
            params={"sort": sort},
            headers=self._headers,
        )
        response.raise_for_status()
        return response.json()
```

- [ ] **Step 2: step1j_opencritic.py 작성**

```python
"""Step 1j: Enrich games with OpenCritic critic scores and reviews."""
from __future__ import annotations

import sqlite3

from rich.console import Console

from steam_crawler.api.opencritic import OpenCriticClient
from steam_crawler.api.rate_limiter import AdaptiveRateLimiter
from steam_crawler.api.resilience import FailureTracker
from steam_crawler.db.repository import (
    get_games_needing_enrichment,
    update_game_opencritic,
    upsert_external_review,
)

console = Console()


def run_step1j(
    conn: sqlite3.Connection,
    version: int,
    source_tag: str | None = None,
    rapidapi_key: str | None = None,
    opencritic_client: OpenCriticClient | None = None,
    failure_tracker: FailureTracker | None = None,
    lock_owner: str | None = None,
) -> int:
    """Enrich games with OpenCritic scores + individual critic reviews. Returns count enriched."""
    if rapidapi_key is None and opencritic_client is None:
        console.print("[yellow]RAPIDAPI_KEY not set, skipping step 1j (OpenCritic)[/yellow]")
        return 0

    client = opencritic_client or OpenCriticClient(
        rapidapi_key=rapidapi_key,
        rate_limiter=AdaptiveRateLimiter(api_name="opencritic", default_delay_ms=3000),
    )
    tracker = failure_tracker or FailureTracker()
    games = get_games_needing_enrichment(
        conn, source="opencritic", source_tag=source_tag, lock_owner=lock_owner
    )
    enriched = 0

    if not games:
        console.print("[dim]Step 1j: No games need OpenCritic enrichment[/dim]")
        return 0

    console.print(f"[bold]Step 1j:[/bold] Enriching {len(games)} games from OpenCritic")

    try:
        for game_row in games:
            appid = game_row["appid"]
            name = game_row["name"]
            try:
                matched = client.search(name)
                if matched is None:
                    update_game_opencritic(conn, appid=appid, opencritic_id=-1)
                    tracker.log_failure(
                        conn=conn, session_id=version, api_name="opencritic",
                        appid=appid, step="step1j",
                        error_type="match_failed",
                        error_message=f"No OpenCritic match for '{name}'",
                    )
                    continue

                oc_id = matched["id"]
                details = client.fetch_game(oc_id)
                if details is None:
                    update_game_opencritic(conn, appid=appid, opencritic_id=-1)
                    continue

                update_game_opencritic(
                    conn,
                    appid=appid,
                    opencritic_id=oc_id,
                    score=details.get("topCriticScore"),
                    pct_recommend=details.get("percentRecommended"),
                    tier=details.get("tier"),
                    review_count=details.get("numReviews"),
                )

                # Fetch and store individual critic reviews
                try:
                    reviews = client.fetch_reviews(oc_id)
                    for rev in reviews[:10]:  # Top 10 reviews
                        outlets = rev.get("Outlet") or {}
                        authors = rev.get("Authors") or [{}]
                        upsert_external_review(
                            conn,
                            appid=appid,
                            source="opencritic",
                            source_id=str(rev.get("id", "")),
                            title=rev.get("title"),
                            score=rev.get("score"),
                            author=authors[0].get("name") if authors else None,
                            outlet=outlets.get("name"),
                            url=rev.get("externalUrl"),
                            snippet=rev.get("snippet"),
                            published_at=rev.get("publishedDate"),
                        )
                except Exception:
                    pass  # Individual reviews are optional; aggregate score is primary

                enriched += 1

            except Exception as e:
                tracker.log_failure(
                    conn=conn, session_id=version, api_name="opencritic",
                    appid=appid, step="step1j", error_message=str(e),
                )
                console.print(f"  [red]OpenCritic error for {name} ({appid}): {e}[/red]")
                continue

        console.print(
            f"[green]Step 1j complete:[/green] {enriched}/{len(games)} games enriched from OpenCritic"
        )
        return enriched
    finally:
        if opencritic_client is None:
            client.close()
```

- [ ] **Step 3: Commit**

```bash
git add steam-crawler/src/steam_crawler/api/opencritic.py
git add steam-crawler/src/steam_crawler/pipeline/step1j_opencritic.py
git commit -m "feat: add OpenCritic critic score enrichment (step1j)"
```

---

## Task 9: PCGamingWiki API 클라이언트 + 파이프라인 스텝

**Files:**
- Create: `steam-crawler/src/steam_crawler/api/pcgamingwiki.py`
- Create: `steam-crawler/src/steam_crawler/pipeline/step1k_pcgamingwiki.py`

`★ Insight: PCGamingWiki의 Cargo API는 다른 소스에서 얻을 수 없는 기술적 데이터를 제공합니다 — 엔진, 그래픽 API, 울트라와이드/HDR 지원 등. 이는 "기술 완성도" 차원의 기획 분석에 핵심적입니다.`

- [ ] **Step 1: PCGamingWiki 클라이언트 작성**

```python
"""PCGamingWiki Cargo API client — technical game data."""

from __future__ import annotations

from steam_crawler.api.base import BaseClient
from steam_crawler.api.rate_limiter import AdaptiveRateLimiter


class PCGamingWikiClient(BaseClient):
    """Fetches technical game info from PCGamingWiki via MediaWiki Cargo API."""

    BASE_URL = "https://www.pcgamingwiki.com/w/api.php"

    def __init__(self, rate_limiter: AdaptiveRateLimiter | None = None):
        super().__init__(rate_limiter=rate_limiter, timeout=15.0)

    def fetch_by_appid(self, appid: int) -> dict | None:
        """Fetch technical data for a Steam game by appid.

        Returns dict with: engine, has_ultrawide, has_hdr, has_controller, graphics_api
        Returns None if game not found.
        """
        # Query Infobox_game table for basic info
        response = self.get(self.BASE_URL, params={
            "action": "cargoquery",
            "tables": "Infobox_game",
            "fields": "Infobox_game._pageName=page,Infobox_game.Engines=engines,"
                      "Infobox_game.Steam_AppID=steam_appid",
            "where": f'Infobox_game.Steam_AppID HOLDS "{appid}"',
            "format": "json",
            "limit": "1",
        })
        response.raise_for_status()
        data = response.json()
        results = data.get("cargoquery", [])
        if not results:
            return None

        row = results[0].get("title", {})
        page_name = row.get("page", "")
        engine = row.get("engines", "")

        # Query Video settings for ultrawide, HDR, graphics API
        video_data = self._fetch_video_settings(page_name)
        # Query Input settings for controller support
        input_data = self._fetch_input_settings(page_name)

        return {
            "engine": engine if engine else None,
            "has_ultrawide": video_data.get("has_ultrawide"),
            "has_hdr": video_data.get("has_hdr"),
            "graphics_api": video_data.get("graphics_api"),
            "has_controller": input_data.get("has_controller"),
        }

    def _fetch_video_settings(self, page_name: str) -> dict:
        """Fetch video settings (ultrawide, HDR, graphics API) for a page."""
        result = {"has_ultrawide": None, "has_hdr": None, "graphics_api": None}
        if not page_name:
            return result

        # Escape double quotes in page_name to prevent Cargo query breakage
        safe_name = page_name.replace('"', '\\"')
        response = self.get(self.BASE_URL, params={
            "action": "cargoquery",
            "tables": "Video",
            "fields": "Video.Ultra_widescreen=ultrawide,"
                      "Video.HDR=hdr,"
                      "Video.API=api",
            "where": f'Video._pageName="{safe_name}"',
            "format": "json",
            "limit": "1",
        })
        if response.status_code != 200:
            return result

        data = response.json()
        rows = data.get("cargoquery", [])
        if not rows:
            return result

        row = rows[0].get("title", {})
        uw = row.get("ultrawide", "")
        result["has_ultrawide"] = uw.lower() == "true" if uw else None
        hdr_val = row.get("hdr", "")
        result["has_hdr"] = hdr_val.lower() == "true" if hdr_val else None
        result["graphics_api"] = row.get("api") or None
        return result

    def _fetch_input_settings(self, page_name: str) -> dict:
        """Fetch input settings (controller support) for a page."""
        result = {"has_controller": None}
        if not page_name:
            return result

        safe_name = page_name.replace('"', '\\"')
        response = self.get(self.BASE_URL, params={
            "action": "cargoquery",
            "tables": "Input",
            "fields": "Input.Controller=controller",
            "where": f'Input._pageName="{safe_name}"',
            "format": "json",
            "limit": "1",
        })
        if response.status_code != 200:
            return result

        data = response.json()
        rows = data.get("cargoquery", [])
        if not rows:
            return result

        row = rows[0].get("title", {})
        ctrl = row.get("controller", "")
        result["has_controller"] = ctrl.lower() == "true" if ctrl else None
        return result
```

- [ ] **Step 2: step1k_pcgamingwiki.py 작성**

```python
"""Step 1k: Enrich games with PCGamingWiki technical data."""
from __future__ import annotations

import sqlite3

from rich.console import Console

from steam_crawler.api.pcgamingwiki import PCGamingWikiClient
from steam_crawler.api.rate_limiter import AdaptiveRateLimiter
from steam_crawler.api.resilience import FailureTracker
from steam_crawler.db.repository import (
    get_games_needing_enrichment,
    update_game_pcgamingwiki,
)

console = Console()


def run_step1k(
    conn: sqlite3.Connection,
    version: int,
    source_tag: str | None = None,
    pcgw_client: PCGamingWikiClient | None = None,
    failure_tracker: FailureTracker | None = None,
    lock_owner: str | None = None,
) -> int:
    """Enrich games with PCGamingWiki technical data. Returns count enriched."""
    client = pcgw_client or PCGamingWikiClient(
        rate_limiter=AdaptiveRateLimiter(api_name="pcgamingwiki", default_delay_ms=1500)
    )
    tracker = failure_tracker or FailureTracker()
    games = get_games_needing_enrichment(
        conn, source="pcgamingwiki", source_tag=source_tag, lock_owner=lock_owner
    )
    enriched = 0

    if not games:
        console.print("[dim]Step 1k: No games need PCGamingWiki enrichment[/dim]")
        return 0

    console.print(f"[bold]Step 1k:[/bold] Enriching {len(games)} games from PCGamingWiki")

    try:
        for game_row in games:
            appid = game_row["appid"]
            name = game_row["name"]
            try:
                data = client.fetch_by_appid(appid)
                if data is None:
                    # Mark as checked — store empty string as sentinel
                    update_game_pcgamingwiki(conn, appid=appid, engine="unknown")
                    continue

                update_game_pcgamingwiki(
                    conn,
                    appid=appid,
                    engine=data.get("engine"),
                    has_ultrawide=data.get("has_ultrawide"),
                    has_hdr=data.get("has_hdr"),
                    has_controller=data.get("has_controller"),
                    graphics_api=data.get("graphics_api"),
                )
                enriched += 1

            except Exception as e:
                tracker.log_failure(
                    conn=conn, session_id=version, api_name="pcgamingwiki",
                    appid=appid, step="step1k", error_message=str(e),
                )
                console.print(f"  [red]PCGamingWiki error for {name} ({appid}): {e}[/red]")
                continue

        console.print(
            f"[green]Step 1k complete:[/green] {enriched}/{len(games)} games enriched from PCGamingWiki"
        )
        return enriched
    finally:
        if pcgw_client is None:
            client.close()
```

- [ ] **Step 3: Commit**

```bash
git add steam-crawler/src/steam_crawler/api/pcgamingwiki.py
git add steam-crawler/src/steam_crawler/pipeline/step1k_pcgamingwiki.py
git commit -m "feat: add PCGamingWiki technical data enrichment (step1k)"
```

---

## Task 10: Pipeline Runner — step1g~1k 통합

**Files:**
- Modify: `steam-crawler/src/steam_crawler/pipeline/runner.py`

- [ ] **Step 1: import 추가**

```python
from steam_crawler.pipeline.step1g_protondb import run_step1g
from steam_crawler.pipeline.step1h_hltb import run_step1h
from steam_crawler.pipeline.step1i_cheapshark import run_step1i
from steam_crawler.pipeline.step1j_opencritic import run_step1j
from steam_crawler.pipeline.step1k_pcgamingwiki import run_step1k
```

- [ ] **Step 2: .env 변수 로딩 추가**

step1f 이후, step1g~1k 호출 전에:

```python
            rapidapi_key = os.environ.get("RAPIDAPI_KEY") or None
```

- [ ] **Step 3: step1f 호출 다음에 step1g~1k 호출 추가**

```python
            # Step 1g: ProtonDB compatibility (no auth needed)
            run_step1g(
                conn, version, source_tag=source_tag,
                failure_tracker=tracker, lock_owner=lock_owner,
            )

            # Step 1h: HowLongToBeat completion times (no auth needed)
            run_step1h(
                conn, version, source_tag=source_tag,
                failure_tracker=tracker, lock_owner=lock_owner,
            )

            # Step 1i: CheapShark deal/price data (no auth needed)
            run_step1i(
                conn, version, source_tag=source_tag,
                failure_tracker=tracker, lock_owner=lock_owner,
            )

            # Step 1j: OpenCritic critic scores (optional, needs RAPIDAPI_KEY)
            run_step1j(
                conn, version, source_tag=source_tag,
                rapidapi_key=rapidapi_key,
                failure_tracker=tracker, lock_owner=lock_owner,
            )

            # Step 1k: PCGamingWiki technical data (no auth needed)
            run_step1k(
                conn, version, source_tag=source_tag,
                failure_tracker=tracker, lock_owner=lock_owner,
            )
```

- [ ] **Step 4: Commit**

```bash
git add steam-crawler/src/steam_crawler/pipeline/runner.py
git commit -m "feat: integrate step1g-1k external sources into pipeline runner"
```

---

## Task 11: 단위 테스트 — 5개 소스

**Files:**
- Create: `steam-crawler/tests/test_protondb.py`
- Create: `steam-crawler/tests/test_hltb.py`
- Create: `steam-crawler/tests/test_cheapshark.py`
- Create: `steam-crawler/tests/test_opencritic.py`
- Create: `steam-crawler/tests/test_pcgamingwiki.py`

- [ ] **Step 1: ProtonDB 테스트**

```python
"""Tests for ProtonDB API client."""
from unittest.mock import MagicMock, patch
from steam_crawler.api.protondb import ProtonDBClient


def test_fetch_summary_success():
    client = ProtonDBClient()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "tier": "gold",
        "confidence": "good",
        "trendingTier": "gold",
        "total": 42,
        "score": 0.72,
        "bestReportedTier": "platinum",
    }
    with patch.object(client, "get", return_value=mock_resp):
        result = client.fetch_summary(730)
    assert result["tier"] == "gold"
    assert result["total"] == 42


def test_fetch_summary_not_found():
    client = ProtonDBClient()
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    with patch.object(client, "get", return_value=mock_resp):
        result = client.fetch_summary(999999999)
    assert result is None
```

- [ ] **Step 2: HLTB 테스트**

```python
"""Tests for HowLongToBeat wrapper."""
from unittest.mock import patch, MagicMock, AsyncMock
from steam_crawler.api.hltb import HLTBClient


def test_search_returns_best_match():
    client = HLTBClient()
    mock_entry = MagicMock()
    mock_entry.similarity = 0.95
    mock_entry.game_id = 12345
    mock_entry.main_story = 25.5
    mock_entry.main_extra = 40.0
    mock_entry.completionist = 80.0

    with patch("steam_crawler.api.hltb.HowLongToBeat") as mock_hltb:
        instance = mock_hltb.return_value
        instance.async_search = AsyncMock(return_value=[mock_entry])
        result = client.search("Hades")

    assert result is not None
    assert result["game_id"] == 12345
    assert result["main_story"] == 25.5


def test_search_no_results():
    client = HLTBClient()
    with patch("steam_crawler.api.hltb.HowLongToBeat") as mock_hltb:
        instance = mock_hltb.return_value
        instance.async_search = AsyncMock(return_value=[])
        result = client.search("NonExistentGame12345")
    assert result is None


def test_search_low_similarity_rejected():
    client = HLTBClient()
    mock_entry = MagicMock()
    mock_entry.similarity = 0.2
    mock_entry.game_id = 99
    mock_entry.main_story = 10.0
    mock_entry.main_extra = 20.0
    mock_entry.completionist = 30.0

    with patch("steam_crawler.api.hltb.HowLongToBeat") as mock_hltb:
        instance = mock_hltb.return_value
        instance.async_search = AsyncMock(return_value=[mock_entry])
        result = client.search("Completely Different Name")
    assert result is None
```

- [ ] **Step 3: CheapShark 테스트**

```python
"""Tests for CheapShark API client."""
from unittest.mock import MagicMock, patch
from steam_crawler.api.cheapshark import CheapSharkClient


def test_search_by_steam_appid_success():
    client = CheapSharkClient()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = [
        {"gameID": "123", "dealRating": "8.5", "title": "Test Game"}
    ]
    with patch.object(client, "get", return_value=mock_resp):
        result = client.search_by_steam_appid(730)
    assert result is not None
    assert result["dealRating"] == "8.5"


def test_search_by_steam_appid_no_deals():
    client = CheapSharkClient()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = []
    with patch.object(client, "get", return_value=mock_resp):
        result = client.search_by_steam_appid(999999)
    assert result is None
```

- [ ] **Step 4: OpenCritic 테스트**

```python
"""Tests for OpenCritic API client."""
from unittest.mock import MagicMock, patch
from steam_crawler.api.opencritic import OpenCriticClient


def test_search_and_fetch():
    client = OpenCriticClient(rapidapi_key="test_key")

    # Mock search
    search_resp = MagicMock()
    search_resp.status_code = 200
    search_resp.json.return_value = [
        {"id": 42, "name": "Hades", "dist": 0}
    ]

    # Mock fetch
    fetch_resp = MagicMock()
    fetch_resp.status_code = 200
    fetch_resp.json.return_value = {
        "id": 42,
        "topCriticScore": 93.5,
        "percentRecommended": 97.0,
        "tier": "Mighty",
        "numReviews": 120,
    }

    with patch.object(client, "get", side_effect=[search_resp, fetch_resp]):
        matched = client.search("Hades")
        assert matched is not None
        details = client.fetch_game(matched["id"])
        assert details["topCriticScore"] == 93.5
        assert details["tier"] == "Mighty"


def test_search_no_results():
    client = OpenCriticClient(rapidapi_key="test_key")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = []
    with patch.object(client, "get", return_value=mock_resp):
        result = client.search("NonExistent12345")
    assert result is None
```

- [ ] **Step 5: PCGamingWiki 테스트**

```python
"""Tests for PCGamingWiki Cargo API client."""
from unittest.mock import MagicMock, patch
from steam_crawler.api.pcgamingwiki import PCGamingWikiClient


def test_fetch_by_appid_success():
    client = PCGamingWikiClient()

    main_resp = MagicMock()
    main_resp.status_code = 200
    main_resp.json.return_value = {
        "cargoquery": [{"title": {
            "page": "Hades",
            "engines": "Supergiant Engine",
            "steam appid": "1145360",
        }}]
    }

    video_resp = MagicMock()
    video_resp.status_code = 200
    video_resp.json.return_value = {
        "cargoquery": [{"title": {
            "ultrawide": "true",
            "hdr": "false",
            "api": "DirectX 11",
        }}]
    }

    input_resp = MagicMock()
    input_resp.status_code = 200
    input_resp.json.return_value = {
        "cargoquery": [{"title": {"controller": "true"}}]
    }

    with patch.object(client, "get", side_effect=[main_resp, video_resp, input_resp]):
        result = client.fetch_by_appid(1145360)

    assert result is not None
    assert result["engine"] == "Supergiant Engine"
    assert result["has_ultrawide"] is True
    assert result["has_hdr"] is False
    assert result["has_controller"] is True
    assert result["graphics_api"] == "DirectX 11"


def test_fetch_by_appid_not_found():
    client = PCGamingWikiClient()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"cargoquery": []}
    with patch.object(client, "get", return_value=mock_resp):
        result = client.fetch_by_appid(999999999)
    assert result is None
```

- [ ] **Step 6: 전체 테스트 실행**

```bash
cd steam-crawler && pytest tests/test_protondb.py tests/test_hltb.py tests/test_cheapshark.py tests/test_opencritic.py tests/test_pcgamingwiki.py -v
```

Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add steam-crawler/tests/test_protondb.py steam-crawler/tests/test_hltb.py
git add steam-crawler/tests/test_cheapshark.py steam-crawler/tests/test_opencritic.py
git add steam-crawler/tests/test_pcgamingwiki.py
git commit -m "test: add unit tests for 5 external source clients"
```

---

## Task 12: 인사이트 스킬 확장

**Files:**
- Modify: `.claude/skills/steam-insight/SKILL.md`

> **주의:** `.env`는 gitignore 대상이므로 커밋하지 않음. RAPIDAPI_KEY는 사용자가 직접 `.env`에 추가해야 함. 없으면 step1j(OpenCritic)는 자동 스킵됨.

- [ ] **Step 1: 인사이트 스킬에 새 데이터 소스 활용 쿼리 추가**

`SKILL.md` 2단계(메커니즘 실체)에 추가:

```sql
-- HowLongToBeat 게임 길이 (기획 밀도 분석)
SELECT hltb_main_story, hltb_main_extra, hltb_completionist
FROM games WHERE appid = ?;
-- ▸ main_story/completionist 비율 → 콘텐츠 깊이 vs 패딩 판단
-- ▸ Steam 리뷰 평균 playtime_at_review와 비교 → 체감 vs 공식 길이 괴리

-- ProtonDB 기술 호환성 (포팅 품질)
SELECT protondb_tier, protondb_confidence, protondb_trending_tier
FROM games WHERE appid = ?;

-- PCGamingWiki 기술 스펙 (기술 완성도)
SELECT pcgw_engine, pcgw_has_ultrawide, pcgw_has_hdr,
       pcgw_has_controller, pcgw_graphics_api
FROM games WHERE appid = ?;
```

5단계(비즈니스 구조)에 추가:

```sql
-- OpenCritic 전문가 평가 (Steam 유저 리뷰와 교차 검증)
SELECT opencritic_score, opencritic_pct_recommend, opencritic_tier,
       opencritic_review_count
FROM games WHERE appid = ?;

-- OpenCritic 개별 리뷰 (매체별 평가 차이)
SELECT outlet, score, snippet, published_at
FROM external_reviews WHERE appid = ? AND source = 'opencritic'
ORDER BY score DESC LIMIT 5;

-- CheapShark 가격 이력 (비즈니스 전략)
SELECT cheapshark_deal_rating, cheapshark_lowest_price, cheapshark_lowest_price_date
FROM games WHERE appid = ?;
-- ▸ deal_rating 높고 lowest_price 낮으면 → 공격적 할인 전략
-- ▸ lowest_price가 출시가와 비슷하면 → 가격 자신감
```

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/steam-insight/SKILL.md
git commit -m "feat: add external source queries to insight skill"
```

---

## Summary: 파이프라인 전체 실행 순서 (완성 후)

```
Step 1   SteamSpy 게임 수집
Step 1b  SteamSpy 태그/장르 보강
Step 1c  Steam Store 상세 설명
Step 1d  IGDB themes/keywords/rating
Step 1e  RAWG description/ratings/retention
Step 1f  Twitch 스트리밍 데이터
Step 1g  ProtonDB 호환성 (NEW)
Step 1h  HowLongToBeat 게임 길이 (NEW)
Step 1i  CheapShark 딜/가격 (NEW)
Step 1j  OpenCritic 전문가 평가 (NEW)
Step 1k  PCGamingWiki 기술 스펙 (NEW)
Step 2   Steam 리뷰 요약 스캔
Step 3   Steam 리뷰 본문 크롤링
```

## 환경 변수 총정리

```env
# 기존
TWITCH_CLIENT_ID=        # IGDB + Twitch (step1d, step1f)
TWITCH_CLIENT_SECRET=    # IGDB + Twitch (step1d, step1f)
RAWG_API_KEY=            # RAWG (step1e)

# 신규
RAPIDAPI_KEY=            # OpenCritic (step1j) — 없으면 자동 스킵
```

ProtonDB, HowLongToBeat, CheapShark, PCGamingWiki는 인증 불필요.
