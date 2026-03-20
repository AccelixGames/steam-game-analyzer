---
name: steam-crawl
description: "Steam 게임 데이터 크롤링 실행. Use when user asks to crawl, collect, or fetch Steam game data, reviews, or wants to analyze a specific game's reviews. Triggers on: 'OO 게임 크롤링', 'OO 태그 게임 수집', 'review 모아줘', 'Steam 데이터 수집', 'collect games', 'fetch reviews', or mentions specific game names with intent to gather data. Also use when user wants to test the crawler or run a quick data pull."
---

# Steam Crawl

Steam 게임 데이터를 SteamSpy + Steam Reviews API로 수집하는 스킬.

## Project Location

크롤러 코드: `steam-crawler/` (모노레포 `steam-game-analyzer/` 내)
DB: `data/steam.db` (프로젝트 루트 기준)

## When to Use

- 사용자가 특정 태그/장르의 게임 데이터를 수집하려 할 때
- 특정 게임의 리뷰를 모으려 할 때
- 크롤러를 테스트하거나 빠르게 데이터를 뽑으려 할 때

## TODO: CLI-Only 실행 정책 (리팩토링 필요)

> **이 스킬은 반드시 CLI 서브커맨드만 사용해야 한다. 임시 Python 코드(`python -c "..."`, 임시 `.py` 파일)를 생성·실행하는 것은 절대 금지한다.**

1. **CLI-Only**: 모든 크롤링은 `steam-crawler` CLI 서브커맨드로만 실행한다
2. **개별 함수 + 전체 파이프라인**: CLI는 각 단계별 개별 서브커맨드와 전체 파이프라인 서브커맨드를 모두 제공해야 한다
   - 예: `steam-crawler step1 --appid 427520` (개별 단계)
   - 예: `steam-crawler collect --appids 427520` (전체 파이프라인)
3. **누락 기능 발견 시**: 필요한 CLI 서브커맨드가 없으면 **직접 코드를 작성하지 말고**:
   - `skill_error_logger`로 기록 (error_type: `missing_cli`)
   - 사용자에게 "이 기능의 CLI 커맨드가 없습니다. 추가해주세요." 안내
   - **임시 Python 코드로 우회 금지**

> 아래 "시나리오 A > 방법 2: Python 직접 호출" 코드 블록은 **레거시(참고용)**이며, CLI 서브커맨드로 대체 예정이다.

---

## How It Works

두 가지 수집 시나리오가 있다. **어느 경우든 전체 파이프라인을 실행한다.**

### 수집 파이프라인 단계

| 단계 | API | 수집 내용 | DB 함수 |
|------|-----|----------|---------|
| **1. SteamSpy** | SteamSpyClient | 게임 기본 정보 (이름, 리뷰수, 소유자, 가격) | `upsert_game()` |
| **1b. 태그/장르** | SteamSpyClient | 태그 (투표수 포함), 장르 | `upsert_game_tags()`, `upsert_game_genres()` |
| **1c. Store** | SteamStoreClient | 짧은/전체 설명(한/영), 헤더 이미지, 스크린샷, 영상 | `update_game_store_details()`, `upsert_game_media()` |
| **1d. IGDB** | IGDBClient | 요약, 스토리라인, 테마, 키워드, 평점 | `update_game_igdb_details()`, `upsert_game_themes()`, `upsert_game_keywords()` |
| **1e. RAWG** | RAWGClient | 설명, 평점, 메타크리틱 점수 | `update_game_rawg_details()` |
| **1f. Twitch** | TwitchClient | 스트리밍 데이터 | `update_game_twitch_details()` |
| **1h. HLTB** | HLTBClient | 게임 클리어 시간 | `update_game_hltb_details()` |
| **1i. CheapShark** | CheapSharkClient | 가격 비교/할인 정보 | `update_game_cheapshark_details()` |
| **1j. OpenCritic** | OpenCriticClient | 평론가 리뷰 점수 | `update_game_opencritic_details()` |
| **1k. PCGamingWiki** | PCGamingWikiClient | PC 기술 정보 (사양, 호환성) | `update_game_pcgamingwiki_details()` |
| **1l. Wikidata** | WikidataClient | 구조화된 메타 정보 | `update_game_wikidata_details()` |
| **2. 리뷰 요약** | SteamReviewsClient | 긍정/부정 수, 평가 등급 | `update_game_review_stats()` |
| **3. 리뷰 본문** | SteamReviewsClient | 리뷰 텍스트, 투표수, 플레이타임 등 | `insert_reviews_batch()` |

> **중요**: 1d(IGDB)/1f(Twitch)는 TWITCH_CLIENT_ID/SECRET, 1e(RAWG)는 RAWG_API_KEY, 1j(OpenCritic)는 RAPIDAPI_KEY 환경변수가 필요하다. 없으면 해당 단계를 건너뛰고 사용자에게 안내한다. 1h(HLTB), 1i(CheapShark), 1k(PCGamingWiki), 1l(Wikidata)는 인증 불필요.

### 시나리오 A: 특정 게임 수집 (이름 또는 appid)

**방법 1: CLI (권장)** — 전체 파이프라인이 자동으로 실행된다.

```bash
cd <project-root>/steam-crawler
steam-crawler collect --appids 526870 --max-reviews 100
```

복수 게임:
```bash
steam-crawler collect --appids 526870,427520 --max-reviews 100
```

**방법 2: Python 직접 호출** — 세밀한 제어가 필요할 때 사용.

```python
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, "<project-root>/steam-crawler/src")

from dotenv import load_dotenv
load_dotenv()

from steam_crawler.db.schema import init_db
from steam_crawler.api.steamspy import SteamSpyClient
from steam_crawler.api.steam_reviews import SteamReviewsClient
from steam_crawler.api.steam_store import SteamStoreClient
from steam_crawler.db.repository import (
    upsert_game, upsert_game_tags, upsert_game_genres,
    update_game_store_details, upsert_game_media,
    update_game_review_stats,
    acquire_crawl_lock, release_crawl_lock,
)

conn = init_db("<project-root>/data/steam.db")

# Crawl lock: 동일 게임 중복 크롤링 방지 (5분 자동 만료)
if not acquire_crawl_lock(conn, APPID, owner="skill"):
    print(f"AppID {APPID} is already being crawled by another process. Skipping.")
    conn.close()
    # → 사용자에게 안내하고 종료

# Step 1: SteamSpy 기본 정보
spy = SteamSpyClient()
game = spy.fetch_app_details(APPID)
spy.close()
upsert_game(conn, game, version=0)

# Step 1b: 태그/장르 저장
if game.tags:
    upsert_game_tags(conn, APPID, game.tags)
if game.genres:    # genres가 있는 경우
    upsert_game_genres(conn, APPID, game.genres)

# Step 1c: Steam Store 상세
store = SteamStoreClient()
details = store.fetch_app_details(APPID)
if details:
    update_game_store_details(conn, APPID,
        short_description_en=details.short_description_en,
        short_description_ko=details.short_description_ko,
        detailed_description_en=details.detailed_description_en,
        detailed_description_ko=details.detailed_description_ko,
        header_image=details.header_image)
    for media in details.media:
        upsert_game_media(conn, APPID, media.media_type, media.media_id,
            media.name, media.url_thumbnail, media.url_full)
store.close()

# Step 1d: IGDB (환경변수 필요: TWITCH_CLIENT_ID, TWITCH_CLIENT_SECRET)
twitch_id = os.environ.get("TWITCH_CLIENT_ID")
twitch_secret = os.environ.get("TWITCH_CLIENT_SECRET")
if twitch_id and twitch_secret:
    from steam_crawler.api.igdb import IGDBClient
    from steam_crawler.pipeline.step1d_igdb import run_step1d
    run_step1d(conn, version=0, client_id=twitch_id, client_secret=twitch_secret, lock_owner="skill")
# → 환경변수가 없으면 건너뛰고 사용자에게 안내

# Step 1e: RAWG (환경변수 필요: RAWG_API_KEY)
rawg_key = os.environ.get("RAWG_API_KEY")
if rawg_key:
    from steam_crawler.pipeline.step1e_rawg import run_step1e
    run_step1e(conn, version=0, api_key=rawg_key, lock_owner="skill")
# → 환경변수가 없으면 건너뛰고 사용자에게 안내

# Step 1f: Twitch (TWITCH_CLIENT_ID/SECRET 재사용)
if twitch_id and twitch_secret:
    from steam_crawler.pipeline.step1f_twitch import run_step1f
    run_step1f(conn, version=0, client_id=twitch_id, client_secret=twitch_secret, lock_owner="skill")

# Step 1h: HowLongToBeat (인증 불필요)
from steam_crawler.pipeline.step1h_hltb import run_step1h
run_step1h(conn, version=0, lock_owner="skill")

# Step 1i: CheapShark (인증 불필요)
from steam_crawler.pipeline.step1i_cheapshark import run_step1i
run_step1i(conn, version=0, lock_owner="skill")

# Step 1j: OpenCritic (RAPIDAPI_KEY 필요)
rapidapi_key = os.environ.get("RAPIDAPI_KEY")
if rapidapi_key:
    from steam_crawler.pipeline.step1j_opencritic import run_step1j
    run_step1j(conn, version=0, rapidapi_key=rapidapi_key, lock_owner="skill")
# → 환경변수가 없으면 건너뛰고 사용자에게 안내

# Step 1k: PCGamingWiki (인증 불필요)
from steam_crawler.pipeline.step1k_pcgamingwiki import run_step1k
run_step1k(conn, version=0, lock_owner="skill")

# Step 1l: Wikidata (인증 불필요)
from steam_crawler.pipeline.step1l_wikidata import run_step1l
run_step1l(conn, version=0, lock_owner="skill")

# Step 2: 리뷰 요약
rev = SteamReviewsClient()
summary = rev.fetch_summary(APPID)
update_game_review_stats(conn, APPID,
    steam_positive=summary.total_positive,
    steam_negative=summary.total_negative,
    review_score=summary.review_score_desc)
rev.close()

# Step 3: Review crawl (SPECIFIC GAMES ONLY — always pass appids)
from steam_crawler.pipeline.step3_crawl import run_step3
TARGET = 100  # user-specified count
APPIDS = [427520]  # user-specified appids — MUST match user's request

run_step3(conn, version=0, appids=APPIDS, max_reviews=TARGET, lock_owner="skill")

# 크롤링 완료 후 반드시 잠금 해제
release_crawl_lock(conn, APPID)
conn.close()
```

### 시나리오 B: 태그/장르 기반 대량 수집 (CLI)

```bash
cd <project-root>/steam-crawler
steam-crawler collect --tag "Roguelike" --limit 10 --top-n 3 --max-reviews 50
```

CLI는 전체 파이프라인(Step 1→1b→1c→1d→1e→1f→1h→1i→1j→1k→1l→2→3)을 자동으로 실행한다.

주요 옵션:
- `--tag TEXT` / `--genre TEXT` / `--top100` / `--appids INT,...` — 수집 대상 (하나 필수)
- `--limit INT` — Step 1 최대 게임 수 (기본: 50)
- `--top-n INT` — 리뷰 크롤링 대상 상위 게임 수 (기본: 10)
- `--max-reviews INT` — 게임당 최대 리뷰 수 (기본: 500)
- `--language TEXT` — 리뷰 언어 필터 (기본: all)
- `--review-type all|positive|negative` — 리뷰 유형 필터
- `--step 1|2|3` — 특정 단계만 실행
- `--resume` — 중단된 수집 재개

결과 조회:
```bash
steam-crawler versions    # 수집 이력
steam-crawler status      # 현재 상태
steam-crawler diff 1 2    # 버전 간 변경사항
```

## Preflight Verification

After calling `run_step3()` or any pipeline function, **always check the output log** before the crawl proceeds:

1. Look for the `[Preflight]` line in the output
2. Verify the listed games match exactly what the user requested
3. Verify the game count matches expectations
4. If the preflight shows unexpected games, STOP immediately and investigate

Example expected output:
```
[Preflight] Step 3: 2 game(s) targeted
  - Factorio (appid=427520) | collected=10001 | max=200000
  - Satisfactory (appid=526870) | collected=10000 | max=200000
```

If output shows games the user did NOT request, abort and report the mismatch to the user.

## Presenting Results

크롤링 결과를 사용자에게 보여줄 때는 다음을 포함한다:

1. **게임 정보**: 이름, 리뷰 수(긍정/부정), 평가, 소유자 수, 가격, 평균 플레이타임
2. **태그**: 상위 5~10개 태그 (투표 수 포함)
3. **Store 상세**: 한글 설명 (있으면), 장르
4. **외부 소스**: IGDB 요약/평점, RAWG 메타크리틱 (수집된 경우)
5. **리뷰 샘플**: 3~5개 리뷰 (긍정/부정 혼합, 텍스트 앞 100자 + 언어 + 플레이타임)
6. **수집 요약 테이블**: 각 단계별 수집 건수 (예: 태그 19개, 스크린샷 5개, 리뷰 100건)
7. **건너뛴 단계**: 환경변수 미설정 등으로 건너뛴 단계가 있으면 안내
8. **태그 기반 수집 시**: SteamSpy 데이터 품질 경고 — 결과 게임이 실제로 해당 태그와 관련 있는지 확인 필요

## Finding Game AppIDs

사용자가 게임 이름만 말한 경우:
1. SteamSpy에는 이름 검색 API가 없음
2. Steam Store 검색으로 appid 찾기: `https://store.steampowered.com/search/?term=GAME_NAME` 파싱하거나
3. 잘 알려진 게임은 직접 appid 입력 (예: CS2=730, Dota2=570, Slay the Spire=646570)
4. 태그 기반 검색으로 우회: `--tag` 사용 후 결과에서 찾기

## Known Limitations

### SteamSpy 태그 데이터 품질
SteamSpy의 tag/genre 엔드포인트는 **관련 없는 게임을 반환할 수 있다** (예: "Roguelike" 검색에 GTA IV가 나옴). 이는 SteamSpy 데이터의 알려진 한계이다. 태그 기반 수집 결과를 사용자에게 보여줄 때 반드시 이 점을 언급하고, 결과가 이상하면 Steam Store에서 직접 확인을 권장한다.

### max-reviews와 페이지 크기
`--max-reviews 10`을 지정해도 Steam API는 페이지 단위(`num_per_page=80`)로 반환하므로, 첫 페이지에서 최대 80개가 한 번에 수집될 수 있다. `max-reviews`는 "이 숫자 이상이면 다음 페이지를 요청하지 않는다"는 의미이다. 사용자가 소량 테스트를 원하면 이 점을 안내한다.

## Rate Limits

- SteamSpy: 1 req/sec
- Steam Reviews: ~1 req/1.5sec, 페이지당 ~93건 (num_per_page=100 기준)
- AdaptiveRateLimiter가 자동으로 조절하므로 별도 설정 불필요

### 예상 소요 시간 (리뷰 수집, 실측 기준)

| 리뷰 수 | 페이지 수 | 예상 시간 |
|---------|----------|----------|
| 1,000 | ~11 | ~16초 |
| 5,000 | ~54 | ~1.5분 |
| 10,000 | ~107 | ~2.7분 |
| 30,000 | ~323 | ~8분 |

- 대량 수집(5,000+) 시 백그라운드 실행을 권장

## Error Handling

API 호출 실패 시 per-game 에러 핸들링으로 한 게임이 실패해도 나머지는 계속 진행된다.
실패 기록은 `failure_logs` 테이블에 자동 저장되며, `steam-diagnose` 스킬로 분석할 수 있다.

## Error Logging (필수)

**에러 발생 시 반드시 아래 순서를 따른다. 순서를 건너뛰지 않는다.**

### 순서: 기록 → 수정 → 해결

1. **즉시 기록** — 에러가 발생하면 수정을 시도하기 전에 `log_skill_error()`를 호출한다
2. **수정 시도** — 기록 후 원인을 분석하고 수정한다
3. **해결 처리** — 수정이 성공하면 `resolve_skill_error()`로 해결 마킹한다

> **금지**: 에러 발생 → 바로 수정 → 기록 생략. 이렇게 하면 반복 패턴을 추적할 수 없다.

### Step 1: 기록

```python
import sys
sys.path.insert(0, "<project-root>/steam-crawler/src")
from steam_crawler.skill_error_logger import log_skill_error

error_id = log_skill_error(
    db_path="<project-root>/data/steam.db",
    skill_name="steam-crawl",
    error_type="<type>",
    error_message="<full error message>",
    traceback="<traceback if available>",
    command="<code that caused error>",
    context={"appid": 286160, "step": "2B-igdb-keywords"},
    fix_applied=None  # 아직 수정 전이므로 None
)
```

### Step 2: 수정 후 해결 처리

```python
from steam_crawler.skill_error_logger import resolve_skill_error

resolve_skill_error(
    db_path="<project-root>/data/steam.db",
    error_id=error_id,
    resolution="code_fixed",  # code_fixed | workaround | skip
    fix_applied="<수정 내용>"
)
```

### error_type 분류
- `encoding` — 인코딩 에러 (cp949, utf-8 등)
- `sql` — SQL 에러 (missing column, syntax 등)
- `import` — 모듈 import 실패
- `timeout` — 실행 시간 초과
- `parse` — 데이터 파싱 실패
- `api` — 외부 API 실패 (IGDB, RAWG, Wikidata 등)
- `unknown` — 기타
