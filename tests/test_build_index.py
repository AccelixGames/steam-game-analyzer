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
