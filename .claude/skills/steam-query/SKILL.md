---
name: steam-query
description: "수집된 Steam 게임/리뷰 데이터 조회 및 출력. Use when user wants to VIEW, LIST, SEARCH, or BROWSE already-collected data. Triggers on: '게임 목록 보여줘', '수집한 데이터', '리뷰 보여줘', '태그 검색', '어떤 게임 있어?', 'show games', 'list reviews', '데이터 출력', '정보 조회'. This skill is for READING data, not collecting — if user wants to crawl/fetch new data, use steam-crawl instead."
---

# Steam Query

수집된 Steam 데이터를 조회하고 보기 좋게 출력하는 스킬. 새 데이터를 수집하는 것이 아니라, 이미 DB에 있는 데이터를 읽는다.

## DB 접근

```python
import sqlite3
conn = sqlite3.connect("<project-root>/data/steam.db")
conn.row_factory = sqlite3.Row
```

## 쿼리 레시피

### 게임 목록

**전체 게임 (리뷰 수 순)**
```sql
SELECT appid, name, positive, negative, steam_positive, steam_negative,
       review_score, owners, price, avg_playtime, source_tag
FROM games ORDER BY positive DESC;
```

**특정 태그의 게임**
```sql
SELECT g.appid, g.name, g.positive, g.negative, g.review_score,
       gt.vote_count as tag_votes
FROM game_tags gt
JOIN games g ON g.appid = gt.appid
WHERE gt.tag_name = ?
ORDER BY gt.vote_count DESC;
```

**게임 검색 (이름)**
```sql
SELECT * FROM games WHERE name LIKE '%검색어%';
```

### 태그

**특정 게임의 태그**
```sql
SELECT tag_name, vote_count FROM game_tags
WHERE appid = ? ORDER BY vote_count DESC;
```

**전체 태그 목록 (게임 수 기준)**
```sql
SELECT tag_name, count(*) as game_count, sum(vote_count) as total_votes
FROM game_tags GROUP BY tag_name
ORDER BY game_count DESC;
```

**두 태그를 동시에 가진 게임**
```sql
SELECT g.appid, g.name, g.positive
FROM games g
WHERE g.appid IN (SELECT appid FROM game_tags WHERE tag_name = ?)
  AND g.appid IN (SELECT appid FROM game_tags WHERE tag_name = ?)
ORDER BY g.positive DESC;
```

### 리뷰

> **⚠ 편향 주의**: 부정 리뷰 보강 수집으로 `reviews` 테이블의 긍/부정 비율은 실제와 다를 수 있음. 전체 긍정률은 `games.steam_positive` / `games.steam_negative` 사용.

**특정 게임 리뷰 (최신순)**
```sql
SELECT recommendation_id, language, review_text, voted_up,
       playtime_at_review, votes_up, votes_funny,
       weighted_vote_score, comment_count, timestamp_created
FROM reviews WHERE appid = ?
ORDER BY timestamp_created DESC;
```

**긍정/부정 리뷰 필터링**
```sql
SELECT * FROM reviews
WHERE appid = ? AND voted_up = ?
ORDER BY votes_up DESC;
```

**가장 도움이 된 리뷰**
```sql
SELECT review_text, voted_up, votes_up, playtime_at_review, language
FROM reviews WHERE appid = ?
ORDER BY weighted_vote_score DESC LIMIT 10;
```

**언어별 리뷰 분포**
```sql
SELECT language, count(*) as cnt,
       sum(voted_up) as positive, count(*) - sum(voted_up) as negative
FROM reviews WHERE appid = ?
GROUP BY language ORDER BY cnt DESC;
```

**리뷰어 플레이타임 분포**
```sql
SELECT
  CASE
    WHEN playtime_at_review < 60 THEN '< 1h'
    WHEN playtime_at_review < 600 THEN '1-10h'
    WHEN playtime_at_review < 3000 THEN '10-50h'
    WHEN playtime_at_review < 6000 THEN '50-100h'
    ELSE '100h+'
  END as playtime_bucket,
  count(*) as cnt,
  round(100.0 * sum(voted_up) / count(*), 1) as positive_rate
FROM reviews WHERE appid = ?
GROUP BY playtime_bucket;
```

### 통계 요약

**전체 DB 요약**
```sql
SELECT
  (SELECT count(*) FROM games) as total_games,
  (SELECT count(*) FROM reviews) as total_reviews,
  (SELECT count(DISTINCT tag_name) FROM game_tags) as unique_tags,
  (SELECT count(*) FROM data_versions) as versions;
```

**수집 이력**
```sql
SELECT version, query_type, query_value, status,
       games_total, reviews_total, created_at, note
FROM data_versions ORDER BY version DESC;
```

### 비교 분석

**게임 간 비교**
```sql
SELECT g.appid, g.name, g.positive, g.negative,
       g.steam_positive, g.review_score, g.owners, g.price,
       g.avg_playtime,
       (SELECT count(*) FROM reviews r WHERE r.appid = g.appid) as review_count
FROM games g
WHERE g.appid IN (?, ?, ?)
ORDER BY g.positive DESC;
```

**태그 공통점 비교 (두 게임)**
```sql
SELECT a.tag_name,
       a.vote_count as game1_votes,
       b.vote_count as game2_votes
FROM game_tags a
JOIN game_tags b ON a.tag_name = b.tag_name
WHERE a.appid = ? AND b.appid = ?
ORDER BY a.vote_count DESC;
```

## 출력 형식

데이터를 보여줄 때는 상황에 맞게 형식을 선택한다:

**게임 목록** — 테이블 형태
```
| Name | Positive | Negative | Score | Owners |
|------|----------|----------|-------|--------|
```

**리뷰 샘플** — 개별 블록
```
[+] english | 32h played | 10 helpful
"리뷰 텍스트 앞 150자..."
```

**통계** — 요약 박스
```
## DB Summary
- Games: 6
- Reviews: 240
- Tags: 45 unique
```

**태그** — 인라인 리스트
```
Tags: Roguelike (1,728) · Card Game (1,588) · Rogue-like (1,398) · ...
```

## 주의사항

- 이 스킬은 **읽기 전용** — DB를 수정하지 않는다
- 데이터가 없으면 "수집된 데이터가 없습니다. `steam-crawl` 스킬로 먼저 수집하세요"라고 안내
- 리뷰 텍스트는 기본 150자까지만 보여주고, 사용자가 원하면 전문 출력
- 플레이타임은 분 단위로 저장되어 있으므로 시간으로 변환하여 표시 (÷60)
- 가격은 센트 단위이므로 달러로 변환 (÷100)

## Error Logging (필수)

Bash로 Python 코드 실행 시 에러가 발생하면, 수정 시도 전에 반드시 기록한다:

```python
import sys
sys.path.insert(0, "<project-root>/steam-crawler/src")
from steam_crawler.skill_error_logger import log_skill_error

log_skill_error(
    db_path="<project-root>/data/steam.db",
    skill_name="steam-query",
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
