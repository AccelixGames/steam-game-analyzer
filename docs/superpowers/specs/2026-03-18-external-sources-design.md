# External Game Data Sources Integration Design

## Overview

Steam 자체 데이터의 한계를 보완하기 위해 IGDB와 RAWG에서 게임 설명, 평점, 테마/키워드 메타데이터를 수집한다. 목적은 **게임 기획 역설계** — "어떤 게임인지, 뭐가 재밌는지, 왜 이런 평가를 받는지"를 구조화된 데이터로 파악하는 것.

## Sources

### IGDB (Internet Game Database)
- **소유**: Twitch (Amazon)
- **인증**: Twitch OAuth client_credentials
- **Rate Limit**: 4 req/sec
- **비용**: 무료
- **핵심 데이터**: summary, storyline, aggregated_rating, themes, keywords
- **API Docs**: https://api-docs.igdb.com/

### RAWG
- **인증**: API Key (query parameter)
- **Rate Limit**: 월 20,000 요청
- **비용**: 무료 (개인/소규모)
- **핵심 데이터**: description_raw, metacritic score, rating, tags
- **API Docs**: https://rawg.io/apidocs

## Architecture

### Pipeline Integration

기존 steam-crawler 파이프라인에 2개 스텝을 추가한다.

```
Step 1  — SteamSpy 게임 수집
Step 1b — SteamSpy 상세 보강
Step 1c — Steam Store 상세 (설명, 미디어)
Step 1d — IGDB 보강 (NEW)
Step 1e — RAWG 보강 (NEW)
Step 2  — 리뷰 대상 스캔
Step 3  — 리뷰 크롤링
```

Step 1d/1e는 Step 1c 이후에 실행되며, games 테이블에 이미 존재하는 게임에 대해서만 외부 데이터를 보강한다.

### Game Matching Strategy

Steam AppID → IGDB/RAWG 게임 매칭:

1. **AppID 직접 검색** — IGDB: `external_games` where category=1(Steam), RAWG: stores에서 Steam ID 매칭
2. **이름 검색 fallback** — AppID 매칭 실패 시 게임 이름으로 검색
3. **유사도 검증** — 이름 매칭 시 유사도 80% 이상만 채택 (difflib.SequenceMatcher)
4. **실패 기록** — 매칭 실패 시 failure_logs에 기록, 진단 스킬로 추적 가능

매칭 성공 시 igdb_id/rawg_id를 games 테이블에 캐시하여 재실행 시 재매칭 방지.
영구적으로 매칭 불가한 게임은 igdb_id=-1 / rawg_id=-1 로 마킹하여 반복 시도 방지.

## Data Model

### games 테이블 컬럼 추가

```sql
-- IGDB 데이터
igdb_id          INTEGER,       -- IGDB 내부 ID (매칭 캐시, -1=매칭불가)
igdb_summary     TEXT,          -- 게임 개요
igdb_storyline   TEXT,          -- 스토리/세계관 설명
igdb_rating      REAL,          -- IGDB 집계 평점 (0-100)

-- RAWG 데이터
rawg_id          INTEGER,       -- RAWG 내부 ID (매칭 캐시, -1=매칭불가)
rawg_description TEXT,          -- 상세 설명 (plain text)
rawg_rating      REAL,          -- RAWG 유저 평점 (0-5)
metacritic_score INTEGER        -- Metacritic 점수 (0-100)
```

**인덱스**: igdb_id, rawg_id에 인덱스 추가 (매칭 캐시 조회 최적화).

### 신규 테이블 (카탈로그 패턴)

기존 tag_catalog/game_tags, genre_catalog/game_genres와 동일한 패턴.

```sql
-- 테마 (IGDB themes)
CREATE TABLE IF NOT EXISTS theme_catalog (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS game_themes (
    appid INTEGER NOT NULL,
    theme_id INTEGER NOT NULL,
    source TEXT NOT NULL DEFAULT 'igdb',
    PRIMARY KEY (appid, theme_id),
    FOREIGN KEY (appid) REFERENCES games(appid),
    FOREIGN KEY (theme_id) REFERENCES theme_catalog(id)
);

-- 키워드 (IGDB keywords)
CREATE TABLE IF NOT EXISTS keyword_catalog (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS game_keywords (
    appid INTEGER NOT NULL,
    keyword_id INTEGER NOT NULL,
    source TEXT NOT NULL DEFAULT 'igdb',
    PRIMARY KEY (appid, keyword_id),
    FOREIGN KEY (appid) REFERENCES games(appid),
    FOREIGN KEY (keyword_id) REFERENCES keyword_catalog(id)
);
```

## API Clients

### IGDBClient

IGDB는 POST 기반 API (Apicalypse 쿼리 언어)를 사용하므로, 기존 BaseClient(GET 전용)를 상속하지 않고 **별도 클라이언트**로 구현한다. 내부적으로 httpx.AsyncClient + AdaptiveRateLimiter를 조합(composition)한다.

```python
class IGDBClient:
    """IGDB API v4 client with Twitch OAuth (composition, not inheritance)."""

    BASE_URL = "https://api.igdb.com/v4"
    AUTH_URL = "https://id.twitch.tv/oauth2/token"

    def __init__(self, client_id, client_secret, rate_limiter):
        self._client_id = client_id
        self._client_secret = client_secret
        self._rate_limiter = rate_limiter
        self._token = None
        self._token_expires_at = 0  # epoch seconds

    # Methods:
    # - authenticate() -> OAuth token via client_credentials, 만료 전 자동 갱신
    # - _post(endpoint, query) -> POST with Apicalypse body
    # - search_by_steam_id(appid) -> game data
    # - search_by_name(name) -> list of candidates
    # - fetch_game_details(igdb_id) -> summary, storyline, rating, themes, keywords
```

- POST 기반 API (body에 Apicalypse 쿼리)
- 필요 필드: `fields name, summary, storyline, aggregated_rating, themes.name, keywords.name, external_games.uid, external_games.category;`
- 토큰 만료 60초 전 자동 갱신 (token_expires_at - 60 기준)

### RAWGClient

RAWG는 GET 기반이므로 기존 BaseClient를 상속한다.

```python
class RAWGClient(BaseClient):
    """RAWG API client."""

    BASE_URL = "https://api.rawg.io/api"

    # Methods:
    # - search_by_name(name) -> list of candidates
    # - search_by_steam_id(appid) -> game via stores filter
    # - fetch_game_details(rawg_id) -> description, rating, metacritic
```

- GET 기반 API (query parameters)
- API key는 `?key=` 파라미터로 전달
- **AppID 매칭**: `/api/games` 엔드포인트에서 `stores=1` (Steam) 필터 + 이름 검색 조합
- Steam store 정보가 `stores` 필드에 포함 → 결과에서 Steam AppID 역추출 가능
- **월간 쿼터 관리**: 요청 횟수를 rate_limit_stats에 기록, 20,000 근접 시 경고

### 인증 정보 관리

환경 변수로 관리:

```
TWITCH_CLIENT_ID=...
TWITCH_CLIENT_SECRET=...
RAWG_API_KEY=...
```

미설정 시 해당 스텝을 건너뛰고 경고 출력 (파이프라인 중단하지 않음).

## Matching Module

```python
# steam-crawler/src/steam_crawler/api/matching.py  (api 패키지 내 배치)

class GameMatcher:
    """Steam AppID <-> 외부 소스 게임 매칭."""

    SIMILARITY_THRESHOLD = 0.8  # 이름 매칭 최소 유사도

    # - match_igdb(appid, name) -> igdb_id | None
    # - match_rawg(appid, name) -> rawg_id | None
    # - _name_similarity(a, b) -> float (difflib.SequenceMatcher)
```

매칭 결과를 igdb_id/rawg_id로 캐시하므로 재실행 시 API 호출 최소화.

## Pipeline Steps

### Step 1d: IGDB Enrichment

```python
# pipeline/step1d_igdb.py
async def run(conn, igdb_client, matcher, failure_tracker):
    """IGDB에서 게임 설명, 평점, 테마, 키워드를 보강."""
    # 1. igdb_id가 NULL인 게임 목록 조회 (igdb_enriched=0 기준)
    # 2. 각 게임에 대해 매칭 시도
    # 3. 매칭 성공 시 상세 데이터 fetch
    # 4. games 테이블 업데이트 (igdb_summary, igdb_storyline, igdb_rating)
    # 5. theme_catalog/game_themes upsert
    # 6. keyword_catalog/game_keywords upsert
    # 7. 실패 시 failure_logs 기록
```

### Step 1e: RAWG Enrichment

```python
# pipeline/step1e_rawg.py
async def run(conn, rawg_client, matcher, failure_tracker):
    """RAWG에서 게임 설명, Metacritic 점수를 보강."""
    # 1. rawg_id가 NULL인 게임 목록 조회 (rawg_enriched=0 기준)
    # 2. 각 게임에 대해 매칭 시도
    # 3. 매칭 성공 시 상세 데이터 fetch
    # 4. games 테이블 업데이트 (rawg_description, rawg_rating, metacritic_score)
    # 5. 실패 시 failure_logs 기록
```

## Error Handling

### 신규 실패 유형

기존 FailureTracker에 추가:

| 유형 | 설명 |
|------|------|
| `match_failed` | AppID + 이름 매칭 모두 실패 |
| `match_ambiguous` | 이름 검색 결과 여러 개, 유사도 부족 |
| `auth_failed` | Twitch OAuth 토큰 발급 실패 |

### 환경 변수 미설정 시

```
[WARN] TWITCH_CLIENT_ID not set, skipping IGDB enrichment
[WARN] RAWG_API_KEY not set, skipping RAWG enrichment
```

파이프라인은 계속 진행. 부분 실행 가능.

## File Structure

```
steam-crawler/src/steam_crawler/
├── api/
│   ├── base.py           -- (기존) BaseClient
│   ├── rate_limiter.py   -- (기존) AdaptiveRateLimiter
│   ├── resilience.py     -- (기존) FailureTracker
│   ├── steamspy.py       -- (기존) SteamSpyClient
│   ├── steam_reviews.py  -- (기존) SteamReviewsClient
│   ├── steam_store.py    -- (기존) SteamStoreClient
│   ├── igdb.py           -- (NEW) IGDBClient
│   └── rawg.py           -- (NEW) RAWGClient
├── pipeline/
│   ├── runner.py         -- (수정) step1d, step1e 호출 추가
│   ├── step1_collect.py  -- (기존)
│   ├── step1b_enrich.py  -- (기존)
│   ├── step1c_store.py   -- (기존)
│   ├── step1d_igdb.py    -- (NEW)
│   └── step1e_rawg.py    -- (NEW)
├── db/
│   ├── schema.py         -- (수정) 테이블 추가
│   └── repository.py     -- (수정) upsert 함수 추가
└── ...

steam-crawler/tests/
├── test_igdb.py          -- (NEW)
├── test_rawg.py          -- (NEW)
├── test_matching.py      -- (NEW)
├── test_step1d.py        -- (NEW)
└── test_step1e.py        -- (NEW)
```

## Testing Strategy

- TDD: 테스트 먼저 작성 후 구현
- API 응답은 pytest-httpx로 모킹
- 매칭 로직은 다양한 케이스 (정확 매칭, fuzzy 매칭, 실패) 커버
- 통합 테스트: 파이프라인 스텝 전체 흐름
