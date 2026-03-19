# 보고서 라이브러리 Index 설계

> **목적**: `docs/insights/`의 모든 기획 인사이트 보고서에 편하게 접근할 수 있는 index 페이지
> **사용 시나리오**: 팀 내부 대시보드 (GitHub Pages 배포)
> **대응 규모**: 1000+ 보고서

---

## 1. 데이터 파이프라인

### 1-A. TEMPLATE.html에 `<meta>` 태그 블록 추가

보고서 HTML `<head>`에 구조화된 메타데이터를 삽입한다. steam-insight 스킬이 보고서 생성 시 자동으로 채운다.

```html
<meta name="report:appid" content="{{APPID}}">
<meta name="report:game_name" content="{{GAME_NAME}}">
<meta name="report:name_ko" content="{{NAME_KO}}">
<meta name="report:positive_rate" content="{{POSITIVE_RATE}}">
<meta name="report:review_score" content="{{REVIEW_SCORE}}">
<meta name="report:owners" content="{{OWNERS}}">
<meta name="report:price" content="{{PRICE}}">
<meta name="report:avg_playtime" content="{{AVG_PLAYTIME}}">
<meta name="report:review_count" content="{{REVIEW_COUNT}}">
<meta name="report:tags" content="{{TAGS}}">
<meta name="report:genres" content="{{GENRES}}">
<meta name="report:date" content="{{DATE}}">
<meta name="report:modified" content="{{DATE}}">
<meta name="report:header_image" content="{{HEADER_IMAGE}}">
```

- `genres`: `game_genres` 테이블의 공식 장르 (Action, Indie, RPG 등)
- `tags`: `game_tags` 테이블의 상위 투표 태그
- `name_ko`: DB `games.name_ko` (Wikidata 파이프라인에서 자동 채워짐)
- `modified`: 마지막 수정일 (보고서 재생성 시 갱신)

### 1-B. steam-insight 스킬 변경

- SKILL.md의 "출력 형식" 섹션에 meta 태그 블록을 필수 요구사항으로 추가
- SKILL.md 끝에 "보고서 생성/갱신 후 `python scripts/build_index.py` 실행" 지시 추가
  - Hook이 아닌 스킬 지시문: steam-insight는 Write 도구로 HTML을 생성하므로, 스킬 내 지시가 정확한 타이밍

### 1-C. reports.json

```json
[
  {
    "slug": "hades",
    "name": "Hades",
    "name_ko": null,
    "appid": 1145360,
    "positive_rate": 98.3,
    "review_score": "Overwhelmingly Positive",
    "owners": "5~10M",
    "price": "$24.99",
    "avg_playtime": "34.5h",
    "review_count": 123456,
    "tags": ["Action Roguelike", "Rogue-lite", "Hack and Slash"],
    "genres": ["Action", "Indie", "RPG"],
    "date": "2026-03-15",
    "modified": "2026-03-15",
    "header_image": "https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/1145360/header.jpg"
  }
]
```

---

## 2. 빌드 스크립트 (`scripts/build_index.py`)

### 역할

`docs/insights/*.html` → `docs/insights/reports.json` + `docs/insights/synonyms.json`

### 증분 빌드

각 엔트리에 `_file_hash` (파일 내용의 MD5)를 내부 필드로 저장. Git clone이나 CI에서도 안정적으로 동작한다.

```
1. reports.json이 이미 존재하면 로드 → {slug: _file_hash} 맵 생성
2. docs/insights/*.html 스캔 (index.html 제외)
3. 각 파일:
   - slug가 기존 맵에 없음 → 새 보고서, 파싱
   - 파일 내용 hash ≠ 기존 _file_hash → 갱신됨, 재파싱
   - 그 외 → 스킵 (기존 데이터 유지)
4. 기존 맵에 있지만 파일 없음 → 삭제된 보고서, 엔트리 제거
5. 변경사항이 있을 때만 reports.json 재작성
6. --force 플래그로 전체 재빌드 가능
```

`_file_hash`는 index.html에서 사용하지 않는 내부 필드이며, reports.json에만 저장된다.

### 파싱 전략

1. **`<meta name="report:*">` 우선** (html.parser)
2. **부분 meta 태그 처리**: meta 태그가 하나라도 있으면 meta 우선 파싱, 빈 필드만 fallback으로 보충. meta 태그가 전혀 없으면 전체 fallback.
3. **Fallback 파싱** (기존 보고서 호환):
   - `<title>` → 게임명
   - `.hero-stat .num` + `.label` → 긍정률, 소유자, 가격, 플레이타임
   - `.hero-bg` background URL → header_image
   - Steam 링크에서 appid 추출 → DB에서 태그/장르/name_ko 보충
4. **중복 appid 처리**: 같은 appid의 파일이 여러 개이면 파일 mtime이 최신인 것만 사용.

### synonyms.json

두 계층으로 구성:

1. **하드코딩 기본 맵** (~50쌍): 태그/장르 한영 매핑. 빌드 스크립트에 내장.
2. **DB 자동 병합** (선택적): DB가 존재하면 `games.name_ko`에서 게임명 한영 매핑을 추출하여 기본 맵에 병합.

DB가 없으면 하드코딩 맵만으로 synonyms.json을 생성한다.

```json
{
  "생존": ["Survival"],
  "로그라이크": ["Roguelike", "Rogue-lite", "Action Roguelike"],
  "경영": ["Management", "Simulation"],
  "농사": ["Farming Sim", "Agriculture"],
  "액션": ["Action", "Hack and Slash"],
  "오픈월드": ["Open World"],
  "멀티": ["Multiplayer", "Co-op"],
  "하데스": ["Hades"],
  "팰월드": ["Palworld"]
}
```

### 의존성

- Python 표준 라이브러리 (`html.parser`, `json`, `glob`, `os`, `hashlib`)
- SQLite (`sqlite3`) — **선택적**, fallback 파싱 시 태그/장르/name_ko 보충 및 synonyms 자동 병합에 사용. DB가 없어도 동작하되 해당 필드가 비어있을 수 있음.

---

## 3. index.html 구조

### 레이아웃

```
┌─────────────────────────────────────────────────┐
│  Steam Game Insight Library                      │
│  N개 보고서 (필터 시: N / 전체M개)                │
├─────────────────────────────────────────────────┤
│  [🔍 검색바       ] [장르 ▾] [태그 ▾] [정렬 ▾]   │  ← sticky 고정
│  [선택된 필터 pill × ] [pill × ] ...              │
├─────────────────────────────────────────────────┤
│  ┌──────┐ ┌──────┐ ┌──────┐                     │
│  │카드1 │ │카드2 │ │카드3 │                     │  ← 3열 그리드
│  └──────┘ └──────┘ └──────┘                     │
│         ↓ infinite scroll ↓                     │
└─────────────────────────────────────────────────┘
```

### 검색

- **Fuse.js** (CDN, ~6KB gzip) 퍼지 검색
- 검색 키: `["name", "name_ko", "appid", "tags", "genres"]`
- debounce 200ms
- **입력 전처리**:
  1. `/app\/(\d+)/` 정규식 매칭 → appid 추출 → appid 필드 검색
  2. 순수 숫자 → appid 직접 매칭
  3. 그 외 → synonyms.json으로 동의어 확장 후 Fuse.js 퍼지 매칭
- 오타 허용: `하대스` → `하데스` (Fuse.js distance), `Hade` → `Hades` (부분 일치)

### 필터

- **장르 드롭다운**: 복수 선택 가능, 커스텀 체크박스 리스트
- **태그 드롭다운**: 보고서에 등장하는 상위 태그들, 복수 선택 가능
- **정렬**: 긍정률순, 리뷰수순, 최신순(modified), 이름순
- 선택된 필터 → pill로 바 아래에 표시, × 로 개별 제거 가능

### Infinite Scroll

- 초기 로드: 30개
- IntersectionObserver로 하단 감지 → 30개씩 추가
- 필터/검색 변경 시 리셋

### 카드

```
┌───────────────────────────┐
│  [header_image]           │  ← 이미지 클린 (오버레이 없음)
├───────────────────────────┤
│  Game Name     98.3%      │  ← 좌=이름, 우=긍정률 (크게)
│  [Roguelike][Action]      │  ← 좌=태그pill, 우=리뷰수
│                123,456건  │
│─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─│
│  5~10M · $24.99 · 34.5h  │  ← 소유자 · 가격 · 플레이타임
└───────────────────────────┘
```

- 3열 반응형: `grid-template-columns: repeat(auto-fill, minmax(280px, 1fr))`
- 장르 pill: gold 계열, 태그 pill: blue/purple 계열
- 긍정률 색상: ≥90% green, ≥70% gold, <70% red
- hover: border `--accent-gold` 트랜지션
- 클릭: `<a href="./{slug}.html" target="_blank">` **별개 탭**으로 열림
- 이미지: `loading="lazy"` 네이티브 레이지로드
- 이미지 로드 실패: `onerror` 핸들러로 `--bg-card` 배경 + 게임명 텍스트 placeholder 표시

### 빈 상태

- 검색/필터 결과 0개: "일치하는 보고서가 없습니다" + 필터 초기화 버튼
- reports.json 로드 실패: "보고서 데이터를 불러올 수 없습니다"
- Fuse.js CDN 로드 실패: `String.includes()` 기반 단순 검색으로 fallback

---

## 4. 디자인 & 스타일링

### 테마

기존 보고서 TEMPLATE.html의 다크 테마를 그대로 계승:

```css
--bg-deep: #0c0e14;
--bg-card: #141620;
--bg-card-hover: #191c28;
--border: #252838;
--text: #e8e8f0;
--text-dim: #9a9ab4;
--accent-gold: #f0c040;
--accent-green: #3ed88a;
--accent-red: #f05868;
--accent-blue: #4c94f0;
--accent-purple: #a46cf0;
```

### 폰트

- Noto Sans KR (본문)
- JetBrains Mono (수치)
- Google Fonts CDN

### 기술 스택

- Vanilla JS, 외부 프레임워크 없음
- Fuse.js CDN (유일한 외부 의존성) + `Fuse.createIndex()` 사전 인덱싱으로 1000+에서도 즉시 응답
- GitHub Pages 정적 배포 호환
- 상대 경로 기반 (`./reports.json`, `./{slug}.html`)

---

## 5. 파일 구조 변경 요약

```
docs/insights/
├── index.html          ← NEW: 보고서 라이브러리 인덱스
├── reports.json        ← NEW: 빌드 스크립트 출력 (git 커밋, CI 빌드 없이 배포)
├── synonyms.json       ← NEW: 한영 동의어 맵
├── hades.html          ← 기존 보고서 (meta 태그 추가)
├── stardew-valley.html
├── ...
scripts/
├── build_index.py      ← NEW: 빌드 스크립트
.claude/skills/steam-insight/
├── SKILL.md            ← 수정: meta 태그 필수 + build_index.py 실행 지시
├── TEMPLATE.html       ← 수정: meta 태그 블록 추가
```
