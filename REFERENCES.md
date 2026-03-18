# Steam 데이터 크롤링 참고 프로젝트

## 게임 데이터 전체 수집 (추천)

| 프로젝트 | 설명 | 특징 |
|----------|------|------|
| [FronkonGames/Steam-Games-Scraper](https://github.com/FronkonGames/Steam-Games-Scraper) | Steam Web API로 전체 게임 정보 추출 → JSON 저장 | SteamSpy 데이터도 함께 수집, 가장 포괄적 |
| [prncc/steam-scraper](https://github.com/prncc/steam-scraper) | Scrapy 기반 스파이더 - 상품 데이터 + 리뷰 크롤링 | 대규모 수집에 적합, 배포 스크립트 포함 |
| [TheRealFanjin/steam-games-scraper](https://github.com/TheRealFanjin/steam-games-scraper) | 플랫폼, 가격, 스펙 데이터 수집 | 가볍고 간단 |

## 리뷰 / 감성분석 특화

| 프로젝트 | 설명 |
|----------|------|
| [aesuli/steam-crawler](https://github.com/aesuli/steam-crawler) | 게임 리뷰 크롤링 → HTML zip + CSV 추출 |
| [mounishvatti/SteamScrape](https://github.com/mounishvatti/SteamScrape) | 리뷰 스크래핑 + 감성분석(Sentiment Analysis) 포함 |

## SteamDB / SteamSpy 데이터

| 프로젝트 | 설명 |
|----------|------|
| [AmyrAhmady/steamdb-js](https://github.com/AmyrAhmady/steamdb-js) | SteamDB 스크래핑 → JSON (JavaScript) |
| [GuildNerd/SteamDB_scraping](https://github.com/GuildNerd/SteamDB_scraping) | Selenium 기반 SteamDB 스크래핑 (Python) |

## Steam API 라이브러리

| 프로젝트 | 설명 |
|----------|------|
| [smiley/steamapi](https://github.com/smiley/steamapi) | Python OOP Steam Web API 라이브러리 |
| [AnttiVainio/Steam-crawler](https://github.com/AnttiVainio/Steam-crawler) | 유저 프로필 통계 수집 크롤러 |

## GitHub Topics (더 많은 프로젝트 탐색)

- [steam-api (Python, 별 순)](https://github.com/topics/steam-api?l=python&o=desc&s=stars)
- [steam-store (Python)](https://github.com/topics/steam-store?l=python)
- [steamspy](https://github.com/topics/steamspy)

## 참고 사항

- Steam 공식 API(`store.steampowered.com/api`)는 rate limit이 비교적 관대하고 안정적
- SteamDB/SteamSpy 웹 스크래핑은 차단 위험이 있으므로 공식 API 기반이 권장됨
- steam-game-analyzer와 연계 시 **FronkonGames/Steam-Games-Scraper**(JSON 출력) 또는 **prncc/steam-scraper**(Scrapy, 대규모 수집)가 적합
