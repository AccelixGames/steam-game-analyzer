# Review Coverage Improvement Design

**Date:** 2026-03-19
**Status:** Approved
**Scope:** valid_reviews 한국어 임계값 + 부정 리뷰 2-pass 보강 + 편향 해소

---

## 배경

1. **한국어 리뷰 과소대표**: `valid_reviews` VIEW의 100자 최소 기준이 모든 언어에 일률 적용됨. 한국어는 음절 문자로 같은 의미를 적은 글자수로 표현하므로, 100자 필터에 과도하게 걸림.
2. **부정 리뷰 수집 부족**: `review_type=all` + `filter=recent`로 수집하면 자연 비율대로 반환되어, 긍정률 높은 게임에서 부정 리뷰 표본이 패턴 분석에 불충분.

---

## 변경 1: `valid_reviews` 한국어 임계값

### 현재
```sql
AND (
  length(review_text) >= 100
  OR playtime_at_review >= 3000
)
```

### 변경 후
```sql
AND (
  CASE
    WHEN language = 'koreana' THEN length(review_text) >= 50
    ELSE length(review_text) >= 100
  END
  OR playtime_at_review >= 3000
)
```

### 영향
- **파일**: `steam-crawler/src/steam_crawler/db/schema.py`, `.claude/skills/steam-insight/SKILL.md`
- VIEW 재생성 필요 (`DROP VIEW IF EXISTS` + `CREATE VIEW`) — `_migrate()`가 이미 이 패턴 사용
- 기존 수집 데이터에 즉시 반영 (VIEW이므로 재수집 불필요)
- 정량 통계 영향 없음 (`reviews` 테이블 사용)
- SKILL.md의 "100자 이상" 설명을 "100자 이상 (한국어: 50자)" 로 업데이트

---

## 변경 2: 부정 리뷰 2-pass 보강

### 공식 비율 컬럼

`games` 테이블에 두 쌍의 긍/부정 컬럼이 존재:
- `positive` / `negative` — SteamSpy 출처
- `steam_positive` / `steam_negative` — Steam Reviews API `query_summary` 출처

**`steam_positive` / `steam_negative` 사용.** Steam Reviews API에서 직접 오므로 리뷰 수집 맥락에 가장 정확.

### 로직
Step 3 수집 완료 후, `reviews_done` 설정 전에 자동 실행:

```
1. 수집 완료 (review_type=all)
2. 가드 체크:
   - steam_positive가 NULL이거나 0이면 → 스킵
   - steam_negative < 10이면 → 스킵 (수집할 부정 리뷰가 거의 없음)
   - review_types_done에 "negative_supplement" 포함 → 스킵 (재실행 방지)
3. DB 조회:
   - collected_positive = COUNT(*) FROM reviews WHERE appid=? AND voted_up=1
   - collected_negative = COUNT(*) FROM reviews WHERE appid=? AND voted_up=0
   - official_ratio = games.steam_negative / games.steam_positive
4. target_negative = min(
     max(200, collected_positive * official_ratio),
     steam_negative  -- 공식 부정 수 초과 방지
   )
5. collected_negative < target_negative → 부정 전용 패스 실행
   - review_type=negative, filter=recent, cursor 기반 페이지네이션
   - target_negative 도달까지 수집 (INSERT OR IGNORE로 중복 안전)
6. collected_negative >= target_negative → 스킵
7. review_types_done JSON 배열에 "negative_supplement" 추가 (기존 값에 append)
```

### 예시

| 공식 비율 | 수집 긍정 | 수집 부정 | 목표 | 보강 |
|-----------|----------|----------|------|------|
| 90:10 | 900 | 50 | min(max(200, 100), 10K) = 200 | +150 |
| 70:30 | 700 | 100 | min(max(200, 300), 30K) = 300 | +200 |
| 95:5 | 950 | 30 | min(max(200, 50), 5K) = 200 | +170 |
| 60:40 | 600 | 400 | min(max(200, 400), 40K) = 400 | 스킵 |
| 99:1 (steam_negative=8) | 990 | 5 | 스킵 (steam_negative < 10) | — |

### 영향
- **파일**: `steam-crawler/src/steam_crawler/steps/step3_crawl.py` (보강 로직 추가)
- `steam_reviews.py` 변경 불필요 (이미 `review_type` 파라미터 지원)
- `repository.py` 변경 불필요 (`INSERT OR IGNORE` 그대로)
- `game_collection_status.review_types_done`에 `"negative_supplement"` **append** (기존 JSON 배열에 추가)
- 실패 시 `FailureTracker`를 통해 `failure_logs` 테이블에 기록 (기존 패턴 준수)
- 수집 시간: 게임당 최대 +2~3페이지 (긍정률 높은 게임만)

### 진행률 표시
Rich 콘솔에 `[부정 보강] 45/200` 형태로 표시

---

## 변경 3: 편향 해소

### 원칙
- **전체 긍정률/부정률**은 항상 `games.steam_positive` / `games.steam_negative` 사용
- **버킷별 분석** (플레이타임별 긍정률, 언어별 분포 등)은 `reviews` 테이블 사용 허용 — `games` 테이블에는 버킷 데이터가 없으므로
- **정성 분석**은 `valid_reviews` 사용 (보강분 포함, 편향 무관)

### 조치
- `reviews` COUNT로 **전체** 비율을 산출하는 기존 코드가 있으면 `games` 테이블 참조로 교체
- 영향 파일:
  - `.claude/skills/steam-insight/SKILL.md` — "정량 비율은 games.steam_positive/steam_negative 사용" 규칙 명시
  - `.claude/skills/steam-query/SKILL.md` — 동일 규칙 명시
- VIEW SQL 또는 SKILL.md에 주의 코멘트 추가: "부정 보강 후 reviews 테이블 COUNT로 전체 긍/부정 비율을 계산하지 말 것"

---

## 테스트 계획

### valid_reviews VIEW 테스트
- 한국어 50자 리뷰 포함 확인
- 한국어 49자 리뷰 제외 확인
- 영어 100자 리뷰 포함 확인
- 영어 99자 리뷰 제외 확인 (playtime < 3000)
- playtime >= 3000이면 글자수 무관 포함 확인

### 2-pass 부정 보강 테스트
- 긍정률 95% 게임: 보강 실행, 200건 목표
- 긍정률 70% 게임: 보강 실행, ratio 기반 목표
- 긍정률 50% 게임: 이미 충분, 스킵 확인
- steam_negative < 10: 스킵 확인
- steam_positive = 0 또는 NULL: 스킵 확인
- 중복 리뷰 INSERT OR IGNORE 확인
- `game_collection_status.review_types_done` JSON 배열 append 확인
- 재실행 시 "negative_supplement" 존재하면 스킵 확인
- 실패 시 `failure_logs` 기록 확인

### 편향 해소 테스트
- 보강 후 `games.steam_positive/steam_negative`와 `reviews` COUNT 비교 → 불일치 확인 (의도된 동작)
- 인사이트 스킬에서 전체 비율 산출 시 `games` 테이블 사용 확인
- 버킷별 분석은 `reviews` 테이블 사용 허용 확인

### 기존 테스트
- `pytest` 전체 통과 확인
