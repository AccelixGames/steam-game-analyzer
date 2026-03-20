# 병렬 리뷰 분석 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `/steam-insight` 스킬의 리뷰 분석을 30건에서 ~1,300건으로 확대하는 서브에이전트 병렬 분석 구조 구현

**Architecture:** SKILL.md의 3-B 섹션을 서브에이전트 병렬 분석 구조로 교체. 메인 Opus가 1~2단계 분석 후 게임 컨텍스트를 요약하고, 7개 서브에이전트(Opus 1 + Sonnet 6)를 병렬 디스패치하여 리뷰를 분석한 뒤 결과를 통합. TEMPLATE.html Footer에 에이전트 메트릭 블록 추가.

**Tech Stack:** Claude Code Agent tool (model 파라미터), SQLite, Markdown skill document

**Spec:** `docs/superpowers/specs/2026-03-19-parallel-review-analysis-design.md`

---

## File Structure

| 파일 | 역할 | 변경 유형 |
|------|------|----------|
| `.claude/skills/steam-insight/SKILL.md` | 스킬 문서 (분석 지침) | 수정: 3-B 섹션 교체, 메타데이터 확장 |
| `.claude/skills/steam-insight/TEMPLATE.html` | HTML 보고서 템플릿 | 수정: Footer에 에이전트 메트릭 블록 추가 |

코드 변경 없음 — 순수 스킬 문서/템플릿 변경.

---

### Task 1: SKILL.md — 3-B 섹션을 병렬 분석 구조로 교체

**Files:**
- Modify: `.claude/skills/steam-insight/SKILL.md:199-250` (3-B 리뷰 분석 섹션 전체)

**변경 내용:** 기존 3개 SQL 쿼리(장문 긍정 LIMIT 10, 도움된 긍정 LIMIT 10, 부정 LIMIT 10)를 서브에이전트 병렬 분석 구조로 교체.

- [ ] **Step 1: 기존 3-B 섹션 확인**

현재 내용 (`SKILL.md:199-250`):
```markdown
### 3-B. 리뷰 분석 (실제 경험의 증거)

**긍정 리뷰 — 기획이 성공한 지점**
-- 장문 긍정 리뷰 LIMIT 10
-- 가장 도움이 된 긍정 리뷰 LIMIT 10

**부정 리뷰 — 기획의 약점**
-- 부정 리뷰 LIMIT 10

**플레이타임별 긍정률** (정량 — 유지)
**언어별 분포** (정량 — 유지)

리뷰 분석 시 주의: ...
```

- [ ] **Step 2: 3-B 섹션을 병렬 분석 구조로 교체**

`SKILL.md:199`부터 `## 4단계` 직전까지를 다음으로 교체:

```markdown
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

7개 서브에이전트 결과가 반환되면 다음 규칙으로 통합:

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
```

- [ ] **Step 3: 교체 실행**

`SKILL.md`의 `### 3-B. 리뷰 분석` 부터 `## 4단계` 직전까지를 Step 2의 내용으로 교체.

보존해야 하는 것:
- `### 3-A. 태그 분석` (3-B 직전) — 변경 없음
- `## 4단계: 삼각 검증` (3-B 직후) — 변경 없음
- 정량 통계 쿼리 (플레이타임별 긍정률, 언어별 분포) — 3-B 내에서 그대로 유지

- [ ] **Step 4: 검증**

SKILL.md를 읽어서:
1. `### 3-B` 섹션이 서브에이전트 구조로 교체되었는지
2. `## 4단계` 이전에 정량 통계 쿼리가 유지되는지
3. `valid_reviews` View 사용이 일관되는지 (정성=valid_reviews, 정량=reviews)
확인한다.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/steam-insight/SKILL.md
git commit -m "feat: replace 3-B review queries with parallel sub-agent analysis"
```

---

### Task 2: SKILL.md — 에이전트 메트릭 추적 지침 추가

**Files:**
- Modify: `.claude/skills/steam-insight/SKILL.md:453-490` (메타데이터 요구사항 섹션)

**변경 내용:** Footer 메타데이터 섹션에 에이전트 메트릭 추적 지침과 `{{AGENT_METRICS}}` 플레이스홀더를 추가.

- [ ] **Step 1: 메타데이터 섹션에 에이전트 메트릭 추가**

`### Footer 메타데이터` 섹션 (기존 `{{DATE}}`, `{{DATA_SOURCES}}`, `{{REVIEW_COUNT}}`)에 추가:

```markdown
- `{{AGENT_METRICS}}`: 서브에이전트 분석 상세 (아래 형식)

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
```

- [ ] **Step 2: `{{REVIEW_COUNT}}` 정의 업데이트**

기존:
```markdown
- `{{REVIEW_COUNT}}`: 분석에 사용된 리뷰 수
```

변경:
```markdown
- `{{REVIEW_COUNT}}`: 분석에 사용된 리뷰 수 (서브에이전트가 읽은 총 건수. 중복 포함)
```

- [ ] **Step 3: 검증**

SKILL.md의 메타데이터 섹션을 읽어 에이전트 메트릭 지침이 추가되었는지 확인.

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/steam-insight/SKILL.md
git commit -m "feat: add agent metrics tracking to steam-insight metadata"
```

---

### Task 3: SKILL.md — 코어 루프 다이어그램 보강 지침 추가

**Files:**
- Modify: `.claude/skills/steam-insight/SKILL.md:435-441` (코어 루프 다이어그램 요구사항 섹션)

**변경 내용:** 코어 루프 다이어그램 요구사항에 "리뷰 기반 교차 검증" 단계를 추가.

- [ ] **Step 1: 코어 루프 섹션에 교차 검증 추가**

기존 `### 코어 루프 다이어그램 요구사항` 끝에 추가:

```markdown

#### 리뷰 기반 코어 루프 교차 검증 (병렬 분석 시)

서브에이전트가 반환한 "코어 루프 증거"를 사용하여 다이어그램을 보강한다:
- **일치**: 2단계 메타데이터 루프가 리뷰에서도 확인됨 → "유저 증언으로 확인됨" 표기 + 인용 첨부
- **보정**: 메타데이터가 놓친 루프를 리뷰에서 발견 → 다이어그램에 추가
- **과장**: 마케팅이 주장하지만 유저가 체감하지 못하는 루프 → 삼각검증 "실행 실패" 후보
```

- [ ] **Step 2: 검증**

SKILL.md의 코어 루프 섹션을 읽어 교차 검증 지침이 추가되었는지 확인.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/steam-insight/SKILL.md
git commit -m "feat: add review-based core loop cross-validation"
```

---

### Task 4: SKILL.md — HTML 보고서 구조 및 주의사항 업데이트

**Files:**
- Modify: `.claude/skills/steam-insight/SKILL.md:367-420` (HTML 보고서 구조)
- Modify: `.claude/skills/steam-insight/SKILL.md:494-501` (주의사항)

**변경 내용:** 보고서 구조 트리에서 Step 03과 Footer를 업데이트하고, 주의사항에 서브에이전트 관련 항목을 추가.

- [ ] **Step 1: HTML 보고서 구조의 Step 03 업데이트**

기존:
```
Step 03: 유저 경험
├── ...
├── 기획 성공 포인트 (리뷰 인용 + 분석 서술 통합)
└── 기획 약점 (리뷰 인용 + 분석 서술 통합)
```

변경:
```
Step 03: 유저 경험
├── ...
├── 기획 성공 포인트 (Opus 심층 분석 + Sonnet 패턴 빈도 통합)
├── 기획 약점 (Opus 심층 분석 + Sonnet 패턴 빈도 통합)
└── 문화권별 차이 (언어 파티션 간 상반된 반응, 있는 경우)
```

- [ ] **Step 2: Footer 구조 업데이트**

기존:
```
Footer
└── 생성일, 데이터 소스, 분석 리뷰 수
```

변경:
```
Footer
├── 생성일, 데이터 소스, 분석 리뷰 수
└── 에이전트 분석 상세 (collapsible — 에이전트별 모델·구역·리뷰수·토큰·시간·핵심발견)
```

- [ ] **Step 3: 주의사항 업데이트**

기존 주의사항 끝에 추가:
```markdown
- 서브에이전트 병렬 분석 시 `valid_reviews` 500건 이하면 Fallback 모드 (메인 단독 TOP 100)
- 서브에이전트 결과는 텍스트로 직접 반환됨 — 파일/DB 중간 저장 없음
- 에이전트 메트릭의 토큰 수는 추정값 (문자수 ÷ 3)
```

- [ ] **Step 4: 검증**

SKILL.md에서 보고서 구조와 주의사항 섹션을 읽어 변경이 반영되었는지 확인.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/steam-insight/SKILL.md
git commit -m "feat: update report structure and notes for parallel analysis"
```

---

### Task 5: TEMPLATE.html — Footer에 에이전트 메트릭 블록 추가

**Files:**
- Modify: `.claude/skills/steam-insight/TEMPLATE.html:894-896` (footer 섹션)

**변경 내용:** Footer에 `{{AGENT_METRICS}}` 플레이스홀더를 가진 collapsible `<details>` 블록 추가.

- [ ] **Step 1: Footer 현재 상태 확인**

현재 (`TEMPLATE.html:894-896`):
```html
<footer class="footer">
  Steam Game Insight Report · Generated {{DATE}} · Data: {{DATA_SOURCES}} · {{REVIEW_COUNT}} reviews analyzed
</footer>
```

- [ ] **Step 2: Footer 확장**

```html
<footer class="footer">
  <p>Steam Game Insight Report · Generated {{DATE}} · Data: {{DATA_SOURCES}} · {{REVIEW_COUNT}} reviews analyzed</p>
  {{AGENT_METRICS}}
  <!--
    에이전트 분석 상세. 서브에이전트 병렬 분석 사용 시 아래 형식으로 채운다.
    Fallback 모드면 이 블록 자체를 "Fallback 모드: 유효 리뷰 N건" 한 줄로 대체.

    예시:
    <details style="margin-top:.8rem;font-size:.78rem;color:var(--text-faint)">
      <summary>에이전트 분석 상세 (7개 에이전트, 총 ~142K 토큰, 89초)</summary>
      <table style="width:100%;margin-top:.5rem;font-size:.75rem;border-collapse:collapse">
        <tr style="border-bottom:1px solid var(--border)">
          <th>에이전트</th><th>모델</th><th>구역</th><th>리뷰수</th>
          <th>입력≈</th><th>출력≈</th><th>시간</th><th>핵심 발견</th>
        </tr>
        <tr>
          <td>Main-Deep</td><td>opus</td><td>TOP 100</td><td>100</td>
          <td>32K</td><td>4K</td><td>45s</td><td>기획성공 5, 약점 4, 인용후보 10</td>
        </tr>
        <tr>
          <td>EN-Positive</td><td>sonnet</td><td>english·긍정</td><td>200</td>
          <td>18K</td><td>3K</td><td>22s</td><td>패턴 4, 특이점 1</td>
        </tr>
      </table>
    </details>
  -->
</footer>
```

- [ ] **Step 3: 검증**

TEMPLATE.html의 footer 섹션을 읽어 `{{AGENT_METRICS}}` 플레이스홀더가 추가되었는지 확인.

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/steam-insight/TEMPLATE.html
git commit -m "feat: add agent metrics placeholder to report footer template"
```

---

### Task 6: 검증 — Palworld 보고서 비교

**Files:**
- 읽기: `docs/insights/palworld.html` (기존 보고서)
- 생성: `docs/insights/palworld-backup.html` (백업)
- 생성: `docs/insights/palworld.html` (신규 보고서)

**선행 조건:** Task 1~5 완료

- [ ] **Step 1: 기존 보고서 백업**

```bash
cp docs/insights/palworld.html docs/insights/palworld-backup.html
```

기존 보고서가 없으면 이 단계 건너뛴다.

- [ ] **Step 2: 신규 보고서 생성**

`/steam-insight` 스킬을 Palworld (appid 1623730)에 대해 실행한다.
서브에이전트 병렬 분석이 동작하는지 확인:
- 유효 리뷰 수 확인 (153,325건 → 500건 초과 → 병렬 모드)
- 상위 3개 언어 확인
- 7개 서브에이전트 디스패치 확인
- 결과 통합 후 HTML 생성

- [ ] **Step 3: 정성 비교**

기존 보고서와 신규 보고서를 비교:
- 기획 성공/약점 포인트의 깊이와 근거
- 리뷰 인용의 다양성과 품질
- 문화권별 차이 포착 여부
- 코어 루프 다이어그램이 리뷰 증거로 보강되었는지

- [ ] **Step 4: 정량 비교**

| 항목 | 이전 | 이후 |
|------|------|------|
| 분석 리뷰 수 | ~30건 | ~1,300건 |
| 에이전트 수 | 0 | 7 |
| 총 토큰 | ? | Footer 메트릭 확인 |
| 총 소요 시간 | ? | Footer 메트릭 확인 |

- [ ] **Step 5: 사용자 의견 수렴**

사용자에게 두 보고서를 비교하여 의견을 요청한다:
- 분석 품질이 향상되었는가?
- 비용 대비 가치가 있는가?
- 개선할 점이 있는가?

- [ ] **Step 6: 백업 정리 및 Commit**

```bash
rm docs/insights/palworld-backup.html  # 비교 완료 후 정리
git add docs/insights/palworld.html
git commit -m "feat: regenerate Palworld report with parallel review analysis"
```
