# Review Coverage Improvement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 한국어 리뷰 과소대표 해소 + 부정 리뷰 2-pass 보강 + 편향 해소

**Architecture:** `valid_reviews` VIEW에 한국어 50자 분기 추가, `step3_crawl.py`에 부정 보강 로직 추가 (기존 수집 완료 후 자동 실행), 스킬 문서에 편향 방지 규칙 명시

**Tech Stack:** Python 3.12, SQLite (raw SQL), pytest, Rich console

**Spec:** `docs/superpowers/specs/2026-03-19-review-coverage-improvement-design.md`

---

## File Structure

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `steam-crawler/src/steam_crawler/db/schema.py:261-294` | `valid_reviews` VIEW에 한국어 분기 추가 |
| Modify | `steam-crawler/src/steam_crawler/pipeline/step3_crawl.py` | 부정 리뷰 보강 로직 추가 |
| Modify | `steam-crawler/tests/test_schema.py` | 한국어 임계값 테스트 추가 |
| Modify | `steam-crawler/tests/test_pipeline.py` | 부정 보강 테스트 추가 |
| Modify | `.claude/skills/steam-insight/SKILL.md` | 문서 업데이트 (50자 규칙, 편향 방지) |
| Modify | `.claude/skills/steam-query/SKILL.md` | 편향 방지 규칙 명시 |

---

### Task 1: `valid_reviews` VIEW 한국어 50자 분기 — 테스트

**Files:**
- Modify: `steam-crawler/tests/test_schema.py`

- [ ] **Step 1: `_insert_review` 헬퍼에 `language` 파라미터 추가**

`test_schema.py`의 `_insert_review` 헬퍼에 `language` 파라미터를 추가한다:

```python
def _insert_review(conn, recommendation_id, appid, review_text,
                   playtime_at_review=100, voted_up=1,
                   weighted_vote_score=0.5, votes_up=1,
                   language=None):
    """테스트용 리뷰 삽입 헬퍼."""
    conn.execute("INSERT OR IGNORE INTO games (appid, name) VALUES (?, ?)",
                 (appid, f"Game{appid}"))
    conn.execute(
        """INSERT INTO reviews
           (recommendation_id, appid, review_text, language, playtime_at_review,
            voted_up, weighted_vote_score, votes_up)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (recommendation_id, appid, review_text, language, playtime_at_review,
         voted_up, weighted_vote_score, votes_up),
    )
    conn.commit()
```

- [ ] **Step 2: 한국어 경계값 테스트 작성**

```python
def test_valid_reviews_korean_50char_passes(db_conn):
    """한국어 50자 리뷰 → 통과."""
    text = "가" * 50
    _insert_review(db_conn, "kr1", 1, text, language="koreana", playtime_at_review=10)
    rows = db_conn.execute("SELECT * FROM valid_reviews WHERE appid=1").fetchall()
    assert len(rows) == 1


def test_valid_reviews_korean_49char_excluded(db_conn):
    """한국어 49자 리뷰 → 제외 (playtime < 3000)."""
    text = "가" * 49
    _insert_review(db_conn, "kr2", 1, text, language="koreana", playtime_at_review=10)
    rows = db_conn.execute("SELECT * FROM valid_reviews WHERE appid=1").fetchall()
    assert len(rows) == 0


def test_valid_reviews_english_100char_still_required(db_conn):
    """영어 99자 리뷰 → 여전히 제외."""
    text = "a" * 99
    _insert_review(db_conn, "en1", 1, text, language="english", playtime_at_review=10)
    rows = db_conn.execute("SELECT * FROM valid_reviews WHERE appid=1").fetchall()
    assert len(rows) == 0


def test_valid_reviews_korean_short_high_playtime(db_conn):
    """한국어 30자 + 플레이타임 50h+ → 통과 (playtime 우선)."""
    text = "가" * 30
    _insert_review(db_conn, "kr3", 1, text, language="koreana", playtime_at_review=3000)
    rows = db_conn.execute("SELECT * FROM valid_reviews WHERE appid=1").fetchall()
    assert len(rows) == 1
```

- [ ] **Step 3: 테스트 실행 — FAIL 확인**

Run: `cd steam-crawler && python -m pytest tests/test_schema.py::test_valid_reviews_korean_50char_passes tests/test_schema.py::test_valid_reviews_korean_49char_excluded tests/test_schema.py::test_valid_reviews_english_100char_still_required tests/test_schema.py::test_valid_reviews_korean_short_high_playtime -v`

Expected: `test_valid_reviews_korean_50char_passes` FAIL (현재 VIEW는 100자 기준이므로 50자 한국어 리뷰가 제외됨)

---

### Task 2: `valid_reviews` VIEW 한국어 50자 분기 — 구현

**Files:**
- Modify: `steam-crawler/src/steam_crawler/db/schema.py:261-294`

- [ ] **Step 1: `VIEWS_SQL`의 length 필터를 CASE 분기로 변경**

`schema.py`의 `VIEWS_SQL` (line 273-276)을 수정한다:

변경 전:
```sql
      AND (
        length(review_text) >= 100
        OR playtime_at_review >= 3000  -- 50시간 (분 단위)
      )
```

변경 후:
```sql
      AND (
        CASE
          WHEN language = 'koreana' THEN length(review_text) >= 50
          ELSE length(review_text) >= 100
        END
        OR playtime_at_review >= 3000  -- 50시간 (분 단위)
      )
```

VIEW 상단 주석도 업데이트:

변경 전:
```sql
-- valid_reviews: 정성 분석용 필터링된 리뷰 View
-- 100자 이상 OR 플레이타임 50시간(3000분) 이상, ASCII art 제거, 게임별 중복 1건
```

변경 후:
```sql
-- valid_reviews: 정성 분석용 필터링된 리뷰 View
-- 100자 이상 (한국어: 50자) OR 플레이타임 50시간(3000분) 이상, ASCII art 제거, 게임별 중복 1건
-- 주의: 부정 보강 후 reviews 테이블 COUNT로 전체 긍/부정 비율 계산 금지 → games.steam_positive/steam_negative 사용
```

- [ ] **Step 2: 테스트 실행 — PASS 확인**

Run: `cd steam-crawler && python -m pytest tests/test_schema.py -v`

Expected: 전체 PASS (기존 테스트 + 새 한국어 테스트 4건)

- [ ] **Step 3: Commit**

```bash
git add steam-crawler/src/steam_crawler/db/schema.py steam-crawler/tests/test_schema.py
git commit -m "feat: add Korean 50-char threshold to valid_reviews VIEW"
```

---

### Task 3: 부정 리뷰 보강 — 테스트

**Files:**
- Modify: `steam-crawler/tests/test_pipeline.py`

**참고**: 기존 `test_pipeline.py`는 `_mock_response`, `_create_version` 헬퍼와 `MOCK_REVIEWS_PAGE`, `MOCK_EMPTY_PAGE` 상수를 사용. 동일 패턴을 따른다. `_supplement_negative_reviews`를 직접 테스트한다 (import: `from steam_crawler.pipeline.step3_crawl import _supplement_negative_reviews, _count_reviews_by_sentiment`).

- [ ] **Step 1: 테스트 헬퍼 및 보강 실행 테스트 추가**

```python
def _setup_game_for_supplement(db_conn, appid=730, steam_positive=9000, steam_negative=1000,
                                num_positive=900, num_negative=50):
    """부정 보강 테스트용 게임+리뷰 셋업."""
    db_conn.execute("INSERT OR IGNORE INTO games (appid, name, steam_positive, steam_negative) VALUES (?, ?, ?, ?)",
                    (appid, f"Game{appid}", steam_positive, steam_negative))
    for i in range(num_positive):
        db_conn.execute(
            "INSERT OR IGNORE INTO reviews (recommendation_id, appid, review_text, voted_up) VALUES (?, ?, ?, ?)",
            (f"pos_{i}", appid, f"positive review {i}", 1))
    for i in range(num_negative):
        db_conn.execute(
            "INSERT OR IGNORE INTO reviews (recommendation_id, appid, review_text, voted_up) VALUES (?, ?, ?, ?)",
            (f"neg_{i}", appid, f"negative review {i}", 0))
    db_conn.commit()


def test_count_reviews_by_sentiment(db_conn):
    """_count_reviews_by_sentiment 헬퍼 정확성 확인."""
    from steam_crawler.pipeline.step3_crawl import _count_reviews_by_sentiment
    _setup_game_for_supplement(db_conn, num_positive=10, num_negative=5)
    pos, neg = _count_reviews_by_sentiment(db_conn, 730)
    assert pos == 10
    assert neg == 5


def test_negative_supplement_runs_when_insufficient(db_conn):
    """부정 리뷰가 목표 미달이면 보강 패스 실행."""
    from steam_crawler.pipeline.step3_crawl import _supplement_negative_reviews
    from steam_crawler.api.steam_reviews import SteamReviewsClient
    from steam_crawler.api.resilience import FailureTracker

    version = _create_version(db_conn)
    _setup_game_for_supplement(db_conn, steam_positive=9000, steam_negative=1000,
                               num_positive=900, num_negative=50)

    client = SteamReviewsClient()
    tracker = FailureTracker()

    # Mock: return negative reviews then empty
    neg_review_page = {
        "success": 1,
        "reviews": [
            {
                "recommendationid": f"supp_neg_{i}", "language": "english",
                "review": f"Bad game {i}", "voted_up": False,
                "steam_purchase": True, "received_for_free": False,
                "written_during_early_access": False,
                "timestamp_created": 1700000000 + i, "votes_up": 1, "votes_funny": 0,
                "weighted_vote_score": "0.5", "comment_count": 0,
                "author": {"steamid": f"supp_{i}", "num_reviews": 1,
                           "playtime_forever": 100, "playtime_at_review": 50},
            }
            for i in range(80)
        ],
        "cursor": "nextcursor==",
    }
    responses = [_mock_response(neg_review_page), _mock_response(neg_review_page),
                 _mock_response(MOCK_EMPTY_PAGE)]
    with patch.object(client._client, "get", side_effect=responses) as mock_get:
        added = _supplement_negative_reviews(db_conn, 730, version, "all", client, tracker)

    assert added > 0
    # Verify review_type=negative was used
    for call in mock_get.call_args_list:
        params = call[1].get("params", call[0][1] if len(call[0]) > 1 else {})
        assert params.get("review_type") == "negative"


def test_negative_supplement_skips_when_sufficient(db_conn):
    """부정 리뷰가 이미 충분하면 스킵."""
    from steam_crawler.pipeline.step3_crawl import _supplement_negative_reviews
    from steam_crawler.api.steam_reviews import SteamReviewsClient
    from steam_crawler.api.resilience import FailureTracker

    version = _create_version(db_conn)
    # target = max(200, 500 * 1000/9000) = 200, already have 250
    _setup_game_for_supplement(db_conn, steam_positive=9000, steam_negative=1000,
                               num_positive=500, num_negative=250)

    client = SteamReviewsClient()
    tracker = FailureTracker()

    with patch.object(client._client, "get") as mock_get:
        added = _supplement_negative_reviews(db_conn, 730, version, "all", client, tracker)

    assert added == 0
    mock_get.assert_not_called()


def test_negative_supplement_skips_low_official_negative(db_conn):
    """steam_negative < 10 → 스킵."""
    from steam_crawler.pipeline.step3_crawl import _supplement_negative_reviews
    from steam_crawler.api.steam_reviews import SteamReviewsClient
    from steam_crawler.api.resilience import FailureTracker

    version = _create_version(db_conn)
    _setup_game_for_supplement(db_conn, steam_positive=10000, steam_negative=5,
                               num_positive=100, num_negative=2)

    client = SteamReviewsClient()
    tracker = FailureTracker()

    with patch.object(client._client, "get") as mock_get:
        added = _supplement_negative_reviews(db_conn, 730, version, "all", client, tracker)

    assert added == 0
    mock_get.assert_not_called()


def test_negative_supplement_skips_zero_positive(db_conn):
    """steam_positive = 0 → 스킵."""
    from steam_crawler.pipeline.step3_crawl import _supplement_negative_reviews
    from steam_crawler.api.steam_reviews import SteamReviewsClient
    from steam_crawler.api.resilience import FailureTracker

    version = _create_version(db_conn)
    db_conn.execute("INSERT INTO games (appid, name, steam_positive, steam_negative) VALUES (999, 'Test', 0, 0)")
    db_conn.commit()

    client = SteamReviewsClient()
    tracker = FailureTracker()

    with patch.object(client._client, "get") as mock_get:
        added = _supplement_negative_reviews(db_conn, 999, version, "all", client, tracker)

    assert added == 0
    mock_get.assert_not_called()


def test_negative_supplement_updates_review_types_done(db_conn):
    """보강 후 review_types_done에 'negative_supplement' append."""
    import json
    from steam_crawler.pipeline.step3_crawl import _supplement_negative_reviews
    from steam_crawler.api.steam_reviews import SteamReviewsClient
    from steam_crawler.api.resilience import FailureTracker
    from steam_crawler.db.repository import update_collection_status

    version = _create_version(db_conn)
    _setup_game_for_supplement(db_conn, steam_positive=9000, steam_negative=1000,
                               num_positive=900, num_negative=50)
    # Pre-set review_types_done
    update_collection_status(db_conn, appid=730, version=version,
                             review_types_done=json.dumps(["all"]))

    client = SteamReviewsClient()
    tracker = FailureTracker()

    responses = [_mock_response(MOCK_EMPTY_PAGE)]  # No reviews returned, but flag should still be set
    with patch.object(client._client, "get", side_effect=responses):
        _supplement_negative_reviews(db_conn, 730, version, "all", client, tracker)

    status = db_conn.execute(
        "SELECT review_types_done FROM game_collection_status WHERE appid=730 AND version=?",
        (version,)
    ).fetchone()
    done_list = json.loads(status["review_types_done"])
    assert "negative_supplement" in done_list
    assert "all" in done_list


def test_negative_supplement_skips_on_rerun(db_conn):
    """review_types_done에 'negative_supplement' 있으면 재실행 시 스킵."""
    import json
    from steam_crawler.pipeline.step3_crawl import _supplement_negative_reviews
    from steam_crawler.api.steam_reviews import SteamReviewsClient
    from steam_crawler.api.resilience import FailureTracker
    from steam_crawler.db.repository import update_collection_status

    version = _create_version(db_conn)
    _setup_game_for_supplement(db_conn, steam_positive=9000, steam_negative=1000,
                               num_positive=900, num_negative=50)
    update_collection_status(db_conn, appid=730, version=version,
                             review_types_done=json.dumps(["all", "negative_supplement"]))

    client = SteamReviewsClient()
    tracker = FailureTracker()

    with patch.object(client._client, "get") as mock_get:
        added = _supplement_negative_reviews(db_conn, 730, version, "all", client, tracker)

    assert added == 0
    mock_get.assert_not_called()


def test_negative_supplement_logs_failure(db_conn):
    """보강 중 에러 발생 시 failure_logs에 기록."""
    from steam_crawler.pipeline.step3_crawl import _supplement_negative_reviews
    from steam_crawler.api.steam_reviews import SteamReviewsClient
    from steam_crawler.api.resilience import FailureTracker

    version = _create_version(db_conn)
    _setup_game_for_supplement(db_conn, steam_positive=9000, steam_negative=1000,
                               num_positive=900, num_negative=50)

    client = SteamReviewsClient()
    tracker = FailureTracker()

    with patch.object(client._client, "get", side_effect=ConnectionError("timeout")):
        _supplement_negative_reviews(db_conn, 730, version, "all", client, tracker)

    failures = db_conn.execute(
        "SELECT * FROM failure_logs WHERE api_name='steam_reviews_negative_supplement'"
    ).fetchall()
    assert len(failures) >= 1
```

- [ ] **Step 2: 테스트 실행 — FAIL 확인**

Run: `cd steam-crawler && python -m pytest tests/test_pipeline.py -k "negative_supplement or count_reviews_by_sentiment" -v`

Expected: FAIL (`_supplement_negative_reviews`와 `_count_reviews_by_sentiment`가 아직 없으므로 ImportError)

---

### Task 4: 부정 리뷰 보강 — 구현

**Files:**
- Modify: `steam-crawler/src/steam_crawler/pipeline/step3_crawl.py`

- [ ] **Step 1: `_count_reviews_by_sentiment` 헬퍼 추가**

`step3_crawl.py`에 기존 `_count_reviews` 아래에 추가:

```python
def _count_reviews_by_sentiment(conn: sqlite3.Connection, appid: int) -> tuple[int, int]:
    """Count positive and negative reviews for a game. Returns (positive, negative)."""
    row = conn.execute(
        """SELECT
           SUM(CASE WHEN voted_up = 1 THEN 1 ELSE 0 END) AS pos,
           SUM(CASE WHEN voted_up = 0 THEN 1 ELSE 0 END) AS neg
           FROM reviews WHERE appid = ?""",
        (appid,),
    ).fetchone()
    return (row[0] or 0, row[1] or 0)
```

- [ ] **Step 2: `_supplement_negative_reviews` 함수 추가**

```python
def _supplement_negative_reviews(
    conn: sqlite3.Connection,
    appid: int,
    version: int,
    language: str,
    client: SteamReviewsClient,
    tracker: FailureTracker,
) -> int:
    """Supplement negative reviews to match official ratio. Returns count added."""
    # Guard: check official stats
    game = conn.execute(
        "SELECT steam_positive, steam_negative FROM games WHERE appid = ?",
        (appid,),
    ).fetchone()
    if not game:
        return 0

    steam_pos = game["steam_positive"] or 0
    steam_neg = game["steam_negative"] or 0

    if steam_pos == 0 or steam_neg < 10:
        return 0

    # Guard: already supplemented?
    status = conn.execute(
        "SELECT review_types_done FROM game_collection_status WHERE appid=? AND version=?",
        (appid, version),
    ).fetchone()
    if status and status["review_types_done"]:
        done_list = json.loads(status["review_types_done"])
        if "negative_supplement" in done_list:
            return 0

    # Calculate target
    collected_pos, collected_neg = _count_reviews_by_sentiment(conn, appid)
    official_ratio = steam_neg / steam_pos
    target = min(max(200, int(collected_pos * official_ratio)), steam_neg)

    if collected_neg >= target:
        return 0

    console.print(
        f"  [yellow]부정 보강: {collected_neg}/{target} → 보강 시작[/yellow]"
    )

    # Fetch negative reviews
    cursor = "*"
    has_more = True
    added = 0

    while collected_neg < target and has_more:
        try:
            reviews, next_cursor, has_more = client.fetch_reviews_page(
                appid=appid, cursor=cursor,
                language=language, review_type="negative",
                review_filter="recent",
            )
        except Exception as e:
            tracker.log_failure(
                conn=conn, session_id=version, api_name="steam_reviews_negative_supplement",
                appid=appid, step="step3_neg_supplement", error_message=str(e),
            )
            console.print(f"  [red]부정 보강 에러: {e}[/red]")
            break
        if not reviews:
            break
        insert_reviews_batch(conn, reviews, version=version)
        prev_neg = collected_neg
        _, collected_neg = _count_reviews_by_sentiment(conn, appid)
        added += collected_neg - prev_neg
        cursor = next_cursor
        console.print(f"  [부정 보강] {collected_neg}/{target}")

    # Update review_types_done
    existing_done = []
    if status and status["review_types_done"]:
        existing_done = json.loads(status["review_types_done"])
    existing_done.append("negative_supplement")
    update_collection_status(
        conn, appid=appid, version=version,
        review_types_done=json.dumps(existing_done),
        reviews_collected=_count_reviews(conn, appid),
    )

    console.print(f"  [green]부정 보강 완료: +{added}건[/green]")
    return added
```

- [ ] **Step 3: `run_step3`에서 `reviews_done` 설정 전에 보강 호출**

`step3_crawl.py`의 `run_step3` 함수에서, `is_done` 체크 직후 (line 153-160)에 보강을 삽입:

변경 전:
```python
                is_done = actual_count >= effective_max or not has_more
                if is_done:
                    update_collection_status(
                        conn, appid=appid, version=version,
                        reviews_done=True,
                        languages_done=json.dumps([language]),
                        review_types_done=json.dumps([review_type]),
                    )
```

변경 후:
```python
                is_done = actual_count >= effective_max or not has_more
                if is_done:
                    # Negative supplement before marking done
                    # _supplement_negative_reviews가 내부에서 review_types_done을 관리함
                    _supplement_negative_reviews(
                        conn, appid, version, language, client, tracker,
                    )
                    actual_count = _count_reviews(conn, appid)
                    # review_types_done: 보강 함수가 이미 "negative_supplement"를 추가했으므로
                    # 여기서는 기존 값을 읽어서 review_type만 merge
                    status_row = conn.execute(
                        "SELECT review_types_done FROM game_collection_status WHERE appid=? AND version=?",
                        (appid, version),
                    ).fetchone()
                    existing_done = json.loads(status_row["review_types_done"]) if status_row and status_row["review_types_done"] else []
                    if review_type not in existing_done:
                        existing_done.insert(0, review_type)
                    update_collection_status(
                        conn, appid=appid, version=version,
                        reviews_done=True,
                        reviews_collected=actual_count,
                        languages_done=json.dumps([language]),
                        review_types_done=json.dumps(existing_done),
                    )
```

**주의**: `_supplement_negative_reviews`가 `review_types_done`에 `"negative_supplement"`를 추가하는 유일한 책임자. 외부 코드는 절대 `"negative_supplement"`를 하드코딩하지 않음. 보강이 스킵된 경우 `review_types_done`에 `"negative_supplement"`가 포함되지 않으며, 이는 의도된 동작.

- [ ] **Step 4: 테스트 실행 — PASS 확인**

Run: `cd steam-crawler && python -m pytest tests/test_pipeline.py -k "negative_supplement" -v`

Expected: 전체 PASS

- [ ] **Step 5: 전체 테스트 실행**

Run: `cd steam-crawler && python -m pytest -v`

Expected: 전체 PASS

- [ ] **Step 6: Commit**

```bash
git add steam-crawler/src/steam_crawler/pipeline/step3_crawl.py steam-crawler/tests/test_pipeline.py
git commit -m "feat: add negative review 2-pass supplementation in step3"
```

---

### Task 5: 스킬 문서 업데이트 (편향 해소)

**Files:**
- Modify: `.claude/skills/steam-insight/SKILL.md`
- Modify: `.claude/skills/steam-query/SKILL.md`

- [ ] **Step 1: `steam-insight/SKILL.md`의 `valid_reviews` 설명 업데이트**

"100자 이상" → "100자 이상 (한국어: 50자)" 로 변경하고, 편향 방지 규칙 추가:

기존에 `## 유효 리뷰 View` 섹션이 있는 부분을 찾아서:
```markdown
## 유효 리뷰 View

`valid_reviews` — 정성 분석용 필터링된 리뷰 View.
- 100자 이상 (한국어: 50자) OR 플레이타임 50시간 이상
- ASCII art 제거, 게임별 중복 텍스트 1건만 유지 (weighted_vote_score 최고)
- **정성 분석(리뷰 인용/분석)에만 사용. 정량 통계는 `reviews` 테이블 사용.**
- playtime_at_review가 NULL이고 글자수 미만인 리뷰는 제외됨
- 필터링으로 일부 게임에서 결과가 LIMIT 미만일 수 있음
- **⚠ 편향 주의**: 부정 리뷰 보강 수집으로 reviews 테이블의 긍/부정 비율은 실제와 다름. 전체 긍정률/부정률은 반드시 `games.steam_positive` / `games.steam_negative` 사용.
```

- [ ] **Step 2: `steam-query/SKILL.md`에 편향 방지 규칙 추가**

전체 비율 관련 쿼리가 있는 부분에 동일한 경고 추가.

- [ ] **Step 3: 전체 비율을 reviews COUNT로 계산하는 기존 쿼리 검색**

Run: `grep -n "count.*voted_up\|sum.*voted_up.*count" .claude/skills/steam-insight/SKILL.md .claude/skills/steam-query/SKILL.md`

해당 쿼리가 **전체 긍정률**(버킷 없이)을 산출하면 `games.steam_positive/steam_negative` 참조로 교체.
**버킷별 분석** (플레이타임별, 언어별)은 `reviews` 테이블 사용 허용 — 변경 불필요.

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/steam-insight/SKILL.md .claude/skills/steam-query/SKILL.md
git commit -m "docs: update skill docs for Korean threshold and bias prevention"
```

---

### Task 6: 통합 테스트 및 최종 검증

- [ ] **Step 1: 전체 pytest 실행**

Run: `cd steam-crawler && python -m pytest -v`

Expected: 전체 PASS

- [ ] **Step 2: VIEW 경계값 수동 확인**

SQLite에서 직접 확인 (기존 DB가 있다면):
```sql
-- 한국어 리뷰 중 50-99자 사이 리뷰가 valid_reviews에 포함되는지
SELECT COUNT(*) FROM valid_reviews WHERE language = 'koreana' AND length(review_text) BETWEEN 50 AND 99;

-- 전체 한국어 valid_reviews 수 확인
SELECT COUNT(*) FROM valid_reviews WHERE language = 'koreana';
SELECT COUNT(*) FROM reviews WHERE language = 'koreana';
```

- [ ] **Step 3: Commit (필요시)**

모든 변경이 이전 태스크에서 커밋되었으면 스킵.
