# Steam Game Analyzer

Steam 게임 데이터를 수집·분석하는 CLI 도구. 11개 외부 소스에서 게임 정보, 리뷰, 가격, 플레이타임, 기술 스펙 등을 수집하고, MCP 서버를 통해 Claude에서 직접 분석할 수 있습니다.

## 주요 기능

- **게임 탐색** — SteamSpy 태그/장르/Top100 기반 게임 목록 수집
- **리뷰 수집** — 커서 기반 페이지네이션으로 대량 리뷰 수집 (중단 시 자동 재개)
- **11개 외부 소스 연동** — IGDB, RAWG, Twitch, HowLongToBeat, CheapShark, OpenCritic, PCGamingWiki, Wikidata 등
- **데이터 버전 관리** — 수집 실행마다 버전 부여, 필드 레벨 변경 이력 추적
- **MCP 서버** — Claude Code에서 리뷰 검색·기획 분석 도구로 직접 사용
- **인사이트 리포트** — 게임별 HTML 분석 리포트 자동 생성

## 프로젝트 구조

```
steam-game-analyzer/
├── steam-crawler/       # 데이터 수집 CLI (Python)
│   ├── api/             # 외부 API 클라이언트 (11개)
│   ├── db/              # SQLite 스키마·리포지토리
│   ├── models/          # GameSummary, Review 데이터 모델
│   └── pipeline/        # 3단계 파이프라인 + 8개 보강 스텝
├── steam-analyzer/      # MCP 분석 서버 (Claude 연동)
│   ├── tools/           # search_reviews, analyze_design, get_analysis_logs
│   └── stats/           # 키워드 추출, 리뷰 통계
├── scripts/             # 유틸리티 (인덱스 빌드, 누락 데이터 수집)
├── docs/insights/       # 생성된 HTML 인사이트 리포트
└── data/                # SQLite DB (gitignored)
```

## 시작하기

### 설치

```bash
cd steam-crawler
pip install -e ".[dev]"
```

### 게임 수집

```bash
# 태그로 수집
steam-crawler collect --tag Roguelike --limit 10

# 장르로 수집
steam-crawler collect --genre RPG --top-n 5

# Top 100 수집
steam-crawler collect --top100

# 리뷰까지 수집 (Step 3)
steam-crawler collect --tag "Deck Building" --limit 5 --step 3 --max-reviews 500
```

### 데이터 확인

```bash
steam-crawler status          # 수집 현황
steam-crawler versions        # 수집 버전 이력
steam-crawler diff 1 2        # 버전 간 변경사항
steam-crawler tags --limit 20 # 태그 목록
steam-crawler genres          # 장르 목록
```

## 수집 파이프라인

| 단계 | 설명 | 소스 |
|------|------|------|
| Step 1 | 게임 목록 수집 | SteamSpy |
| Step 1b | 태그·장르 보강 | SteamSpy |
| Step 1c | 스토어 상세 (설명, 이미지) | Steam Store API |
| Step 1d | 내러티브·레이팅 | IGDB (Twitch OAuth) |
| Step 1e | 설명·평점 | RAWG |
| Step 1f | 스트리밍 데이터 | Twitch Helix |
| Step 1h | 클리어 타임 | HowLongToBeat |
| Step 1i | 할인·가격 이력 | CheapShark |
| Step 1j | 평론가 점수 | OpenCritic (RapidAPI) |
| Step 1k | 기술 스펙 (엔진, HDR 등) | PCGamingWiki |
| Step 1l | 구조화된 게임 속성 | Wikidata SPARQL |
| Step 2 | 리뷰 요약 스캔 | Steam Reviews API |
| Step 3 | 리뷰 텍스트 수집 | Steam Reviews API |

## 외부 API 설정

일부 API는 인증이 필요합니다. `.env.example`을 복사하여 `.env`를 만드세요:

```bash
cp .env.example .env
```

```env
TWITCH_CLIENT_ID=       # IGDB + Twitch (필수: Step 1d, 1f)
TWITCH_CLIENT_SECRET=
RAWG_API_KEY=           # RAWG (필수: Step 1e)
```

> 인증 없는 소스 (SteamSpy, Steam API, HowLongToBeat, CheapShark, PCGamingWiki, Wikidata)는 키 없이 동작합니다.

## MCP 서버 (Claude 연동)

steam-analyzer는 [MCP](https://modelcontextprotocol.io) 서버로, Claude Code에서 직접 사용할 수 있습니다.

### 제공 도구

| 도구 | 설명 |
|------|------|
| `search_reviews` | 태그/appid로 리뷰 검색, 키워드 분석, 감성 비율 |
| `analyze_design` | 기획서를 경쟁작 리뷰와 비교 분석 |
| `get_analysis_logs` | 수집 실패 로그 조회·진단 |

### 설정

`.mcp.json`이 프로젝트 루트에 포함되어 있어 Claude Code에서 자동 인식됩니다.

## 기술 스택

- **Python 3.12+**
- **SQLite** — ORM 없이 raw SQL
- **curl_cffi** — 브라우저 임퍼소네이션 (안티봇 우회)
- **click + rich** — CLI 프레임워크
- **MCP** — Claude 도구 연동 프로토콜
- **AdaptiveRateLimiter** — 응답 시간·429 에러 기반 자동 속도 조절

## 테스트

```bash
cd steam-crawler
pytest
```

## 라이선스

MIT
