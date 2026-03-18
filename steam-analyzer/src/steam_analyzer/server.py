"""Steam Analyzer MCP stdio server."""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from steam_analyzer.error_logger import init_analysis_logs
from steam_analyzer.tools.search_reviews import handle_search_reviews
from steam_analyzer.tools.analyze_design import handle_analyze_design
from steam_analyzer.tools.analysis_logs import handle_get_analysis_logs

DEFAULT_DB_PATH = "../data/steam.db"

server = Server("steam-analyzer")


def _get_db_path() -> str:
    return os.environ.get("STEAM_DB_PATH", DEFAULT_DB_PATH)


def _get_connection() -> sqlite3.Connection:
    db_path = _get_db_path()
    if not Path(db_path).exists():
        raise FileNotFoundError(f"Database not found at {db_path}")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    init_analysis_logs(conn)
    return conn


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="search_reviews",
            description="Search Steam reviews by tag or appid. Returns keyword stats and sample reviews.",
            inputSchema={
                "type": "object",
                "properties": {
                    "tag": {"type": "string", "description": "Tag name (e.g., 'Roguelike')"},
                    "appid": {"type": "integer", "description": "Steam App ID"},
                    "language": {"type": "string", "description": "Review language filter"},
                    "sample_count": {"type": "integer", "description": "Number of sample reviews (default: 20, max: 50)"},
                },
            },
        ),
        Tool(
            name="analyze_design",
            description="Analyze a game design document against competitor reviews. Returns design + competitor stats for feedback generation.",
            inputSchema={
                "type": "object",
                "properties": {
                    "design_file": {"type": "string", "description": "Path to design document"},
                    "design_text": {"type": "string", "description": "Design document text"},
                    "tag": {"type": "string", "description": "Competitor tag"},
                    "appids": {"type": "array", "items": {"type": "integer"}, "description": "Specific competitor app IDs"},
                },
            },
        ),
        Tool(
            name="get_analysis_logs",
            description="View error logs for diagnosing issues. Shows recent errors with suggestions.",
            inputSchema={
                "type": "object",
                "properties": {
                    "unresolved_only": {"type": "boolean", "description": "Only show unresolved errors (default: true)"},
                    "limit": {"type": "integer", "description": "Max results (default: 10)"},
                },
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        conn = _get_connection()
    except FileNotFoundError as e:
        result = {
            "error": True,
            "error_type": "db_not_found",
            "error_message": str(e),
            "suggestion": f"Run steam-crawler to collect data first. DB expected at: {_get_db_path()}",
        }
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]

    try:
        if name == "search_reviews":
            result = handle_search_reviews(conn, **arguments)
        elif name == "analyze_design":
            result = handle_analyze_design(conn, **arguments)
        elif name == "get_analysis_logs":
            result = handle_get_analysis_logs(conn, **arguments)
        else:
            result = {"error": True, "error_message": f"Unknown tool: {name}"}
    except Exception as e:
        from steam_analyzer.error_logger import make_error_response
        result = make_error_response(
            conn, name, json.dumps(arguments, ensure_ascii=False),
            "unknown", str(e),
            "Unexpected error. Check analysis_logs for details.",
        )
    finally:
        conn.close()

    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, default=str))]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
