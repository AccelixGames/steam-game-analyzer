# Steam Analyzer — MCP 서버 설계

## 개요

Steam 리뷰 데이터를 분석하고, 게임 기획서에 대한 피드백을 제공하는 로컬 MCP 서버.
인디 게임 개발자가 경쟁작 리뷰를 분석해 "플레이어가 뭘 좋아하고 뭘 싫어하는지" 파악하고,
자신의 기획서를 입력하면 경쟁작 리뷰 데이터 기반 피드백을 받을 수 있다.

## 아키텍처

### 디렉토리 구조

```
steam-analyzer/
├── pyproject.toml
├── src/steam_analyzer/
│   ├── __init__.py
│   ├── server.py               # MCP stdio 서버 메인
│   ├── db_queries.py           # analyzer 전용 SQL 쿼리 함수
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── search_reviews.py   # search_reviews tool
│   │   └── analyze_design.py   # analyze_design tool
│   └── stats/
│       ├── __init__.py
│       └── review_stats.py     # 키워드 빈도, 긍부정 비율 등 통계 로직
└── tests/
    ├── conftest.py
    ├── test_search_reviews.py
    └── test_analyze_design.py
```

### 의존성 흐름

```
steam-analyzer  →  steam-crawler (editable install)
     │                    │
     ├── db_queries.py    └── db/schema.py (init_db, DB 구조)
     ├── stats/                models/ (GameSummary, Review)
     └── tools/
```

- `server.py`가 MCP stdio 서버를 띄움 (Python `mcp` SDK 사용)
- `db_queries.py`가 analyzer 전용 SQL 쿼리를 담당 (crawler의 repository와 별개)
- `steam_crawler`에서는 모델(`GameSummary`, `Review`)과 `init_db`만 재사용
- DB 경로: 환경변수 `STEAM_DB_PATH` 또는 기본값 `../data/steam.db`

### steam-crawler 참조 방식

`pip install -e ../steam-crawler`로 editable install.
- 재사용: `steam_crawler.models` (데이터 클래스), `steam_crawler.db.schema.init_db`
- 재사용하지 않음: `steam_crawler.db.repository` (crawler 전용 쓰기 로직)
- analyzer 전용 읽기 쿼리는 `db_queries.py`에 직접 작성

## Tool 스펙

### Tool 1: `search_reviews`

**목적:** 특정 태그/게임의 리뷰 데이터를 통계 요약 + 샘플로 반환.

**파라미터:**

| 이름 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `tag` | string | 택1 | 태그명 (예: "Roguelike"). `games.tags` JSON에서 검색 |
| `appid` | int | 택1 | 특정 게임 ID |
| `language` | string | 아니오 | 리뷰 언어 필터 (기본: 전체) |
| `sample_count` | int | 아니오 | 샘플 리뷰 수 (기본: 20, 최대: 50) |

`tag` 또는 `appid` 중 하나는 필수. (`genre` 제거 — DB에 장르 데이터 없음. tags가 장르를 포함.)

**태그 검색 방식:** 정규화된 `game_tags` 테이블 사용 (인덱스 `idx_game_tags_tag` 활용).
`SELECT appid FROM game_tags WHERE tag_name = ?`로 검색. `games.tags` JSON은 사용하지 않음.

**반환 구조:**

```json
{
  "games_count": 45,
  "total_reviews": 12340,
  "positive_ratio": 0.82,
  "top_keywords_positive": [{"word": "fun", "count": 320}],
  "top_keywords_negative": [{"word": "bug", "count": 180}],
  "sample_reviews": [
    {
      "appid": 123,
      "game_name": "GameName",
      "voted_up": true,
      "review_text": "리뷰 텍스트 (최대 500자로 잘림)...",
      "playtime_forever": 1200
    }
  ]
}
```

**샘플 리뷰 쿼리:** `reviews JOIN games ON reviews.appid = games.appid`로 `game_name` 포함.
`weighted_vote_score DESC`로 정렬하여 가장 유용한 리뷰 우선. 리뷰 텍스트는 500자로 truncate.

**빈 데이터 처리:** 해당 태그/앱ID에 데이터가 없으면 `games_count: 0`, 빈 배열 반환. DB 파일 미존재 시 에러 메시지 반환.

### Tool 2: `analyze_design`

**목적:** 기획서와 경쟁작 리뷰 데이터를 묶어 분석 컨텍스트 반환. Claude가 이 결과를 보고 피드백 생성.

**파라미터:**

| 이름 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `design_file` | string | 택1 | 기획서 파일 경로 (CWD 기준 상대경로 또는 절대경로) |
| `design_text` | string | 택1 | 기획서 텍스트 직접 입력 |
| `tag` | string | 택1 | 경쟁작 태그 |
| `appids` | int[] | 택1 | 특정 경쟁작 목록 |

`design_file` 또는 `design_text` 중 하나 필수.
`tag` 또는 `appids` 중 하나 필수.

**기획서 파일 처리:**
- 텍스트 기반 파일만 지원 (md, txt, etc.)
- 최대 1MB
- 경로는 MCP 서버 CWD 기준으로 해석

**반환 구조:**

```json
{
  "design_content": "기획서 내용...",
  "competitor_summary": {
    "games_count": 30,
    "positive_ratio": 0.78,
    "top_keywords_positive": [{"word": "...", "count": 100}],
    "top_keywords_negative": [{"word": "...", "count": 80}]
  },
  "sample_reviews_positive": [],
  "sample_reviews_negative": []
}
```

내부적으로 `search_reviews`와 동일한 통계 로직을 재사용.
Claude가 `design_content`와 `competitor_summary`를 함께 보고 피드백을 생성한다.

## 통계 로직 (stats/review_stats.py)

### 키워드 추출

- 영어: 공백 기반 토큰화 + 소문자 정규화 + 불용어 제거
- 한국어: 공백 기반 토큰화 + 불용어 제거
- `collections.Counter`로 빈도 집계
- 2글자 이하 토큰 제거, 숫자 전용 토큰 제거
- 외부 형태소 분석기 없이 시작. 추후 필요시 추가.

### 통계 항목

- 긍정/부정 비율: `voted_up` 기준
- 키워드 빈도: 긍정/부정 리뷰 각각 상위 30개
- 샘플 리뷰: `weighted_vote_score` 상위 N건 (가장 유용한 리뷰 우선)
- 샘플 리뷰 텍스트: 500자로 truncate

## DB 쿼리 (db_queries.py)

analyzer 전용 읽기 쿼리:

- `get_games_by_tag(conn, tag)` — `game_tags` 테이블에서 태그 검색, 게임 목록 반환
- `get_reviews_for_games(conn, appids, language=None)` — 게임 ID 목록으로 리뷰 조회, `reviews JOIN games` (`games.name AS game_name`)
- `get_review_samples(conn, appids, voted_up, limit, language=None)` — `weighted_vote_score DESC` 정렬, `reviews JOIN games` (`games.name AS game_name`), 텍스트 500자 truncate

## MCP 서버 통합

### .mcp.json (프로젝트 루트)

```json
{
  "mcpServers": {
    "steam-analyzer": {
      "command": "python",
      "args": ["-m", "steam_analyzer.server"],
      "cwd": "./steam-analyzer",
      "env": {
        "STEAM_DB_PATH": "../data/steam.db"
      }
    }
  }
}
```

### 설치

```bash
cd steam-crawler && pip install -e .
cd ../steam-analyzer && pip install -e ".[dev]"
```

## 사용 시나리오

### 리뷰 분석

사용자: "Roguelike 태그 경쟁작 리뷰를 분석해줘"
→ Claude가 `search_reviews(tag="Roguelike")` 호출
→ 통계 + 샘플 반환
→ Claude가 인사이트 정리

### 기획 피드백

사용자: "내 기획서 design.md를 기반으로 Roguelike 경쟁작 대비 피드백 줘"
→ Claude가 `analyze_design(design_file="design.md", tag="Roguelike")` 호출
→ 기획서 + 경쟁작 데이터 반환
→ Claude가 피드백 생성

## 에러 처리

- DB 파일 미존재: `{"error": "Database not found at <path>. Run steam-crawler first."}`
- 데이터 없음: 정상 응답 구조에 `games_count: 0`, 빈 배열 반환
- 기획서 파일 미존재/읽기 실패: `{"error": "Cannot read design file: <path>"}`
- 기획서 크기 초과 (>1MB): `{"error": "Design file too large (max 1MB)"}`

## 테스트 전략

- `conftest.py`: 테스트용 SQLite DB에 샘플 게임/리뷰 데이터 삽입
- `test_search_reviews.py`: 태그/앱ID 필터링, 통계 계산 정확성, 샘플 반환, 빈 데이터 케이스
- `test_analyze_design.py`: 파일/텍스트 입력, 경쟁작 데이터 매칭, 반환 구조 검증, 에러 케이스
- 외부 의존성 없음 (DB만 사용)
