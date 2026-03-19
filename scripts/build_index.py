"""Build index script for Steam insight HTML reports.

Pipeline: docs/insights/*.html → reports.json → index page
"""
from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Optional


class ReportMetaParser(HTMLParser):
    """Extracts <meta name="report:*"> tags, <title>, and Steam app links."""

    def __init__(self) -> None:
        super().__init__()
        self.meta: dict[str, str] = {}
        self.title: str = ""
        self._in_title: bool = False
        self._appid_from_link: Optional[int] = None

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

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data


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

    return {
        "slug": slug,
        "name": name_raw or None,
        "name_ko": _str_or_none(meta.get("name_ko", "")),
        "appid": appid,
        "positive_rate": _parse_positive_rate(meta.get("positive_rate", "")),
        "review_score": _str_or_none(meta.get("review_score", "")),
        "owners": _str_or_none(meta.get("owners", "")),
        "price": _str_or_none(meta.get("price", "")),
        "avg_playtime": _str_or_none(meta.get("avg_playtime", "")),
        "review_count": _parse_review_count(meta.get("review_count", "")),
        "tags": _parse_list(meta.get("tags", "")),
        "genres": _parse_list(meta.get("genres", "")),
        "date": _str_or_none(meta.get("date", "")),
        "modified": _str_or_none(meta.get("modified", "")),
        "header_image": _str_or_none(meta.get("header_image", "")),
    }
