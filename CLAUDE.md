# Steam Game Analyzer

## 프로젝트 개요
Steam 게임을 태그/장르별로 필터링하고, 리뷰 데이터를 수집하는 CLI 도구.

## 모노레포 구조
- `steam-crawler/` — Python CLI (click + rich + httpx)
- `steam-analyzer/` — placeholder (추후 구현)
- `data/` — SQLite DB (gitignored)

## 개발 환경
- Python 3.12+
- 테스트: `cd steam-crawler && pytest`
- 설치: `cd steam-crawler && pip install -e ".[dev]"`

## 핵심 규칙
- DB는 SQLite, ORM 없이 raw SQL 사용
- API 호출은 반드시 AdaptiveRateLimiter를 통해 수행
- 모든 실패는 failure_logs 테이블에 기록
- 리뷰 API는 `filter=recent`, `purchase_type=all`, `num_per_page=80` 고정

## Git 워크플로우
- 브랜치: `feat/`, `fix/`, `chore/` + 소문자-하이픈 (`^(feat|fix|chore)/[a-z0-9-]+$`)
- master 직접 push 금지 → 반드시 브랜치 → PR (squash merge)
- 작업 시작: `git checkout -b feat/xxx origin/master`
- Hook 설정: `git config core.hooksPath .githooks`

## 스킬
- `.claude/skills/steam-crawl/` — Steam 게임 데이터 **수집** (CLI + Python 직접 호출)
- `.claude/skills/steam-query/` — 수집된 데이터 **조회/출력** (읽기 전용)
- `.claude/skills/steam-diagnose/` — 크롤러 **진단**, 실패 분석, 자동 개선
- `.claude/skills/steam-similar/` — Steam Store **유사 게임 탐색** (More Like This)
- `.claude/skills/steam-insight/` — 게임 **기획 인사이트 분석** (3자 비교 프레임워크)
