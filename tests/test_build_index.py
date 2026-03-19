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
