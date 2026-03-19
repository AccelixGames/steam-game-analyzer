# Wikidata SPARQL Integration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wikidata SPARQL에서 게임 메카닉, 캐릭터, 배경, 테마, 수상 이력 등 기획 관련 구조화 데이터를 수집하여 인사이트 분석을 강화한다. 신규 테이블은 정규화(A 방식)로 설계하고, 기존 games 66컬럼은 건드리지 않는다.

**Architecture:** `game_wikidata_claims` 단일 테이블로 Wikidata의 다중값 데이터(mechanics, characters, locations, depicts, awards)를 통합 저장. claim_type 컬럼으로 구분. Steam AppID(P1733)로 직접 조회하므로 이름 매칭 불필요.

**Tech Stack:** Python 3.12+, curl_cffi, SQLite, Wikidata SPARQL endpoint

---

## 설계 결정 사항

### DB 스키마 방향
- **신규 추가**: 정규화 테이블 분리 (A 방식)
- **기존 games 테이블**: 변경 없음 (향후 리팩토링 대상)
- **Wikidata 다중값**: `game_wikidata_claims` 하나로 통합 (데이터 규모가 작아 분리 불필요)

### game_wikidata_claims 테이블 설계

```sql
CREATE TABLE IF NOT EXISTS game_wikidata_claims (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    appid       INTEGER NOT NULL REFERENCES games(appid),
    claim_type  TEXT NOT NULL,     -- 'genre', 'mechanic', 'character', 'location',
                                   -- 'depicts', 'award', 'nominated', 'input_device'
    name        TEXT NOT NULL,     -- human-readable label (English)
    wikidata_id TEXT,              -- Q-ID (e.g., 'Q867123' for open world)
    property_id TEXT,              -- P-ID (e.g., 'P4151' for game mechanic)
    extra       TEXT,              -- optional JSON for additional data
    fetched_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(appid, claim_type, wikidata_id)
);

CREATE INDEX IF NOT EXISTS idx_wdc_appid ON game_wikidata_claims(appid);
CREATE INDEX IF NOT EXISTS idx_wdc_type ON game_wikidata_claims(claim_type);
CREATE INDEX IF NOT EXISTS idx_wdc_name ON game_wikidata_claims(name);
```

### games 테이블 확장 (스칼라 값만)

```sql
-- _migrate()에 추가
("wikidata_id", "TEXT"),          -- Q-ID (e.g., 'Q63952889')
("wikidata_fetched_at", "TIMESTAMP"),
```

### claim_type → Wikidata Property 매핑

| claim_type | Property | 예시 |
|------------|----------|------|
| `genre` | P136 | roguelike, ARPG, management sim |
| `mechanic` | P4151 | open world, crafting, permadeath, fishing minigame |
| `character` | P674 | Zeus, Zagreus, Megaera |
| `location` | P840 | Tartarus, Elysium, Greek underworld |
| `depicts` | P180 | Greek mythology, LGBTQ character |
| `award` | P166 | BAFTA Game Design, Hugo Award |
| `nominated` | P1411 | TGA Game of the Year, Steam Award |
| `input_device` | P479 | keyboard, mouse, controller |
| `game_mode` | P404 | single-player, co-op |
| `characteristic` | P1552 | indie game |

---

## File Structure

| Action | File | Responsibility |
|--------|------|---------------|
| Modify | `steam-crawler/src/steam_crawler/db/schema.py` | `game_wikidata_claims` 테이블 + games에 wikidata_id 컬럼 |
| Modify | `steam-crawler/src/steam_crawler/db/repository.py` | wikidata claims CRUD + get_games_needing_enrichment 확장 |
| Create | `steam-crawler/src/steam_crawler/api/wikidata.py` | Wikidata SPARQL 클라이언트 |
| Create | `steam-crawler/src/steam_crawler/pipeline/step1l_wikidata.py` | Wikidata enrichment 파이프라인 스텝 |
| Modify | `steam-crawler/src/steam_crawler/pipeline/runner.py` | step1l 통합 |
| Create | `steam-crawler/tests/test_wikidata.py` | Wikidata 클라이언트 테스트 |
| Modify | `.claude/skills/steam-insight/SKILL.md` | Wikidata 쿼리 추가 |

---

## Task 1: DB 스키마 — game_wikidata_claims 테이블 + games.wikidata_id

**Files:**
- Modify: `steam-crawler/src/steam_crawler/db/schema.py`

- [ ] **Step 1: SCHEMA_SQL에 game_wikidata_claims 테이블 추가**

external_reviews 테이블 다음에 추가:

```sql
CREATE TABLE IF NOT EXISTS game_wikidata_claims (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    appid       INTEGER NOT NULL REFERENCES games(appid),
    claim_type  TEXT NOT NULL,
    name        TEXT NOT NULL,
    wikidata_id TEXT,
    property_id TEXT,
    extra       TEXT,
    fetched_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(appid, claim_type, wikidata_id)
);

CREATE INDEX IF NOT EXISTS idx_wdc_appid ON game_wikidata_claims(appid);
CREATE INDEX IF NOT EXISTS idx_wdc_type ON game_wikidata_claims(claim_type);
CREATE INDEX IF NOT EXISTS idx_wdc_name ON game_wikidata_claims(name);
```

- [ ] **Step 2: _migrate()에 wikidata 스칼라 컬럼 추가**

```python
        # Wikidata
        ("wikidata_id", "TEXT"),
        ("wikidata_fetched_at", "TIMESTAMP"),
```

- [ ] **Step 3: 마이그레이션 확인**

```bash
cd steam-crawler && python -c "
from steam_crawler.db.schema import init_db
conn = init_db('../data/steam.db')
tables = [r[0] for r in conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()]
print('game_wikidata_claims:', 'game_wikidata_claims' in tables)
cols = [r[1] for r in conn.execute('PRAGMA table_info(games)').fetchall() if 'wikidata' in r[1]]
print('wikidata columns:', cols)
"
```

- [ ] **Step 4: Commit**

```bash
git add steam-crawler/src/steam_crawler/db/schema.py
git commit -m "feat: add game_wikidata_claims table + wikidata_id column"
```

---

## Task 2: Repository — Wikidata claims CRUD

**Files:**
- Modify: `steam-crawler/src/steam_crawler/db/repository.py`

- [ ] **Step 1: upsert_wikidata_claims 함수**

```python
def upsert_wikidata_claims(
    conn: sqlite3.Connection,
    appid: int,
    claims: list[dict],
) -> int:
    """Insert or update Wikidata claims for a game.

    Each claim dict: {claim_type, name, wikidata_id, property_id, extra?}
    Returns count inserted/updated.
    """
    now = _now()
    count = 0
    for claim in claims:
        conn.execute(
            """INSERT INTO game_wikidata_claims
               (appid, claim_type, name, wikidata_id, property_id, extra, fetched_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(appid, claim_type, wikidata_id) DO UPDATE SET
                   name=excluded.name, extra=excluded.extra, fetched_at=excluded.fetched_at""",
            (appid, claim["claim_type"], claim["name"],
             claim.get("wikidata_id"), claim.get("property_id"),
             claim.get("extra"), now),
        )
        count += 1
    conn.commit()
    return count


def get_wikidata_claims(
    conn: sqlite3.Connection,
    appid: int,
    claim_type: str | None = None,
) -> list[dict]:
    """Get Wikidata claims for a game, optionally filtered by type."""
    if claim_type:
        rows = conn.execute(
            "SELECT * FROM game_wikidata_claims WHERE appid=? AND claim_type=? ORDER BY name",
            (appid, claim_type),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM game_wikidata_claims WHERE appid=? ORDER BY claim_type, name",
            (appid,),
        ).fetchall()
    return [dict(r) for r in rows]


def update_game_wikidata(
    conn: sqlite3.Connection,
    appid: int,
    wikidata_id: str,
) -> None:
    """Update Wikidata Q-ID and fetch timestamp on games table."""
    conn.execute(
        "UPDATE games SET wikidata_id=?, wikidata_fetched_at=?, updated_at=? WHERE appid=?",
        (wikidata_id, _now(), _now(), appid),
    )
    conn.commit()
```

- [ ] **Step 2: get_games_needing_enrichment에 wikidata 추가**

```python
    id_col_map = {
        ...
        "wikidata": "wikidata_id",
    }
```

- [ ] **Step 3: Commit**

```bash
git add steam-crawler/src/steam_crawler/db/repository.py
git commit -m "feat: add Wikidata claims repository functions"
```

---

## Task 3: Wikidata SPARQL 클라이언트

**Files:**
- Create: `steam-crawler/src/steam_crawler/api/wikidata.py`

- [ ] **Step 1: WikidataClient 작성**

```python
"""Wikidata SPARQL client — structured game design data."""

from __future__ import annotations

import time

from steam_crawler.api.base import BaseClient
from steam_crawler.api.rate_limiter import AdaptiveRateLimiter

# Wikidata property IDs for game-design-relevant claims
DESIGN_PROPERTIES = {
    "P136": "genre",
    "P4151": "mechanic",
    "P674": "character",
    "P840": "location",
    "P180": "depicts",
    "P404": "game_mode",
    "P479": "input_device",
    "P1552": "characteristic",
    "P166": "award",
    "P1411": "nominated",
}


class WikidataClient(BaseClient):
    """Fetches game design data from Wikidata SPARQL endpoint."""

    SPARQL_URL = "https://query.wikidata.org/sparql"

    def __init__(self, rate_limiter: AdaptiveRateLimiter | None = None):
        super().__init__(rate_limiter=rate_limiter, timeout=30.0)
        self._headers = {
            "Accept": "application/json",
            "User-Agent": "steam-game-analyzer/1.0 (game design research)",
        }

    def fetch_by_steam_appid(self, appid: int) -> dict | None:
        """Fetch all design-relevant claims for a Steam game.

        Uses Steam AppID (P1733) to find the Wikidata item, then queries
        all design-relevant properties in a single SPARQL query.

        Returns dict: {
            "wikidata_id": "Q...",
            "claims": [
                {"claim_type": "genre", "name": "roguelite", "wikidata_id": "Q...", "property_id": "P136"},
                ...
            ]
        } or None if not found.
        """
        prop_values = " ".join(f"wdt:{pid}" for pid in DESIGN_PROPERTIES)

        query = f'''
        SELECT ?game ?prop ?val ?valLabel WHERE {{
          ?game wdt:P1733 "{appid}" .
          ?game ?prop ?val .
          VALUES ?prop {{ {prop_values} }}
          ?property wikibase:directClaim ?prop .
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" }}
        }}
        '''

        response = self.get(
            self.SPARQL_URL,
            params={"format": "json", "query": query},
            headers=self._headers,
        )

        if response.status_code != 200:
            return None

        data = response.json()
        bindings = data.get("results", {}).get("bindings", [])

        if not bindings:
            return None

        # Extract Wikidata Q-ID from game URI
        game_uri = bindings[0].get("game", {}).get("value", "")
        wikidata_id = game_uri.split("/")[-1] if game_uri else None

        claims = []
        for row in bindings:
            prop_uri = row.get("prop", {}).get("value", "")
            pid = prop_uri.split("/")[-1]
            claim_type = DESIGN_PROPERTIES.get(pid, pid)

            val_uri = row.get("val", {}).get("value", "")
            val_qid = val_uri.split("/")[-1] if "/entity/" in val_uri else None
            val_label = row.get("valLabel", {}).get("value", val_qid or "")

            claims.append({
                "claim_type": claim_type,
                "name": val_label,
                "wikidata_id": val_qid,
                "property_id": pid,
            })

        return {
            "wikidata_id": wikidata_id,
            "claims": claims,
        }
```

- [ ] **Step 2: 동작 확인 (Hades AppID 1145360)**

```bash
cd steam-crawler && python -c "
from steam_crawler.api.wikidata import WikidataClient
c = WikidataClient()
result = c.fetch_by_steam_appid(1145360)
print(f'Wikidata ID: {result[\"wikidata_id\"]}')
print(f'Claims: {len(result[\"claims\"])}')
for claim in result['claims'][:15]:
    print(f'  [{claim[\"claim_type\"]}] {claim[\"name\"]} ({claim[\"wikidata_id\"]})')
c.close()
"
```

Expected: wikidata_id + 40+ claims (genre, mechanic, characters, locations, awards...)

- [ ] **Step 3: Commit**

```bash
git add steam-crawler/src/steam_crawler/api/wikidata.py
git commit -m "feat: add Wikidata SPARQL client for game design data"
```

---

## Task 4: step1l_wikidata 파이프라인 스텝

**Files:**
- Create: `steam-crawler/src/steam_crawler/pipeline/step1l_wikidata.py`

- [ ] **Step 1: step1l 작성**

```python
"""Step 1l: Enrich games with Wikidata structured design data."""
from __future__ import annotations

import sqlite3

from rich.console import Console

from steam_crawler.api.wikidata import WikidataClient
from steam_crawler.api.rate_limiter import AdaptiveRateLimiter
from steam_crawler.api.resilience import FailureTracker
from steam_crawler.db.repository import (
    get_games_needing_enrichment,
    update_game_wikidata,
    upsert_wikidata_claims,
)

console = Console()


def run_step1l(
    conn: sqlite3.Connection,
    version: int,
    source_tag: str | None = None,
    wikidata_client: WikidataClient | None = None,
    failure_tracker: FailureTracker | None = None,
    lock_owner: str | None = None,
) -> int:
    """Enrich games with Wikidata claims. Returns count enriched."""
    client = wikidata_client or WikidataClient(
        rate_limiter=AdaptiveRateLimiter(api_name="wikidata", default_delay_ms=2000)
    )
    tracker = failure_tracker or FailureTracker()
    games = get_games_needing_enrichment(
        conn, source="wikidata", source_tag=source_tag, lock_owner=lock_owner
    )
    enriched = 0

    if not games:
        console.print("[dim]Step 1l: No games need Wikidata enrichment[/dim]")
        return 0

    console.print(f"[bold]Step 1l:[/bold] Enriching {len(games)} games from Wikidata")

    try:
        for game_row in games:
            appid = game_row["appid"]
            name = game_row["name"]
            try:
                result = client.fetch_by_steam_appid(appid)
                if result is None:
                    # Mark as checked but not found
                    update_game_wikidata(conn, appid=appid, wikidata_id="not_found")
                    continue

                # Save Wikidata Q-ID
                update_game_wikidata(conn, appid=appid, wikidata_id=result["wikidata_id"])

                # Save all claims
                if result["claims"]:
                    upsert_wikidata_claims(conn, appid=appid, claims=result["claims"])

                claim_types = set(c["claim_type"] for c in result["claims"])
                console.print(
                    f"  [green]{name}[/green]: {len(result['claims'])} claims "
                    f"({', '.join(sorted(claim_types))})"
                )
                enriched += 1

            except Exception as e:
                tracker.log_failure(
                    conn=conn, session_id=version, api_name="wikidata",
                    appid=appid, step="step1l", error_message=str(e),
                )
                console.print(f"  [red]Wikidata error for {name} ({appid}): {e}[/red]")
                continue

        console.print(
            f"[green]Step 1l complete:[/green] {enriched}/{len(games)} games enriched from Wikidata"
        )
        return enriched
    finally:
        if wikidata_client is None:
            client.close()
```

- [ ] **Step 2: Commit**

```bash
git add steam-crawler/src/steam_crawler/pipeline/step1l_wikidata.py
git commit -m "feat: add Wikidata enrichment pipeline step (step1l)"
```

---

## Task 5: Pipeline Runner — step1l 통합

**Files:**
- Modify: `steam-crawler/src/steam_crawler/pipeline/runner.py`

- [ ] **Step 1: import + 호출 추가**

import 추가:
```python
from steam_crawler.pipeline.step1l_wikidata import run_step1l
```

step1k 호출 다음에 추가:
```python
            # Step 1l: Wikidata structured design data (no auth needed)
            run_step1l(
                conn, version, source_tag=source_tag,
                failure_tracker=tracker, lock_owner=lock_owner,
            )
```

- [ ] **Step 2: Commit**

```bash
git add steam-crawler/src/steam_crawler/pipeline/runner.py
git commit -m "feat: integrate step1l Wikidata into pipeline runner"
```

---

## Task 6: 단위 테스트

**Files:**
- Create: `steam-crawler/tests/test_wikidata.py`

- [ ] **Step 1: WikidataClient 테스트 작성**

```python
"""Tests for Wikidata SPARQL client."""
from unittest.mock import MagicMock, patch
from steam_crawler.api.wikidata import WikidataClient


def test_fetch_by_appid_success():
    client = WikidataClient()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "results": {
            "bindings": [
                {
                    "game": {"value": "http://www.wikidata.org/entity/Q63952889"},
                    "prop": {"value": "http://www.wikidata.org/prop/direct/P136"},
                    "val": {"value": "http://www.wikidata.org/entity/Q60053"},
                    "valLabel": {"value": "roguelite"},
                },
                {
                    "game": {"value": "http://www.wikidata.org/entity/Q63952889"},
                    "prop": {"value": "http://www.wikidata.org/prop/direct/P4151"},
                    "val": {"value": "http://www.wikidata.org/entity/Q22808320"},
                    "valLabel": {"value": "fishing minigame"},
                },
                {
                    "game": {"value": "http://www.wikidata.org/entity/Q63952889"},
                    "prop": {"value": "http://www.wikidata.org/prop/direct/P674"},
                    "val": {"value": "http://www.wikidata.org/entity/Q41410"},
                    "valLabel": {"value": "Zeus"},
                },
            ]
        }
    }
    with patch.object(client, "get", return_value=mock_resp):
        result = client.fetch_by_steam_appid(1145360)

    assert result is not None
    assert result["wikidata_id"] == "Q63952889"
    assert len(result["claims"]) == 3

    types = {c["claim_type"] for c in result["claims"]}
    assert "genre" in types
    assert "mechanic" in types
    assert "character" in types

    genre = [c for c in result["claims"] if c["claim_type"] == "genre"][0]
    assert genre["name"] == "roguelite"
    assert genre["wikidata_id"] == "Q60053"


def test_fetch_by_appid_not_found():
    client = WikidataClient()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"results": {"bindings": []}}
    with patch.object(client, "get", return_value=mock_resp):
        result = client.fetch_by_steam_appid(999999999)
    assert result is None


def test_fetch_by_appid_http_error():
    client = WikidataClient()
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    with patch.object(client, "get", return_value=mock_resp):
        result = client.fetch_by_steam_appid(1145360)
    assert result is None
```

- [ ] **Step 2: 테스트 실행**

```bash
cd steam-crawler && pytest tests/test_wikidata.py -v
```

- [ ] **Step 3: Commit**

```bash
git add steam-crawler/tests/test_wikidata.py
git commit -m "test: add Wikidata SPARQL client unit tests"
```

---

## Task 7: 인사이트 스킬 — Wikidata 쿼리 추가

**Files:**
- Modify: `.claude/skills/steam-insight/SKILL.md`

- [ ] **Step 1: 2단계에 Wikidata 쿼리 추가**

2-B (IGDB 구조화 메타데이터) 다음에 새 섹션 추가:

```markdown
### 2-C. Wikidata 구조화 기획 데이터

Wikidata의 커뮤니티 온톨로지에서 추출한 구조화된 기획 데이터. IGDB/Steam과 독립적인 제3의 분류 체계.

\```sql
-- Wikidata 기본 정보
SELECT wikidata_id FROM games WHERE appid = ?;

-- 전체 claims (mechanic, character, location, depicts, award 등)
SELECT claim_type, name, wikidata_id
FROM game_wikidata_claims WHERE appid = ?
ORDER BY claim_type, name;
\```

분석 포인트:
- **Wikidata genre vs Steam tags vs IGDB keywords 3중 교차**: 세 소스에서 공통으로 나타나는 분류는 게임의 확실한 정체성, 하나에만 있는 것은 관점 차이
- **P4151 mechanic**: open world, crafting, permadeath 등 구조화된 메카닉 분류. Steam 태그보다 정밀한 기획 패턴 식별
- **P674 character**: 등장인물 수와 목록 → 내러티브 규모 측정
- **P840 location**: 배경 세계 구조 → 레벨/맵 디자인 규모
- **P166/P1411 award**: 수상 이력 → 어떤 기획 요소가 업계에서 인정받았는지 (Best Design, Best Narrative 등 카테고리별 의미)
- **P180 depicts**: 게임이 다루는 주제/소재 (mythology, LGBTQ 등) → 문화적 포지셔닝
- wikidata_id가 NULL 또는 'not_found'이면 "Wikidata 데이터 없음" 명시
```

- [ ] **Step 2: 보고서 구조에 반영**

Step 02 메커니즘 실체 섹션에 추가:
```
├── Wikidata 기획 온톨로지 — 메카닉/캐릭터/배경/수상 (NEW)
```

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/steam-insight/SKILL.md
git commit -m "feat: add Wikidata claims queries to insight skill"
```

---

## Summary: 완성 후 파이프라인

```
Step 1   SteamSpy 게임 수집
Step 1b  SteamSpy 태그/장르 보강
Step 1c  Steam Store 상세 설명
Step 1d  IGDB themes/keywords/rating
Step 1e  RAWG description/ratings/retention
Step 1f  Twitch 스트리밍 데이터
Step 1g  ProtonDB 호환성 (Phase 2)
Step 1h  HowLongToBeat 게임 길이 (Phase 2)
Step 1i  CheapShark 딜/가격 (Phase 2)
Step 1j  OpenCritic 전문가 평가 (Phase 2)
Step 1k  PCGamingWiki 기술 스펙 (Phase 2)
Step 1l  Wikidata 기획 온톨로지 (NEW) ← 인증 불필요
Step 2   Steam 리뷰 요약 스캔
Step 3   Steam 리뷰 본문 크롤링
```

## 향후 리팩토링 메모

games 테이블 66컬럼 → 정규화 분리 대상:
- `game_igdb` (igdb_id, summary, storyline, rating)
- `game_rawg` (rawg_id, description, rating, metacritic, 15개 status/pct 컬럼)
- `game_twitch` (twitch_game_id, stream_count, viewer_count, ...)
- `game_protondb` (tier, confidence, trending_tier, report_count)
- `game_hltb` (hltb_id, main_story, main_extra, completionist)
- `game_cheapshark` (deal_rating, lowest_price, lowest_price_date)
- `game_opencritic` (opencritic_id, score, pct_recommend, tier, review_count)
- `game_pcgamingwiki` (engine, has_ultrawide, has_hdr, has_controller, graphics_api)

이 리팩토링은 별도 플랜으로 진행. 기존 코드(repository.py, step1c~1k, insight SKILL.md)의 SQL 쿼리를 모두 수정해야 하므로 규모가 큼.
