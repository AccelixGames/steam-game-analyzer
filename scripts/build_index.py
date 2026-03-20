"""Build index script for Steam insight HTML reports.

Pipeline: docs/insights/*.html → reports.json → index page
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from html.parser import HTMLParser
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INSIGHTS_DIR = PROJECT_ROOT / "docs" / "insights"
DB_PATH = PROJECT_ROOT / "data" / "steam.db"


class ReportMetaParser(HTMLParser):
    """Extracts <meta name="report:*"> tags, <title>, Steam app links, and hero stats."""

    def __init__(self) -> None:
        super().__init__()
        self.meta: dict[str, str] = {}
        self.title: str = ""
        self._in_title: bool = False
        self._appid_from_link: Optional[int] = None

        # Hero stat fallback tracking
        self.hero_stats: list[tuple[str, str]] = []  # (value, label) pairs
        self._in_hero_stat: bool = False
        self._in_num_span: bool = False
        self._in_label_span: bool = False
        self._current_stat_value: str = ""
        self._current_stat_label: str = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        attr_dict = dict(attrs)

        if tag == "meta":
            name = attr_dict.get("name", "")
            content = attr_dict.get("content", "") or ""
            if name and name.startswith("report:"):
                key = name[len("report:"):]
                self.meta[key] = content

        elif tag == "title":
            self._in_title = True

        elif tag == "a":
            href = attr_dict.get("href", "") or ""
            m = re.search(r"/app/(\d+)/", href)
            if m and self._appid_from_link is None:
                self._appid_from_link = int(m.group(1))

        elif tag == "div":
            classes = (attr_dict.get("class", "") or "").split()
            if "hero-stat" in classes:
                self._in_hero_stat = True
                self._current_stat_value = ""
                self._current_stat_label = ""

        elif tag == "span" and self._in_hero_stat:
            classes = (attr_dict.get("class", "") or "").split()
            if "num" in classes:
                self._in_num_span = True
            elif "label" in classes:
                self._in_label_span = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        elif tag == "span":
            if self._in_num_span:
                self._in_num_span = False
            elif self._in_label_span:
                self._in_label_span = False
        elif tag == "div" and self._in_hero_stat:
            # Only close the hero-stat when we have collected both parts.
            # Since divs can be nested, only finalize if we have a label.
            if self._current_stat_label:
                self.hero_stats.append(
                    (self._current_stat_value.strip(), self._current_stat_label.strip())
                )
                self._in_hero_stat = False
                self._current_stat_value = ""
                self._current_stat_label = ""

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data
        elif self._in_num_span:
            self._current_stat_value += data
        elif self._in_label_span:
            self._current_stat_label += data


def _parse_positive_rate(value: str) -> Optional[float]:
    """'98.3%' → 98.3, None if invalid."""
    value = value.strip().rstrip("%")
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _parse_review_count(value: str) -> Optional[int]:
    """'123,456' or '123456' → 123456, None if invalid."""
    value = value.strip().replace(",", "")
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _parse_list(value: str) -> list[str]:
    """'Action Roguelike,Rogue-lite,Hack and Slash' → list of stripped strings."""
    if not value.strip():
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _str_or_none(value: str) -> Optional[str]:
    """Return None for empty/whitespace strings."""
    stripped = value.strip()
    return stripped if stripped else None


def parse_report_html(html_content: str, slug: str) -> dict:
    """Parse a report HTML file and return a metadata dict.

    Args:
        html_content: Full HTML content of the report file.
        slug: Filename stem used as the report's identifier.

    Returns:
        Dict with keys: slug, name, name_ko, appid, positive_rate, review_score,
        owners, price, avg_playtime, review_count, tags, genres, date, modified,
        header_image.
    """
    parser = ReportMetaParser()
    parser.feed(html_content)

    meta = parser.meta

    # appid: meta tag takes priority, fallback to link extraction
    appid_raw = meta.get("appid", "").strip()
    if appid_raw:
        try:
            appid = int(appid_raw)
        except ValueError:
            appid = parser._appid_from_link
    else:
        appid = parser._appid_from_link

    # game_name: meta tag takes priority, fallback to title parsing
    name_raw = meta.get("game_name", "").strip()
    if not name_raw and parser.title:
        # Title format: "GameName — 기획 인사이트 보고서"
        name_raw = parser.title.split("—")[0].strip()

    # Build result from meta tags first
    positive_rate = _parse_positive_rate(meta.get("positive_rate", ""))
    review_score = _str_or_none(meta.get("review_score", ""))
    owners = _str_or_none(meta.get("owners", ""))
    price = _str_or_none(meta.get("price", ""))
    avg_playtime = _str_or_none(meta.get("avg_playtime", ""))

    # Fallback: fill None fields from hero-stat sections
    for stat_value, stat_label in parser.hero_stats:
        if "긍정률" in stat_label:
            if positive_rate is None:
                positive_rate = _parse_positive_rate(stat_value)
            if review_score is None:
                # Extract text inside parentheses: "긍정률 (Overwhelmingly Positive)"
                m = re.search(r"\(([^)]+)\)", stat_label)
                if m:
                    review_score = m.group(1).strip()
        elif "소유자" in stat_label:
            if owners is None:
                owners = stat_value or None
        elif "가격" in stat_label:
            if price is None:
                price = stat_value or None
        elif "플레이타임" in stat_label:
            if avg_playtime is None:
                avg_playtime = stat_value or None

    return {
        "slug": slug,
        "name": name_raw or None,
        "name_ko": _str_or_none(meta.get("name_ko", "")),
        "appid": appid,
        "positive_rate": positive_rate,
        "review_score": review_score,
        "owners": owners,
        "price": price,
        "avg_playtime": avg_playtime,
        "review_count": _parse_review_count(meta.get("review_count", "")),
        "tags": _parse_list(meta.get("tags", "")),
        "genres": _parse_list(meta.get("genres", "")),
        "date": _str_or_none(meta.get("date", "")),
        "modified": _str_or_none(meta.get("modified", "")),
        "header_image": _str_or_none(meta.get("header_image", "")),
    }


def file_hash(path: Path) -> str:
    """Return MD5 hex digest of the file's contents."""
    return hashlib.md5(path.read_bytes()).hexdigest()


def build_reports_json(
    insights_dir: Path, force: bool, db_path: Optional[Path]
) -> list[dict]:
    """Parse insight HTML reports and return a list of metadata dicts.

    Supports incremental builds: unchanged files are reused from the existing
    reports.json. Deduplicates by appid, keeping the entry from the newest file.

    Args:
        insights_dir: Directory containing *.html report files.
        force: When True, re-parse all files regardless of cache.
        db_path: Path to SQLite DB for enriching fallback-parsed reports.

    Returns:
        List of metadata dicts, one per unique appid (or slug if no appid).
    """
    # Load existing cache keyed by slug
    cache: dict[str, dict] = {}
    reports_json = insights_dir / "reports.json"
    if not force and reports_json.exists():
        try:
            existing = json.loads(reports_json.read_text(encoding="utf-8"))
            for entry in existing:
                cache[entry["slug"]] = entry
        except (json.JSONDecodeError, KeyError):
            cache = {}

    # Collect all HTML files (exclude index.html)
    html_files = [
        p for p in insights_dir.glob("*.html") if p.name != "index.html"
    ]

    # Parse each file, using cache when possible
    parsed: list[tuple[float, dict]] = []  # (mtime, entry)
    for html_path in html_files:
        slug = html_path.stem
        h = file_hash(html_path)
        if not force and slug in cache and cache[slug].get("_file_hash") == h:
            parsed.append((html_path.stat().st_mtime, cache[slug]))
        else:
            content = html_path.read_text(encoding="utf-8")
            entry = parse_report_html(content, slug)
            entry["_file_hash"] = h
            parsed.append((html_path.stat().st_mtime, entry))

    # Fill missing date/modified from file mtime
    for mtime, entry in parsed:
        if not entry.get("modified"):
            from datetime import datetime, timezone
            entry["modified"] = datetime.fromtimestamp(mtime, tz=timezone.utc).strftime("%Y-%m-%d")
        if not entry.get("date"):
            entry["date"] = entry.get("modified")

    # Enrich entries with missing tags/genres/header_image from DB
    if db_path is not None and Path(db_path).exists():
        try:
            conn = sqlite3.connect(str(db_path))
            for _, entry in parsed:
                appid = entry.get("appid")
                if appid is None:
                    continue
                # Fill tags from DB if empty
                if not entry.get("tags"):
                    rows = conn.execute(
                        "SELECT tag_name FROM game_tags WHERE appid = ? ORDER BY vote_count DESC LIMIT 5",
                        (appid,),
                    ).fetchall()
                    if rows:
                        entry["tags"] = [r[0] for r in rows]
                # Fill genres from DB if empty
                if not entry.get("genres"):
                    rows = conn.execute(
                        "SELECT genre_name FROM game_genres WHERE appid = ?",
                        (appid,),
                    ).fetchall()
                    if rows:
                        entry["genres"] = [r[0] for r in rows]
                # Fill header_image from DB if missing
                if not entry.get("header_image"):
                    row = conn.execute(
                        "SELECT header_image FROM games WHERE appid = ?",
                        (appid,),
                    ).fetchone()
                    if row and row[0]:
                        entry["header_image"] = row[0]
                # Fill name_ko from DB if missing
                if not entry.get("name_ko"):
                    row = conn.execute(
                        "SELECT name_ko FROM games WHERE appid = ?",
                        (appid,),
                    ).fetchone()
                    if row and row[0] and row[0].strip():
                        entry["name_ko"] = row[0].strip()
                # Fill review_count from DB if missing
                if entry.get("review_count") is None:
                    row = conn.execute(
                        "SELECT count(*) FROM reviews WHERE appid = ?",
                        (appid,),
                    ).fetchone()
                    if row and row[0]:
                        entry["review_count"] = row[0]
            conn.close()
        except Exception:
            pass  # DB errors are non-fatal

    # Deduplicate by appid — keep the entry from the newest file
    # Files without an appid are kept as-is (keyed by slug)
    appid_best: dict[int, tuple[float, dict]] = {}
    no_appid: list[dict] = []
    for mtime, entry in parsed:
        appid = entry.get("appid")
        if appid is None:
            no_appid.append(entry)
        else:
            if appid not in appid_best or mtime > appid_best[appid][0]:
                appid_best[appid] = (mtime, entry)

    result = [e for _, e in appid_best.values()] + no_appid
    return result


# ---------------------------------------------------------------------------
# Hardcoded Korean → English synonym map (~50 entries)
# ---------------------------------------------------------------------------
_HARDCODED_SYNONYMS: dict[str, list[str]] = {
    "생존": ["Survival"],
    "로그라이크": ["Roguelike", "Rogue-lite", "Action Roguelike"],
    "로그라이트": ["Rogue-lite", "Roguelike"],
    "경영": ["Management", "Simulation"],
    "시뮬레이션": ["Simulation"],
    "농사": ["Farming Sim", "Agriculture"],
    "액션": ["Action", "Hack and Slash"],
    "인디": ["Indie"],
    "오픈월드": ["Open World"],
    "멀티": ["Multiplayer", "Co-op"],
    "협동": ["Co-op", "Multiplayer"],
    "싱글": ["Singleplayer"],
    "전략": ["Strategy"],
    "퍼즐": ["Puzzle"],
    "공포": ["Horror"],
    "어드벤처": ["Adventure"],
    "플랫포머": ["Platformer"],
    "샌드박스": ["Sandbox"],
    "크래프팅": ["Crafting"],
    "건설": ["Building", "Base Building"],
    "카드": ["Card Game", "TCG"],
    "턴제": ["Turn-Based"],
    "실시간": ["Real-Time"],
    "소울라이크": ["Souls-like"],
    "메트로배니아": ["Metroidvania"],
    "타워디펜스": ["Tower Defense"],
    "슈팅": ["Shooter", "FPS", "TPS"],
    "격투": ["Fighting"],
    "레이싱": ["Racing"],
    "스포츠": ["Sports"],
    "음악": ["Rhythm", "Music"],
    "비주얼노벨": ["Visual Novel"],
    "연애": ["Dating Sim", "Romance"],
    "요리": ["Cooking"],
    "낚시": ["Fishing"],
    "탐험": ["Exploration"],
    "스텔스": ["Stealth"],
    "좀비": ["Zombies"],
    "우주": ["Space"],
    "중세": ["Medieval"],
    "판타지": ["Fantasy"],
    "SF": ["Sci-fi"],
    "디펜스": ["Tower Defense", "Defense"],
    "로봇": ["Robots", "Mechs"],
    "해적": ["Pirates"],
    "뱀파이어": ["Vampire"],
    "마법": ["Magic"],
}

_KOREAN_RE = re.compile(r"[\uac00-\ud7a3]")


def build_synonyms_json(db_path: Optional[Path]) -> dict[str, list[str]]:
    """Build a Korean → English synonym map.

    Starts with hardcoded entries, then enriches from the games DB when
    available (queries name_ko column for Korean name variants).

    Args:
        db_path: Path to the SQLite DB, or None to use only hardcoded entries.

    Returns:
        Dict mapping Korean term → list of English equivalents.
    """
    synonyms: dict[str, list[str]] = {
        k: list(v) for k, v in _HARDCODED_SYNONYMS.items()
    }

    if db_path is not None and Path(db_path).exists():
        try:
            conn = sqlite3.connect(str(db_path))
            rows = conn.execute(
                "SELECT name, name_ko FROM games WHERE name_ko IS NOT NULL AND name_ko != ''"
            ).fetchall()
            conn.close()
            for name_en, name_ko_raw in rows:
                if not name_en or not name_ko_raw:
                    continue
                # Split by "/" and find parts that contain Korean characters
                parts = [p.strip() for p in name_ko_raw.split("/")]
                for part in parts:
                    if _KOREAN_RE.search(part) and part not in synonyms:
                        synonyms[part] = [name_en]
        except Exception:
            pass  # DB errors are non-fatal

    return synonyms


def main() -> None:
    """CLI entry point for building reports.json and synonyms.json."""
    parser = argparse.ArgumentParser(
        description="Build reports.json and synonyms.json from insight HTML files."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-parse all HTML files, ignoring the cache.",
    )
    parser.add_argument(
        "--insights-dir",
        type=Path,
        default=INSIGHTS_DIR,
        help=f"Directory containing insight HTML files (default: {INSIGHTS_DIR})",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=None,
        help="Path to SQLite DB for synonym enrichment (default: auto-detect).",
    )
    args = parser.parse_args()

    insights_dir: Path = args.insights_dir
    db_path: Optional[Path] = args.db_path
    if db_path is None and DB_PATH.exists():
        db_path = DB_PATH

    # Build reports.json
    reports = build_reports_json(insights_dir, force=args.force, db_path=db_path)
    reports_path = insights_dir / "reports.json"
    new_content = json.dumps(reports, ensure_ascii=False, indent=2)
    old_content = reports_path.read_text(encoding="utf-8") if reports_path.exists() else ""
    if new_content != old_content:
        reports_path.write_text(new_content, encoding="utf-8")
        print(f"reports.json updated: {len(reports)} reports")
    else:
        print(f"reports.json unchanged: {len(reports)} reports")

    # Build synonyms.json
    synonyms = build_synonyms_json(db_path=db_path)
    synonyms_path = insights_dir / "synonyms.json"
    synonyms_content = json.dumps(synonyms, ensure_ascii=False, indent=2)
    synonyms_path.write_text(synonyms_content, encoding="utf-8")
    print(f"synonyms.json written: {len(synonyms)} entries")


if __name__ == "__main__":
    main()
