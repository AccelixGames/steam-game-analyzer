# valid_reviews View Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** DB View `valid_reviews`를 추가하여 `/steam-insight` 스킬의 정성 분석 리뷰 품질을 개선한다.

**Architecture:** `VIEWS_SQL` 상수를 schema.py에 분리 추가하고, `init_db()`와 `_migrate()`에서 View를 생성/재생성한다. 스킬 문서의 정성 분석 쿼리만 `valid_reviews`로 교체한다.

**Tech Stack:** SQLite (윈도우 함수 ROW_NUMBER), Python, pytest

**Spec:** `docs/superpowers/specs/2026-03-19-valid-reviews-view-design.md`

---

## File Map

| 파일 | 변경 | 역할 |
|------|------|------|
| `steam-crawler/src/steam_crawler/db/schema.py` | Modify | `VIEWS_SQL` 상수 추가, `init_db()` 수정, `_migrate()` 수정 |
| `steam-crawler/tests/test_schema.py` | Modify | View 생성/필터링/중복제거/멱등성 테스트 추가 |
| `.claude/skills/steam-insight/SKILL.md` | Modify | View 설명 추가, 3-B 쿼리 교체 |

---

### Task 1: View 생성 테스트 작성

**Files:**
- Modify: `steam-crawler/tests/test_schema.py`

- [ ] **Step 1: valid_reviews View 존재 확인 테스트 작성**

```python
def test_valid_reviews_view_exists(db_conn):
    """valid_reviews View가 init_db로 생성된다."""
    cursor = db_conn.execute(
        "SELECT name FROM sqlite_master WHERE type='view'"
    )
    views = {row[0] for row in cursor.fetchall()}
    assert "valid_reviews" in views
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd steam-crawler && python -m pytest tests/test_schema.py::test_valid_reviews_view_exists -v`
Expected: FAIL — `valid_reviews` View가 아직 없음

---

### Task 2: VIEWS_SQL 상수 및 init_db 수정

**Files:**
- Modify: `steam-crawler/src/steam_crawler/db/schema.py:259` (SCHEMA_SQL 끝 이후)

- [ ] **Step 1: VIEWS_SQL 상수 추가 (SCHEMA_SQL 문자열 닫힌 직후)**

`schema.py`에서 `SCHEMA_SQL = """..."""` 끝나는 라인(259행) 바로 다음에 추가:

```python
VIEWS_SQL = """
-- valid_reviews: 정성 분석용 필터링된 리뷰 View
-- 100자 이상 OR 플레이타임 50시간(3000분) 이상, ASCII art 제거, 게임별 중복 1건
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
            PARTITION BY appid, review_text
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
"""
```

- [ ] **Step 2: init_db()에서 VIEWS_SQL 실행 추가**

`init_db()` 함수에서 `conn.executescript(SCHEMA_SQL)` 바로 다음 줄에 추가:

```python
conn.executescript(VIEWS_SQL)
```

- [ ] **Step 3: _migrate()에 View 재생성 추가**

`_migrate()` 함수의 인덱스 생성 블록(line 333-334) 이후, 마지막 `conn.commit()` (line 335) 직전에 추가:

```python
    # View 재생성 (정의 변경 시 기존 View 교체)
    conn.execute("DROP VIEW IF EXISTS valid_reviews")
    conn.executescript(VIEWS_SQL)
```

주의: `VIEWS_SQL`은 모듈 레벨 상수이므로 `_migrate()` 내에서 직접 참조 가능.

- [ ] **Step 4: Task 1 테스트 통과 확인**

Run: `cd steam-crawler && python -m pytest tests/test_schema.py::test_valid_reviews_view_exists -v`
Expected: PASS

- [ ] **Step 5: 기존 테스트 깨지지 않았는지 확인**

Run: `cd steam-crawler && python -m pytest tests/test_schema.py -v`
Expected: ALL PASS

- [ ] **Step 6: 커밋**

```bash
git add steam-crawler/src/steam_crawler/db/schema.py steam-crawler/tests/test_schema.py
git commit -m "feat: add valid_reviews View to schema"
```

---

### Task 3: View 필터링 로직 테스트

**Files:**
- Modify: `steam-crawler/tests/test_schema.py`

- [ ] **Step 1: 헬퍼 함수 + 필터링 테스트 작성**

`test_schema.py` 맨 아래에 추가:

```python
def _insert_review(conn, recommendation_id, appid, review_text,
                   playtime_at_review=100, voted_up=1,
                   weighted_vote_score=0.5, votes_up=1):
    """테스트용 리뷰 삽입 헬퍼."""
    conn.execute("INSERT OR IGNORE INTO games (appid, name) VALUES (?, ?)",
                 (appid, f"Game{appid}"))
    conn.execute(
        """INSERT INTO reviews
           (recommendation_id, appid, review_text, playtime_at_review,
            voted_up, weighted_vote_score, votes_up)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (recommendation_id, appid, review_text, playtime_at_review,
         voted_up, weighted_vote_score, votes_up),
    )
    conn.commit()


def test_valid_reviews_filters_short_text(db_conn):
    """100자 미만 + 플레이타임 50h 미만 → 제외."""
    _insert_review(db_conn, "r1", 1, "short", playtime_at_review=100)
    rows = db_conn.execute("SELECT * FROM valid_reviews WHERE appid=1").fetchall()
    assert len(rows) == 0


def test_valid_reviews_passes_long_text(db_conn):
    """100자 이상 → 통과."""
    long_text = "a" * 100
    _insert_review(db_conn, "r1", 1, long_text, playtime_at_review=10)
    rows = db_conn.execute("SELECT * FROM valid_reviews WHERE appid=1").fetchall()
    assert len(rows) == 1


def test_valid_reviews_passes_short_text_high_playtime(db_conn):
    """100자 미만이지만 플레이타임 50h+ → 통과."""
    _insert_review(db_conn, "r1", 1, "good game", playtime_at_review=3000)
    rows = db_conn.execute("SELECT * FROM valid_reviews WHERE appid=1").fetchall()
    assert len(rows) == 1


def test_valid_reviews_excludes_empty_text(db_conn):
    """빈 텍스트 → 제외."""
    _insert_review(db_conn, "r1", 1, "", playtime_at_review=5000)
    _insert_review(db_conn, "r2", 1, "   ", playtime_at_review=5000)
    _insert_review(db_conn, "r3", 1, None, playtime_at_review=5000)
    rows = db_conn.execute("SELECT * FROM valid_reviews WHERE appid=1").fetchall()
    assert len(rows) == 0


def test_valid_reviews_excludes_ascii_art(db_conn):
    """ASCII art 패턴 포함 → 제외."""
    art = "█" * 200
    _insert_review(db_conn, "r1", 1, art, playtime_at_review=100)
    rows = db_conn.execute("SELECT * FROM valid_reviews WHERE appid=1").fetchall()
    assert len(rows) == 0


def test_valid_reviews_excludes_null_playtime_short_text(db_conn):
    """playtime NULL + 짧은 텍스트 → 제외."""
    _insert_review(db_conn, "r1", 1, "short", playtime_at_review=None)
    rows = db_conn.execute("SELECT * FROM valid_reviews WHERE appid=1").fetchall()
    assert len(rows) == 0
```

- [ ] **Step 2: 테스트 실행**

Run: `cd steam-crawler && python -m pytest tests/test_schema.py -k "valid_reviews" -v`
Expected: ALL PASS

- [ ] **Step 3: 커밋**

```bash
git add steam-crawler/tests/test_schema.py
git commit -m "test: add valid_reviews filtering tests"
```

---

### Task 4: View 중복 제거 테스트

**Files:**
- Modify: `steam-crawler/tests/test_schema.py`

- [ ] **Step 1: 중복 제거 테스트 작성**

```python
def test_valid_reviews_deduplicates_same_game(db_conn):
    """동일 게임 내 동일 텍스트 → weighted_vote_score 최고 1건만 유지."""
    text = "a" * 150
    _insert_review(db_conn, "r1", 1, text, weighted_vote_score=0.3, votes_up=1)
    _insert_review(db_conn, "r2", 1, text, weighted_vote_score=0.9, votes_up=5)
    _insert_review(db_conn, "r3", 1, text, weighted_vote_score=0.6, votes_up=3)
    rows = db_conn.execute("SELECT * FROM valid_reviews WHERE appid=1").fetchall()
    assert len(rows) == 1
    assert rows[0]["recommendation_id"] == "r2"  # 최고 score


def test_valid_reviews_keeps_dupes_across_games(db_conn):
    """다른 게임의 동일 텍스트 → 각각 유지."""
    text = "a" * 150
    _insert_review(db_conn, "r1", 1, text, weighted_vote_score=0.5)
    _insert_review(db_conn, "r2", 2, text, weighted_vote_score=0.5)
    rows = db_conn.execute("SELECT * FROM valid_reviews").fetchall()
    assert len(rows) == 2
```

- [ ] **Step 2: 테스트 실행**

Run: `cd steam-crawler && python -m pytest tests/test_schema.py -k "dedup" -v`
Expected: ALL PASS

- [ ] **Step 3: 커밋**

```bash
git add steam-crawler/tests/test_schema.py
git commit -m "test: add valid_reviews deduplication tests"
```

---

### Task 5: 멱등성 테스트

**Files:**
- Modify: `steam-crawler/tests/test_schema.py`

- [ ] **Step 1: View 재생성 멱등성 테스트 작성**

```python
def test_valid_reviews_survives_reinit(db_path):
    """init_db 두 번 호출해도 View가 정상 동작한다."""
    from steam_crawler.db.schema import init_db

    conn1 = init_db(str(db_path))
    conn1.close()
    conn2 = init_db(str(db_path))
    views = {
        row[0]
        for row in conn2.execute(
            "SELECT name FROM sqlite_master WHERE type='view'"
        ).fetchall()
    }
    assert "valid_reviews" in views
    conn2.close()
```

- [ ] **Step 2: 테스트 실행**

Run: `cd steam-crawler && python -m pytest tests/test_schema.py::test_valid_reviews_survives_reinit -v`
Expected: PASS

- [ ] **Step 3: 전체 테스트 스위트 실행**

Run: `cd steam-crawler && python -m pytest tests/test_schema.py -v`
Expected: ALL PASS

- [ ] **Step 4: 커밋**

```bash
git add steam-crawler/tests/test_schema.py
git commit -m "test: add valid_reviews idempotency test"
```

---

### Task 6: 스킬 문서 업데이트

**Files:**
- Modify: `.claude/skills/steam-insight/SKILL.md:10-17` (DB 접근 섹션 직후)
- Modify: `.claude/skills/steam-insight/SKILL.md:190-210` (3-B 쿼리)

- [ ] **Step 1: DB 접근 섹션 직후에 View 설명 추가**

SKILL.md의 `## DB 접근` 섹션 (라인 10-17) 코드블록 닫힘 직후, `## 분석 프레임워크` 직전에 삽입:

```markdown
## 유효 리뷰 View

`valid_reviews` — 정성 분석용 필터링된 리뷰 View.
- 100자 이상 OR 플레이타임 50시간 이상
- ASCII art 제거, 게임별 중복 텍스트 1건만 유지 (weighted_vote_score 최고)
- **정성 분석(리뷰 인용/분석)에만 사용. 정량 통계는 `reviews` 테이블 사용.**
- playtime_at_review가 NULL이고 100자 미만인 리뷰는 제외됨
- 필터링으로 일부 게임에서 결과가 LIMIT 미만일 수 있음
```

- [ ] **Step 2: 3-B 정성 분석 쿼리 교체**

SKILL.md 라인 193-210의 SQL 블록을 다음으로 교체:

```sql
-- 장문 긍정 리뷰 (깊이 있는 피드백) — valid_reviews 사용
SELECT language, review_text, playtime_at_review, votes_up
FROM valid_reviews WHERE appid = ? AND voted_up = 1 AND length(review_text) > 200
ORDER BY length(review_text) DESC LIMIT 10;

-- 가장 도움이 된 긍정 리뷰 — valid_reviews 사용
SELECT language, review_text, playtime_at_review, votes_up, weighted_vote_score
FROM valid_reviews WHERE appid = ? AND voted_up = 1
ORDER BY weighted_vote_score DESC LIMIT 10;
```

부정 리뷰도 교체:

```sql
-- 부정 리뷰 — valid_reviews 사용
SELECT language, review_text, playtime_at_review, votes_up, weighted_vote_score
FROM valid_reviews WHERE appid = ? AND voted_up = 0
ORDER BY weighted_vote_score DESC LIMIT 10;
```

교체하지 않는 쿼리 (정량 — `FROM reviews` 유지):
- 플레이타임별 긍정률 (라인 214-226)
- 언어별 분포 (라인 230-234)
- Footer 리뷰 수 카운트 (라인 475)

- [ ] **Step 3: 커밋**

```bash
git add .claude/skills/steam-insight/SKILL.md
git commit -m "feat: update steam-insight skill to use valid_reviews View"
```

---

### Task 7: 실 데이터 검증

- [ ] **Step 1: View가 실 DB에서 동작하는지 확인**

```bash
cd steam-crawler && python -c "
import sqlite3, sys, os
sys.stdout.reconfigure(encoding='utf-8')
from steam_crawler.db.schema import init_db
db_path = os.path.join('..', 'data', 'steam.db')
conn = init_db(db_path)
total = conn.execute('SELECT count(*) FROM reviews').fetchone()[0]
valid = conn.execute('SELECT count(*) FROM valid_reviews').fetchone()[0]
print(f'전체: {total}, 유효: {valid} ({100*valid/total:.1f}%)')
# 샘플
for row in conn.execute('SELECT appid, count(*) as cnt FROM valid_reviews GROUP BY appid ORDER BY cnt DESC LIMIT 5').fetchall():
    print(f'  appid={row[0]}: {row[1]}건')
conn.close()
"
```

Expected: 유효 리뷰가 전체의 약 22-30% 수준으로 필터링됨

- [ ] **Step 2: 전체 테스트 스위트 최종 확인**

Run: `cd steam-crawler && python -m pytest -v`
Expected: ALL PASS

- [ ] **Step 3: 최종 커밋 (필요시)**

남은 변경사항이 있으면 커밋.
