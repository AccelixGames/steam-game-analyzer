# Steam Game Analyzer

Steam 게임 데이터 수집 및 분석 도구.

## 프로젝트 구조

- `steam-crawler/` — 데이터 수집기 (SteamSpy + Steam Reviews API)
- `steam-analyzer/` — 데이터 분석기 (추후 구현)
- `data/` — 공유 데이터 (SQLite DB, gitignored)

## 시작하기

```bash
cd steam-crawler
pip install -e ".[dev]"
steam-crawler collect --tag Roguelike --limit 5
```
