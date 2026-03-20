# Reports 레이어 구조 리팩토링

## 목표
reports/ 를 L1(단일 게임 분석), L2(비교/유사게임 탐색) 레이어로 분리

## 구조안
```
docs/insights/
  reports.json          ← layer, type 필드 추가
  reports/
    L1/                 ← 단일 게임 분석 (기존 8개 이동)
    L2/                 ← 비교/유사/크로스 분석
```

## reports.json 스키마 변경
- `layer`: 1 | 2
- `type`: `"analysis"` | `"similar"` | `"compare"`
- `source_games`: L2 전용, 원본 게임 appid 배열

## index.html 변경
- 상단 레이어 탭 추가 (L1 게임분석 / L2 비교분석)
- 카드 링크 경로: `./reports/L1/{slug}.html` or `./reports/L2/{slug}.html`

## 임시 조치
- L2 리포트는 `reports-layer2-temp/` 에 우선 저장 중
- 리팩토링 시 reports/L2/ 로 이동 예정
