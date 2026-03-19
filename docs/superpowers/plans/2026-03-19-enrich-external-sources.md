# External Sources Enrichment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 외부 소스 데이터를 확장하여 인사이트 분석의 2단계(메커니즘 실체)를 강화한다. 3개 작업: (1) 인사이트 스킬에서 기존 IGDB themes/keywords 활용, (2) RAWG `added_by_status` 리텐션 프록시 수집, (3) Twitch 스트리밍 데이터 신규 소스 추가.

**Architecture:** 기존 파이프라인 패턴(step1d/step1e)을 따르는 step1f_twitch 추가. RAWG는 기존 step1e 확장. 인사이트 스킬은 SQL 쿼리만 추가. DB 스키마는 `_migrate()`로 안전하게 확장.

**Tech Stack:** Python 3.12+, httpx, SQLite, rich

---

## File Structure

| Action | File | Responsibility |
|--------|------|---------------|
| Modify | `.claude/skills/steam-insight/SKILL.md` | 2단계에 themes/keywords/RAWG retention/Twitch 쿼리 추가 |
| Modify | `steam-crawler/src/steam_crawler/db/schema.py` | `games` 테이블에 RAWG retention + Twitch 컬럼 추가 (`_migrate`) |
| Modify | `steam-crawler/src/steam_crawler/db/repository.py` | `update_game_rawg_details` 확장 + `update_game_twitch_stats` 추가 |
| Modify | `steam-crawler/src/steam_crawler/api/rawg.py` | `fetch_game_details`에서 이미 전체 JSON 반환 — 변경 없음 |
| Modify | `steam-crawler/src/steam_crawler/pipeline/step1e_rawg.py` | `added_by_status` + `ratings` 파싱 추가 |
| Create | `steam-crawler/src/steam_crawler/api/twitch.py` | Twitch Helix API 클라이언트 |
| Create | `steam-crawler/src/steam_crawler/pipeline/step1f_twitch.py` | Twitch enrichment 파이프라인 스텝 |
| Modify | `steam-crawler/src/steam_crawler/pipeline/runner.py` | step1f 통합 |
| Create | `steam-crawler/tests/test_twitch.py` | Twitch 클라이언트 + step1f 테스트 |
| Modify | `steam-crawler/tests/test_rawg_enrichment.py` (있으면) | RAWG retention 필드 테스트 |
| Modify | `.env.example` | 변경 없음 (Twitch 인증은 IGDB와 공유) |

---

### Task 1: DB 스키마 확장 — RAWG retention + Twitch 컬럼

**Files:**
- Modify: `steam-crawler/src/steam_crawler/db/schema.py:238-247` (`_migrate` 함수)

- [ ] **Step 1: `_migrate()`에 새 컬럼 추가**

`games` 테이블에 다음 컬럼을 추가하는 마이그레이션:

```python
# schema.py _migrate() 내부에 추가할 컬럼 목록
new_columns = [
    # RAWG retention proxy
    ("rawg_ratings_count", "INTEGER"),        # total ratings on RAWG
    ("rawg_added", "INTEGER"),                # total users who added
    ("rawg_status_yet", "INTEGER"),           # 관심만 (backlog)
    ("rawg_status_owned", "INTEGER"),         # 소유
    ("rawg_status_beaten", "INTEGER"),        # 클리어
    ("rawg_status_toplay", "INTEGER"),        # 플레이 예정
    ("rawg_status_dropped", "INTEGER"),       # 드롭
    ("rawg_status_playing", "INTEGER"),       # 플레이 중
    ("rawg_exceptional_pct", "REAL"),         # exceptional 비율
    ("rawg_recommended_pct", "REAL"),         # recommended 비율
    ("rawg_meh_pct", "REAL"),                 # meh 비율
    ("rawg_skip_pct", "REAL"),                # skip 비율
    # Twitch streaming
    ("twitch_game_id", "TEXT"),               # Twitch category ID
    ("twitch_stream_count", "INTEGER"),       # 라이브 채널 수 (스냅샷)
    ("twitch_viewer_count", "INTEGER"),       # 총 시청자 수 (스냅샷)
    ("twitch_top_language", "TEXT"),           # 최다 스트리머 언어
    ("twitch_lang_distribution", "TEXT"),      # JSON: {"en":35,"de":6,...}
    ("twitch_fetched_at", "TIMESTAMP"),       # 스냅샷 시점
]
```

기존 `_migrate()` 패턴을 따라 `ALTER TABLE games ADD COLUMN` 사용:

```python
def _migrate(conn: sqlite3.Connection) -> None:
    """Add columns that may be missing in older databases."""
    existing = {row[1] for row in conn.execute("PRAGMA table_info(games)").fetchall()}
    migrations = [
        ("detailed_description_en", "TEXT"),
        ("detailed_description_ko", "TEXT"),
        # RAWG retention proxy
        ("rawg_ratings_count", "INTEGER"),
        ("rawg_added", "INTEGER"),
        ("rawg_status_yet", "INTEGER"),
        ("rawg_status_owned", "INTEGER"),
        ("rawg_status_beaten", "INTEGER"),
        ("rawg_status_toplay", "INTEGER"),
        ("rawg_status_dropped", "INTEGER"),
        ("rawg_status_playing", "INTEGER"),
        ("rawg_exceptional_pct", "REAL"),
        ("rawg_recommended_pct", "REAL"),
        ("rawg_meh_pct", "REAL"),
        ("rawg_skip_pct", "REAL"),
        # Twitch streaming
        ("twitch_game_id", "TEXT"),
        ("twitch_stream_count", "INTEGER"),
        ("twitch_viewer_count", "INTEGER"),
        ("twitch_top_language", "TEXT"),
        ("twitch_lang_distribution", "TEXT"),
        ("twitch_fetched_at", "TIMESTAMP"),
    ]
    for col, col_type in migrations:
        if col not in existing:
            conn.execute(f"ALTER TABLE games ADD COLUMN {col} {col_type}")
    conn.commit()
```

- [ ] **Step 2: 실행하여 마이그레이션 확인**

Run: `cd steam-crawler && python -c "from steam_crawler.db.schema import init_db; conn=init_db('../data/steam.db'); print([r[1] for r in conn.execute('PRAGMA table_info(games)').fetchall() if 'rawg_status' in r[1] or 'twitch' in r[1]])"`

Expected: 새 컬럼명 목록 출력

- [ ] **Step 3: Commit**

```bash
git add steam-crawler/src/steam_crawler/db/schema.py
git commit -m "feat: add RAWG retention + Twitch streaming columns to schema"
```

---

### Task 2: Repository — RAWG 업데이트 함수 확장 + Twitch 함수 추가

**Files:**
- Modify: `steam-crawler/src/steam_crawler/db/repository.py:373-386` (`update_game_rawg_details`)

- [ ] **Step 1: `update_game_rawg_details` 확장**

기존 함수에 새 파라미터 추가:

```python
def update_game_rawg_details(
    conn: sqlite3.Connection,
    appid: int,
    rawg_id: int,
    rawg_description: str | None = None,
    rawg_rating: float | None = None,
    metacritic_score: int | None = None,
    # 새로 추가
    rawg_ratings_count: int | None = None,
    rawg_added: int | None = None,
    rawg_status_yet: int | None = None,
    rawg_status_owned: int | None = None,
    rawg_status_beaten: int | None = None,
    rawg_status_toplay: int | None = None,
    rawg_status_dropped: int | None = None,
    rawg_status_playing: int | None = None,
    rawg_exceptional_pct: float | None = None,
    rawg_recommended_pct: float | None = None,
    rawg_meh_pct: float | None = None,
    rawg_skip_pct: float | None = None,
) -> None:
    """Update RAWG enrichment data on the games table."""
    conn.execute(
        """UPDATE games SET rawg_id=?, rawg_description=?, rawg_rating=?,
           metacritic_score=?, rawg_ratings_count=?, rawg_added=?,
           rawg_status_yet=?, rawg_status_owned=?, rawg_status_beaten=?,
           rawg_status_toplay=?, rawg_status_dropped=?, rawg_status_playing=?,
           rawg_exceptional_pct=?, rawg_recommended_pct=?,
           rawg_meh_pct=?, rawg_skip_pct=?,
           updated_at=? WHERE appid=?""",
        (rawg_id, rawg_description, rawg_rating, metacritic_score,
         rawg_ratings_count, rawg_added,
         rawg_status_yet, rawg_status_owned, rawg_status_beaten,
         rawg_status_toplay, rawg_status_dropped, rawg_status_playing,
         rawg_exceptional_pct, rawg_recommended_pct,
         rawg_meh_pct, rawg_skip_pct,
         _now(), appid),
    )
    conn.commit()
```

- [ ] **Step 2: `update_game_twitch_stats` 추가**

```python
def update_game_twitch_stats(
    conn: sqlite3.Connection,
    appid: int,
    twitch_game_id: str,
    stream_count: int,
    viewer_count: int,
    top_language: str | None = None,
    lang_distribution: str | None = None,
) -> None:
    """Update Twitch streaming stats on the games table."""
    conn.execute(
        """UPDATE games SET twitch_game_id=?, twitch_stream_count=?,
           twitch_viewer_count=?, twitch_top_language=?,
           twitch_lang_distribution=?, twitch_fetched_at=?,
           updated_at=? WHERE appid=?""",
        (twitch_game_id, stream_count, viewer_count,
         top_language, lang_distribution, _now(), _now(), appid),
    )
    conn.commit()
```

- [ ] **Step 3: `get_games_needing_enrichment`에 twitch 소스 지원 추가**

`source` 파라미터에 `'twitch'` 옵션 추가. id_col 매핑:

```python
def get_games_needing_enrichment(
    conn: sqlite3.Connection,
    source: str,
    source_tag: str | None = None,
    lock_owner: str | None = None,
) -> list[dict]:
    id_col_map = {"igdb": "igdb_id", "rawg": "rawg_id", "twitch": "twitch_game_id"}
    id_col = id_col_map[source]
    # ... 나머지 동일
```

- [ ] **Step 4: Commit**

```bash
git add steam-crawler/src/steam_crawler/db/repository.py
git commit -m "feat: extend RAWG details + add Twitch stats repository functions"
```

---

### Task 3: RAWG Step1e — `added_by_status` + `ratings` 파싱

**Files:**
- Modify: `steam-crawler/src/steam_crawler/pipeline/step1e_rawg.py:66-78`

- [ ] **Step 1: step1e에서 RAWG 상세 응답의 추가 필드 파싱**

`details` dict에서 `added_by_status`와 `ratings`를 추출하여 repository 함수에 전달:

```python
# step1e_rawg.py 내 details 처리 부분 (기존 update_game_rawg_details 호출 대체)

# Parse added_by_status
abs_data = details.get("added_by_status") or {}
# Parse ratings (list of {id, title, count, percent})
ratings_data = details.get("ratings") or []
rating_pcts = {}
for r in ratings_data:
    title = r.get("title", "")
    pct = r.get("percent", 0.0)
    if title in ("exceptional", "recommended", "meh", "skip"):
        rating_pcts[f"rawg_{title}_pct"] = pct

update_game_rawg_details(
    conn, appid=appid, rawg_id=rawg_id,
    rawg_description=details.get("description_raw"),
    rawg_rating=details.get("rating"),
    metacritic_score=details.get("metacritic"),
    rawg_ratings_count=details.get("ratings_count"),
    rawg_added=details.get("added"),
    rawg_status_yet=abs_data.get("yet"),
    rawg_status_owned=abs_data.get("owned"),
    rawg_status_beaten=abs_data.get("beaten"),
    rawg_status_toplay=abs_data.get("toplay"),
    rawg_status_dropped=abs_data.get("dropped"),
    rawg_status_playing=abs_data.get("playing"),
    rawg_exceptional_pct=rating_pcts.get("rawg_exceptional_pct"),
    rawg_recommended_pct=rating_pcts.get("rawg_recommended_pct"),
    rawg_meh_pct=rating_pcts.get("rawg_meh_pct"),
    rawg_skip_pct=rating_pcts.get("rawg_skip_pct"),
)
```

- [ ] **Step 2: 테스트 — 기존 RAWG 데이터가 있는 게임을 re-enrich하여 새 필드 확인**

Run: `cd steam-crawler && python -c "
from steam_crawler.db.schema import init_db
conn=init_db('../data/steam.db')
r=conn.execute('SELECT rawg_added, rawg_status_dropped, rawg_exceptional_pct FROM games WHERE rawg_id IS NOT NULL AND rawg_added IS NOT NULL LIMIT 3').fetchall()
for row in r: print(dict(row))
"`

Expected: 새 필드에 값이 채워진 행 (re-enrich 전이면 NULL)

- [ ] **Step 3: Commit**

```bash
git add steam-crawler/src/steam_crawler/pipeline/step1e_rawg.py
git commit -m "feat: parse RAWG added_by_status + ratings in step1e"
```

---

### Task 4: Twitch API 클라이언트

**Files:**
- Create: `steam-crawler/src/steam_crawler/api/twitch.py`

- [ ] **Step 1: TwitchClient 작성**

IGDB와 동일한 Twitch OAuth 인증을 공유하되, Helix API 엔드포인트 사용:

```python
"""Twitch Helix API client for game streaming data."""

from __future__ import annotations

import time
import httpx

from steam_crawler.api.rate_limiter import AdaptiveRateLimiter


class TwitchClient:
    """Twitch Helix API client. Shares Twitch OAuth with IGDB."""

    BASE_URL = "https://api.twitch.tv/helix"
    AUTH_URL = "https://id.twitch.tv/oauth2/token"

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        rate_limiter: AdaptiveRateLimiter | None = None,
        timeout: float = 10.0,
    ):
        self._client_id = client_id
        self._client_secret = client_secret
        self._rate_limiter = rate_limiter
        self._http = httpx.Client(timeout=timeout)
        self._token: str | None = None
        self._token_expires_at: float = 0

    def authenticate(self) -> None:
        """Obtain or refresh Twitch OAuth token."""
        response = self._http.post(
            self.AUTH_URL,
            params={
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "grant_type": "client_credentials",
            },
        )
        response.raise_for_status()
        data = response.json()
        self._token = data["access_token"]
        self._token_expires_at = time.time() + data["expires_in"]

    def _ensure_auth(self) -> None:
        if self._token is None or time.time() >= self._token_expires_at - 60:
            self.authenticate()

    def _get(self, endpoint: str, params: dict) -> dict:
        """GET request to Helix API with auth + rate limiting."""
        self._ensure_auth()
        if self._rate_limiter:
            self._rate_limiter.wait()

        url = f"{self.BASE_URL}/{endpoint}"
        headers = {
            "Client-ID": self._client_id,
            "Authorization": f"Bearer {self._token}",
        }

        start = time.monotonic()
        response = self._http.get(url, params=params, headers=headers)
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
                    response = self._http.get(url, params=params, headers=headers)
                    elapsed_ms = (time.monotonic() - start) * 1000
                    if response.status_code < 400:
                        break
            else:
                self._rate_limiter.record_success(elapsed_ms)

        response.raise_for_status()
        return response.json()

    def search_game(self, name: str) -> dict | None:
        """Search Twitch categories by game name. Returns best match."""
        data = self._get("search/categories", {"query": name, "first": 5})
        results = data.get("data", [])
        # Exact match first, then first result
        name_lower = name.lower()
        for r in results:
            if r["name"].lower() == name_lower:
                return r
        return results[0] if results else None

    def get_live_stats(self, game_id: str, max_pages: int = 5) -> dict:
        """Get aggregated live streaming stats for a game.

        Returns: {
            "stream_count": int,
            "viewer_count": int,
            "top_language": str | None,
            "lang_distribution": dict[str, int],
        }
        """
        all_streams = []
        cursor = None
        for _ in range(max_pages):
            params = {"game_id": game_id, "first": 100}
            if cursor:
                params["after"] = cursor
            data = self._get("streams", params)
            streams = data.get("data", [])
            if not streams:
                break
            all_streams.extend(streams)
            cursor = data.get("pagination", {}).get("cursor")
            if not cursor:
                break

        if not all_streams:
            return {
                "stream_count": 0,
                "viewer_count": 0,
                "top_language": None,
                "lang_distribution": {},
            }

        total_viewers = sum(s["viewer_count"] for s in all_streams)
        langs: dict[str, int] = {}
        for s in all_streams:
            lang = s["language"]
            langs[lang] = langs.get(lang, 0) + 1

        top_lang = max(langs, key=langs.get) if langs else None
        return {
            "stream_count": len(all_streams),
            "viewer_count": total_viewers,
            "top_language": top_lang,
            "lang_distribution": langs,
        }

    def close(self) -> None:
        self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
```

- [ ] **Step 2: Commit**

```bash
git add steam-crawler/src/steam_crawler/api/twitch.py
git commit -m "feat: add Twitch Helix API client"
```

---

### Task 5: Step1f Twitch 파이프라인 스텝

**Files:**
- Create: `steam-crawler/src/steam_crawler/pipeline/step1f_twitch.py`

- [ ] **Step 1: step1f 작성**

step1d/step1e 패턴을 따름:

```python
"""Step 1f: Enrich games with Twitch streaming data (live channels, viewers)."""
from __future__ import annotations

import json
import sqlite3

from rich.console import Console

from steam_crawler.api.twitch import TwitchClient
from steam_crawler.api.resilience import FailureTracker
from steam_crawler.db.repository import (
    get_games_needing_enrichment,
    update_game_twitch_stats,
)

console = Console()


def run_step1f(
    conn: sqlite3.Connection,
    version: int,
    source_tag: str | None = None,
    client_id: str | None = None,
    client_secret: str | None = None,
    twitch_client: TwitchClient | None = None,
    failure_tracker: FailureTracker | None = None,
    lock_owner: str | None = None,
) -> int:
    """Enrich games with Twitch streaming data. Returns count enriched."""
    if client_id is None and twitch_client is None:
        console.print("[yellow]Twitch credentials not set, skipping step 1f[/yellow]")
        return 0

    client = twitch_client or TwitchClient(
        client_id=client_id, client_secret=client_secret
    )
    tracker = failure_tracker or FailureTracker()
    games = get_games_needing_enrichment(
        conn, source="twitch", source_tag=source_tag, lock_owner=lock_owner
    )
    enriched = 0

    if not games:
        console.print("[dim]Step 1f: No games need Twitch enrichment[/dim]")
        return 0

    console.print(f"[bold]Step 1f:[/bold] Enriching {len(games)} games from Twitch")

    try:
        for game_row in games:
            appid = game_row["appid"]
            name = game_row["name"]
            try:
                matched = client.search_game(name)
                if matched is None:
                    # Mark as unmatchable with sentinel
                    conn.execute(
                        "UPDATE games SET twitch_game_id='-1' WHERE appid=?",
                        (appid,),
                    )
                    conn.commit()
                    tracker.log_failure(
                        conn=conn, session_id=version, api_name="twitch",
                        appid=appid, step="step1f",
                        error_type="match_failed",
                        error_message=f"No Twitch category for '{name}'",
                    )
                    continue

                game_id = matched["id"]
                stats = client.get_live_stats(game_id)

                update_game_twitch_stats(
                    conn, appid=appid,
                    twitch_game_id=game_id,
                    stream_count=stats["stream_count"],
                    viewer_count=stats["viewer_count"],
                    top_language=stats["top_language"],
                    lang_distribution=json.dumps(
                        stats["lang_distribution"], ensure_ascii=False
                    ),
                )
                enriched += 1

            except Exception as e:
                tracker.log_failure(
                    conn=conn, session_id=version, api_name="twitch",
                    appid=appid, step="step1f", error_message=str(e),
                )
                console.print(
                    f"  [red]Twitch error for {name} ({appid}): {e}[/red]"
                )
                continue

        console.print(
            f"[green]Step 1f complete:[/green] {enriched}/{len(games)} games enriched from Twitch"
        )
        return enriched
    finally:
        if twitch_client is None:
            client.close()
```

- [ ] **Step 2: Commit**

```bash
git add steam-crawler/src/steam_crawler/pipeline/step1f_twitch.py
git commit -m "feat: add step1f Twitch enrichment pipeline step"
```

---

### Task 6: Pipeline Runner — step1f 통합

**Files:**
- Modify: `steam-crawler/src/steam_crawler/pipeline/runner.py:35-37` (import), `runner.py:213-219` (step1e 이후)

- [ ] **Step 1: import 추가**

```python
from steam_crawler.pipeline.step1f_twitch import run_step1f
```

- [ ] **Step 2: step1e 호출 다음에 step1f 호출 추가**

`runner.py`에서 step1e (RAWG) 호출 이후에 추가:

```python
            # Step 1f: Twitch streaming data (optional, uses same Twitch creds as IGDB)
            run_step1f(
                conn, version, source_tag=source_tag,
                client_id=igdb_cid, client_secret=igdb_csec,
                failure_tracker=tracker, lock_owner=lock_owner,
            )
```

`igdb_cid`/`igdb_csec`는 이미 step1d용으로 선언된 변수를 재사용.

- [ ] **Step 3: Commit**

```bash
git add steam-crawler/src/steam_crawler/pipeline/runner.py
git commit -m "feat: integrate step1f Twitch into pipeline runner"
```

---

### Task 7: 인사이트 스킬 — 외부 소스 쿼리 강화

**Files:**
- Modify: `.claude/skills/steam-insight/SKILL.md:61-77` (2단계 섹션)

- [ ] **Step 1: 2단계에 IGDB themes/keywords 쿼리 추가**

SKILL.md 2단계 섹션에 다음 SQL 쿼리를 추가:

```sql
-- IGDB Themes (제3자 테마 분류)
SELECT c.name FROM game_themes t
JOIN theme_catalog c ON t.theme_id = c.id
WHERE t.appid = ?;

-- IGDB Keywords (제3자 키워드 — Steam 태그와 교차 비교용)
SELECT c.name FROM game_keywords k
JOIN keyword_catalog c ON k.keyword_id = c.id
WHERE k.appid = ?;
```

분석 포인트에 추가:
- **IGDB keywords vs Steam tags 교차**: IGDB keywords에만 있는 것은 제3자가 인식한 숨은 특성 (예: `gambling`, `skateboarding`)
- **IGDB themes**: 대분류 시선 — Steam 태그보다 상위 수준의 분류

- [ ] **Step 2: 2단계에 RAWG 리텐션 프록시 쿼리 추가**

```sql
-- RAWG 유저 상태 분포 (리텐션 프록시)
SELECT rawg_added, rawg_status_yet, rawg_status_owned,
       rawg_status_beaten, rawg_status_toplay,
       rawg_status_dropped, rawg_status_playing,
       rawg_exceptional_pct, rawg_recommended_pct,
       rawg_meh_pct, rawg_skip_pct
FROM games WHERE appid = ?;
```

분석 포인트에 추가:
- **드롭률**: `dropped / added` = 이탈 비율
- **클리어률**: `beaten / (owned + playing + beaten)` = 완주 비율
- **exceptional vs meh 비율**: RAWG 유저의 4단계 평가 분포
- Steam 리뷰의 긍정률과 RAWG 평가 분포의 괴리가 있으면 인사이트

- [ ] **Step 3: 5단계에 Twitch 스트리밍 데이터 쿼리 추가**

```sql
-- Twitch 스트리밍 데이터 (비즈니스 지표)
SELECT twitch_stream_count, twitch_viewer_count,
       twitch_top_language, twitch_lang_distribution,
       twitch_fetched_at
FROM games WHERE appid = ?;
```

분석 포인트에 추가:
- **스트리밍 인기도**: 라이브 채널 수 × 시청자 수 = "watchability" 지표
- **스트리밍 언어 vs 리뷰 언어**: 분포 괴리 = 잠재 미개척 시장
- Twitch 데이터는 스냅샷이므로 `twitch_fetched_at` 명시

- [ ] **Step 4: TEMPLATE.html 보고서 구조에 새 섹션 위치 반영**

보고서 구조 설명에 추가:
```
Step 02: 메커니즘 실체
├── 코어 루프 다이어그램
├── IGDB Themes/Keywords 교차 분석 (NEW)
├── RAWG 리텐션 프록시 — 드롭률/클리어률 (NEW)
└── 마케팅이 말하지 않은 시스템들

Step 05: 비즈니스 구조
├── 추정 매출, 가성비, 수익 모델
├── Twitch 스트리밍 데이터 (NEW)
└── 수익 확장 가능성
```

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/steam-insight/SKILL.md
git commit -m "feat: add IGDB themes/keywords + RAWG retention + Twitch queries to insight skill"
```

---

### Task 8: 테스트

**Files:**
- Create: `steam-crawler/tests/test_twitch.py`

- [ ] **Step 1: TwitchClient 단위 테스트 작성**

```python
"""Tests for Twitch Helix API client."""
import pytest
from unittest.mock import MagicMock, patch
from steam_crawler.api.twitch import TwitchClient


def make_client():
    """Create a TwitchClient with mock auth."""
    client = TwitchClient(client_id="test_id", client_secret="test_secret")
    client._token = "test_token"
    client._token_expires_at = float("inf")
    return client


def test_search_game_exact_match():
    client = make_client()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": [
            {"id": "999", "name": "Schedule II"},
            {"id": "123", "name": "Schedule I"},
        ]
    }
    with patch.object(client._http, "get", return_value=mock_response):
        result = client.search_game("Schedule I")
    assert result is not None
    assert result["id"] == "123"
    assert result["name"] == "Schedule I"


def test_search_game_no_match():
    client = make_client()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": []}
    with patch.object(client._http, "get", return_value=mock_response):
        result = client.search_game("NonExistentGame12345")
    assert result is None


def test_get_live_stats_empty():
    client = make_client()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": []}
    with patch.object(client._http, "get", return_value=mock_response):
        stats = client.get_live_stats("123")
    assert stats["stream_count"] == 0
    assert stats["viewer_count"] == 0
    assert stats["top_language"] is None


def test_get_live_stats_aggregation():
    client = make_client()
    streams = [
        {"viewer_count": 100, "language": "en"},
        {"viewer_count": 50, "language": "en"},
        {"viewer_count": 30, "language": "de"},
    ]
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": streams, "pagination": {}}
    with patch.object(client._http, "get", return_value=mock_response):
        stats = client.get_live_stats("123")
    assert stats["stream_count"] == 3
    assert stats["viewer_count"] == 180
    assert stats["top_language"] == "en"
    assert stats["lang_distribution"] == {"en": 2, "de": 1}
```

- [ ] **Step 2: 테스트 실행**

Run: `cd steam-crawler && pytest tests/test_twitch.py -v`
Expected: All 4 tests PASS

- [ ] **Step 3: Commit**

```bash
git add steam-crawler/tests/test_twitch.py
git commit -m "test: add Twitch client unit tests"
```

---

### Task 9: 기존 데이터 Re-enrichment (RAWG 리텐션)

**Files:** 없음 (일회성 스크립트 실행)

- [ ] **Step 1: 기존 RAWG 데이터가 있는 게임에 대해 리텐션 필드 채우기**

기존에 `rawg_id`가 있지만 `rawg_added`가 NULL인 게임을 찾아 re-enrich:

```bash
cd steam-crawler && python -c "
from dotenv import load_dotenv; load_dotenv('../.env')
import os
from steam_crawler.db.schema import init_db
from steam_crawler.api.rawg import RAWGClient
from steam_crawler.db.repository import update_game_rawg_details

conn = init_db('../data/steam.db')
rk = os.getenv('RAWG_API_KEY')
client = RAWGClient(api_key=rk)

rows = conn.execute('''
    SELECT appid, name, rawg_id FROM games
    WHERE rawg_id IS NOT NULL AND rawg_id > 0 AND rawg_added IS NULL
''').fetchall()
print(f'Re-enriching {len(rows)} games...')

for r in rows:
    details = client.fetch_game_details(r['rawg_id'])
    if not details:
        continue
    abs_data = details.get('added_by_status') or {}
    ratings_data = details.get('ratings') or []
    rating_pcts = {}
    for rd in ratings_data:
        t = rd.get('title','')
        if t in ('exceptional','recommended','meh','skip'):
            rating_pcts[f'rawg_{t}_pct'] = rd.get('percent', 0.0)

    update_game_rawg_details(
        conn, appid=r['appid'], rawg_id=r['rawg_id'],
        rawg_description=details.get('description_raw'),
        rawg_rating=details.get('rating'),
        metacritic_score=details.get('metacritic'),
        rawg_ratings_count=details.get('ratings_count'),
        rawg_added=details.get('added'),
        rawg_status_yet=abs_data.get('yet'),
        rawg_status_owned=abs_data.get('owned'),
        rawg_status_beaten=abs_data.get('beaten'),
        rawg_status_toplay=abs_data.get('toplay'),
        rawg_status_dropped=abs_data.get('dropped'),
        rawg_status_playing=abs_data.get('playing'),
        rawg_exceptional_pct=rating_pcts.get('rawg_exceptional_pct'),
        rawg_recommended_pct=rating_pcts.get('rawg_recommended_pct'),
        rawg_meh_pct=rating_pcts.get('rawg_meh_pct'),
        rawg_skip_pct=rating_pcts.get('rawg_skip_pct'),
    )
    print(f'  {r[\"name\"]}: added={details.get(\"added\")}, dropped={abs_data.get(\"dropped\")}')

client.close()
print('Done')
"
```

- [ ] **Step 2: 결과 확인**

Run: `cd steam-crawler && python -c "
from steam_crawler.db.schema import init_db
conn=init_db('../data/steam.db')
rows=conn.execute('SELECT name, rawg_added, rawg_status_dropped, rawg_status_beaten, rawg_exceptional_pct FROM games WHERE rawg_added IS NOT NULL LIMIT 5').fetchall()
for r in rows: print(dict(r))
"`

Expected: 리텐션 필드에 값이 채워진 행
