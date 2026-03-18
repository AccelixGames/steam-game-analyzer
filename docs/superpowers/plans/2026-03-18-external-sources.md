# External Game Data Sources (IGDB + RAWG) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enrich Steam game data with IGDB summaries/themes/keywords and RAWG descriptions/Metacritic scores via new pipeline steps 1d/1e.

**Architecture:** Two new pipeline steps (step1d_igdb, step1e_rawg) follow the existing step1c pattern. Each uses a dedicated API client, a shared GameMatcher for Steam-to-external-ID resolution, and stores results via the existing repository/catalog pattern.

**Tech Stack:** Python 3.12+, httpx, difflib, pytest, pytest-httpx, SQLite

**Spec:** `docs/superpowers/specs/2026-03-18-external-sources-design.md`

---

### Task 1: Schema — Add columns and tables

**Files:**
- Modify: `steam-crawler/src/steam_crawler/db/schema.py`
- Test: `steam-crawler/tests/test_schema.py`

- [ ] **Step 1: Write failing test for new columns and tables**

```python
# In steam-crawler/tests/test_schema.py — add these tests

def test_games_has_igdb_columns(db_conn):
    """games table has IGDB enrichment columns."""
    row = db_conn.execute("PRAGMA table_info(games)").fetchall()
    col_names = [r["name"] for r in row]
    assert "igdb_id" in col_names
    assert "igdb_summary" in col_names
    assert "igdb_storyline" in col_names
    assert "igdb_rating" in col_names


def test_games_has_rawg_columns(db_conn):
    """games table has RAWG enrichment columns."""
    row = db_conn.execute("PRAGMA table_info(games)").fetchall()
    col_names = [r["name"] for r in row]
    assert "rawg_id" in col_names
    assert "rawg_description" in col_names
    assert "rawg_rating" in col_names
    assert "metacritic_score" in col_names


def test_theme_catalog_table_exists(db_conn):
    """theme_catalog and game_themes tables exist with correct schema."""
    db_conn.execute("INSERT INTO theme_catalog (id, name) VALUES (1, 'Horror')")
    db_conn.execute("INSERT INTO games (appid, name) VALUES (730, 'CS2')")
    db_conn.execute(
        "INSERT INTO game_themes (appid, theme_id, source) VALUES (730, 1, 'igdb')"
    )
    db_conn.commit()
    row = db_conn.execute("SELECT * FROM game_themes WHERE appid=730").fetchone()
    assert row["theme_id"] == 1
    assert row["source"] == "igdb"


def test_keyword_catalog_table_exists(db_conn):
    """keyword_catalog and game_keywords tables exist with correct schema."""
    db_conn.execute("INSERT INTO keyword_catalog (id, name) VALUES (1, 'roguelike')")
    db_conn.execute("INSERT INTO games (appid, name) VALUES (730, 'CS2')")
    db_conn.execute(
        "INSERT INTO game_keywords (appid, keyword_id, source) VALUES (730, 1, 'igdb')"
    )
    db_conn.commit()
    row = db_conn.execute("SELECT * FROM game_keywords WHERE appid=730").fetchone()
    assert row["keyword_id"] == 1


```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd steam-crawler && python -m pytest tests/test_schema.py -v -k "igdb or rawg or theme or keyword"`
Expected: FAIL — columns/tables don't exist yet

- [ ] **Step 3: Add schema changes**

In `steam-crawler/src/steam_crawler/db/schema.py`, add to the `games` CREATE TABLE (before `source_tag`):

```sql
    igdb_id          INTEGER,
    igdb_summary     TEXT,
    igdb_storyline   TEXT,
    igdb_rating      REAL,
    rawg_id          INTEGER,
    rawg_description TEXT,
    rawg_rating      REAL,
    metacritic_score INTEGER,
```

Add new tables after `game_media`:

```sql
CREATE TABLE IF NOT EXISTS theme_catalog (
    id   INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS game_themes (
    appid    INTEGER NOT NULL,
    theme_id INTEGER NOT NULL,
    source   TEXT NOT NULL DEFAULT 'igdb',
    PRIMARY KEY (appid, theme_id),
    FOREIGN KEY (appid) REFERENCES games(appid),
    FOREIGN KEY (theme_id) REFERENCES theme_catalog(id)
);

CREATE INDEX IF NOT EXISTS idx_game_themes_theme ON game_themes(theme_id);

CREATE TABLE IF NOT EXISTS keyword_catalog (
    id   INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS game_keywords (
    appid      INTEGER NOT NULL,
    keyword_id INTEGER NOT NULL,
    source     TEXT NOT NULL DEFAULT 'igdb',
    PRIMARY KEY (appid, keyword_id),
    FOREIGN KEY (appid) REFERENCES games(appid),
    FOREIGN KEY (keyword_id) REFERENCES keyword_catalog(id)
);

CREATE INDEX IF NOT EXISTS idx_game_keywords_keyword ON game_keywords(keyword_id);

CREATE INDEX IF NOT EXISTS idx_games_igdb_id ON games(igdb_id);
CREATE INDEX IF NOT EXISTS idx_games_rawg_id ON games(rawg_id);
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd steam-crawler && python -m pytest tests/test_schema.py -v`
Expected: ALL PASS

- [ ] **Step 5: Run full test suite to check no regressions**

Run: `cd steam-crawler && python -m pytest -v`
Expected: ALL PASS (existing tests should not break because new columns have no NOT NULL constraints and existing INSERTs don't touch them)

- [ ] **Step 6: Commit**

```bash
cd steam-crawler
git add src/steam_crawler/db/schema.py tests/test_schema.py
git commit -m "feat: add IGDB/RAWG columns, theme/keyword catalog tables to schema"
```

---

### Task 2: Repository — IGDB/RAWG upsert functions

**Files:**
- Modify: `steam-crawler/src/steam_crawler/db/repository.py`
- Test: `steam-crawler/tests/test_repository.py`

- [ ] **Step 1: Write failing tests for new repository functions**

```python
# Add to steam-crawler/tests/test_repository.py

def _insert_game(db_conn, appid=730, name="CS2"):
    """Helper to insert a game for FK constraints."""
    db_conn.execute(
        "INSERT INTO games (appid, name) VALUES (?, ?)", (appid, name)
    )
    db_conn.commit()


def test_update_game_igdb_details(db_conn):
    from steam_crawler.db.repository import update_game_igdb_details

    _insert_game(db_conn)
    update_game_igdb_details(
        db_conn, appid=730, igdb_id=12345,
        igdb_summary="A tactical shooter", igdb_storyline="Counter-terrorists vs terrorists",
        igdb_rating=85.5,
    )
    row = db_conn.execute("SELECT * FROM games WHERE appid=730").fetchone()
    assert row["igdb_id"] == 12345
    assert row["igdb_summary"] == "A tactical shooter"
    assert row["igdb_storyline"] == "Counter-terrorists vs terrorists"
    assert row["igdb_rating"] == 85.5


def test_update_game_rawg_details(db_conn):
    from steam_crawler.db.repository import update_game_rawg_details

    _insert_game(db_conn)
    update_game_rawg_details(
        db_conn, appid=730, rawg_id=4200,
        rawg_description="A detailed description of the game",
        rawg_rating=4.2, metacritic_score=83,
    )
    row = db_conn.execute("SELECT * FROM games WHERE appid=730").fetchone()
    assert row["rawg_id"] == 4200
    assert row["rawg_description"] == "A detailed description of the game"
    assert row["rawg_rating"] == 4.2
    assert row["metacritic_score"] == 83


def test_upsert_game_themes(db_conn):
    from steam_crawler.db.repository import upsert_game_themes

    _insert_game(db_conn)
    themes = {1: "Horror", 2: "Survival"}
    count = upsert_game_themes(db_conn, appid=730, themes=themes)
    assert count == 2
    rows = db_conn.execute(
        "SELECT t.name FROM game_themes gt JOIN theme_catalog t ON gt.theme_id=t.id WHERE gt.appid=730"
    ).fetchall()
    names = {r["name"] for r in rows}
    assert names == {"Horror", "Survival"}


def test_upsert_game_themes_auto_creates_catalog(db_conn):
    """Themes are auto-created in theme_catalog if they don't exist."""
    from steam_crawler.db.repository import upsert_game_themes

    _insert_game(db_conn)
    upsert_game_themes(db_conn, appid=730, themes={99: "NewTheme"})
    cat = db_conn.execute("SELECT * FROM theme_catalog WHERE id=99").fetchone()
    assert cat["name"] == "NewTheme"


def test_upsert_game_keywords(db_conn):
    from steam_crawler.db.repository import upsert_game_keywords

    _insert_game(db_conn)
    keywords = {10: "roguelike", 20: "procedural"}
    count = upsert_game_keywords(db_conn, appid=730, keywords=keywords)
    assert count == 2
    rows = db_conn.execute(
        "SELECT k.name FROM game_keywords gk JOIN keyword_catalog k ON gk.keyword_id=k.id WHERE gk.appid=730"
    ).fetchall()
    names = {r["name"] for r in rows}
    assert names == {"roguelike", "procedural"}


def test_get_games_needing_igdb(db_conn):
    from steam_crawler.db.repository import get_games_needing_enrichment

    _insert_game(db_conn, appid=730, name="CS2")
    _insert_game(db_conn, appid=570, name="Dota 2")
    # Mark 730 as already having igdb_id
    db_conn.execute("UPDATE games SET igdb_id=12345 WHERE appid=730")
    db_conn.commit()
    games = get_games_needing_enrichment(db_conn, source="igdb")
    appids = [g["appid"] for g in games]
    assert 570 in appids
    assert 730 not in appids


def test_get_games_needing_rawg(db_conn):
    from steam_crawler.db.repository import get_games_needing_enrichment

    _insert_game(db_conn, appid=730, name="CS2")
    _insert_game(db_conn, appid=570, name="Dota 2")
    db_conn.execute("UPDATE games SET rawg_id=4200 WHERE appid=730")
    db_conn.commit()
    games = get_games_needing_enrichment(db_conn, source="rawg")
    appids = [g["appid"] for g in games]
    assert 570 in appids
    assert 730 not in appids


def test_get_games_needing_enrichment_excludes_unmatchable(db_conn):
    """Games with id=-1 (unmatchable) are excluded."""
    from steam_crawler.db.repository import get_games_needing_enrichment

    _insert_game(db_conn, appid=730, name="CS2")
    db_conn.execute("UPDATE games SET igdb_id=-1 WHERE appid=730")
    db_conn.commit()
    games = get_games_needing_enrichment(db_conn, source="igdb")
    assert len(games) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd steam-crawler && python -m pytest tests/test_repository.py -v -k "igdb or rawg or theme or keyword or enrichment"`
Expected: FAIL — functions don't exist yet

- [ ] **Step 3: Implement repository functions**

Add to `steam-crawler/src/steam_crawler/db/repository.py`:

```python
def update_game_igdb_details(
    conn: sqlite3.Connection,
    appid: int,
    igdb_id: int,
    igdb_summary: str | None = None,
    igdb_storyline: str | None = None,
    igdb_rating: float | None = None,
) -> None:
    """Update IGDB enrichment data on the games table."""
    conn.execute(
        "UPDATE games SET igdb_id=?, igdb_summary=?, igdb_storyline=?, igdb_rating=?, updated_at=? WHERE appid=?",
        (igdb_id, igdb_summary, igdb_storyline, igdb_rating, _now(), appid),
    )
    conn.commit()


def update_game_rawg_details(
    conn: sqlite3.Connection,
    appid: int,
    rawg_id: int,
    rawg_description: str | None = None,
    rawg_rating: float | None = None,
    metacritic_score: int | None = None,
) -> None:
    """Update RAWG enrichment data on the games table."""
    conn.execute(
        "UPDATE games SET rawg_id=?, rawg_description=?, rawg_rating=?, metacritic_score=?, updated_at=? WHERE appid=?",
        (rawg_id, rawg_description, rawg_rating, metacritic_score, _now(), appid),
    )
    conn.commit()


def upsert_game_themes(conn: sqlite3.Connection, appid: int, themes: dict[int, str]) -> int:
    """Insert or replace game themes. themes = {igdb_theme_id: theme_name}.
    Auto-creates theme_catalog entries. Returns count inserted."""
    inserted = 0
    for theme_id, theme_name in themes.items():
        conn.execute(
            "INSERT OR REPLACE INTO theme_catalog (id, name) VALUES (?, ?)",
            (theme_id, theme_name),
        )
        conn.execute(
            "INSERT OR REPLACE INTO game_themes (appid, theme_id, source) VALUES (?, ?, 'igdb')",
            (appid, theme_id),
        )
        inserted += 1
    conn.commit()
    return inserted


def upsert_game_keywords(conn: sqlite3.Connection, appid: int, keywords: dict[int, str]) -> int:
    """Insert or replace game keywords. keywords = {igdb_keyword_id: keyword_name}.
    Auto-creates keyword_catalog entries. Returns count inserted."""
    inserted = 0
    for keyword_id, keyword_name in keywords.items():
        conn.execute(
            "INSERT OR REPLACE INTO keyword_catalog (id, name) VALUES (?, ?)",
            (keyword_id, keyword_name),
        )
        conn.execute(
            "INSERT OR REPLACE INTO game_keywords (appid, keyword_id, source) VALUES (?, ?, 'igdb')",
            (appid, keyword_id),
        )
        inserted += 1
    conn.commit()
    return inserted


def get_games_needing_enrichment(
    conn: sqlite3.Connection, source: str, source_tag: str | None = None,
) -> list[dict]:
    """Return games that haven't been enriched by the given source.
    source: 'igdb' or 'rawg'. Excludes id=-1 (unmatchable)."""
    id_col = "igdb_id" if source == "igdb" else "rawg_id"
    if source_tag:
        rows = conn.execute(
            f"SELECT appid, name FROM games WHERE ({id_col} IS NULL) AND source_tag = ? ORDER BY positive DESC",
            (source_tag,),
        ).fetchall()
    else:
        rows = conn.execute(
            f"SELECT appid, name FROM games WHERE ({id_col} IS NULL) ORDER BY positive DESC"
        ).fetchall()
    return [dict(r) for r in rows]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd steam-crawler && python -m pytest tests/test_repository.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
cd steam-crawler
git add src/steam_crawler/db/repository.py tests/test_repository.py
git commit -m "feat: add IGDB/RAWG repository functions (upsert, themes, keywords)"
```

---

### Task 3: GameMatcher — name similarity matching

**Files:**
- Create: `steam-crawler/src/steam_crawler/api/matching.py`
- Test: `steam-crawler/tests/test_matching.py`

- [ ] **Step 1: Write failing tests**

```python
# steam-crawler/tests/test_matching.py
from steam_crawler.api.matching import GameMatcher


def test_name_similarity_exact():
    m = GameMatcher()
    assert m.name_similarity("Hades", "Hades") == 1.0


def test_name_similarity_case_insensitive():
    m = GameMatcher()
    assert m.name_similarity("hades", "Hades") == 1.0


def test_name_similarity_partial():
    m = GameMatcher()
    score = m.name_similarity("Slay the Spire", "Slay the Spire: Downfall")
    assert 0.6 < score < 1.0


def test_name_similarity_unrelated():
    m = GameMatcher()
    score = m.name_similarity("Hades", "Grand Theft Auto V")
    assert score < 0.5


def test_best_match_above_threshold():
    m = GameMatcher()
    candidates = [
        {"id": 1, "name": "Hades"},
        {"id": 2, "name": "Hades II"},
        {"id": 3, "name": "Stardew Valley"},
    ]
    result = m.best_match("Hades", candidates)
    assert result is not None
    assert result["id"] == 1


def test_best_match_returns_none_below_threshold():
    m = GameMatcher()
    candidates = [
        {"id": 1, "name": "Completely Different Game"},
        {"id": 2, "name": "Another Unrelated Title"},
    ]
    result = m.best_match("Hades", candidates)
    assert result is None


def test_best_match_empty_candidates():
    m = GameMatcher()
    result = m.best_match("Hades", [])
    assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd steam-crawler && python -m pytest tests/test_matching.py -v`
Expected: FAIL — module doesn't exist

- [ ] **Step 3: Implement GameMatcher**

```python
# steam-crawler/src/steam_crawler/api/matching.py
"""Game name matching utilities for cross-source ID resolution."""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any


class GameMatcher:
    """Matches games across sources using name similarity."""

    SIMILARITY_THRESHOLD = 0.8

    def name_similarity(self, a: str, b: str) -> float:
        """Compute similarity ratio between two game names (case-insensitive)."""
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()

    def best_match(
        self, name: str, candidates: list[dict[str, Any]], name_key: str = "name"
    ) -> dict[str, Any] | None:
        """Find the best matching candidate above SIMILARITY_THRESHOLD.
        Returns the candidate dict or None."""
        if not candidates:
            return None

        best = None
        best_score = 0.0

        for candidate in candidates:
            score = self.name_similarity(name, candidate[name_key])
            if score > best_score:
                best_score = score
                best = candidate

        if best_score >= self.SIMILARITY_THRESHOLD:
            return best
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd steam-crawler && python -m pytest tests/test_matching.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
cd steam-crawler
git add src/steam_crawler/api/matching.py tests/test_matching.py
git commit -m "feat: add GameMatcher with name similarity matching"
```

---

### Task 4: Failure types — add match_failed, match_ambiguous, auth_failed

**Files:**
- Modify: `steam-crawler/src/steam_crawler/api/resilience.py`
- Modify: `steam-crawler/tests/test_resilience.py`

- [ ] **Step 1: Write failing tests**

```python
# Add to steam-crawler/tests/test_resilience.py

def test_classify_match_failed():
    from steam_crawler.api.resilience import FailureTracker
    t = FailureTracker()
    assert t.classify(error_type="match_failed") == "match_failed"


def test_classify_match_ambiguous():
    from steam_crawler.api.resilience import FailureTracker
    t = FailureTracker()
    assert t.classify(error_type="match_ambiguous") == "match_ambiguous"


def test_classify_auth_failed():
    from steam_crawler.api.resilience import FailureTracker
    t = FailureTracker()
    assert t.classify(error_type="auth_failed") == "auth_failed"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd steam-crawler && python -m pytest tests/test_resilience.py -v -k "match_failed or match_ambiguous or auth_failed"`
Expected: FAIL — types not in FAILURE_TYPES tuple

- [ ] **Step 3: Add new failure types**

In `steam-crawler/src/steam_crawler/api/resilience.py`, update `FAILURE_TYPES`:

```python
FAILURE_TYPES = (
    "rate_limited",
    "server_error",
    "timeout",
    "parse_error",
    "connection_error",
    "cursor_invalid",
    "data_quality",
    "empty_response",
    "match_failed",
    "match_ambiguous",
    "auth_failed",
    "unknown",
)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd steam-crawler && python -m pytest tests/test_resilience.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
cd steam-crawler
git add src/steam_crawler/api/resilience.py tests/test_resilience.py
git commit -m "feat: add match_failed, match_ambiguous, auth_failed failure types"
```

---

### Task 5: IGDBClient — Twitch OAuth + Apicalypse API

**Files:**
- Create: `steam-crawler/src/steam_crawler/api/igdb.py`
- Create: `steam-crawler/tests/test_igdb.py`

**Note:** IGDB uses POST requests with Apicalypse query language in the body. The client uses composition (not BaseClient inheritance) because BaseClient only supports GET. Uses httpx.Client (sync, matching codebase pattern).

- [ ] **Step 1: Write failing tests**

```python
# steam-crawler/tests/test_igdb.py
import time
import pytest
from steam_crawler.api.igdb import IGDBClient


MOCK_TOKEN_RESPONSE = {
    "access_token": "test_token_abc",
    "expires_in": 5000,
    "token_type": "bearer",
}

MOCK_IGDB_GAME_BY_STEAM = [
    {
        "id": 1942,
        "name": "The Witcher 3: Wild Hunt",
        "summary": "An open world RPG",
        "storyline": "Geralt searches for Ciri",
        "aggregated_rating": 92.5,
        "themes": [{"id": 1, "name": "Fantasy"}, {"id": 17, "name": "Open World"}],
        "keywords": [{"id": 42, "name": "rpg"}, {"id": 99, "name": "choices-matter"}],
        "external_games": [{"uid": "292030", "category": 1}],
    }
]

MOCK_IGDB_SEARCH_RESULTS = [
    {"id": 1942, "name": "The Witcher 3: Wild Hunt"},
    {"id": 1943, "name": "The Witcher 3: Wild Hunt - Blood and Wine"},
]

MOCK_IGDB_EMPTY = []


def test_authenticate(httpx_mock):
    httpx_mock.add_response(json=MOCK_TOKEN_RESPONSE)
    client = IGDBClient("client_id", "client_secret")
    client.authenticate()
    assert client._token == "test_token_abc"
    assert client._token_expires_at > time.time()


def test_search_by_steam_id(httpx_mock):
    httpx_mock.add_response(json=MOCK_TOKEN_RESPONSE)
    httpx_mock.add_response(json=MOCK_IGDB_GAME_BY_STEAM)
    client = IGDBClient("client_id", "client_secret")
    result = client.search_by_steam_id(292030)
    assert result is not None
    assert result["id"] == 1942
    assert result["summary"] == "An open world RPG"


def test_search_by_steam_id_not_found(httpx_mock):
    httpx_mock.add_response(json=MOCK_TOKEN_RESPONSE)
    httpx_mock.add_response(json=MOCK_IGDB_EMPTY)
    client = IGDBClient("client_id", "client_secret")
    result = client.search_by_steam_id(999999)
    assert result is None


def test_search_by_name(httpx_mock):
    httpx_mock.add_response(json=MOCK_TOKEN_RESPONSE)
    httpx_mock.add_response(json=MOCK_IGDB_SEARCH_RESULTS)
    client = IGDBClient("client_id", "client_secret")
    results = client.search_by_name("The Witcher 3")
    assert len(results) == 2
    assert results[0]["name"] == "The Witcher 3: Wild Hunt"


def test_fetch_game_details(httpx_mock):
    httpx_mock.add_response(json=MOCK_TOKEN_RESPONSE)
    httpx_mock.add_response(json=MOCK_IGDB_GAME_BY_STEAM)
    client = IGDBClient("client_id", "client_secret")
    details = client.fetch_game_details(1942)
    assert details["summary"] == "An open world RPG"
    assert details["storyline"] == "Geralt searches for Ciri"
    assert details["aggregated_rating"] == 92.5
    assert len(details["themes"]) == 2
    assert len(details["keywords"]) == 2


def test_auto_reauthenticate_on_expired_token(httpx_mock):
    httpx_mock.add_response(json=MOCK_TOKEN_RESPONSE)
    client = IGDBClient("client_id", "client_secret")
    client.authenticate()
    # Force token expiry
    client._token_expires_at = time.time() - 100
    httpx_mock.add_response(json=MOCK_TOKEN_RESPONSE)  # re-auth
    httpx_mock.add_response(json=MOCK_IGDB_GAME_BY_STEAM)
    result = client.search_by_steam_id(292030)
    assert result is not None


def test_authenticate_failure_raises(httpx_mock):
    """Auth failure (invalid credentials) raises httpx.HTTPStatusError."""
    import httpx as httpx_mod
    httpx_mock.add_response(status_code=401, json={"message": "invalid client"})
    client = IGDBClient("bad_id", "bad_secret")
    with pytest.raises(httpx_mod.HTTPStatusError):
        client.authenticate()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd steam-crawler && python -m pytest tests/test_igdb.py -v`
Expected: FAIL — module doesn't exist

- [ ] **Step 3: Implement IGDBClient**

```python
# steam-crawler/src/steam_crawler/api/igdb.py
"""IGDB API v4 client with Twitch OAuth authentication."""

from __future__ import annotations

import time
import httpx

from steam_crawler.api.rate_limiter import AdaptiveRateLimiter


class IGDBClient:
    """IGDB API v4 client using composition (not BaseClient inheritance).

    IGDB uses POST requests with Apicalypse query language in the body.
    Authentication via Twitch OAuth client_credentials grant.
    """

    BASE_URL = "https://api.igdb.com/v4"
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
        """Auto-authenticate if token is missing or expiring within 60s."""
        if self._token is None or time.time() >= self._token_expires_at - 60:
            self.authenticate()

    def _post(self, endpoint: str, query: str) -> list[dict]:
        """POST an Apicalypse query to an IGDB endpoint with retry on 429/5xx."""
        self._ensure_auth()

        if self._rate_limiter:
            self._rate_limiter.wait()

        url = f"{self.BASE_URL}/{endpoint}"
        headers = {
            "Client-ID": self._client_id,
            "Authorization": f"Bearer {self._token}",
        }

        start = time.monotonic()
        response = self._http.post(url, content=query, headers=headers)
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
                    response = self._http.post(url, content=query, headers=headers)
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

        response.raise_for_status()
        return response.json()

    def search_by_steam_id(self, appid: int) -> dict | None:
        """Search IGDB for a game by Steam AppID. Returns game dict or None."""
        query = (
            f"fields name, summary, storyline, aggregated_rating, "
            f"themes.id, themes.name, keywords.id, keywords.name, "
            f"external_games.uid, external_games.category; "
            f"where external_games.category = 1 & external_games.uid = \"{appid}\"; "
            f"limit 1;"
        )
        results = self._post("games", query)
        return results[0] if results else None

    def search_by_name(self, name: str) -> list[dict]:
        """Search IGDB for games by name. Returns list of candidates."""
        safe_name = name.replace('"', '\\"')
        query = (
            f'search "{safe_name}"; '
            f"fields name, summary, storyline, aggregated_rating, "
            f"themes.id, themes.name, keywords.id, keywords.name; "
            f"limit 10;"
        )
        return self._post("games", query)

    def fetch_game_details(self, igdb_id: int) -> dict | None:
        """Fetch full details for a specific IGDB game ID."""
        query = (
            f"fields name, summary, storyline, aggregated_rating, "
            f"themes.id, themes.name, keywords.id, keywords.name; "
            f"where id = {igdb_id}; limit 1;"
        )
        results = self._post("games", query)
        return results[0] if results else None

    def close(self) -> None:
        self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd steam-crawler && python -m pytest tests/test_igdb.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
cd steam-crawler
git add src/steam_crawler/api/igdb.py tests/test_igdb.py
git commit -m "feat: add IGDBClient with Twitch OAuth and Apicalypse queries"
```

---

### Task 6: RAWGClient — API key authentication

**Files:**
- Create: `steam-crawler/src/steam_crawler/api/rawg.py`
- Create: `steam-crawler/tests/test_rawg.py`

- [ ] **Step 1: Write failing tests**

```python
# steam-crawler/tests/test_rawg.py
import pytest
from steam_crawler.api.rawg import RAWGClient


MOCK_RAWG_SEARCH = {
    "count": 2,
    "results": [
        {
            "id": 3328,
            "name": "The Witcher 3: Wild Hunt",
            "description_raw": "A detailed description",
            "metacritic": 92,
            "rating": 4.66,
            "stores": [{"store": {"id": 1, "slug": "steam"}}],
        },
        {
            "id": 3329,
            "name": "The Witcher 3: Wild Hunt - GOTY",
            "metacritic": 91,
            "rating": 4.5,
            "stores": [],
        },
    ],
}

MOCK_RAWG_DETAILS = {
    "id": 3328,
    "name": "The Witcher 3: Wild Hunt",
    "description_raw": "An RPG with open world exploration and a rich story.",
    "metacritic": 92,
    "rating": 4.66,
    "stores": [{"store": {"id": 1, "slug": "steam"}, "url": "https://store.steampowered.com/app/292030"}],
}

MOCK_RAWG_EMPTY = {"count": 0, "results": []}


def test_search_by_name(httpx_mock):
    httpx_mock.add_response(json=MOCK_RAWG_SEARCH)
    client = RAWGClient(api_key="test_key")
    results = client.search_by_name("The Witcher 3")
    assert len(results) == 2
    assert results[0]["name"] == "The Witcher 3: Wild Hunt"


def test_search_by_name_empty(httpx_mock):
    httpx_mock.add_response(json=MOCK_RAWG_EMPTY)
    client = RAWGClient(api_key="test_key")
    results = client.search_by_name("nonexistent game xyz")
    assert results == []


def test_fetch_game_details(httpx_mock):
    httpx_mock.add_response(json=MOCK_RAWG_DETAILS)
    client = RAWGClient(api_key="test_key")
    details = client.fetch_game_details(3328)
    assert details["description_raw"] == "An RPG with open world exploration and a rich story."
    assert details["metacritic"] == 92
    assert details["rating"] == 4.66


def test_search_by_steam_id(httpx_mock):
    """RAWG can search by Steam store filter to find games by AppID."""
    httpx_mock.add_response(json=MOCK_RAWG_SEARCH)
    client = RAWGClient(api_key="test_key")
    results = client.search_by_steam_id(292030)
    assert len(results) >= 1
    request = httpx_mock.get_requests()[0]
    assert "stores=1" in str(request.url)


def test_api_key_in_params(httpx_mock):
    httpx_mock.add_response(json=MOCK_RAWG_EMPTY)
    client = RAWGClient(api_key="my_secret_key")
    client.search_by_name("test")
    request = httpx_mock.get_requests()[0]
    assert "key=my_secret_key" in str(request.url)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd steam-crawler && python -m pytest tests/test_rawg.py -v`
Expected: FAIL — module doesn't exist

- [ ] **Step 3: Implement RAWGClient**

```python
# steam-crawler/src/steam_crawler/api/rawg.py
"""RAWG Video Games Database API client."""

from __future__ import annotations

from steam_crawler.api.base import BaseClient
from steam_crawler.api.rate_limiter import AdaptiveRateLimiter


class RAWGClient(BaseClient):
    """RAWG API client. Inherits BaseClient (GET-based API)."""

    BASE_URL = "https://api.rawg.io/api"

    def __init__(
        self,
        api_key: str,
        rate_limiter: AdaptiveRateLimiter | None = None,
    ):
        super().__init__(rate_limiter=rate_limiter)
        self._api_key = api_key

    def _params(self, extra: dict | None = None) -> dict:
        """Build query params with API key included."""
        params = {"key": self._api_key}
        if extra:
            params.update(extra)
        return params

    def search_by_name(self, name: str) -> list[dict]:
        """Search RAWG for games by name. Returns list of result dicts."""
        response = self.get(
            f"{self.BASE_URL}/games",
            params=self._params({"search": name, "page_size": 10}),
        )
        response.raise_for_status()
        data = response.json()
        return data.get("results", [])

    def search_by_steam_id(self, appid: int) -> list[dict]:
        """Search RAWG for games available on Steam (store=1) matching AppID.
        Uses name search + stores=1 filter. Caller checks results for AppID match."""
        response = self.get(
            f"{self.BASE_URL}/games",
            params=self._params({"stores": "1", "page_size": 5}),
        )
        response.raise_for_status()
        data = response.json()
        return data.get("results", [])

    def fetch_game_details(self, rawg_id: int) -> dict | None:
        """Fetch full details for a specific RAWG game ID."""
        response = self.get(
            f"{self.BASE_URL}/games/{rawg_id}",
            params=self._params(),
        )
        response.raise_for_status()
        return response.json()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd steam-crawler && python -m pytest tests/test_rawg.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
cd steam-crawler
git add src/steam_crawler/api/rawg.py tests/test_rawg.py
git commit -m "feat: add RAWGClient with API key authentication"
```

---

### Task 7: Step 1d — IGDB enrichment pipeline step

**Files:**
- Create: `steam-crawler/src/steam_crawler/pipeline/step1d_igdb.py`
- Create: `steam-crawler/tests/test_step1d.py`

**Pattern:** Follow `step1c_store.py` — iterate games, try/except per game, log failures.

- [ ] **Step 1: Write failing tests**

```python
# steam-crawler/tests/test_step1d.py
import pytest


MOCK_TOKEN = {"access_token": "tok", "expires_in": 5000, "token_type": "bearer"}

MOCK_IGDB_GAME = [
    {
        "id": 1942,
        "name": "CS2",
        "summary": "A tactical FPS",
        "storyline": "Counter-terrorists fight",
        "aggregated_rating": 88.0,
        "themes": [{"id": 1, "name": "Action"}],
        "keywords": [{"id": 10, "name": "fps"}, {"id": 20, "name": "multiplayer"}],
        "external_games": [{"uid": "730", "category": 1}],
    }
]


def _setup_game(db_conn):
    from steam_crawler.db.repository import create_version
    version = create_version(db_conn, "tag", "FPS")
    db_conn.execute(
        "INSERT INTO games (appid, name, source_tag, first_seen_ver) VALUES (730, 'CS2', 'tag:FPS', ?)",
        (version,),
    )
    db_conn.commit()
    return version


def test_step1d_enriches_game(httpx_mock, db_conn):
    from steam_crawler.pipeline.step1d_igdb import run_step1d

    version = _setup_game(db_conn)
    httpx_mock.add_response(json=MOCK_TOKEN)      # auth
    httpx_mock.add_response(json=MOCK_IGDB_GAME)  # search_by_steam_id

    count = run_step1d(
        db_conn, version=version, source_tag="tag:FPS",
        client_id="cid", client_secret="csec",
    )
    assert count == 1

    row = db_conn.execute("SELECT * FROM games WHERE appid=730").fetchone()
    assert row["igdb_id"] == 1942
    assert row["igdb_summary"] == "A tactical FPS"
    assert row["igdb_rating"] == 88.0

    themes = db_conn.execute(
        "SELECT t.name FROM game_themes gt JOIN theme_catalog t ON gt.theme_id=t.id WHERE gt.appid=730"
    ).fetchall()
    assert len(themes) == 1
    assert themes[0]["name"] == "Action"

    keywords = db_conn.execute(
        "SELECT k.name FROM game_keywords gk JOIN keyword_catalog k ON gk.keyword_id=k.id WHERE gk.appid=730"
    ).fetchall()
    assert len(keywords) == 2


def test_step1d_skips_already_enriched(httpx_mock, db_conn):
    from steam_crawler.pipeline.step1d_igdb import run_step1d

    version = _setup_game(db_conn)
    db_conn.execute("UPDATE games SET igdb_id=1942 WHERE appid=730")
    db_conn.commit()

    httpx_mock.add_response(json=MOCK_TOKEN)

    count = run_step1d(
        db_conn, version=version, source_tag="tag:FPS",
        client_id="cid", client_secret="csec",
    )
    assert count == 0


def test_step1d_name_fallback(httpx_mock, db_conn):
    from steam_crawler.pipeline.step1d_igdb import run_step1d

    version = _setup_game(db_conn)
    httpx_mock.add_response(json=MOCK_TOKEN)
    httpx_mock.add_response(json=[])              # steam_id search returns empty
    httpx_mock.add_response(json=[               # name search returns match
        {"id": 1942, "name": "CS2", "summary": "Found by name",
         "themes": [], "keywords": []},
    ])
    httpx_mock.add_response(json=[               # fetch_game_details
        {"id": 1942, "name": "CS2", "summary": "Found by name",
         "aggregated_rating": 85.0, "themes": [], "keywords": []},
    ])

    count = run_step1d(
        db_conn, version=version, source_tag="tag:FPS",
        client_id="cid", client_secret="csec",
    )
    assert count == 1
    row = db_conn.execute("SELECT igdb_summary FROM games WHERE appid=730").fetchone()
    assert row["igdb_summary"] == "Found by name"


def test_step1d_match_failed_marks_unmatchable(httpx_mock, db_conn):
    from steam_crawler.pipeline.step1d_igdb import run_step1d

    version = _setup_game(db_conn)
    httpx_mock.add_response(json=MOCK_TOKEN)
    httpx_mock.add_response(json=[])  # steam_id search empty
    httpx_mock.add_response(json=[    # name search returns unrelated
        {"id": 999, "name": "Completely Different Game"},
    ])

    count = run_step1d(
        db_conn, version=version, source_tag="tag:FPS",
        client_id="cid", client_secret="csec",
    )
    assert count == 0
    row = db_conn.execute("SELECT igdb_id FROM games WHERE appid=730").fetchone()
    assert row["igdb_id"] == -1  # marked unmatchable

    failures = db_conn.execute(
        "SELECT * FROM failure_logs WHERE failure_type='match_failed'"
    ).fetchall()
    assert len(failures) == 1


def test_step1d_skips_when_no_credentials(db_conn):
    from steam_crawler.pipeline.step1d_igdb import run_step1d

    version = _setup_game(db_conn)
    count = run_step1d(
        db_conn, version=version, source_tag="tag:FPS",
        client_id=None, client_secret=None,
    )
    assert count == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd steam-crawler && python -m pytest tests/test_step1d.py -v`
Expected: FAIL — module doesn't exist

- [ ] **Step 3: Implement step1d_igdb.py**

```python
# steam-crawler/src/steam_crawler/pipeline/step1d_igdb.py
"""Step 1d: Enrich games with IGDB data (summary, storyline, themes, keywords)."""
from __future__ import annotations

import sqlite3

from rich.console import Console

from steam_crawler.api.igdb import IGDBClient
from steam_crawler.api.matching import GameMatcher
from steam_crawler.api.resilience import FailureTracker
from steam_crawler.db.repository import (
    get_games_needing_enrichment,
    update_game_igdb_details,
    upsert_game_themes,
    upsert_game_keywords,
)

console = Console()


def run_step1d(
    conn: sqlite3.Connection,
    version: int,
    source_tag: str | None = None,
    client_id: str | None = None,
    client_secret: str | None = None,
    igdb_client: IGDBClient | None = None,
    failure_tracker: FailureTracker | None = None,
) -> int:
    """Enrich games with IGDB data. Returns count enriched."""
    if client_id is None and igdb_client is None:
        console.print("[yellow]IGDB credentials not set, skipping step 1d[/yellow]")
        return 0

    client = igdb_client or IGDBClient(client_id, client_secret)
    tracker = failure_tracker or FailureTracker()
    matcher = GameMatcher()
    games = get_games_needing_enrichment(conn, source="igdb", source_tag=source_tag)
    enriched = 0

    if not games:
        console.print("[dim]Step 1d: No games need IGDB enrichment[/dim]")
        return 0

    console.print(f"[bold]Step 1d:[/bold] Enriching {len(games)} games from IGDB")

    try:
        for game_row in games:
            appid = game_row["appid"]
            name = game_row["name"]
            try:
                # 1. Try AppID match
                result = client.search_by_steam_id(appid)

                # 2. Fallback: name search
                if result is None:
                    candidates = client.search_by_name(name)
                    matched = matcher.best_match(name, candidates)
                    if matched is None:
                        # Mark unmatchable
                        conn.execute(
                            "UPDATE games SET igdb_id=-1 WHERE appid=?", (appid,)
                        )
                        conn.commit()
                        tracker.log_failure(
                            conn=conn, session_id=version, api_name="igdb",
                            appid=appid, step="step1d",
                            error_type="match_failed",
                            error_message=f"No match for '{name}'",
                        )
                        continue
                    # Fetch full details for matched game
                    result = client.fetch_game_details(matched["id"])
                    if result is None:
                        continue

                igdb_id = result["id"]
                update_game_igdb_details(
                    conn, appid=appid, igdb_id=igdb_id,
                    igdb_summary=result.get("summary"),
                    igdb_storyline=result.get("storyline"),
                    igdb_rating=result.get("aggregated_rating"),
                )

                # Themes
                themes_raw = result.get("themes") or []
                if themes_raw:
                    themes = {t["id"]: t["name"] for t in themes_raw}
                    upsert_game_themes(conn, appid=appid, themes=themes)

                # Keywords
                keywords_raw = result.get("keywords") or []
                if keywords_raw:
                    keywords = {k["id"]: k["name"] for k in keywords_raw}
                    upsert_game_keywords(conn, appid=appid, keywords=keywords)

                enriched += 1

            except Exception as e:
                tracker.log_failure(
                    conn=conn, session_id=version, api_name="igdb",
                    appid=appid, step="step1d", error_message=str(e),
                )
                console.print(f"  [red]IGDB error for {name} ({appid}): {e}[/red]")
                continue

        console.print(
            f"[green]Step 1d complete:[/green] {enriched}/{len(games)} games enriched from IGDB"
        )
        return enriched
    finally:
        if igdb_client is None:
            client.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd steam-crawler && python -m pytest tests/test_step1d.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
cd steam-crawler
git add src/steam_crawler/pipeline/step1d_igdb.py tests/test_step1d.py
git commit -m "feat: add step1d IGDB enrichment pipeline step"
```

---

### Task 8: Step 1e — RAWG enrichment pipeline step

**Files:**
- Create: `steam-crawler/src/steam_crawler/pipeline/step1e_rawg.py`
- Create: `steam-crawler/tests/test_step1e.py`

- [ ] **Step 1: Write failing tests**

```python
# steam-crawler/tests/test_step1e.py
import pytest


MOCK_RAWG_SEARCH = {
    "count": 1,
    "results": [
        {"id": 3328, "name": "CS2", "metacritic": 83, "rating": 4.2,
         "stores": [{"store": {"id": 1, "slug": "steam"}}]},
    ],
}

MOCK_RAWG_DETAILS = {
    "id": 3328,
    "name": "CS2",
    "description_raw": "An iconic tactical shooter.",
    "metacritic": 83,
    "rating": 4.2,
}

MOCK_RAWG_EMPTY = {"count": 0, "results": []}


def _setup_game(db_conn):
    from steam_crawler.db.repository import create_version
    version = create_version(db_conn, "tag", "FPS")
    db_conn.execute(
        "INSERT INTO games (appid, name, source_tag, first_seen_ver) VALUES (730, 'CS2', 'tag:FPS', ?)",
        (version,),
    )
    db_conn.commit()
    return version


def test_step1e_enriches_game(httpx_mock, db_conn):
    from steam_crawler.pipeline.step1e_rawg import run_step1e

    version = _setup_game(db_conn)
    httpx_mock.add_response(json=MOCK_RAWG_SEARCH)   # search
    httpx_mock.add_response(json=MOCK_RAWG_DETAILS)  # details

    count = run_step1e(
        db_conn, version=version, source_tag="tag:FPS", api_key="test_key",
    )
    assert count == 1

    row = db_conn.execute("SELECT * FROM games WHERE appid=730").fetchone()
    assert row["rawg_id"] == 3328
    assert row["rawg_description"] == "An iconic tactical shooter."
    assert row["rawg_rating"] == 4.2
    assert row["metacritic_score"] == 83


def test_step1e_skips_already_enriched(db_conn):
    from steam_crawler.pipeline.step1e_rawg import run_step1e

    version = _setup_game(db_conn)
    db_conn.execute("UPDATE games SET rawg_id=3328 WHERE appid=730")
    db_conn.commit()

    count = run_step1e(
        db_conn, version=version, source_tag="tag:FPS", api_key="test_key",
    )
    assert count == 0


def test_step1e_match_failed_marks_unmatchable(httpx_mock, db_conn):
    from steam_crawler.pipeline.step1e_rawg import run_step1e

    version = _setup_game(db_conn)
    httpx_mock.add_response(json={"count": 1, "results": [
        {"id": 999, "name": "Totally Different Game", "metacritic": None, "rating": 0},
    ]})

    count = run_step1e(
        db_conn, version=version, source_tag="tag:FPS", api_key="test_key",
    )
    assert count == 0
    row = db_conn.execute("SELECT rawg_id FROM games WHERE appid=730").fetchone()
    assert row["rawg_id"] == -1


def test_step1e_skips_when_no_api_key(db_conn):
    from steam_crawler.pipeline.step1e_rawg import run_step1e

    version = _setup_game(db_conn)
    count = run_step1e(
        db_conn, version=version, source_tag="tag:FPS", api_key=None,
    )
    assert count == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd steam-crawler && python -m pytest tests/test_step1e.py -v`
Expected: FAIL — module doesn't exist

- [ ] **Step 3: Implement step1e_rawg.py**

```python
# steam-crawler/src/steam_crawler/pipeline/step1e_rawg.py
"""Step 1e: Enrich games with RAWG data (description, Metacritic score, rating)."""
from __future__ import annotations

import sqlite3

from rich.console import Console

from steam_crawler.api.matching import GameMatcher
from steam_crawler.api.rawg import RAWGClient
from steam_crawler.api.resilience import FailureTracker
from steam_crawler.db.repository import (
    get_games_needing_enrichment,
    update_game_rawg_details,
)

console = Console()


def run_step1e(
    conn: sqlite3.Connection,
    version: int,
    source_tag: str | None = None,
    api_key: str | None = None,
    rawg_client: RAWGClient | None = None,
    failure_tracker: FailureTracker | None = None,
) -> int:
    """Enrich games with RAWG data. Returns count enriched."""
    if api_key is None and rawg_client is None:
        console.print("[yellow]RAWG API key not set, skipping step 1e[/yellow]")
        return 0

    client = rawg_client or RAWGClient(api_key=api_key)
    tracker = failure_tracker or FailureTracker()
    matcher = GameMatcher()
    games = get_games_needing_enrichment(conn, source="rawg", source_tag=source_tag)
    enriched = 0

    if not games:
        console.print("[dim]Step 1e: No games need RAWG enrichment[/dim]")
        return 0

    console.print(f"[bold]Step 1e:[/bold] Enriching {len(games)} games from RAWG")

    try:
        for game_row in games:
            appid = game_row["appid"]
            name = game_row["name"]
            try:
                # Search by name
                candidates = client.search_by_name(name)
                matched = matcher.best_match(name, candidates)

                if matched is None:
                    conn.execute(
                        "UPDATE games SET rawg_id=-1 WHERE appid=?", (appid,)
                    )
                    conn.commit()
                    tracker.log_failure(
                        conn=conn, session_id=version, api_name="rawg",
                        appid=appid, step="step1e",
                        error_type="match_failed",
                        error_message=f"No match for '{name}'",
                    )
                    continue

                rawg_id = matched["id"]

                # Fetch full details
                details = client.fetch_game_details(rawg_id)
                if details is None:
                    continue

                update_game_rawg_details(
                    conn, appid=appid, rawg_id=rawg_id,
                    rawg_description=details.get("description_raw"),
                    rawg_rating=details.get("rating"),
                    metacritic_score=details.get("metacritic"),
                )
                enriched += 1

            except Exception as e:
                tracker.log_failure(
                    conn=conn, session_id=version, api_name="rawg",
                    appid=appid, step="step1e", error_message=str(e),
                )
                console.print(f"  [red]RAWG error for {name} ({appid}): {e}[/red]")
                continue

        console.print(
            f"[green]Step 1e complete:[/green] {enriched}/{len(games)} games enriched from RAWG"
        )
        return enriched
    finally:
        if rawg_client is None:
            client.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd steam-crawler && python -m pytest tests/test_step1e.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
cd steam-crawler
git add src/steam_crawler/pipeline/step1e_rawg.py tests/test_step1e.py
git commit -m "feat: add step1e RAWG enrichment pipeline step"
```

---

### Task 9: Pipeline runner — integrate step1d and step1e

**Files:**
- Modify: `steam-crawler/src/steam_crawler/pipeline/runner.py`
- Modify: `steam-crawler/tests/test_runner.py`

- [ ] **Step 1: Write failing test**

```python
# Add to steam-crawler/tests/test_runner.py

def test_runner_calls_step1d_step1e(httpx_mock, db_conn, monkeypatch):
    """Runner calls step1d and step1e when env vars are set."""
    import os
    monkeypatch.setenv("TWITCH_CLIENT_ID", "test_cid")
    monkeypatch.setenv("TWITCH_CLIENT_SECRET", "test_csec")
    monkeypatch.setenv("RAWG_API_KEY", "test_key")

    # Step1 mock (SteamSpy tag)
    httpx_mock.add_response(json={
        "730": {"appid": 730, "name": "CS2", "positive": 7000000, "negative": 1000000,
                "owners": "50M", "average_forever": 30000, "price": "0", "score_rank": "",
                "userscore": 0, "developer": "Valve", "publisher": "Valve"},
    })
    # Step1b mock (app details)
    httpx_mock.add_response(json={
        "appid": 730, "name": "CS2", "positive": 7000000, "negative": 1000000,
        "owners": "50M", "average_forever": 30000, "price": "0", "score_rank": "",
        "tags": {"FPS": 90000}, "genre": "Action",
    })
    # Step1c mock (store EN)
    httpx_mock.add_response(json={"730": {"success": True, "data": {
        "short_description": "Tactical FPS", "header_image": "img.jpg",
        "screenshots": [], "movies": [],
    }}})
    # Step1c mock (store KO)
    httpx_mock.add_response(json={"730": {"success": True, "data": {
        "short_description": "FPS", "screenshots": [], "movies": [],
    }}})
    # Step1d mock (IGDB auth)
    httpx_mock.add_response(json={"access_token": "tok", "expires_in": 5000, "token_type": "bearer"})
    # Step1d mock (IGDB search by steam id)
    httpx_mock.add_response(json=[{
        "id": 1942, "name": "CS2", "summary": "A FPS", "themes": [], "keywords": [],
        "external_games": [{"uid": "730", "category": 1}],
    }])
    # Step1e mock (RAWG search)
    httpx_mock.add_response(json={"count": 1, "results": [
        {"id": 3328, "name": "CS2", "metacritic": 83, "rating": 4.2},
    ]})
    # Step1e mock (RAWG details)
    httpx_mock.add_response(json={
        "id": 3328, "name": "CS2", "description_raw": "Detailed", "metacritic": 83, "rating": 4.2,
    })

    from steam_crawler.pipeline.runner import run_pipeline
    run_pipeline(db_conn, query_type="tag", query_value="FPS", limit=1, top_n=0, step=1)

    row = db_conn.execute("SELECT igdb_id, rawg_id FROM games WHERE appid=730").fetchone()
    assert row["igdb_id"] == 1942
    assert row["rawg_id"] == 3328
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd steam-crawler && python -m pytest tests/test_runner.py -v -k "step1d_step1e"`
Expected: FAIL — runner doesn't call step1d/1e yet

- [ ] **Step 3: Modify runner.py**

Add imports:

```python
import os
from steam_crawler.pipeline.step1d_igdb import run_step1d
from steam_crawler.pipeline.step1e_rawg import run_step1e
```

In `run_pipeline`, after the `run_step1c(...)` call (inside `if step is None or step == 1:`), add:

```python
            # Step 1d: IGDB enrichment (optional, needs env vars)
            igdb_cid = os.environ.get("TWITCH_CLIENT_ID")
            igdb_csec = os.environ.get("TWITCH_CLIENT_SECRET")
            run_step1d(
                conn, version, source_tag=source_tag,
                client_id=igdb_cid, client_secret=igdb_csec,
                failure_tracker=tracker,
            )

            # Step 1e: RAWG enrichment (optional, needs env var)
            rawg_key = os.environ.get("RAWG_API_KEY")
            run_step1e(
                conn, version, source_tag=source_tag,
                api_key=rawg_key,
                failure_tracker=tracker,
            )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd steam-crawler && python -m pytest tests/test_runner.py -v`
Expected: ALL PASS

- [ ] **Step 5: Run full test suite**

Run: `cd steam-crawler && python -m pytest -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
cd steam-crawler
git add src/steam_crawler/pipeline/runner.py tests/test_runner.py
git commit -m "feat: integrate step1d (IGDB) and step1e (RAWG) into pipeline runner"
```

---

### Task 10: Final integration test and cleanup

**Files:**
- Modify: `steam-crawler/tests/test_pipeline.py` (optional integration test)
- No new files

- [ ] **Step 1: Run full test suite**

Run: `cd steam-crawler && python -m pytest -v --tb=short`
Expected: ALL PASS

- [ ] **Step 2: Verify total test count**

Run: `cd steam-crawler && python -m pytest --co -q | tail -1`
Expected: Test count should be previous count + new tests (~20+ new tests)

- [ ] **Step 3: Final commit if any adjustments were needed**

```bash
git add -A
git commit -m "test: verify full integration of IGDB/RAWG enrichment pipeline"
```
