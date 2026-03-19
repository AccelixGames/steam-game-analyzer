# valid_reviews View 설계

## 목적

`/steam-insight` 스킬의 정성 분석(3단계 3-B)에서 사용할 "유효 리뷰" 필터를 DB View로 제공한다.
정량 통계(플레이타임별 긍정률, 언어별 분포 등)는 기존 `reviews` 테이블을 그대로 사용한다.

## 유효 리뷰 기준

| 규칙 | 조건 |
|------|------|
| 기본 통과 | `length(review_text) >= 100` |
| 짧아도 통과 | `length(review_text) < 100` AND `playtime_at_review >= 3000` (50시간) |
| 제외: 빈 텍스트 | `review_text IS NULL OR trim(review_text) = ''` |
| 제외: ASCII art | `⣿`, `█`, `▀` 패턴 포함 |
| 제외: 중복 텍스트 | 동일 게임 내 동일 텍스트 → `weighted_vote_score` 최고 1건만 유지 |

Edge case: `playtime_at_review`가 NULL이고 텍스트가 100자 미만인 리뷰는 제외된다 (NULL >= 3000은 SQLite에서 false).

## View 정의

```sql
CREATE VIEW IF NOT EXISTS valid_reviews AS
WITH filtered AS (
    SELECT *
    FROM reviews
    WHERE review_text IS NOT NULL
      AND trim(review_text) != ''
      AND review_text NOT LIKE '%⣿%'
      AND review_text NOT LIKE '%█%'
      AND review_text NOT LIKE '%▀%'
      AND (
        length(review_text) >= 100
        OR playtime_at_review >= 3000  -- 50시간 (분 단위)
      )
),
deduped AS (
    SELECT *,
        ROW_NUMBER() OVER (
            PARTITION BY appid, review_text  -- 게임별 중복 제거
            ORDER BY weighted_vote_score DESC, votes_up DESC
        ) AS rn
    FROM filtered
)
SELECT recommendation_id, appid, language, review_text,
       voted_up, playtime_forever, playtime_at_review,
       early_access, steam_purchase, received_for_free,
       dev_response, timestamp_created, votes_up, votes_funny,
       weighted_vote_score, comment_count, author_steamid,
       author_num_reviews, author_playtime_forever,
       collected_ver, collected_at
FROM deduped WHERE rn = 1;
```

## schema.py 변경

### 1. View SQL을 별도 상수로 분리

`SCHEMA_SQL` 끝에 직접 추가하지 않고 `VIEWS_SQL` 상수로 분리한다.
향후 View 정의 변경 시 `_migrate()`에서 `DROP VIEW + CREATE VIEW`로 교체하기 쉽게 하기 위함.

```python
VIEWS_SQL = """
CREATE VIEW IF NOT EXISTS valid_reviews AS
...
"""
```

### 2. init_db()에서 VIEWS_SQL 실행

```python
def init_db(db_path):
    ...
    conn.executescript(SCHEMA_SQL)
    conn.executescript(VIEWS_SQL)
    _migrate(conn)
    return conn
```

### 3. _migrate()에 View 재생성 패턴 추가

기존 DB에서 View 정의가 변경되었을 때를 대비:

```python
def _migrate(conn):
    ...
    # View 재생성 (정의 변경 시 기존 View 교체)
    conn.execute("DROP VIEW IF EXISTS valid_reviews")
    conn.executescript(VIEWS_SQL)
```

## 스킬 문서 변경

### 1. `## DB 접근` 섹션 직후에 View 설명 추가

```markdown
## 유효 리뷰 View

`valid_reviews` — 정성 분석용 필터링된 리뷰 View.
- 100자 이상 OR 플레이타임 50시간 이상
- ASCII art 제거, 게임별 중복 텍스트 1건만 유지
- 정성 분석(리뷰 인용/분석)에만 사용. 정량 통계는 `reviews` 테이블 사용.
```

### 2. 3단계 3-B 쿼리 교체

`FROM reviews` → `FROM valid_reviews` (정성 분석 쿼리만):

- 장문 긍정 리뷰 (`length > 200` 조건 유지 — View 위에 추가 필터)
- 가장 도움이 된 긍정 리뷰
- 부정 리뷰

교체하지 않는 쿼리 (정량):
- 플레이타임별 긍정률
- 언어별 분포

### 3. 주의사항 추가

- `valid_reviews`는 필터링된 View이므로 일부 게임에서 결과가 LIMIT 미만일 수 있음
- 리뷰 수가 적은 경우 `reviews` 테이블의 전체 건수도 함께 명시

## 변경하지 않는 것

- 정량 통계 쿼리 (플레이타임별 긍정률, 언어별 분포) — `reviews` 유지
- Footer 메타데이터의 리뷰 수 카운트 — `reviews` 유지
- MCP 서버의 `search_reviews` — 향후 별도 판단 (이번 스코프 아님)
