from steam_analyzer.error_logger import get_all_logs


def handle_get_analysis_logs(conn, unresolved_only=True, limit=10):
    logs = get_all_logs(conn, unresolved_only=unresolved_only, limit=limit)
    return {"logs": logs, "count": len(logs), "unresolved_only": unresolved_only}
