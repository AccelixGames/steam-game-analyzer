# 보고서 라이브러리 Index Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `docs/insights/index.html` — 모든 기획 인사이트 보고서에 검색/필터로 접근하는 내부 대시보드 구축

**Architecture:** 빌드 스크립트(`scripts/build_index.py`)가 보고서 HTML에서 메타데이터를 파싱하여 `reports.json`을 생성하고, `index.html`이 이를 fetch하여 Fuse.js 퍼지 검색 + 필터 + infinite scroll로 렌더링한다.

**Tech Stack:** Python 3.12 (빌드), Vanilla JS + Fuse.js CDN (프론트), GitHub Pages 정적 배포

**Spec:** `docs/superpowers/specs/2026-03-19-insight-index-design.md`

**Security Note:** 카드 렌더링 시 `innerHTML`/`insertAdjacentHTML` 대신 `document.createElement` + `textContent` 기반 안전한 DOM 구성을 사용한다. reports.json은 자체 빌드 스크립트에서 생성한 신뢰 데이터이지만, 안전한 패턴을 기본으로 한다.

---

## File Structure

```
scripts/
├── build_index.py                    ← NEW: HTML 파싱 → reports.json + synonyms.json
tests/
├── test_build_index.py               ← NEW: 빌드 스크립트 테스트
docs/insights/
├── index.html                        ← NEW: 보고서 라이브러리 인덱스 페이지
├── reports.json                      ← NEW: 빌드 출력 (git 커밋)
├── synonyms.json                     ← NEW: 한영 동의어 맵
.claude/skills/steam-insight/
├── TEMPLATE.html                     ← MODIFY: <meta> 태그 블록 추가
├── SKILL.md                          ← MODIFY: meta 태그 필수 + build_index.py 실행 지시
```

---

### Task 1: TEMPLATE.html에 meta 태그 블록 추가

**Files:**
- Modify: `.claude/skills/steam-insight/TEMPLATE.html:62-68` (`<head>` 내부)

- [ ] **Step 1: TEMPLATE.html 변수 목록 주석에 새 변수 추가**

`.claude/skills/steam-insight/TEMPLATE.html` 상단 주석의 변수 목록에 추가:

```
  {{NAME_KO}}            — 한국어 게임 이름 (games.name_ko, 없으면 빈 문자열)
  {{TAGS}}               — 상위 태그 (쉼표 구분: "Action Roguelike,Rogue-lite,Hack and Slash")
  {{GENRES}}             — 공식 장르 (쉼표 구분: "Action,Indie,RPG")
```

- [ ] **Step 2: `<head>` 내부에 meta 태그 블록 삽입**

`<title>` 태그 바로 아래, `<link>` 태그 위에 삽입:

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

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/steam-insight/TEMPLATE.html
git commit -m "feat: add report metadata meta tags to insight template"
```

---

### Task 2: SKILL.md에 meta 태그 필수 지시 + build_index.py 실행 지시 추가

**Files:**
- Modify: `.claude/skills/steam-insight/SKILL.md:323-336` (출력 형식 섹션)
- Modify: `.claude/skills/steam-insight/SKILL.md:465-473` (주의사항 뒤)

- [ ] **Step 1: 출력 형식 > 템플릿 섹션에 meta 태그 필수 요구 추가**

SKILL.md의 "### 템플릿" 섹션 뒤에 추가:

```markdown
### 인덱스 메타데이터 (필수)

모든 보고서는 `<head>` 내부에 `<meta name="report:*">` 태그를 포함해야 한다.
TEMPLATE.html에 정의된 meta 태그 블록을 반드시 채운다.

- `{{TAGS}}`: `game_tags` 상위 5개 태그를 쉼표로 구분 (예: "Action Roguelike,Rogue-lite,Hack and Slash")
- `{{GENRES}}`: `game_genres` 전체를 쉼표로 구분 (예: "Action,Indie,RPG")
- `{{NAME_KO}}`: `games.name_ko` 값. NULL이면 빈 문자열.
```

```sql
-- 태그 상위 5개
SELECT tag_name FROM game_tags WHERE appid = ? ORDER BY vote_count DESC LIMIT 5;
-- 장르 전체
SELECT genre_name FROM game_genres WHERE appid = ?;
-- 한국어 이름
SELECT name_ko FROM games WHERE appid = ?;
```

- [ ] **Step 2: 주의사항 섹션 뒤에 빌드 스크립트 실행 지시 추가**

SKILL.md 맨 끝에 추가:

```markdown
---

## 보고서 생성 후 작업

보고서 HTML을 `docs/insights/`에 생성하거나 갱신한 후, 반드시 다음을 실행한다:

\`\`\`bash
python scripts/build_index.py
\`\`\`

이 스크립트는 `docs/insights/reports.json`과 `synonyms.json`을 갱신하여 보고서 라이브러리 인덱스를 최신 상태로 유지한다.
```

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/steam-insight/SKILL.md
git commit -m "docs: add meta tag requirement and build_index.py instruction to steam-insight skill"
```

---

### Task 3: 빌드 스크립트 — meta 태그 파서

**Files:**
- Create: `scripts/build_index.py`
- Create: `tests/test_build_index.py`

- [ ] **Step 1: 테스트용 HTML 픽스처와 meta 파싱 테스트 작성**

`tests/test_build_index.py`:

```python
"""Tests for scripts/build_index.py"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import pytest

SAMPLE_HTML_WITH_META = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>Hades — 기획 인사이트 보고서</title>
<meta name="report:appid" content="1145360">
<meta name="report:game_name" content="Hades">
<meta name="report:name_ko" content="">
<meta name="report:positive_rate" content="98.3%">
<meta name="report:review_score" content="Overwhelmingly Positive">
<meta name="report:owners" content="5~10M">
<meta name="report:price" content="$24.99">
<meta name="report:avg_playtime" content="34.5h">
<meta name="report:review_count" content="123456">
<meta name="report:tags" content="Action Roguelike,Rogue-lite,Hack and Slash">
<meta name="report:genres" content="Action,Indie,RPG">
<meta name="report:date" content="2026-03-15">
<meta name="report:modified" content="2026-03-15">
<meta name="report:header_image" content="https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/1145360/header.jpg">
</head>
<body></body>
</html>"""


def test_parse_meta_tags():
    from build_index import parse_report_html
    result = parse_report_html(SAMPLE_HTML_WITH_META, "hades")
    assert result["name"] == "Hades"
    assert result["appid"] == 1145360
    assert result["positive_rate"] == 98.3
    assert result["tags"] == ["Action Roguelike", "Rogue-lite", "Hack and Slash"]
    assert result["genres"] == ["Action", "Indie", "RPG"]
    assert result["review_count"] == 123456
    assert result["slug"] == "hades"
    assert result["name_ko"] is None  # empty string → None
```

- [ ] **Step 2: 테스트 실행하여 실패 확인**

Run: `python -m pytest tests/test_build_index.py::test_parse_meta_tags -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'build_index'`

- [ ] **Step 3: `parse_report_html` 함수 구현**

`scripts/build_index.py` 생성: `ReportMetaParser(HTMLParser)` 클래스로 `<meta name="report:*">` 파싱, `<title>` 파싱, Steam 링크에서 appid 추출. `parse_report_html(html_content, slug) -> dict` 함수로 구조화된 메타데이터 반환.

핵심 파싱 로직:
- `positive_rate`: "98.3%" → `float(98.3)`
- `review_count`: "123,456" or "123456" → `int(123456)`
- `tags`/`genres`: 쉼표 구분 문자열 → `list[str]`
- `name_ko`: 빈 문자열 → `None`

- [ ] **Step 4: 테스트 실행하여 통과 확인**

Run: `python -m pytest tests/test_build_index.py::test_parse_meta_tags -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/build_index.py tests/test_build_index.py
git commit -m "feat: add report HTML meta tag parser for build_index"
```

---

### Task 4: 빌드 스크립트 — fallback 파싱 (기존 보고서 호환)

**Files:**
- Modify: `scripts/build_index.py`
- Modify: `tests/test_build_index.py`

- [ ] **Step 1: fallback 파싱 테스트 작성**

`tests/test_build_index.py`에 추가:

```python
SAMPLE_HTML_NO_META = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>Hades — 기획 인사이트 보고서</title>
</head>
<body>
<header class="hero">
  <div class="hero-top-bar">
    <a href="https://store.steampowered.com/app/1145360/">Steam</a>
  </div>
  <h1>Hades</h1>
  <div class="hero-stats">
    <div class="hero-stat">
      <span class="num gold">98.3%</span>
      <span class="label">긍정률 (Overwhelmingly Positive)</span>
    </div>
    <div class="hero-stat">
      <span class="num">5~10M</span>
      <span class="label">소유자 수</span>
    </div>
    <div class="hero-stat">
      <span class="num green">$24.99</span>
      <span class="label">가격</span>
    </div>
    <div class="hero-stat">
      <span class="num">34.5h</span>
      <span class="label">평균 플레이타임</span>
    </div>
  </div>
</header>
</body>
</html>"""


def test_fallback_parse_no_meta():
    from build_index import parse_report_html
    result = parse_report_html(SAMPLE_HTML_NO_META, "hades")
    assert result["name"] == "Hades"
    assert result["appid"] == 1145360
    assert result["positive_rate"] == 98.3
    assert result["owners"] == "5~10M"
    assert result["price"] == "$24.99"
    assert result["avg_playtime"] == "34.5h"


def test_partial_meta_uses_fallback():
    """Meta 태그가 일부만 있으면, 빈 필드를 fallback으로 보충."""
    partial = """<!DOCTYPE html>
<html><head>
<title>TestGame — 기획 인사이트 보고서</title>
<meta name="report:appid" content="999">
<meta name="report:game_name" content="TestGame">
</head><body>
<div class="hero-stats">
  <div class="hero-stat">
    <span class="num gold">85.0%</span>
    <span class="label">긍정률 (Very Positive)</span>
  </div>
</div>
</body></html>"""
    from build_index import parse_report_html
    result = parse_report_html(partial, "testgame")
    assert result["appid"] == 999
    assert result["name"] == "TestGame"
    assert result["positive_rate"] == 85.0
```

- [ ] **Step 2: 테스트 실행하여 실패 확인**

Run: `python -m pytest tests/test_build_index.py -k "fallback or partial" -v`
Expected: FAIL

- [ ] **Step 3: fallback 파서 구현**

`ReportMetaParser`에 hero-stat 파싱 추가: `<div class="hero-stat">` 내부의 `<span class="num">` + `<span class="label">` 추출. `parse_report_html`에서 meta 값이 없는 필드를 hero_stats로 보충:
- "긍정률" 라벨 → positive_rate + review_score
- "소유자" → owners
- "가격" → price
- "플레이타임" → avg_playtime

- [ ] **Step 4: 테스트 실행하여 통과 확인**

Run: `python -m pytest tests/test_build_index.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/build_index.py tests/test_build_index.py
git commit -m "feat: add fallback hero-stat parsing for legacy reports"
```

---

### Task 5: 빌드 스크립트 — 증분 빌드 + synonyms + CLI

**Files:**
- Modify: `scripts/build_index.py`
- Modify: `tests/test_build_index.py`

- [ ] **Step 1: 증분 빌드 테스트 작성**

```python
def test_incremental_build_skips_unchanged(tmp_path):
    from build_index import build_reports_json
    insights_dir = tmp_path / "insights"
    insights_dir.mkdir()
    (insights_dir / "hades.html").write_text(SAMPLE_HTML_WITH_META, encoding="utf-8")
    result1 = build_reports_json(insights_dir, force=False, db_path=None)
    assert len(result1) == 1
    (insights_dir / "reports.json").write_text(json.dumps(result1), encoding="utf-8")
    result2 = build_reports_json(insights_dir, force=False, db_path=None)
    assert result2[0]["_file_hash"] == result1[0]["_file_hash"]


def test_incremental_build_detects_change(tmp_path):
    from build_index import build_reports_json
    insights_dir = tmp_path / "insights"
    insights_dir.mkdir()
    (insights_dir / "hades.html").write_text(SAMPLE_HTML_WITH_META, encoding="utf-8")
    result1 = build_reports_json(insights_dir, force=False, db_path=None)
    (insights_dir / "reports.json").write_text(json.dumps(result1), encoding="utf-8")
    modified = SAMPLE_HTML_WITH_META.replace("98.3%", "99.0%")
    (insights_dir / "hades.html").write_text(modified, encoding="utf-8")
    result2 = build_reports_json(insights_dir, force=False, db_path=None)
    assert result2[0]["positive_rate"] == 99.0
    assert result2[0]["_file_hash"] != result1[0]["_file_hash"]


def test_deleted_report_removed(tmp_path):
    from build_index import build_reports_json
    insights_dir = tmp_path / "insights"
    insights_dir.mkdir()
    (insights_dir / "hades.html").write_text(SAMPLE_HTML_WITH_META, encoding="utf-8")
    result1 = build_reports_json(insights_dir, force=False, db_path=None)
    (insights_dir / "reports.json").write_text(json.dumps(result1), encoding="utf-8")
    (insights_dir / "hades.html").unlink()
    result2 = build_reports_json(insights_dir, force=False, db_path=None)
    assert len(result2) == 0


def test_force_rebuild_reparses_unchanged(tmp_path):
    """force=True이면 hash가 같아도 재파싱한다."""
    from build_index import build_reports_json
    insights_dir = tmp_path / "insights"
    insights_dir.mkdir()
    (insights_dir / "hades.html").write_text(SAMPLE_HTML_WITH_META, encoding="utf-8")
    result1 = build_reports_json(insights_dir, force=False, db_path=None)
    (insights_dir / "reports.json").write_text(json.dumps(result1), encoding="utf-8")
    # force=True should still re-parse and return valid data
    result2 = build_reports_json(insights_dir, force=True, db_path=None)
    assert len(result2) == 1
    assert result2[0]["name"] == "Hades"


def test_duplicate_appid_keeps_newest(tmp_path):
    """같은 appid의 파일이 여러 개이면 최신 mtime만 유지."""
    import time
    from build_index import build_reports_json
    insights_dir = tmp_path / "insights"
    insights_dir.mkdir()
    (insights_dir / "hades-old.html").write_text(SAMPLE_HTML_WITH_META, encoding="utf-8")
    time.sleep(0.1)  # ensure different mtime
    newer = SAMPLE_HTML_WITH_META.replace("98.3%", "99.5%")
    (insights_dir / "hades-new.html").write_text(newer, encoding="utf-8")
    result = build_reports_json(insights_dir, force=True, db_path=None)
    # Should keep only one entry for appid 1145360
    appid_entries = [r for r in result if r["appid"] == 1145360]
    assert len(appid_entries) == 1
    assert appid_entries[0]["positive_rate"] == 99.5


def test_build_synonyms_hardcoded_only():
    """DB 없이 하드코딩 동의어만 반환."""
    from build_index import build_synonyms_json
    synonyms = build_synonyms_json(db_path=None)
    assert "로그라이크" in synonyms
    assert "Roguelike" in synonyms["로그라이크"]
    assert "생존" in synonyms
    assert len(synonyms) >= 30  # 최소 30쌍 이상


def test_build_synonyms_with_db(tmp_path):
    """DB에서 name_ko를 자동 병합."""
    import sqlite3
    from build_index import build_synonyms_json
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE games (appid INTEGER, name TEXT, name_ko TEXT)")
    conn.execute("INSERT INTO games VALUES (1, 'Palworld', 'Palworld / 팰월드')")
    conn.execute("INSERT INTO games VALUES (2, 'Hades', NULL)")
    conn.commit()
    conn.close()
    synonyms = build_synonyms_json(db_path=db_path)
    assert "팰월드" in synonyms
    assert "Palworld" in synonyms["팰월드"]
```

- [ ] **Step 2: 테스트 실행하여 실패 확인**

Run: `python -m pytest tests/test_build_index.py -k "incremental or deleted or force or duplicate or synonyms" -v`
Expected: FAIL

- [ ] **Step 3: `build_reports_json`, `build_synonyms_json`, `main` 구현**

- `build_reports_json(insights_dir, force, db_path)`: MD5 해시 기반 증분 빌드, 중복 appid 처리 (최신 mtime 유지), force=True 시 기존 캐시 무시
- `build_synonyms_json(db_path)`: 하드코딩 ~50쌍 + DB name_ko 자동 병합 (선택적)
- `main()`: argparse CLI (`--force`, `--insights-dir`, `--db-path`)

- [ ] **Step 4: 테스트 실행하여 통과 확인**

Run: `python -m pytest tests/test_build_index.py -v`
Expected: ALL PASS

- [ ] **Step 5: 실제 보고서로 빌드 실행 테스트**

```bash
cd C:/WorkSpace/github.com/AccelixGames/steam-game-analyzer
python scripts/build_index.py --force
```
Expected: `reports.json updated: 5 reports` + `synonyms.json updated: N entries`

- [ ] **Step 6: Commit**

```bash
git add scripts/build_index.py tests/test_build_index.py docs/insights/reports.json docs/insights/synonyms.json
git commit -m "feat: add incremental build script with CLI, synonyms, and dedup"
```

---

### Task 6: index.html — HTML 구조 + CSS + 카드 렌더링

**Files:**
- Create: `docs/insights/index.html`

이 태스크에서 `@frontend-design` 스킬을 호출하여 디자인 품질 확보.

- [ ] **Step 1: index.html 전체 파일 작성**

단일 HTML 파일로 구성:
- `<head>`: 폰트 CDN, CSS (기존 보고서와 동일한 CSS 변수 + toolbar/card-grid/filter 스타일)
- `<body>`: 헤더, toolbar (검색바 + 필터 드롭다운), active-filters 영역, card-grid, empty-state, scroll-sentinel
- Fuse.js CDN `<script>` 태그
- `<script>`: 전체 JS (데이터 로드, 카드 렌더링, 검색, 필터, 정렬, infinite scroll)

핵심 CSS:
- `.toolbar`: `position: sticky; top: 0; z-index: 100;` 배경 `--bg-deep`
- `.card-grid`: `display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 12px;`
- `.card`: 세로 분할 미니카드 (상=이미지, 하=정보). hover 시 border 강조
- `.pill`: 태그/장르 pill. gold/blue/purple 계열
- `.filter-dropdown`: 커스텀 체크박스 멀티셀렉트

핵심 JS — 카드 렌더링 (`document.createElement` 기반, `innerHTML` 미사용):

```javascript
function createCard(report) {
  const a = document.createElement('a');
  a.href = './' + report.slug + '.html';
  a.target = '_blank';
  a.className = 'card';

  // Image
  const imgWrap = document.createElement('div');
  imgWrap.className = 'card-image';
  const img = document.createElement('img');
  img.src = report.header_image || '';
  img.alt = report.name;
  img.loading = 'lazy';
  img.onerror = function() {
    this.style.display = 'none';
    fallback.style.display = 'flex';
  };
  const fallback = document.createElement('div');
  fallback.className = 'card-image-fallback';
  fallback.textContent = report.name;
  imgWrap.append(img, fallback);

  // Body
  const body = document.createElement('div');
  body.className = 'card-body';

  // Top row: name+tags | rate+reviews
  const top = document.createElement('div');
  top.className = 'card-top';

  const info = document.createElement('div');
  info.className = 'card-info';
  const nameEl = document.createElement('div');
  nameEl.className = 'card-name';
  nameEl.textContent = report.name;
  const pills = document.createElement('div');
  pills.className = 'card-pills';
  (report.tags || []).slice(0, 3).forEach(t => {
    const pill = document.createElement('span');
    pill.className = 'pill pill-tag';
    pill.textContent = t;
    pills.appendChild(pill);
  });
  info.append(nameEl, pills);

  const stats = document.createElement('div');
  stats.className = 'card-stats';
  const rate = document.createElement('div');
  rate.className = 'card-rate';
  rate.style.color = report.positive_rate >= 90 ? 'var(--accent-green)'
    : report.positive_rate >= 70 ? 'var(--accent-gold)' : 'var(--accent-red)';
  rate.textContent = report.positive_rate != null ? report.positive_rate + '%' : '-';
  const reviews = document.createElement('div');
  reviews.className = 'card-reviews';
  reviews.textContent = report.review_count ? report.review_count.toLocaleString() + '건' : '';
  stats.append(rate, reviews);

  top.append(info, stats);

  // Bottom row
  const bottom = document.createElement('div');
  bottom.className = 'card-bottom';
  bottom.textContent = [report.owners, report.price, report.avg_playtime].filter(Boolean).join(' · ');

  body.append(top, bottom);
  a.append(imgWrap, body);
  return a;
}

function renderBatch() {
  const grid = document.getElementById('cardGrid');
  const batch = filteredReports.slice(displayedCount, displayedCount + BATCH_SIZE);
  const fragment = document.createDocumentFragment();
  batch.forEach(r => fragment.appendChild(createCard(r)));
  grid.appendChild(fragment);
  displayedCount += batch.length;
  updateCount();
}
```

- [ ] **Step 2: 브라우저에서 로컬 서버로 확인**

```bash
cd docs/insights && python -m http.server 8080
```
→ http://localhost:8080 에서 확인:
- 카드 렌더링, 레이아웃, 다크 테마
- 빈 상태: reports.json 삭제 후 "보고서 데이터를 불러올 수 없습니다" 표시
- 이미지 로드 실패: header_image URL을 잘못된 값으로 바꿔서 placeholder 표시 확인
- Fuse.js 실패: CDN script 태그 제거 후 검색이 includes() fallback으로 동작하는지 확인

- [ ] **Step 3: Commit**

```bash
git add docs/insights/index.html
git commit -m "feat: add insight library index.html with cards, search, filters, and infinite scroll"
```

---

### Task 7: index.html — 검색 (Fuse.js + 동의어 + URL/appid)

**Files:**
- Modify: `docs/insights/index.html` (JS 영역)

- [ ] **Step 1: 검색 JS 구현**

`initSearch()`: Fuse.js 초기화 + `Fuse.createIndex()` 사전 인덱싱
`searchReports(query)`:
1. `/app\/(\d+)/` 정규식 → appid 추출
2. 순수 숫자 → appid 직접 매칭
3. 동의어 확장 → Fuse.js 퍼지 매칭
4. Fuse.js 로드 실패 → `String.includes()` fallback

검색바 `input` 이벤트에 debounce 200ms.

- [ ] **Step 2: 검색 기능 브라우저 테스트**

테스트 입력: "Hades", "1145360", "https://store.steampowered.com/app/1145360/", "hade", "로그라이크"

- [ ] **Step 3: Commit**

```bash
git add docs/insights/index.html
git commit -m "feat: add fuzzy search with synonym expansion and URL/appid detection"
```

---

### Task 8: index.html — 필터 + 정렬

**Files:**
- Modify: `docs/insights/index.html` (JS 영역)

- [ ] **Step 1: 필터/정렬 JS 구현**

- `populateDropdowns()`: reports 데이터에서 고유 장르/태그 추출, 드롭다운 체크박스 렌더링 (DOM API)
- `applyFiltersAndSearch()`: 검색 → 장르 필터 → 태그 필터 → 정렬 → 렌더
- 정렬 옵션: 긍정률순, 리뷰수순, 최신순(modified), 이름순
- active filter pill: 선택된 필터를 pill로 표시, × 클릭 시 제거

- [ ] **Step 2: 브라우저에서 필터/정렬 동작 확인**

- [ ] **Step 3: Commit**

```bash
git add docs/insights/index.html
git commit -m "feat: add genre/tag filters, sorting, and active filter pills"
```

---

### Task 9: index.html — Infinite Scroll

**Files:**
- Modify: `docs/insights/index.html` (JS 영역)

- [ ] **Step 1: IntersectionObserver 구현**

```javascript
const sentinel = document.getElementById('scrollSentinel');
const observer = new IntersectionObserver((entries) => {
  if (entries[0].isIntersecting && displayedCount < filteredReports.length) {
    renderBatch();
  }
}, { rootMargin: '200px' });
observer.observe(sentinel);
```

- [ ] **Step 2: Commit**

```bash
git add docs/insights/index.html
git commit -m "feat: add infinite scroll with IntersectionObserver"
```

---

### Task 10: 빌드 스크립트 첫 실행 + 전체 통합 테스트

- [ ] **Step 1: 빌드 스크립트 실행**

```bash
cd C:/WorkSpace/github.com/AccelixGames/steam-game-analyzer
python scripts/build_index.py --force
```

- [ ] **Step 2: 생성 결과 확인**

```bash
python -c "import json; d=json.load(open('docs/insights/reports.json','r',encoding='utf-8')); print(len(d), 'reports'); print(json.dumps(d[0], indent=2, ensure_ascii=False))"
```

- [ ] **Step 3: 로컬 서버에서 전체 기능 테스트**

```bash
cd docs/insights && python -m http.server 8080
```
→ http://localhost:8080 에서 카드 렌더링, 검색, 필터, 정렬, 카드 클릭(새 탭) 확인

- [ ] **Step 4: 증분 빌드 확인**

```bash
python scripts/build_index.py
# Expected: "reports.json unchanged: 5 reports"
```

- [ ] **Step 5: 전체 테스트 실행**

```bash
cd steam-crawler && python -m pytest ../tests/test_build_index.py -v
```

- [ ] **Step 6: Commit generated files**

```bash
git add docs/insights/reports.json docs/insights/synonyms.json
git commit -m "chore: generate initial reports.json and synonyms.json"
```

- [ ] **Step 7: `@superpowers:verification-before-completion` 실행**

최종 검증 후 완료 선언.
