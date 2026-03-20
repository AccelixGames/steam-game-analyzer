---
name: steam-diagnose
description: "Steam 크롤러 진단, 실패 분석, 자동 개선. Use when user asks about crawler health, failure analysis, error logs, rate limiting issues, or wants to improve crawler reliability. Triggers on: '크롤러 진단', '실패 로그 분석', '에러 확인', '크롤링 상태', 'diagnose crawler', 'fix failures', 'improve crawler', 'check errors', '왜 실패했어', '크롤링이 안돼'. Also trigger when user mentions rate limits, 429 errors, timeouts, or asks why data is missing."
---

# Steam Diagnose

steam-crawler의 실패 로그를 분석하고 자동으로 개선하는 스킬.

## Project Location

크롤러 코드: `steam-crawler/src/steam_crawler/`
DB: `data/steam.db`

## Core Concept

steam-crawler는 모든 실패를 `failure_logs` 테이블에 기록하고, rate limit 메트릭을 `rate_limit_stats`에 저장한다. 이 데이터를 분석하여 문제를 진단하고, 가능한 경우 코드를 수정하여 자동으로 해결한다.

## Diagnostic Workflow

### Step 1: 데이터 수집

SQLite DB를 열어서 진단에 필요한 데이터를 쿼리한다.

```python
import sys, sqlite3, json
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, "<project-root>/steam-crawler/src")

conn = sqlite3.connect("<project-root>/data/steam.db")
conn.row_factory = sqlite3.Row
```

#### 핵심 쿼리들

**미해결 실패 건수 (유형별)**
```sql
SELECT failure_type, count(*) as cnt
FROM failure_logs WHERE resolved = 0
GROUP BY failure_type ORDER BY cnt DESC;
```

**최근 세션 실패 요약**
```sql
SELECT dv.version, dv.query_type, dv.query_value, dv.status,
       count(fl.id) as failures, sum(fl.resolved) as resolved
FROM data_versions dv
LEFT JOIN failure_logs fl ON fl.session_id = dv.version
GROUP BY dv.version ORDER BY dv.version DESC LIMIT 5;
```

**Rate Limit 학습 상태**
```sql
SELECT api_name, requests_made, errors_429, errors_5xx,
       avg_response_ms, optimal_delay_ms, recorded_at
FROM rate_limit_stats ORDER BY recorded_at DESC LIMIT 10;
```

**수집 진행 상태 (미완료 게임)**
```sql
SELECT gcs.appid, g.name, gcs.version, gcs.steamspy_done,
       gcs.summary_done, gcs.reviews_done,
       gcs.reviews_collected, gcs.reviews_total
FROM game_collection_status gcs
JOIN games g ON g.appid = gcs.appid
WHERE gcs.reviews_done = 0
ORDER BY gcs.version DESC;
```

**실패 패턴 분석 (같은 appid가 반복 실패)**
```sql
SELECT appid, failure_type, count(*) as cnt,
       group_concat(DISTINCT error_message) as messages
FROM failure_logs WHERE resolved = 0
GROUP BY appid, failure_type
HAVING cnt >= 2
ORDER BY cnt DESC;
```

**API 스키마 변경 감지 (parse_error가 급증했는지)**
```sql
SELECT session_id, count(*) as parse_errors
FROM failure_logs WHERE failure_type = 'parse_error'
GROUP BY session_id
ORDER BY session_id DESC LIMIT 5;
```

**스킬 실행 에러 (유형별)**
```sql
SELECT skill_name, error_type, count(*) as cnt
FROM skill_errors WHERE resolved = 0
GROUP BY skill_name, error_type ORDER BY cnt DESC;
```

**반복 스킬 에러 패턴**
```sql
SELECT error_type, error_message, count(*) as cnt,
       group_concat(DISTINCT fix_applied) as fixes
FROM skill_errors WHERE resolved = 0
GROUP BY error_type, error_message HAVING cnt >= 2;
```

**최근 스킬 에러 (최신 10건)**
```sql
SELECT skill_name, error_type, error_message, fix_applied, created_at
FROM skill_errors ORDER BY created_at DESC LIMIT 10;
```

### Step 2: 진단 리포트 생성

수집한 데이터를 분석하여 사용자에게 리포트를 제공한다. 다음 항목을 포함한다:

1. **전체 상태 요약**: 총 수집 건수, 실패율, 학습된 최적 딜레이
2. **문제 분류**: 실패 유형별 건수 + 심각도 판단
3. **패턴 분석**: 반복 실패하는 appid, 특정 시간대 실패 집중 등
4. **권장 조치**: 각 문제에 대한 해결 방안

### Step 3: 자동 수정 (사용자 확인 후)

문제 유형별 자동 수정 전략:

#### rate_limited (HTTP 429)
- **진단**: `rate_limit_stats`에서 `errors_429` 비율 확인
- **수정**: `rate_limiter.py`의 기본 딜레이 값 상향 조정
- **또는**: 이미 AdaptiveRateLimiter가 학습하고 있으므로 다음 세션에서 자동 개선됨을 안내

#### server_error (HTTP 5xx)
- **진단**: 특정 appid에 집중되는지, 전반적인지 확인
- **수정 (특정 appid)**: 해당 게임이 삭제/비공개되었을 수 있음 → `game_collection_status`에서 스킵 처리
- **수정 (전반적)**: Steam 서버 문제 → 재시도 권장 (`--resume`)

#### timeout
- **진단**: `avg_response_ms` 추이 확인
- **수정**: `base.py`의 timeout 값 증가 (10s → 20s → 30s)

#### parse_error
- **진단**: `response_body` 내용 확인하여 API 응답 구조 변경 여부 판단
- **수정**: API 응답 파싱 코드(`models/game.py`, `models/review.py`의 `from_steamspy`, `from_steam_api`) 수정
- 이건 가장 중요한 케이스 — API가 바뀌면 파서를 업데이트해야 함

#### empty_response
- **진단**: 해당 appid가 Steam에서 삭제되었거나 비공개인지 확인
- **수정**: 해당 게임을 수집 대상에서 제외하거나 `resolved` 처리

#### data_quality
- **진단**: SteamSpy vs Steam API 데이터 편차 분석
- **수정**: 일반적으로 자동 수정 불필요 (데이터 소스 차이는 정상). 편차가 극단적이면 SteamSpy 데이터 신뢰도 경고

#### connection_error
- **진단**: 네트워크 문제인지, DNS 문제인지 확인
- **수정**: 재실행 권장. 반복되면 프록시/VPN 설정 확인 안내

#### cursor_invalid
- **진단**: 이전 세션의 커서가 만료된 경우
- **수정**: `game_collection_status.last_cursor`를 NULL로 리셋하여 해당 게임을 처음부터 재수집
```sql
UPDATE game_collection_status
SET last_cursor = NULL, reviews_collected = 0, reviews_done = 0
WHERE appid = ? AND version = ?;
```

#### skill_error (스킬 실행 에러)
- **진단**: `skill_errors` 테이블에서 미해결 에러 조회
- **수정 전략**:
  - `encoding` 반복 → 해당 스킬의 Python 코드에 `sys.stdout.reconfigure(encoding='utf-8')` 추가 권장
  - `sql` 반복 → DB 스키마와 쿼리 불일치 확인, 스킬의 SQL 수정
  - `import` → 패키지 설치 확인
  - `parse` → 데이터 구조 변경 확인
  - `api` → 외부 API 상태 확인, 재시도 또는 fallback
- **해결 처리**:
```python
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, "<project-root>/steam-crawler/src")
from steam_crawler.skill_error_logger import resolve_skill_error

resolve_skill_error(
    db_path="<project-root>/data/steam.db",
    error_id=<id>,
    resolution="code_fixed",  # code_fixed | workaround | skip
    fix_applied="<수정 내용>"
)
```

### Step 4: 코드 수정 적용

진단 결과에 따라 코드를 수정해야 할 때:

1. **파서 수정** (`parse_error`): `failure_logs.response_body`에 저장된 실제 응답을 분석하여 `models/game.py` 또는 `models/review.py`의 파싱 로직 수정
2. **타임아웃 조정** (`timeout`): `api/base.py`의 `BaseClient.__init__` timeout 파라미터 수정
3. **딜레이 조정** (`rate_limited`): `api/rate_limiter.py`의 기본값 또는 `min_delay_ms` 수정
4. **재시도 로직 개선**: `api/base.py`의 retry 로직에 새로운 패턴 추가

수정 후 반드시:
- 기존 테스트 실행: `cd steam-crawler && pytest tests/ -v`
- 수정된 부분에 대한 테스트 추가 (해당되는 경우)

### Step 5: 실패 건 해결 처리

수정이 적용된 후, 해결된 실패 건들을 resolved로 마킹:

```sql
UPDATE failure_logs SET resolved = 1, resolution = '<해결방법>'
WHERE failure_type = '<type>' AND resolved = 0;
```

resolution 값 예시:
- `retried_ok` — 재시도로 해결됨
- `skipped` — 해당 게임 스킵 처리
- `param_adjusted` — 파라미터 조정으로 해결
- `parser_fixed` — 파서 코드 수정으로 해결
- `manual_review` — 수동 확인 후 해결

## Presenting Diagnostics

진단 결과를 사용자에게 보여줄 때는 테이블 형식을 사용한다:

```
## 크롤러 건강 상태

| 항목 | 값 |
|------|-----|
| 총 수집 게임 | 45 |
| 총 수집 리뷰 | 2,340 |
| 미해결 실패 | 3건 |
| 학습된 딜레이 | SteamSpy: 850ms, Reviews: 1200ms |

## 실패 분석

| 유형 | 건수 | 심각도 | 권장 조치 |
|------|------|--------|----------|
| rate_limited | 2 | 낮음 | 자동 학습 중, 조치 불필요 |
| parse_error | 1 | 높음 | API 응답 변경 감지, 파서 수정 필요 |
```

진단 리포트에 스킬 에러 섹션도 포함한다:

```
## 스킬 에러 분석

| 스킬 | 유형 | 건수 | 최근 수정 |
|------|------|------|----------|
| steam-insight | encoding | 3 | PYTHONIOENCODING=utf-8 |
| steam-query | sql | 1 | 컬럼명 수정 |
```

## Proactive Recommendations

진단 외에도 다음을 확인하여 선제적으로 권장한다:

- rate_limit_stats에서 `errors_429` 비율이 10% 이상이면 딜레이 증가 권장
- parse_error가 3건 이상 미해결이면 API 스키마 변경 경고
- 미완료 게임이 있으면 `--resume` 실행 안내
- 마지막 수집이 7일 이상 전이면 재수집 권장

## Error Logging (필수)

Bash로 Python 코드 실행 시 에러가 발생하면, 수정 시도 전에 반드시 기록한다:

```python
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, "<project-root>/steam-crawler/src")
from steam_crawler.skill_error_logger import log_skill_error

log_skill_error(
    db_path="<project-root>/data/steam.db",
    skill_name="steam-diagnose",
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
