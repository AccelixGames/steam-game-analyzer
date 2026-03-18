---
name: steam-insight
description: "Steam 게임 기획 인사이트 분석. 수집된 데이터로 게임의 설계 의도, 핵심 루프, 기획 성공/실패 포인트를 분석한다. Use when user asks about game design, planning, mechanics, core loop, what makes a game work, or why a game succeeded/failed. Triggers on: '기획 분석', '인사이트', '게임 분석', '핵심 루프', '왜 성공했어', '왜 재밌어', '게임 구조', 'game design', 'core loop', 'what makes this game work', 'insight', '메커니즘', '비즈니스 모델', '이 게임 분석해줘'. Also trigger when user asks about a specific game's strengths, weaknesses, or design philosophy after viewing its data."
---

# Steam Game Design Analyzer

수집된 Steam 데이터(메타정보, 태그, 리뷰, 외부 소스)를 종합하여 게임의 기획을 분석하는 스킬.

## DB 접근

```python
import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')
conn = sqlite3.connect("<project-root>/data/steam.db")
conn.row_factory = sqlite3.Row
```

## 분석 프레임워크: 3자 비교 (Triangulation)

게임 기획 분석은 세 가지 시선을 교차 검증하여 수행한다:

```
[1단계] 마케팅 포지셔닝  →  개발사가 "뭘 팔고 싶었는가"
[2단계] 메커니즘 실체     →  실제로 "뭘 만들었는가"
[3단계] 유저 경험         →  유저가 "뭘 느꼈는가"
         ↓
[4단계] 삼각 검증         →  일치 = 기획 성공, 불일치 = 인사이트
[5단계] 비즈니스 구조     →  숫자가 말하는 결과
```

각 단계는 아래 순서대로 실행한다.

---

## 1단계: 마케팅 포지셔닝 (개발사의 의도)

Steam 공식 설명에서 개발사가 강조하는 키워드와 포지셔닝을 추출한다.
short_description은 한 줄 엘리베이터 피치, detailed_description은 전체 세일즈 피치다.

```sql
SELECT short_description_en, short_description_ko,
       detailed_description_en, detailed_description_ko,
       header_image
FROM games WHERE appid = ?;
```

### 1-A. 한 줄 피치 분석 (short_description)
- 어떤 단어를 골랐는가? (동사, 형용사에 주목)
- 어떤 감정/경험을 약속하는가?
- 한국어 설명이 있다면 영문과 뉘앙스 차이가 있는가?
- header_image가 전달하는 분위기는?

### 1-B. 전체 피치 분석 (detailed_description)
- **섹션 구조**: 어떤 피처를 먼저 소개하는가? 순서 = 개발사가 생각하는 우선순위
- **피처 목록 추출**: 전체 설명에서 언급된 구체적 기능/시스템 나열
- **short vs detailed 갭**: 한 줄 피치에선 빠졌지만 전체 설명에선 강조하는 요소 (숨은 셀링포인트)
- **톤 변화**: 마케팅 카피(short)와 상세 설명(detailed)의 어조 차이 — 감성 호소 vs 기능 나열
- detailed_description이 NULL이면 "전체 설명 미수집" 명시 후 short만으로 분석

## 2단계: 메커니즘 실체 (실제 구현)

IGDB/RAWG의 제3자 설명, 구조화된 메타데이터, 리텐션 프록시를 교차하여 실제 구현된 시스템을 파악한다.

### 2-A. 제3자 설명 + 평점

```sql
SELECT igdb_summary, igdb_storyline, igdb_rating,
       rawg_description, rawg_rating, metacritic_score
FROM games WHERE appid = ?;
```

### 2-B. IGDB 구조화 메타데이터 (themes/keywords)

Steam 태그와 독립적인 제3자 분류 체계. Steam 태그와 교차 비교하여 숨은 특성을 발견한다.

```sql
-- IGDB Themes (대분류 — Action, Open World, Horror 등)
SELECT c.name FROM game_themes t
JOIN theme_catalog c ON t.theme_id = c.id
WHERE t.appid = ?;

-- IGDB Keywords (세분류 — drugs, gambling, skateboarding 등)
SELECT c.name FROM game_keywords k
JOIN keyword_catalog c ON k.keyword_id = c.id
WHERE k.appid = ?;
```

분석 포인트:
- **IGDB keywords vs Steam tags 교차**: IGDB에만 있는 키워드는 제3자가 인식한 숨은 특성 (예: `gambling`이 Steam 태그에는 없지만 IGDB keywords에 있으면, 게임에 갬블링 요소가 있지만 Steam 커뮤니티가 이를 핵심 정체성으로 인식하지 않는다는 의미)
- **IGDB themes**: 대분류 시선. Steam 태그보다 상위 수준의 분류로, 게임의 장르적 위치를 확인
- themes/keywords가 없으면 "IGDB 메타데이터 없음" 명시

### 2-C. RAWG 리텐션 프록시 (유저 상태 분포)

RAWG의 `added_by_status`는 유저가 게임을 어떻게 분류했는지 보여주는 리텐션 프록시다.

```sql
SELECT rawg_added, rawg_status_yet, rawg_status_owned,
       rawg_status_beaten, rawg_status_toplay,
       rawg_status_dropped, rawg_status_playing,
       rawg_exceptional_pct, rawg_recommended_pct,
       rawg_meh_pct, rawg_skip_pct
FROM games WHERE appid = ?;
```

분석 포인트:
- **드롭률**: `dropped / added` — 이탈 비율. 높으면 초반 이탈 문제
- **클리어률**: `beaten / (owned + playing + beaten)` — 완주 비율. 낮으면 콘텐츠 고갈 또는 반복 플레이 중심
- **exceptional vs meh 비율**: RAWG 4단계 평가(exceptional/recommended/meh/skip) 분포
- **Steam 긍정률 vs RAWG 평가 괴리**: Steam에서 긍정적이지만 RAWG에서 meh가 높으면, "재미있지만 추천하기 어려운" 게임
- rawg_added가 NULL이면 "RAWG 리텐션 데이터 없음" 명시

### 2-D. 종합 분석

분석 포인트:
- **detailed_description에서 추출한 피처 vs 제3자 설명 교차**: 개발사가 나열한 피처 중 IGDB/RAWG에서도 확인되는 것은 실제 구현된 것, 제3자 설명에만 있는 것은 마케팅에서 빠진 요소
- 1단계 마케팅에선 언급하지 않았지만 실제로 존재하는 시스템은?
- 마케팅이 과장한 부분은?
- 핵심 메커니즘(core mechanics)은 무엇인가?
- storyline이 있다면 내러티브 구조는?

## 3단계: 유저 경험 (실제 반응)

### 3-A. 태그 분석 (유저가 인식한 정체성)

```sql
SELECT tag_name, vote_count FROM game_tags
WHERE appid = ? ORDER BY vote_count DESC;
```

분석 포인트:
- 상위 태그들의 투표 수 분포 (균등 vs 편중)
  - 균등: 다축 설계가 동시에 작동
  - 편중: 하나의 정체성이 지배적
- 태그를 기획 축(pillar)으로 분류:
  - 장르/메커니즘 축 (Roguelike, Card Game, Simulation 등)
  - 분위기/감성 축 (Relaxing, Atmospheric, Dark 등)
  - 플랫폼/접근성 축 (Moddable, Controller, Multiplayer 등)
- 마케팅 설명과 태그 사이의 괴리가 있는가?

### 3-B. 리뷰 분석 (실제 경험의 증거)

**긍정 리뷰 — 기획이 성공한 지점**
```sql
-- 장문 긍정 리뷰 (깊이 있는 피드백)
SELECT language, review_text, playtime_at_review, votes_up
FROM reviews WHERE appid = ? AND voted_up = 1 AND length(review_text) > 200
ORDER BY length(review_text) DESC LIMIT 10;

-- 가장 도움이 된 긍정 리뷰
SELECT language, review_text, playtime_at_review, votes_up, weighted_vote_score
FROM reviews WHERE appid = ? AND voted_up = 1
ORDER BY weighted_vote_score DESC LIMIT 10;
```

**부정 리뷰 — 기획의 약점**
```sql
SELECT language, review_text, playtime_at_review, votes_up, weighted_vote_score
FROM reviews WHERE appid = ? AND voted_up = 0
ORDER BY weighted_vote_score DESC LIMIT 10;
```

**플레이타임별 긍정률 — 리텐션 곡선**
```sql
SELECT
  CASE
    WHEN playtime_at_review < 60 THEN '< 1h'
    WHEN playtime_at_review < 600 THEN '1-10h'
    WHEN playtime_at_review < 3000 THEN '10-50h'
    WHEN playtime_at_review < 6000 THEN '50-100h'
    ELSE '100h+'
  END as playtime_bucket,
  count(*) as cnt,
  sum(voted_up) as positive,
  round(100.0 * sum(voted_up) / count(*), 1) as positive_rate
FROM reviews WHERE appid = ?
GROUP BY playtime_bucket;
```

**언어별 분포 — 시장 도달 범위**
```sql
SELECT language, count(*) as cnt,
       sum(voted_up) as positive, count(*) - sum(voted_up) as negative
FROM reviews WHERE appid = ?
GROUP BY language ORDER BY cnt DESC LIMIT 10;
```

리뷰 분석 시 주의:
- 단일 리뷰가 아닌 **여러 언어/플레이타임대에서 반복되는 패턴**을 찾는다
- 문화권을 넘어 공통 출현하는 키워드/감정이 기획의 구조적 특성
- 리뷰 텍스트를 인용할 때 원문+번역을 함께 제공한다

## 4단계: 삼각 검증 (Triangulation)

3개 시선을 교차하여 기획의 성공/실패 포인트를 도출한다.

| 마케팅 (1단계) | 메커니즘 (2단계) | 유저 경험 (3단계) | 판정 |
|---------------|-----------------|------------------|------|
| 강조함 | 구현됨 | 긍정 반응 | **기획 성공** |
| 강조함 | 구현됨 | 부정/무반응 | **실행 실패** — 있지만 재미없다 |
| 강조함 | 미구현/약함 | 부정 반응 | **과대 마케팅** |
| 언급 안 함 | 구현됨 | 긍정 반응 | **숨은 강점** — 마케팅에서 놓친 셀링포인트 |
| 언급 안 함 | 미구현 | 긍정 반응 | **커뮤니티 창발** — 유저가 만든 가치 |

이 표를 기반으로 각 기획 요소를 판정하고, 구체적 증거(리뷰 인용, 태그 수치)를 첨부한다.

## 5단계: 비즈니스 구조

```sql
SELECT price, owners, avg_playtime, review_score, metacritic_score
FROM games WHERE appid = ?;
```

### 5-A. Twitch 스트리밍 데이터

```sql
SELECT twitch_stream_count, twitch_viewer_count,
       twitch_top_language, twitch_lang_distribution,
       twitch_fetched_at
FROM games WHERE appid = ?;
```

분석 포인트:
- **스트리밍 인기도**: 라이브 채널 수 × 시청자 수 = "watchability" 지표. 높으면 콘텐츠 크리에이터에게 매력적인 게임
- **스트리밍 언어 vs 리뷰 언어 분포 교차**: 괴리가 있으면 잠재 미개척 시장 (예: 리뷰는 영어 중심인데 스트리밍은 독일어가 높으면 독일 시장 성장 가능성)
- `twitch_lang_distribution`은 JSON 문자열 — 파싱하여 언어별 스트리머 수 확인
- Twitch 데이터는 **스냅샷**(수집 시점의 라이브 데이터)이므로 `twitch_fetched_at` 시점을 반드시 명시
- twitch_stream_count가 NULL이면 "Twitch 데이터 없음" 명시

### 5-B. 기존 분석 포인트

분석 포인트:
- 가격대 (price ÷ 100 = 달러)
- 소유자 규모
- 평균 플레이타임 (avg_playtime ÷ 60 = 시간) → DLC/IAP 전환 기회
- 수익 모델 추론 (DLC 확장? 모딩 커뮤니티? 시즌 콘텐츠?)

---

## 출력 형식: HTML 보고서

분석 결과는 **단일 HTML 파일**로 `docs/insights/{game-slug}.html`에 생성한다.

### 템플릿

**TEMPLATE.html** (같은 디렉토리)을 반드시 읽고 참고한다.
- CSS 변수, 클래스명, 컴포넌트 구조를 그대로 사용
- `{{PLACEHOLDER}}`를 실제 데이터로 치환
- `/frontend-design` 스킬을 함께 호출하여 디자인 품질 확보

### 파일 경로 규칙
- 게임 이름을 kebab-case로 변환: "TCG Card Shop Simulator" → `tcg-card-shop-simulator.html`
- 저장 위치: `<project-root>/docs/insights/`

### HTML 보고서 구조

```
Hero
├── Steam 상점 링크 뱃지 (https://store.steampowered.com/app/{appid}/)
├── 게임 헤더 이미지 배경 (header_image)
├── 게임 이름, 한 줄 요약
└── 핵심 수치 (긍정률, 소유자, 가격, 플레이타임)

Step 01: 마케팅 포지셔닝
├── 한 줄 피치 (short_description) 한/영 비교
├── 전체 피치 (detailed_description) 섹션 구조 분석
│   ├── 피처 우선순위 (소개 순서 기반)
│   └── short vs detailed 갭 — 한 줄 피치에서 빠진 요소 강조
└── 마케팅 키워드 분석

Step 02: 메커니즘 실체
├── 코어 루프 다이어그램 (2중 구조: 내부 루프 + 외부 루프)
│   ├── 내부 루프 (일일): 팩 주문 → 개봉/판매 → 수익 → 고객 응대
│   ├── 외부 루프 (성장): 수익 재투자 → 확장/자동화
│   └── 핵심 텐션: 확정 보상 vs 가변 보상 설명
├── IGDB Themes/Keywords 교차 분석 (Steam 태그 vs IGDB 키워드 비교)
├── RAWG 리텐션 프록시 — 드롭률/클리어률/평가 분포
└── 마케팅이 말하지 않은 시스템들 (IGDB/RAWG 기반)

Step 03: 유저 경험
├── 태그 수평 바 차트 (투표수 비례, 태그명 + 바 + 수치)
├── 기획 축 분류 테이블 (태그를 축별 그룹핑 + 합산 투표 + 비중)
│   예: 경영/경제 722(지배적), 수집/카드 415(강력), 분위기/접근성 201(보조)
├── 플레이타임별 긍정률 바 차트
├── 언어별 리뷰 분포 바 차트
├── 기획 성공 포인트 (리뷰 인용 + 분석 서술 통합)
└── 기획 약점 (리뷰 인용 + 분석 서술 통합)

Step 04: 삼각 검증 (Triangulation Table)
└── 기획 요소별 마케팅/구현/유저 반응 교차 판정표
    판정 뱃지: 기획 성공(초록), 실행 미흡(빨강), 숨은 강점(보라), 커뮤니티 창발(골드)

Step 05: 비즈니스 구조
├── 추정 매출, 가성비, 수익 모델
├── Twitch 스트리밍 데이터 (채널 수, 시청자, 언어 분포)
└── 수익 확장 가능성

결론
└── 구조적 결론 — 태그 데이터를 근거로 인용하며 성공/실패의 구조적 원인을 설명
    (단순 감상이 아닌, 데이터 기반 논증)

Footer
└── 생성일, 데이터 소스, 분석 리뷰 수
```

### 기획 축 분류 기준

태그를 다음 축으로 그룹핑하고, 합산 투표수와 비중을 계산한다:

| 기획 축 | 포함 태그 예시 | 비중 판정 |
|---------|--------------|----------|
| 경영/경제 | Simulation, Management, Economy, Capitalism, Shop Keeper | 합산 투표 기준 |
| 수집/카드 | Collectathon, TCG, Card Game, Trading | 지배적/강력/보조 |
| 분위기/접근성 | Relaxing, Casual, Life Sim | 중 하나로 판정 |
| 시점/기술 | 3D, First-Person, Immersive Sim | |
| 플랫폼 | Singleplayer, Early Access, Co-op, Multiplayer | |

### 코어 루프 다이어그램 요구사항

단순 일렬 노드가 아닌 **2중 루프 구조**로 표현:
- **내부 루프 (일일 운영)**: 반복적 일상 — 팩 주문 → 개봉/판매 → 수익 → 고객 응대
- **외부 루프 (성장)**: 장기 목표 — 수익 재투자 → 매장 확장 → 자동화 → 더 많은 내부 루프
- **핵심 텐션**: 확정 보상(매출, 확장)과 가변 보상(팩 개봉 희귀 카드)이 교차하는 구조를 명시
- 자동화(직원 고용)가 플레이어 역할을 "경영자"에서 "수집가/도박사"로 전환시키는 기획적 의미 포함

### 리뷰 인용 형식

- 긍정 리뷰: 골드 좌측 보더
- 부정 리뷰: 빨간 좌측 보더
- 메타 정보: `언어 · 플레이타임 · helpful 수`
- 비영어 리뷰: 번역을 별도 블록으로 표시
- 인용 후 바로 분석 서술을 연결 (인용과 분석이 분리되지 않도록)

---

## 주의사항

- 이 스킬은 **읽기 전용** — DB를 수정하지 않는다
- 데이터가 없으면 "수집된 데이터가 없습니다. `steam-crawl` 스킬로 먼저 수집하세요"라고 안내
- igdb/rawg 데이터가 NULL인 경우 해당 소스 없이 분석하되, 2단계가 약해진다고 명시
- 리뷰가 적은 경우(<50개) 통계적 신뢰도가 낮다고 명시
- 플레이타임은 분 단위 저장 → 시간 변환 (÷60)
- 가격은 센트 단위 저장 → 달러 변환 (÷100)
