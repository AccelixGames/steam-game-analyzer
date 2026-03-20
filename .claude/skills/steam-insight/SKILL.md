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

## 유효 리뷰 View

`valid_reviews` — 정성 분석용 필터링된 리뷰 View.
- 100자 이상 (한국어: 50자) OR 플레이타임 50시간 이상
- ASCII art 제거, 게임별 중복 텍스트 1건만 유지 (weighted_vote_score 최고)
- **정성 분석(리뷰 인용/분석)에만 사용. 정량 통계는 `reviews` 테이블 사용.**
- playtime_at_review가 NULL이고 100자 미만인 리뷰는 제외됨
- 필터링으로 일부 게임에서 결과가 LIMIT 미만일 수 있음
- **⚠ 편향 주의**: 부정 리뷰 보강 수집으로 reviews 테이블의 긍/부정 비율은 실제와 다름. 전체 긍정률/부정률은 반드시 `games.steam_positive` / `games.steam_negative` 사용.

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

### 2-C. Wikidata 구조화 기획 데이터

Wikidata의 커뮤니티 온톨로지에서 추출한 구조화된 기획 데이터. IGDB/Steam과 독립적인 제3의 분류 체계.

```sql
-- Wikidata 기본 정보
SELECT wikidata_id FROM games WHERE appid = ?;

-- 전체 claims (mechanic, character, location, depicts, award 등)
SELECT claim_type, name, wikidata_id
FROM game_wikidata_claims WHERE appid = ?
ORDER BY claim_type, name;
```

분석 포인트:
- **Wikidata genre vs Steam tags vs IGDB keywords 3중 교차**: 세 소스에서 공통으로 나타나는 분류는 게임의 확실한 정체성, 하나에만 있는 것은 관점 차이
- **P4151 mechanic**: open world, crafting, permadeath 등 구조화된 메카닉 분류. Steam 태그보다 정밀한 기획 패턴 식별
- **P674 character**: 등장인물 수와 목록 → 내러티브 규모 측정
- **P840 location**: 배경 세계 구조 → 레벨/맵 디자인 규모
- **P166/P1411 award**: 수상 이력 → 어떤 기획 요소가 업계에서 인정받았는지 (Best Design, Best Narrative 등 카테고리별 의미)
- **P180 depicts**: 게임이 다루는 주제/소재 (mythology, LGBTQ 등) → 문화적 포지셔닝
- wikidata_id가 NULL 또는 'not_found'이면 "Wikidata 데이터 없음" 명시

### 2-D. RAWG 리텐션 프록시 (유저 상태 분포)

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

### 2-E. HowLongToBeat 게임 길이 (기획 밀도 분석)

```sql
SELECT hltb_main_story, hltb_main_extra, hltb_completionist
FROM games WHERE appid = ?;
```

분석 포인트:
- **main_story/completionist 비율** → 콘텐츠 깊이 vs 패딩 판단. 비율이 1:1.5 이하면 메인 경험에 집중된 설계, 1:5 이상이면 반복 콘텐츠/수집 요소 무거움
- **Steam 리뷰 평균 playtime_at_review와 비교** → 유저가 메인스토리 길이의 몇 %에서 리뷰를 쓰는가? 50% 미만이면 초반 강점, 150% 이상이면 리플레이 가치
- hltb_main_story가 NULL이면 "HLTB 데이터 없음" 명시

### 2-F. PCGamingWiki 기술 스펙 (기술 완성도)

```sql
-- PCGamingWiki 기술 스펙
SELECT pcgw_engine, pcgw_has_ultrawide, pcgw_has_hdr,
       pcgw_has_controller, pcgw_graphics_api
FROM games WHERE appid = ?;
```

분석 포인트:
- **엔진**: 엔진 선택은 기획적 제약을 결정 (예: Unity → 모바일 포팅 용이, Unreal → 비주얼 강점)
- **울트라와이드/HDR/컨트롤러**: 기술적 세심함의 지표. 인디 게임이 이를 지원하면 기술 품질 높음

### 2-G. 종합 분석

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

#### Fallback 판정

먼저 유효 리뷰 수를 확인한다:
```sql
SELECT count(*) as valid_count FROM valid_reviews WHERE appid = ?;
```

- **500건 이하**: 서브에이전트 없이 메인이 직접 TOP 100건 분석 (아래 "Fallback 모드" 참조)
- **500건 초과**: 서브에이전트 병렬 분석 실행

> Fallback 시 사용자에게 안내: "이 게임의 유효 리뷰는 N건입니다. 더 풍부한 분석을 위해 `/steam-crawl`로 리뷰를 추가 수집하세요."

#### 파티션 결정

상위 3개 언어 결정 (N = 실제 언어 수, 1~3):
```sql
SELECT language, count(*) as cnt
FROM valid_reviews WHERE appid = ?
GROUP BY language ORDER BY cnt DESC LIMIT 3;
```

#### 서브에이전트 병렬 디스패치

1~2단계와 3-A를 먼저 완료한 후, 게임 컨텍스트를 요약한다:

**게임 컨텍스트 (모든 서브에이전트에게 전달):**
```
- 게임명: {{name}}
- 장르: {{genres}}
- 태그 TOP 10: {{tags with vote counts}}
- 마케팅 한 줄 피치: {{short_description}}
- 핵심 메커니즘: {{2단계에서 파악한 코어루프 2~3문장}}
```

다음 서브에이전트를 **단일 메시지에서 동시에** Agent 도구로 디스패치한다 (총 1 + N×2개, 최대 7개):

**① Opus 서브에이전트 (TOP 100 심층 분석)**
- model: opus
- 쿼리:
```sql
SELECT recommendation_id, language, review_text, voted_up,
       playtime_at_review, votes_up, weighted_vote_score, playtime_forever
FROM valid_reviews WHERE appid = ?
ORDER BY weighted_vote_score DESC LIMIT 100;
```
- 프롬프트:
```
당신은 게임 기획 분석가입니다. 아래는 {{게임명}}의 유저 리뷰 중
커뮤니티가 가장 도움이 된다고 평가한 상위 100건입니다.

{{게임 컨텍스트}}

## 임무
각 리뷰를 읽고 **게임 기획 관점**에서 분석하세요.
단순 감상이 아닌, 기획의 성공/실패를 증거하는 리뷰를 찾아내세요.

## 출력 형식

### 기획 성공 포인트 (최대 5개)
각 포인트:
- **패턴명**: 한 줄 요약
- **증거 리뷰**: 원문 인용 (언어 · 플레이타임 · helpful수)
- **비영어면 번역 포함**
- **기획적 의미**: 왜 기획의 성공인가 (2~3문장)

### 기획 약점 (최대 5개)
(같은 형식)

### 흥미로운 발견 (최대 3개)
- 기획 성공/실패로 분류 어렵지만 주목할 패턴

### 보고서 인용 추천 리뷰 (최대 10개)
- recommendation_id, 원문(발췌), 인용 이유 1줄

### 코어 루프 증거 (최대 3개)
- 리뷰에서 발견된 실제 플레이 루프 묘사 (유저가 반복적으로 하는 행동 패턴)
- 각각: 원문 발췌 + "이 리뷰가 드러내는 루프 구조" 1~2문장
- 2단계 메타데이터 기반 루프와 일치하면 확인, 불일치하면 보정 근거

## 리뷰 데이터
{{100건의 리뷰}}
```

**② Sonnet 서브에이전트 ×(N×2) (언어별 긍/부정 패턴 분석)**
- model: sonnet
- 파티션별 쿼리:
```sql
SELECT recommendation_id, review_text, playtime_at_review,
       votes_up, weighted_vote_score, playtime_forever
FROM valid_reviews
WHERE appid = ? AND language = ? AND voted_up = ?
ORDER BY weighted_vote_score DESC LIMIT 200;
```
- 프롬프트:
```
당신은 게임 리뷰 분석가입니다. 아래는 {{게임명}}의
{{언어}} {{긍정/부정}} 리뷰 상위 200건입니다.

{{게임 컨텍스트}}

## 임무
200건의 리뷰에서 **반복되는 패턴**을 찾아내세요.
개별 리뷰 분석이 아닌, 여러 리뷰에 걸쳐 나타나는 공통 주제를 추출하세요.

## 출력 형식

### 핵심 패턴 (3~5개, 빈도순)
각 패턴:
- **패턴명**: 한 줄 요약
- **빈도**: 대략 몇 건에서 언급 (예: "약 40/200건")
- **대표 인용**: 패턴을 가장 잘 보여주는 리뷰 1건 (원문 발췌)
- **비영어면 번역 포함**
- **기획 시사점**: 이 패턴이 게임 설계에 대해 말해주는 것 (1~2문장)

### 이 언어/감정 고유의 특이점 (0~2개)
- 이 구역에서만 두드러지는 발견

### 코어 루프 증거 (0~2개)
- 유저가 묘사하는 반복 행동 패턴
- 원문 발췌 + 루프 구조 해석 1문장

### 요약 통계
- 가장 자주 언급된 게임 시스템/피처 TOP 3
- 감정 강도: 강한 표현 비율 체감
```

#### 결과 통합 규칙

모든 서브에이전트 결과가 반환되면 다음 규칙으로 통합:

**패턴 병합:**
1. 여러 파티션에서 같은 시스템/피처를 언급하면 하나로 병합
2. 병합 시 빈도 합산, 대표 인용은 가장 구체적인 것 1~2개 채택
3. 보고서에 반영되는 고유 패턴은 최대 10개

**충돌 해결:**
- 긍정/부정 파티션에서 같은 시스템에 상반된 평가 → "양면적 요소"로 기록
- 언어별 상반된 반응 → "문화권별 차이"로 기록

**코어 루프 보강:**
1. Opus 최대 3개 + Sonnet 파티션별 최대 2개 = 최대 15개 루프 증거 수집
2. 2단계 메타데이터 루프 vs 리뷰 루프 증거 교차 검증
   - 일치 → 루프 다이어그램에 "유저 증언 확인" 표기 + 리뷰 인용
   - 불일치 → 다이어그램 추가/수정
   - 마케팅만 존재 → 삼각검증 "실행 실패" 후보

**최종 반영량:**
- 기획 성공/약점: Opus 분석이 뼈대, Sonnet 빈도가 보강
- 보고서 인용: Opus 추천 10개 우선, Sonnet 대표 인용으로 언어/관점 보충 → 최종 15~20개
- 삼각검증: Opus 기획 판정 + Sonnet 빈도 데이터로 신뢰도 표기

#### Fallback 모드 (≤ 500건)

서브에이전트 없이 메인 Opus가 직접 분석:
1. `valid_reviews` TOP 100건 추출 (Opus용 쿼리와 동일)
2. 메인이 직접 기획 성공/약점/인용 후보 판단
3. 언어별/감정별 패턴은 정량 SQL 통계로 대체
4. 보고서 Footer에 "Fallback 모드" 명시

#### 정량 통계 (기존 유지 — 변경 없음)

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

### 5-B. OpenCritic 전문가 평가 (Steam 유저 리뷰와 교차 검증)

```sql
-- 집계 점수
SELECT opencritic_score, opencritic_pct_recommend, opencritic_tier,
       opencritic_review_count
FROM games WHERE appid = ?;

-- 개별 매체 리뷰 (상위 5개)
SELECT outlet, score, snippet, published_at
FROM external_reviews WHERE appid = ? AND source = 'opencritic'
ORDER BY score DESC LIMIT 5;
```

분석 포인트:
- **OpenCritic score vs Steam 긍정률 괴리**: 전문가와 유저 시각 차이. 전문가 높고 유저 낮으면 "완성도 높지만 취향 갈림", 반대면 "대중적이지만 평론 기준 미달"
- **percentRecommended**: 전문가 추천률 — score보다 직관적인 지표
- **tier**: Mighty(90+), Strong(75+), Fair(60+), Weak(<60)
- 개별 리뷰 snippet에서 반복되는 키워드 → 전문가가 인식한 핵심 특성
- opencritic_score가 NULL이면 "OpenCritic 데이터 없음" 명시

### 5-C. CheapShark 가격 이력 (비즈니스 전략)

```sql
SELECT cheapshark_deal_rating, cheapshark_lowest_price, cheapshark_lowest_price_date
FROM games WHERE appid = ?;
```

분석 포인트:
- **deal_rating 높고 lowest_price 낮으면** → 공격적 할인 전략 (유저 유입 우선)
- **lowest_price가 출시가와 비슷하면** → 가격 자신감 (프리미엄 포지셔닝)
- **할인 시점**: lowest_price_date가 출시 후 얼마 지나서인가? 빠르면 초기 판매 부진
- cheapshark_deal_rating이 NULL이면 "CheapShark 데이터 없음" 명시

### 5-D. 기존 분석 포인트

분석 포인트:
- 가격대 (price ÷ 100 = 달러)
- 소유자 규모
- 평균 플레이타임 (avg_playtime ÷ 60 = 시간) → DLC/IAP 전환 기회
- 수익 모델 추론 (DLC 확장? 모딩 커뮤니티? 시즌 콘텐츠?)

---

## 출력 형식: HTML 보고서

분석 결과는 **단일 HTML 파일**로 `docs/insights/reports/{game-slug}.html`에 생성한다.

### 템플릿

**TEMPLATE.html** (같은 디렉토리)을 반드시 읽고 참고한다.
- CSS 변수, 클래스명, 컴포넌트 구조를 그대로 사용
- `{{PLACEHOLDER}}`를 실제 데이터로 치환
- `/frontend-design` 스킬을 함께 호출하여 디자인 품질 확보

### 인덱스 메타데이터 (필수)

모든 보고서는 `<head>` 내부에 `<meta name="report:*">` 태그를 포함해야 한다.
TEMPLATE.html에 정의된 meta 태그 블록을 반드시 채운다.

- `{{TAGS}}`: `game_tags` 상위 5개 태그를 쉼표로 구분 (예: "Action Roguelike,Rogue-lite,Hack and Slash")
- `{{GENRES}}`: `game_genres` 전체를 쉼표로 구분 (예: "Action,Indie,RPG")
- `{{NAME_KO}}`: `games.name_ko` 값. NULL이면 빈 문자열.

```sql
-- 태그 상위 5개
SELECT tag_name FROM game_tags WHERE appid = ? ORDER BY vote_count DESC LIMIT 5;
-- 장르 전체
SELECT genre_name FROM game_genres WHERE appid = ?;
-- 한국어 이름
SELECT name_ko FROM games WHERE appid = ?;
```


### 파일 경로 규칙
- 게임 이름을 kebab-case로 변환: "TCG Card Shop Simulator" → `tcg-card-shop-simulator.html`
- 저장 위치: `<project-root>/docs/insights/reports/`

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
├── Wikidata 기획 온톨로지 — 메카닉/캐릭터/배경/수상 (NEW)
├── RAWG 리텐션 프록시 — 드롭률/클리어률/평가 분포
├── HowLongToBeat 게임 길이 — 기획 밀도 분석 (NEW)
├── PCGamingWiki 기술 스펙 (NEW)
└── 마케팅이 말하지 않은 시스템들 (IGDB/RAWG 기반)

Step 03: 유저 경험
├── 태그 수평 바 차트 (투표수 비례, 태그명 + 바 + 수치)
├── 기획 축 분류 테이블 (태그를 축별 그룹핑 + 합산 투표 + 비중)
│   예: 경영/경제 722(지배적), 수집/카드 415(강력), 분위기/접근성 201(보조)
├── 플레이타임별 긍정률 바 차트
├── 언어별 리뷰 분포 바 차트
├── 기획 성공 포인트 (Opus 심층 분석 + Sonnet 패턴 빈도 통합)
├── 기획 약점 (Opus 심층 분석 + Sonnet 패턴 빈도 통합)
└── 문화권별 차이 (언어 파티션 간 상반된 반응, 있는 경우)

Step 04: 삼각 검증 (Triangulation Table)
└── 기획 요소별 마케팅/구현/유저 반응 교차 판정표
    판정 뱃지: 기획 성공(초록), 실행 미흡(빨강), 숨은 강점(보라), 커뮤니티 창발(골드)

Step 05: 비즈니스 구조
├── 추정 매출, 가성비, 수익 모델
├── Twitch 스트리밍 데이터 (채널 수, 시청자, 언어 분포)
├── OpenCritic 전문가 평가 — 유저 vs 전문가 교차 검증 (NEW)
├── CheapShark 가격 이력 — 할인 전략 분석 (NEW)
└── 수익 확장 가능성

결론
└── 구조적 결론 — 태그 데이터를 근거로 인용하며 성공/실패의 구조적 원인을 설명
    (단순 감상이 아닌, 데이터 기반 논증)

Footer
├── 생성일, 데이터 소스, 분석 리뷰 수
└── 에이전트 분석 상세 (collapsible — 에이전트별 모델·구역·리뷰수·토큰·시간·핵심발견)
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

#### 리뷰 기반 코어 루프 교차 검증 (병렬 분석 시)

서브에이전트가 반환한 "코어 루프 증거"를 사용하여 다이어그램을 보강한다:
- **일치**: 2단계 메타데이터 루프가 리뷰에서도 확인됨 → "유저 증언으로 확인됨" 표기 + 인용 첨부
- **보정**: 메타데이터가 놓친 루프를 리뷰에서 발견 → 다이어그램에 추가
- **과장**: 마케팅이 주장하지만 유저가 체감하지 못하는 루프 → 삼각검증 "실행 실패" 후보

### 리뷰 인용 형식

- 긍정 리뷰: 골드 좌측 보더
- 부정 리뷰: 빨간 좌측 보더
- 메타 정보: `언어 · 플레이타임 · helpful 수`
- 비영어 리뷰: 번역을 별도 블록으로 표시
- 인용 후 바로 분석 서술을 연결 (인용과 분석이 분리되지 않도록)

---

## 메타데이터 요구사항 (필수)

모든 보고서는 **생성일자**와 **데이터 소스**를 반드시 기록한다.

### Footer 메타데이터
- `{{DATE}}`: 보고서 생성일 (YYYY-MM-DD 형식)
- `{{DATA_SOURCES}}`: 실제 쿼리하여 데이터가 존재한 소스만 나열 (NULL이 아닌 것)
- `{{REVIEW_COUNT}}`: 분석에 사용된 리뷰 수 (서브에이전트가 읽은 총 건수. 중복 포함)
- `{{AGENT_METRICS}}`: 서브에이전트 분석 상세 (아래 형식)

### 데이터 소스 판정 기준

보고서 생성 시 아래 쿼리로 실제 사용된 소스를 확인한다:

```sql
SELECT
  1 as steamspy,  -- 항상 사용 (games 테이블)
  CASE WHEN steam_positive IS NOT NULL THEN 1 ELSE 0 END as steam_reviews,
  CASE WHEN igdb_id IS NOT NULL THEN 1 ELSE 0 END as igdb,
  CASE WHEN rawg_id IS NOT NULL THEN 1 ELSE 0 END as rawg,
  CASE WHEN hltb_main_story IS NOT NULL THEN 1 ELSE 0 END as hltb,
  CASE WHEN cheapshark_deal_rating IS NOT NULL THEN 1 ELSE 0 END as cheapshark,
  CASE WHEN pcgw_engine IS NOT NULL THEN 1 ELSE 0 END as pcgamingwiki,
  CASE WHEN opencritic_score IS NOT NULL THEN 1 ELSE 0 END as opencritic,
  CASE WHEN twitch_stream_count IS NOT NULL THEN 1 ELSE 0 END as twitch,
  CASE WHEN wikidata_id IS NOT NULL AND wikidata_id != 'not_found' THEN 1 ELSE 0 END as wikidata
FROM games WHERE appid = ?;
```

존재하는 소스만 `+`로 연결: `SteamSpy + Steam Reviews API + IGDB + RAWG`

리뷰 수:
```sql
SELECT count(*) FROM reviews WHERE appid = ?;
```

### 날짜 알 수 없는 기존 보고서
- 생성일을 확인할 수 없는 보고서는 **날짜를 삭제**하고 "날짜 미상"으로 표기
- 데이터 소스를 확인할 수 없는 경우도 동일하게 삭제

### 에이전트 메트릭 추적

서브에이전트 병렬 분석 사용 시, 각 에이전트의 메트릭을 추적하여 보고서에 기록한다.

**추적 항목 (에이전트별):**
| 메트릭 | 측정 방법 |
|--------|----------|
| 입력 토큰 (추정) | 프롬프트 + 리뷰 텍스트 총 문자수 ÷ 3 |
| 출력 토큰 (추정) | 반환된 마크다운 문자수 ÷ 3 |
| 소모 시간 | 디스패치 전후 시간 차이 (초) |
| 리뷰 건수 | 실제 전달된 리뷰 수 |
| 모델 | opus / sonnet |

**메인 에이전트 전체 실행 메트릭도 기록:**
- 총 소요 시간 (시작~HTML 저장)
- 서브에이전트 합산 토큰
- 메인 에이전트 추정 토큰 (서브 제외)

**Fallback 모드에서는:** 서브에이전트 없으므로 메인 에이전트 메트릭만 기록. Footer에 "Fallback 모드: 유효 리뷰 N건 (500건 이하)" 명시.

---

## Error Logging (필수)

**에러 발생 시 반드시 아래 순서를 따른다. 순서를 건너뛰지 않는다.**

### 순서: 기록 → 수정 → 해결

1. **즉시 기록** — 에러가 발생하면 수정을 시도하기 전에 `log_skill_error()`를 호출한다
2. **수정 시도** — 기록 후 원인을 분석하고 수정한다
3. **해결 처리** — 수정이 성공하면 `resolve_skill_error()`로 해결 마킹한다

> **금지**: 에러 발생 → 바로 수정 → 기록 생략. 이렇게 하면 반복 패턴을 추적할 수 없다.

### Step 1: 기록

```python
import sys
sys.path.insert(0, "<project-root>/steam-crawler/src")
from steam_crawler.skill_error_logger import log_skill_error

error_id = log_skill_error(
    db_path="<project-root>/data/steam.db",
    skill_name="steam-insight",
    error_type="<type>",
    error_message="<full error message>",
    traceback="<traceback if available>",
    command="<code that caused error>",
    context={"appid": 286160, "step": "2B-igdb-keywords"},
    fix_applied=None  # 아직 수정 전이므로 None
)
```

### Step 2: 수정 후 해결 처리

```python
from steam_crawler.skill_error_logger import resolve_skill_error

resolve_skill_error(
    db_path="<project-root>/data/steam.db",
    error_id=error_id,
    resolution="code_fixed",  # code_fixed | workaround | skip
    fix_applied="<수정 내용>"
)
```

### error_type 분류
- `encoding` — 인코딩 에러 (cp949, utf-8 등)
- `sql` — SQL 에러 (missing column, syntax 등)
- `import` — 모듈 import 실패
- `timeout` — 실행 시간 초과
- `parse` — 데이터 파싱 실패
- `api` — 외부 API 실패 (IGDB, RAWG, Wikidata 등)
- `unknown` — 기타

## 주의사항

- 이 스킬은 **읽기 전용** — DB를 수정하지 않는다
- 데이터가 없으면 "수집된 데이터가 없습니다. `steam-crawl` 스킬로 먼저 수집하세요"라고 안내
- igdb/rawg 데이터가 NULL인 경우 해당 소스 없이 분석하되, 2단계가 약해진다고 명시
- 리뷰가 적은 경우(<50개) 통계적 신뢰도가 낮다고 명시
- 플레이타임은 분 단위 저장 → 시간 변환 (÷60)
- 가격은 센트 단위 저장 → 달러 변환 (÷100)
- 서브에이전트 병렬 분석 시 `valid_reviews` 500건 이하면 Fallback 모드 (메인 단독 TOP 100)
- 서브에이전트 결과는 텍스트로 직접 반환됨 — 파일/DB 중간 저장 없음
- 에이전트 메트릭의 토큰 수는 추정값 (문자수 ÷ 3)
---

## 보고서 생성 후 작업

보고서 HTML을 `docs/insights/reports/`에 생성하거나 갱신한 후, 반드시 다음을 실행한다:

```bash
python scripts/build_index.py
```

이 스크립트는 `docs/insights/reports.json`과 `synonyms.json`을 갱신하여 보고서 라이브러리 인덱스를 최신 상태로 유지한다.
