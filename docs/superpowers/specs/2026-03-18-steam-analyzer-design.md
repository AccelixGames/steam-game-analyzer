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
     └── stats/           └── db/repository, models/
         review_stats.py       GameSummary, Review
```

- `server.py`가 MCP stdio 서버를 띄움 (Python `mcp` SDK 사용)
- 각 tool은 `steam_crawler.db`에서 데이터를 가져와 `stats/`로 가공 후 반환
- DB 경로: 환경변수 `STEAM_DB_PATH` 또는 기본값 `../data/steam.db`

### steam-crawler 참조 방식

`pip install -e ../steam-crawler`로 editable install.
`steam_crawler.db.repository`, `steam_crawler.models` 등을 직접 import하여 재사용.

## Tool 스펙

### Tool 1: `search_reviews`

**목적:** 특정 태그/장르/게임의 리뷰 데이터를 통계 요약 + 샘플로 반환.

**파라미터:**

| 이름 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `tag` | string | 택1 | 태그명 (예: "Roguelike") |
| `genre` | string | 택1 | 장르명 (예: "Action") |
| `appid` | int | 택1 | 특정 게임 ID |
| `language` | string | 아니오 | 리뷰 언어 필터 (기본: 전체) |
| `sample_count` | int | 아니오 | 샘플 리뷰 수 (기본: 20) |

`tag`, `genre`, `appid` 중 하나는 필수.

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
      "review_text": "...",
      "playtime_forever": 1200
    }
  ]
}
```

### Tool 2: `analyze_design`

**목적:** 기획서와 경쟁작 리뷰 데이터를 묶어 분석 컨텍스트 반환. Claude가 이 결과를 보고 피드백 생성.

**파라미터:**

| 이름 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `design_file` | string | 택1 | 기획서 파일 경로 |
| `design_text` | string | 택1 | 기획서 텍스트 직접 입력 |
| `tag` | string | 택1 | 경쟁작 태그 |
| `genre` | string | 택1 | 경쟁작 장르 |
| `appids` | int[] | 택1 | 특정 경쟁작 목록 |

`design_file` 또는 `design_text` 중 하나 필수.
`tag`, `genre`, `appids` 중 하나 필수.

**반환 구조:**

```json
{
  "design_content": "기획서 내용...",
  "competitor_summary": {
    "games_count": 30,
    "positive_ratio": 0.78,
    "top_keywords_positive": [],
    "top_keywords_negative": [],
    "common_complaints": ["긴 로딩", "밸런스"],
    "common_praises": ["아트 스타일", "리플레이성"]
  },
  "sample_reviews_positive": [],
  "sample_reviews_negative": []
}
```

## 통계 로직 (stats/review_stats.py)

### 키워드 추출

- 영어: 공백 기반 토큰화 + 소문자 정규화 + 불용어 제거
- 한국어: 공백 기반 토큰화 + 불용어 제거
- `collections.Counter`로 빈도 집계
- 외부 형태소 분석기 없이 시작. 추후 필요시 추가.

### 통계 항목

- 긍정/부정 비율: `voted_up` 기준
- 키워드 빈도: 긍정/부정 리뷰 각각 상위 30개
- 샘플 리뷰: `weighted_vote_score` 상위 N건 (가장 유용한 리뷰 우선)

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
        "STEAM_DB_PATH": "./data/steam.db"
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

## 테스트 전략

- `conftest.py`: 테스트용 SQLite DB에 샘플 게임/리뷰 데이터 삽입
- `test_search_reviews.py`: 태그/장르/앱ID 필터링, 통계 계산 정확성, 샘플 반환
- `test_analyze_design.py`: 파일/텍스트 입력, 경쟁작 데이터 매칭, 반환 구조 검증
- 외부 의존성 없음 (DB만 사용)
