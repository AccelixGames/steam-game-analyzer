# Steam Game Analyzer — 전체 아키텍처 및 데이터 수집 구현 계획

## Context

스팀 게임을 장르/태그별로 필터링하고, 긍정/부정 리뷰 수 및 리뷰 본문을 대량 수집하여 경쟁작 분석에 활용한다. 전체 시스템은 **두 개의 독립 프로젝트**로 분리된다:

```
steam-game-analyzer/          ← 모노레포 루트
├── steam-crawler/            ← 데이터 수집기 (이번 구현 대상)
├── steam-analyzer/           ← 분석기 (placeholder, 추후 구현)
└── data/                     ← 공유 데이터 (SQLite DB)
```

**이번 구현은 `steam-crawler` (데이터 수집기)에만 집중**한다.
`steam-analyzer`는 빈 폴더 + README placeholder만 생성한다.

### 핵심 설계 결정 (사용자 승인 완료)

| 항목 | 결정 |
|------|------|
| 도구 형태 | Python CLI (click + rich) |
| DB | SQLite |
| 버전 관리 방식 | 변경 로그 (changelog) — 최신 데이터 1벌만 유지, 변경 이력은 별도 기록 |
| 자동 튜닝 | Adaptive Resilience — rate limit 뿐 아니라 모든 실패를 로깅·학습하여 완전 자동 운영 목표 |
| 분석 범위 | 이번에는 수집만. 분석(키워드 빈도 등)은 별도 프로젝트 |
| 리뷰 언어 | 영어 + 한국어 (Kiwi 형태소 분석기 — 분석 파트에서 사용) |

---

## 프로젝트 구조

```
steam-game-analyzer/                    ← 모노레포 루트
├── .gitignore
├── CLAUDE.md
├── README.md
│
├── steam-crawler/                      ← 데이터 수집기 (이번 구현)
│   ├── pyproject.toml
│   ├── src/steam_crawler/
│   │   ├── __init__.py
│   │   ├── cli.py                      # Click CLI 엔트리포인트
│   │   │
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── game.py                 # GameSummary dataclass
│   │   │   └── review.py              # Review, ReviewSummary dataclass
│   │   │
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── base.py                # BaseClient (httpx 래핑)
│   │   │   ├── rate_limiter.py        # AdaptiveRateLimiter
│   │   │   ├── resilience.py          # FailureTracker — 실패 로깅·분류·자동 복구
│   │   │   ├── steamspy.py            # SteamSpy API client
│   │   │   └── steam_reviews.py       # Steam Reviews API client
│   │   │
│   │   ├── pipeline/
│   │   │   ├── __init__.py
│   │   │   ├── runner.py              # 파이프라인 오케스트레이터
│   │   │   ├── step1_collect.py       # 게임 목록 수집 (SteamSpy tag/genre)
│   │   │   ├── step1b_enrich.py       # 게임 상세 보강 (SteamSpy appdetails → tags)
│   │   │   ├── step2_scan.py          # 리뷰 요약 스캔 (Steam API)
│   │   │   └── step3_crawl.py         # 리뷰 본문 크롤링
│   │   │
│   │   └── db/
│   │       ├── __init__.py
│   │       ├── schema.py              # 테이블 생성 DDL
│   │       ├── repository.py          # CRUD 함수 (games, reviews)
│   │       └── changelog.py           # 변경 로그 기록/조회
│   │
│   └── tests/
│
├── steam-analyzer/                     ← 분석기 (placeholder)
│   ├── README.md                       # "추후 구현 예정" + 예상 기능 목록
│   └── pyproject.toml                  # 최소 설정만
│
└── data/                               ← 공유 데이터 (gitignore)
    └── steam.db
```

---

## SQLite 스키마

### games — 게임 기본 정보 (최신 데이터만 유지)

```sql
CREATE TABLE games (
  appid          INTEGER PRIMARY KEY,
  name           TEXT NOT NULL,
  positive       INTEGER,
  negative       INTEGER,
  owners         TEXT,
  price          INTEGER,
  tags           TEXT,           -- JSON: {"Management": 500, ...}
  avg_playtime   INTEGER,
  score_rank     TEXT,
  steam_positive INTEGER,
  steam_negative INTEGER,
  review_score   TEXT,           -- "Very Positive"
  source_tag     TEXT,           -- 이 게임을 발견한 쿼리 ("tag:Management", "genre:Simulation")
  first_seen_ver INTEGER,
  updated_at     TIMESTAMP
);
```

### reviews — 리뷰 본문

```sql
CREATE TABLE reviews (
  recommendation_id TEXT PRIMARY KEY,
  appid            INTEGER REFERENCES games(appid),
  language         TEXT,
  review_text      TEXT,
  voted_up         BOOLEAN,
  playtime_forever INTEGER,
  playtime_at_review INTEGER,
  early_access     BOOLEAN,
  steam_purchase   BOOLEAN,
  received_for_free BOOLEAN,
  dev_response     TEXT,
  timestamp_created INTEGER,
  votes_up         INTEGER,
  votes_funny      INTEGER,
  weighted_vote_score REAL,    -- 유용성 랭킹 점수
  comment_count    INTEGER,    -- 댓글 수 (논쟁적 리뷰 식별)
  author_steamid   TEXT,       -- 리뷰어 Steam ID
  author_num_reviews INTEGER,  -- 리뷰어 총 리뷰 수
  author_playtime_forever INTEGER,  -- 리뷰어 총 플레이타임(분)
  collected_ver    INTEGER,
  collected_at     TIMESTAMP
);

CREATE INDEX idx_reviews_appid ON reviews(appid);
CREATE INDEX idx_reviews_language ON reviews(language);
CREATE INDEX idx_reviews_voted_up ON reviews(voted_up);
```

### data_versions — 수집 버전 메타

```sql
CREATE TABLE data_versions (
  version       INTEGER PRIMARY KEY AUTOINCREMENT,
  query_type    TEXT NOT NULL,    -- 'tag', 'genre', 'top100'
  query_value   TEXT,             -- 'Management', 'Simulation'
  status        TEXT NOT NULL,    -- 'running', 'completed', 'interrupted'
  games_total   INTEGER,
  reviews_total INTEGER,
  config        TEXT,             -- JSON: 실행 시 사용한 설정
  created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  note          TEXT
);
```

### changelog — 변경 로그 (버전 간 diff의 핵심)

```sql
CREATE TABLE changelog (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  version       INTEGER REFERENCES data_versions(version),
  change_type   TEXT NOT NULL,    -- 'game_added', 'game_updated',
                                  -- 'reviews_batch_added', 'reviews_count_changed'
  appid         INTEGER,
  field_name    TEXT,
  old_value     TEXT,
  new_value     TEXT,
  created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_changelog_version ON changelog(version);
CREATE INDEX idx_changelog_appid ON changelog(appid);
```

### rate_limit_stats — 자동 튜닝 메트릭

```sql
CREATE TABLE rate_limit_stats (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  api_name        TEXT NOT NULL,
  session_id      INTEGER REFERENCES data_versions(version),
  requests_made   INTEGER,
  errors_429      INTEGER DEFAULT 0,
  errors_5xx      INTEGER DEFAULT 0,
  avg_response_ms REAL,
  optimal_delay_ms REAL,
  recorded_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### failure_logs — 실패 기록 및 자가 개선 (Adaptive Resilience 핵심)

```sql
CREATE TABLE failure_logs (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id      INTEGER REFERENCES data_versions(version),
  api_name        TEXT NOT NULL,       -- 'steamspy_tag', 'steamspy_appdetails',
                                       -- 'steam_reviews_summary', 'steam_reviews_crawl'
  appid           INTEGER,
  step            TEXT,                -- 'step1', 'step2', 'step3'
  failure_type    TEXT NOT NULL,       -- 분류: 아래 참고
  http_status     INTEGER,
  error_message   TEXT,
  request_url     TEXT,
  response_body   TEXT,                -- 디버깅용 (truncated, 최대 1000자)
  retry_count     INTEGER DEFAULT 0,
  resolved        BOOLEAN DEFAULT 0,  -- 재시도로 해결되었는지
  resolution      TEXT,               -- 'retried_ok', 'skipped', 'param_adjusted', ...
  created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_failure_logs_type ON failure_logs(failure_type);
CREATE INDEX idx_failure_logs_session ON failure_logs(session_id);
CREATE INDEX idx_failure_logs_unresolved ON failure_logs(resolved) WHERE resolved = 0;
```

**failure_type 분류**:

| failure_type | 설명 | 자동 복구 전략 |
|---|---|---|
| `rate_limited` | HTTP 429 | 딜레이 증가 + 지수 백오프 |
| `server_error` | HTTP 5xx | 재시도 후 스킵, 다음 세션에서 재시도 대상 |
| `timeout` | 응답 시간 초과 | 타임아웃 값 점진적 증가 |
| `parse_error` | JSON 파싱 실패 / 예상 필드 누락 | response_body 저장, API 스키마 변경 감지 |
| `empty_response` | 성공이지만 데이터 없음 | appid 유효성 재확인 |
| `data_quality` | SteamSpy 태그 결과에 관련 없는 게임 등 | 이상치 플래그, 수동 검토 대상 |
| `connection_error` | DNS/TCP 연결 실패 | 네트워크 상태 확인 후 재시도 |
| `cursor_invalid` | 커서 만료/무효 | 처음부터 재수집 |

### game_collection_status — 게임별 수집 진행 상태 (재개용)

```sql
CREATE TABLE game_collection_status (
  appid           INTEGER,
  version         INTEGER REFERENCES data_versions(version),
  steamspy_done   BOOLEAN DEFAULT 0,
  summary_done    BOOLEAN DEFAULT 0,
  reviews_done    BOOLEAN DEFAULT 0,
  last_cursor     TEXT,
  reviews_collected INTEGER DEFAULT 0,
  reviews_total     INTEGER,
  languages_done  TEXT,             -- JSON: ["english"]
  review_types_done TEXT,           -- JSON: ["positive"]
  updated_at      TIMESTAMP,
  PRIMARY KEY (appid, version)
);
```

---

## 수집 파이프라인 3단계

### Step 1: 게임 목록 수집 (SteamSpy)

- **입력**: `--tag Management` 또는 `--genre Simulation`
- **API**: `steamspy.com/api.php?request=tag&tag=X` (또는 `request=genre`)
- **처리**:
  1. SteamSpy에서 게임 목록 수집 (페이지네이션 없음, 한 번에 전체 반환)
  2. `--limit`에 따라 클라이언트 측 필터링 (positive 기준 내림차순 정렬 후 상위 N개)
  3. `games` 테이블에 UPSERT (appid 기준)
  4. 새 게임이면 `changelog`에 `game_added` 기록
  5. 기존 게임인데 positive/negative 등이 바뀌었으면 `game_updated` 기록
- **Rate**: 1.0 req/sec (adaptive)
- **⚠ 주의사항**:
  - tag/genre 엔드포인트 응답에 `tags`, `languages`, `genre` 필드가 **포함되지 않음**
  - 인기 태그(Action, Indie 등)는 응답이 10MB+ / 수천 건 가능
  - SteamSpy 태그 데이터는 부정확할 수 있음 (관련 없는 게임 포함 가능)

### Step 1.5: 게임 상세 보강 (SteamSpy appdetails)

- **입력**: Step 1에서 수집한 게임 목록 (limit 적용 후)
- **API**: `steamspy.com/api.php?request=appdetails&appid=X`
- **처리**:
  1. 게임별 `appdetails` 호출로 `tags` 필드 수집
  2. `games` 테이블의 `tags` 컬럼 업데이트
  3. `game_collection_status.steamspy_done = 1` 표시
- **Rate**: 1.0 req/sec (adaptive)
- **참고**: tag/genre 엔드포인트가 반환하지 않는 필드를 보강하는 단계

### Step 2: 리뷰 요약 스캔 (Steam appreviews)

- **입력**: Step 1에서 수집한 게임 목록
- **API**: `store.steampowered.com/appreviews/<appid>?json=1&cursor=%2A&filter=recent&purchase_type=all&num_per_page=0`
- **처리**:
  1. 각 게임에 대해 `query_summary`만 파싱 (cursor=* 첫 요청에만 포함됨, 1 req/game)
  2. `steam_positive`, `steam_negative`, `review_score` 업데이트
  3. SteamSpy vs Steam API 데이터 10% 이상 차이 시 `failure_logs`에 `data_quality` 기록
  4. `changelog`에 `reviews_count_changed` 기록
- **Rate**: 1.0s delay (adaptive) — Step 3과 같은 엔드포인트이므로 동일 rate limit 적용
- **⚠ 주의**: `query_summary`는 cursor=* (첫 요청)에서만 반환됨

### Step 3: 리뷰 본문 크롤링

- **입력**: Step 2까지 완료된 상위 N개 게임 (`--top-n`)
- **API**: `store.steampowered.com/appreviews/<appid>?json=1&filter=recent&purchase_type=all&num_per_page=80&cursor=...`
- **필수 파라미터**:
  - `filter=recent` — 전체 리뷰 순회에 필수 (`all`은 day_range 윈도우 제한)
  - `purchase_type=all` — 기본값 `steam`이면 non-Steam 구매 리뷰 누락
  - `language` — CLI의 `--language` 값 전달 (기본: `all`)
  - `review_type` — CLI의 `--review-type` 값 전달 (기본: `all`)
- **처리**:
  1. cursor 기반 페이지네이션 (`num_per_page=80`, 첫 요청 cursor=`*`)
  2. `reviews` 테이블에 `INSERT OR IGNORE` (recommendation_id 기준 중복 방지)
  3. 게임 단위로 `changelog`에 `reviews_batch_added` 기록 (count=N)
  4. 진행 상태를 `game_collection_status`에 실시간 저장
  5. 중단 시 `last_cursor` 저장 → `--resume`으로 재개 가능
  6. `reviews` 배열이 빈 배열이면 해당 게임의 모든 리뷰 수집 완료
- **Rate**: 1.5s delay (adaptive)
- **⚠ 주의**:
  - `num_per_page=100`은 버그 있음, 80 이하 사용
  - cursor 값은 **URL 인코딩 필수** (`=`, `+` 등 포함)
  - `query_summary`는 첫 요청(cursor=*)에서만 반환, 이후 페이지에선 없음

---

## CLI 인터페이스

```
steam-crawler collect [OPTIONS]

# 필수 (하나 선택)
  --tag TEXT           태그로 수집 ("Management", "Roguelike")
  --genre TEXT         장르로 수집 ("Simulation", "RPG")
  --top100             최근 2주 인기 Top 100

# 수집 범위
  --limit INT          Step 1 최대 게임 수 (기본: 50)
  --top-n INT          Step 3 리뷰 크롤링 대상 상위 게임 수 (기본: 10)
  --max-reviews INT    게임당 최대 리뷰 수 (기본: 500)
  --language TEXT       리뷰 언어 필터 (기본: all)
  --review-type TEXT    리뷰 유형 필터: all/positive/negative (기본: all)

# 제어
  --resume             이전 중단된 수집 재개
  --step 1|2|3         특정 단계만 실행
  --note TEXT          이 버전에 대한 메모

# 조회
steam-crawler versions              수집 버전 목록 조회
steam-crawler diff V1 V2            두 버전 간 변경사항 조회
steam-crawler status                현재 수집 진행 상태 조회
```

---

## Adaptive Resilience 시스템

**목표**: 모든 실패를 기록·분류하고, 세션 간 학습을 통해 완전 자동 운영 달성.

### 1. AdaptiveRateLimiter (속도 자동 조절)

```
세션 시작:
  → rate_limit_stats에서 해당 API의 최근 optimal_delay_ms 조회
  → 없으면 기본값 (SteamSpy: 1000ms, Reviews: 1500ms)

매 요청 후:
  성공 + 응답 < 500ms  → 딜레이 5% 감소 (하한선까지)
  성공 + 응답 > 2000ms → 딜레이 유지
  HTTP 429             → 딜레이 1.5배 증가 + 지수 백오프(5s, 15s, 45s) 재시도
  HTTP 5xx             → 3회 재시도 후 스킵

세션 종료:
  → rate_limit_stats에 최종 메트릭 저장
  → 다음 세션에서 학습된 딜레이로 시작
```

### 2. FailureTracker (실패 추적 + 자동 복구)

```
모든 API 요청 실패 시:
  1. failure_logs에 상세 기록 (HTTP status, response body, URL 등)
  2. failure_type 자동 분류
  3. 분류별 자동 복구 전략 실행:
     - rate_limited   → RateLimiter에 위임
     - server_error   → 재시도 큐에 추가, 다음 세션에서 우선 처리
     - timeout        → 타임아웃 값 점진적 증가 (10s → 20s → 30s)
     - parse_error    → response_body 저장, API 스키마 변경 감지 경고
     - empty_response → appid 유효성 재확인 (삭제된 게임?)
     - data_quality   → 이상치 플래그, 수동 검토 대상으로 표시
     - connection_error → 네트워크 상태 확인 후 전체 일시정지
     - cursor_invalid → last_cursor 초기화, 해당 게임 처음부터 재수집

세션 시작 시:
  → 이전 세션의 미해결(resolved=0) failure_logs 조회
  → server_error/timeout 건은 자동으로 재시도 대상에 포함
  → parse_error가 N건 이상이면 API 스키마 변경 가능성 경고

세션 종료 시:
  → 실패 요약 리포트 출력 (유형별 건수, 해결률)
  → 미해결 건수가 임계치 초과 시 경고
```

### 3. 세션 간 학습 흐름

```
1회차: 기본값으로 수집 → 실패 패턴 기록
2회차: 학습된 딜레이 + 이전 실패 재시도 → 성공률 개선
3회차~: 안정화된 파라미터로 완전 자동 운영
         ↳ 새로운 유형의 실패 발생 시 → 기록 + 경고 → 대응 전략 추가
```

---

## 의존성

```toml
# steam-crawler/pyproject.toml
[project]
name = "steam-crawler"
version = "0.1.0"
requires-python = ">=3.12"

dependencies = [
    "httpx>=0.27",
    "click>=8.1",
    "rich>=13.0",
]

[project.scripts]
steam-crawler = "steam_crawler.cli:main"
```

---

## 구현 순서

### Phase 0: 모노레포 + Placeholder (3개 파일)
1. `.gitignore` — data/, __pycache__, .venv 등
2. `steam-analyzer/README.md` — 분석기 placeholder (예상 기능 목록)
3. `steam-analyzer/pyproject.toml` — 최소 설정

### Phase 1: steam-crawler 기반 (4개 파일)
1. `steam-crawler/pyproject.toml` — 프로젝트 설정, 의존성
2. `steam-crawler/src/steam_crawler/__init__.py` — 버전
3. `steam-crawler/src/steam_crawler/db/schema.py` — DDL, 테이블 생성
4. `CLAUDE.md` — 프로젝트 가이드

### Phase 2: 데이터 모델 + DB 레이어 (4개 파일)
1. `steam-crawler/src/steam_crawler/models/game.py` — GameSummary dataclass
2. `steam-crawler/src/steam_crawler/models/review.py` — Review dataclass
3. `steam-crawler/src/steam_crawler/db/repository.py` — games/reviews CRUD
4. `steam-crawler/src/steam_crawler/db/changelog.py` — 변경 로그 기록/조회

### Phase 3: API 클라이언트 + Resilience (5개 파일)
1. `steam-crawler/src/steam_crawler/api/base.py` — BaseClient (httpx 래핑)
2. `steam-crawler/src/steam_crawler/api/rate_limiter.py` — AdaptiveRateLimiter
3. `steam-crawler/src/steam_crawler/api/resilience.py` — FailureTracker (실패 로깅·분류·복구)
4. `steam-crawler/src/steam_crawler/api/steamspy.py` — SteamSpy API
5. `steam-crawler/src/steam_crawler/api/steam_reviews.py` — Steam Reviews API

### Phase 4: 파이프라인 (5개 파일)
1. `steam-crawler/src/steam_crawler/pipeline/step1_collect.py` — 게임 목록 (SteamSpy tag/genre)
2. `steam-crawler/src/steam_crawler/pipeline/step1b_enrich.py` — 게임 상세 보강 (SteamSpy appdetails → tags)
3. `steam-crawler/src/steam_crawler/pipeline/step2_scan.py` — 리뷰 요약 스캔
4. `steam-crawler/src/steam_crawler/pipeline/step3_crawl.py` — 리뷰 본문 크롤링
5. `steam-crawler/src/steam_crawler/pipeline/runner.py` — 오케스트레이터

### Phase 5: CLI + 마무리 (1개 파일)
1. `steam-crawler/src/steam_crawler/cli.py` — collect/versions/diff/status 명령어

---

## 검증 방법

1. **Step 1 테스트**: `steam-crawler collect --tag Roguelike --limit 5 --step 1`
   - games 테이블에 5개 게임 저장 확인
   - changelog에 game_added 5건 확인

2. **Step 2 테스트**: `steam-crawler collect --tag Roguelike --step 2`
   - steam_positive/negative 업데이트 확인
   - review_score 필드 채워졌는지 확인

3. **Step 3 테스트**: `steam-crawler collect --tag Roguelike --top-n 1 --max-reviews 50 --step 3`
   - reviews 테이블에 ~50건 저장 확인
   - Ctrl+C로 중단 후 `--resume`으로 재개 확인

4. **버전 diff 테스트**: 동일 태그로 2회 수집 후 `steam-crawler diff 1 2`
   - 변경사항 출력 확인

5. **자동 튜닝 테스트**: rate_limit_stats에 메트릭 저장 확인
   - 2회차 실행 시 이전 딜레이 값 사용 확인

6. **Adaptive Resilience 테스트**:
   - failure_logs에 실패 기록 저장 확인
   - 의도적으로 잘못된 appid 전달 → empty_response 분류 확인
   - 2회차 실행 시 이전 미해결 실패 건 자동 재시도 확인
   - 세션 종료 시 실패 요약 리포트 출력 확인

7. **Step 1.5 보강 테스트**: `steam-crawler collect --tag Roguelike --limit 5 --step 1`
   - games 테이블의 `tags` 컬럼에 JSON 데이터 채워졌는지 확인
