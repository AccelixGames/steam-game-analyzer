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

## How It Works

두 가지 실행 방식이 있다. 상황에 맞게 선택한다.

### 방식 1: CLI (간단한 수집)

태그/장르 기반 대량 수집에 적합하다.

```bash
cd <project-root>/steam-crawler
steam-crawler collect --tag "Roguelike" --limit 10 --top-n 3 --max-reviews 50
```

주요 옵션:
- `--tag TEXT` / `--genre TEXT` / `--top100` — 수집 대상 (하나 필수)
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

### 방식 2: Python 직접 호출 (세밀한 제어)

특정 게임 하나만 조회하거나, 결과를 바로 가공해서 보여줄 때 사용한다.

```python
import sys
sys.path.insert(0, "<project-root>/steam-crawler/src")

from steam_crawler.db.schema import init_db
from steam_crawler.api.steamspy import SteamSpyClient
from steam_crawler.api.steam_reviews import SteamReviewsClient
from steam_crawler.db.repository import upsert_game, insert_reviews_batch, update_game_review_stats
```

#### 특정 게임 조회 (appid로)

```python
spy = SteamSpyClient()
game = spy.fetch_app_details(APPID)
spy.close()
# game.name, game.positive, game.negative, game.owners, game.tags, game.price, game.avg_playtime
```

#### 리뷰 요약 조회

```python
rev = SteamReviewsClient()
summary = rev.fetch_summary(APPID)
# summary.total_positive, summary.total_negative, summary.review_score_desc
```

#### 리뷰 본문 수집

```python
reviews, cursor, has_more = rev.fetch_reviews_page(APPID, cursor="*", language="all")
# reviews[i].review_text, .voted_up, .playtime_at_review, .language, .author_steamid
rev.close()
```

#### DB에 저장

```python
conn = init_db("<project-root>/data/steam.db")
upsert_game(conn, game, version=0)
insert_reviews_batch(conn, reviews, version=0)
conn.close()
```

## Presenting Results

크롤링 결과를 사용자에게 보여줄 때는 다음을 포함한다:

1. **게임 정보**: 이름, 리뷰 수(긍정/부정), 평가, 소유자 수, 가격, 평균 플레이타임
2. **태그**: 상위 5~10개 태그 (투표 수 포함)
3. **리뷰 샘플**: 3~5개 리뷰 (긍정/부정 혼합, 텍스트 앞 100자 + 언어 + 플레이타임)
4. **DB 저장 여부**: 저장했으면 건수 알려주기
5. **태그 기반 수집 시**: SteamSpy 데이터 품질 경고 — 결과 게임이 실제로 해당 태그와 관련 있는지 확인 필요

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
- Steam Reviews: ~1 req/1.5sec
- AdaptiveRateLimiter가 자동으로 조절하므로 별도 설정 불필요
- 대량 수집(100+ 게임) 시 시간이 오래 걸릴 수 있음을 사용자에게 안내

## Error Handling

API 호출 실패 시 per-game 에러 핸들링으로 한 게임이 실패해도 나머지는 계속 진행된다.
실패 기록은 `failure_logs` 테이블에 자동 저장되며, `steam-diagnose` 스킬로 분석할 수 있다.
