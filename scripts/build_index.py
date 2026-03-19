"""Build index script for Steam insight HTML reports.

Pipeline: docs/insights/*.html → reports.json → index page
"""
from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Optional


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
