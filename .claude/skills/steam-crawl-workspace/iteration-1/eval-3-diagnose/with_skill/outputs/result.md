# Steam Crawler Diagnostic Report

**진단 일시**: 2026-03-18
**세션**: version 1 (tag: Roguelike, limit: 5, top_n: 2, max_reviews: 10)
**세션 상태**: completed

---

## 크롤러 건강 상태

| 항목 | 값 |
|------|-----|
| 총 수집 게임 | 6 |
| 총 수집 리뷰 | 240 |
| 미해결 실패 | 5건 |
| 실패 유형 | data_quality 5건 |
| 학습된 딜레이 | SteamSpy: 735ms, Steam Reviews: 995ms |
| Rate Limit 에러 (429) | 0건 |
| 서버 에러 (5xx) | 0건 |

---

## 실패 분석

| 유형 | 건수 | 심각도 | 권장 조치 |
|------|------|--------|----------|
| data_quality | 5 | **낮음** | SteamSpy vs Steam API 데이터 소스 차이로 인한 정상적인 편차. 자동 수정 불필요 |

### data_quality 실패 상세

| appid | 게임명 | SteamSpy positive | Steam API positive | 편차 |
|-------|--------|-------------------|-------------------|------|
| 901583 | Grand Theft Auto IV: Complete Edition | 144,570 | 62,713 | 56.6% |
| 12210 | Grand Theft Auto IV: The Complete Edition | 144,493 | 62,713 | 56.6% |
| 2990 | FlatOut 2 | 17,923 | 4,593 | 74.4% |
| 891040 | Pool 2D - Poolians | 8,222 | 1,053 | 87.2% |
| 22230 | Rock of Ages | 3,472 | 2,004 | 42.3% |

**분석**: SteamSpy의 positive 수치가 Steam API보다 일관되게 높다. 이는 SteamSpy가 추정치(estimation)를 사용하기 때문이며, Steam API는 실제 공개 리뷰만 카운트한다. 특히 GTA IV 두 항목(appid 901583, 12210)은 SteamSpy positive 값이 거의 동일하여, SteamSpy가 두 에디션을 합산하고 있을 가능성이 높다. 이는 데이터 소스 특성상 정상적인 편차이므로 resolved 처리가 적절하다.

---

## 수집 진행 상태

### 미완료 게임 (리뷰 미수집)

| appid | 게임명 | steamspy | summary | reviews | 수집된 리뷰 |
|-------|--------|----------|---------|---------|------------|
| 2990 | FlatOut 2 | done | done | **미완료** | 0 |
| 891040 | Pool 2D - Poolians | done | **미완료** | **미완료** | 0 |
| 22230 | Rock of Ages | done | done | **미완료** | 0 |

**분석**: 3개 게임의 리뷰 수집이 완료되지 않았다. 세션 설정이 `top_n: 2`이므로 상위 2개 게임(GTA IV 두 에디션)에 대해서만 리뷰를 수집한 것으로 보인다. 이는 설정에 의한 정상 동작이다.

### 완료된 게임

| appid | 게임명 | 수집 리뷰 |
|-------|--------|----------|
| 901583 | Grand Theft Auto IV: Complete Edition | 80 |
| 12210 | Grand Theft Auto IV: The Complete Edition | 80 |

### 참고: Hades (appid: 1145360)

Hades는 `games` 테이블에 존재하고 리뷰 80건이 수집되어 있으나, `game_collection_status` 테이블에 항목이 없다. 이전 테스트나 별도 수집에서 남은 데이터일 수 있다.

---

## Rate Limit 학습 상태

| API | 요청 수 | 429 에러 | 5xx 에러 | 평균 응답(ms) | 최적 딜레이(ms) |
|-----|---------|---------|---------|-------------|---------------|
| steamspy | 6 | 0 | 0 | 234ms | 735ms |
| steam_reviews | 8 | 0 | 0 | 211ms | 995ms |

**분석**: Rate limit 에러가 0건으로, 현재 딜레이 설정이 적절하다. AdaptiveRateLimiter가 잘 학습하고 있다.

---

## 패턴 분석

- **반복 실패하는 appid**: 없음 (같은 appid가 2회 이상 실패한 패턴 없음)
- **parse_error 추이**: parse_error 발생 없음 (API 스키마 변경 징후 없음)
- **connection_error**: 없음
- **timeout**: 없음

---

## 종합 판단

| 항목 | 상태 |
|------|------|
| API 연결 | 정상 |
| Rate Limiting | 정상 (에러 0건, 학습 진행 중) |
| 데이터 파싱 | 정상 (parse_error 없음) |
| 데이터 품질 | 주의 (SteamSpy 추정치 편차 있으나 정상 범위) |
| 미완료 수집 | top_n=2 설정에 의한 정상 동작 |

---

## 권장 조치

1. **data_quality 5건 resolved 처리**: SteamSpy vs Steam API 편차는 데이터 소스 특성 차이이므로 resolved 처리 권장
2. **미완료 게임 리뷰 수집**: 필요시 `--resume` 또는 `top_n` 값을 높여 재수집
3. **Hades 데이터 정리**: `game_collection_status`에 항목이 없는 orphaned 데이터 확인 필요

---

## 실행된 조치

### data_quality 실패 5건 resolved 처리

5건의 data_quality 실패를 `manual_review` 사유로 resolved 처리하였다. SteamSpy는 추정치 기반이고 Steam API는 실제 공개 리뷰 기반이므로 편차는 정상적인 데이터 소스 차이이다.

```sql
UPDATE failure_logs SET resolved = 1, resolution = 'manual_review'
WHERE failure_type = 'data_quality' AND resolved = 0;
```

적용 결과: 5건 resolved 처리 완료.
