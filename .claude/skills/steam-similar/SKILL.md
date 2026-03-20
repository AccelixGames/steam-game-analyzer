---
name: steam-similar
description: "Steam 유사 게임 탐색. Use when user asks to find similar games, compare games, or wants 'More Like This' recommendations. Triggers on: '비슷한 게임', '유사한 게임', '추천 게임', 'similar games', 'more like this', 'games like X', '이거랑 비슷한', '관련 게임', '경쟁작', 'competitors'"
---

# Steam Similar Games

Steam Store의 "More Like This" 추천 데이터를 기반으로 유사 게임을 탐색하는 스킬.

## Project Location

크롤러 코드: `steam-crawler/src/steam_crawler/`
DB: `data/steam.db`

## When to Use

- 특정 게임과 비슷한 게임을 찾을 때
- 경쟁작/유사작을 리뷰수 기준으로 비교할 때
- 유사 게임의 리뷰를 수집하기 전 대상을 선정할 때

## How It Works

### 핵심 API: `SteamStoreClient.fetch_similar_appids()`

Steam Store 페이지에 임베딩된 "More Like This" 캐러셀의 appID 목록을 파싱한다.
Steam의 추천 알고리즘(플레이어 행동 데이터 기반)을 활용하므로 태그 기반 검색보다 정확하다.

```python
import sys
sys.path.insert(0, "<project-root>/steam-crawler/src")

from steam_crawler.api.steam_store import SteamStoreClient
from steam_crawler.api.steamspy import SteamSpyClient

store = SteamStoreClient()
spy = SteamSpyClient()
```

### Step 1: 대상 게임 정보 확인

사용자가 URL을 제공하면 appid를 추출한다. 이름만 제공하면 Steam Store 검색으로 appid를 찾는다.

```python
# URL에서 appid 추출
import re
url = "https://store.steampowered.com/app/3070070/TCG_Card_Shop_Simulator/"
appid = int(re.search(r'/app/(\d+)', url).group(1))

# 대상 게임 정보 조회
target = spy.fetch_app_details(appid)
print(f"{target.name}: +{target.positive}/-{target.negative}")
print(f"태그: {list(target.tags.keys())[:10]}")
```

### Step 2: 유사 게임 목록 조회

```python
similar_appids = store.fetch_similar_appids(appid)
# 최대 30개 appid 반환 (Steam이 추천하는 순서)
```

### Step 3: 유사 게임 상세 정보 수집

SteamSpy로 각 게임의 리뷰수, 태그, 소유자 등을 조회한다.

```python
import time

results = []
for aid in similar_appids:
    try:
        game = spy.fetch_app_details(aid)
        total_reviews = game.positive + game.negative
        results.append({
            "appid": aid,
            "name": game.name,
            "positive": game.positive,
            "negative": game.negative,
            "total_reviews": total_reviews,
            "owners": game.owners,
            "price": game.price,
            "tags": list(game.tags.keys())[:5] if game.tags else [],
        })
        time.sleep(1.2)  # SteamSpy rate limit
    except Exception as e:
        print(f"SKIP [{aid}]: {e}")

# 리뷰수 기준 정렬
results.sort(key=lambda x: x["total_reviews"], reverse=True)
```

### Step 4: 결과를 사용자에게 보여주기 (선택) 리뷰 크롤링

유사 게임 중 상위 N개를 선정한 후, `steam-crawl` 스킬의 Python 직접 호출 방식으로 리뷰를 수집할 수 있다.

```python
spy.close()
store.close()
```

## Presenting Results

결과를 보여줄 때는 **대상 게임과 비교 가능한 테이블**을 제공한다:

```
## [대상 게임] 유사 게임 TOP 5 (리뷰수 기준)

| 순위 | 게임 | 리뷰 | 긍정률 | 소유자 | 가격 | 공통 태그 |
|------|------|------|--------|--------|------|----------|
| 1 | Game A | 95,144 | 94.2% | 2~5M | $24.99 | Sim, Mgmt |
| ... | ... | ... | ... | ... | ... | ... |
```

포함할 항목:
1. 리뷰수 (긍정/부정), 긍정률
2. 소유자 수, 가격
3. 대상 게임과의 **공통 태그** (유사도 판단 근거)
4. 태그 기반 SteamSpy 검색이 아닌 Steam 추천 알고리즘 기반임을 안내

## Finding AppID from Game Name or URL

```python
import re

# URL에서 추출
def appid_from_url(url: str) -> int | None:
    m = re.search(r'/app/(\d+)', url)
    return int(m.group(1)) if m else None

# 이름으로 검색 — Steam Store 검색 페이지 파싱
def search_appid(name: str) -> list[tuple[int, str]]:
    import httpx
    resp = httpx.get(
        "https://store.steampowered.com/search/",
        params={"term": name, "category1": "998"},  # 998 = games only
        headers={"Accept-Language": "en"},
        follow_redirects=True,
        timeout=15,
    )
    matches = re.findall(
        r'data-ds-appid="(\d+)".*?<span class="title">([^<]+)</span>',
        resp.text, re.DOTALL,
    )
    return [(int(aid), title) for aid, title in matches[:10]]
```

## Known Limitations

- Steam Store 페이지의 "More Like This"는 최대 **30개**까지만 반환
- 추천 목록은 **셔플 순서**이므로 매번 순서가 다를 수 있음 (게임 목록 자체는 동일)
- SteamSpy에 등록되지 않은 신작은 상세 정보 조회 실패 가능
- 비공개/삭제된 게임은 store 페이지 접근 불가

## Rate Limits

- Steam Store 페이지: 1 req/1.5sec (기본 딜레이)
- SteamSpy: 1 req/sec
- 30개 유사 게임 전체 조회 시 약 40~50초 소요

## Error Logging (필수)

Bash로 Python 코드 실행 시 에러가 발생하면, 수정 시도 전에 반드시 기록한다:

```python
import sys
sys.path.insert(0, "<project-root>/steam-crawler/src")
from steam_crawler.skill_error_logger import log_skill_error

log_skill_error(
    db_path="<project-root>/data/steam.db",
    skill_name="steam-similar",
    error_type="<type>",
    error_message="<full error message>",
    traceback="<traceback if available>",
    command="<code that caused error>",
    context={"appid": 286160, "step": "2B-igdb-keywords"},
    fix_applied="<fix description, if applied>"
)
```

error_type 분류:
- `encoding` — 인코딩 에러 (cp949, utf-8 등)
- `sql` — SQL 에러 (missing column, syntax 등)
- `import` — 모듈 import 실패
- `timeout` — 실행 시간 초과
- `parse` — 데이터 파싱 실패
- `api` — 외부 API 실패 (IGDB, RAWG, Wikidata 등)
- `unknown` — 기타
