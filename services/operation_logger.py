"""
Operation Logger
────────────────
Logs every engine operation to:
  1. _LOGS list  — shown live in Streamlit Ops Log tab
  2. operation_logs.txt — persists to disk for submission screenshots
"""

import os
from datetime import datetime

_LOGS: list[dict] = []
_LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "operation_logs.txt")


def log_operation(operation: str, message: str, detail: str = "",
                  level: str = "INFO", actor: str = "system") -> dict:
    entry = {
        "id":        len(_LOGS) + 1,
        "timestamp": datetime.now(),
        "operation": operation,
        "message":   message,
        "detail":    detail,
        "level":     level,
        "actor":     actor,
    }
    _LOGS.append(entry)
    _write(entry)
    return entry


def get_logs(operation_filter: str = None, level_filter: str = None) -> list:
    logs = list(reversed(_LOGS))
    if operation_filter:
        logs = [l for l in logs if l["operation"] == operation_filter]
    if level_filter:
        logs = [l for l in logs if l["level"] == level_filter]
    return logs


def get_log_stats() -> dict:
    stats = {"TOTAL": len(_LOGS), "SUCCESS": 0, "INFO": 0, "WARNING": 0, "ERROR": 0}
    for e in _LOGS:
        lvl = e.get("level", "INFO")
        stats[lvl] = stats.get(lvl, 0) + 1
    return stats


def export_logs_as_text() -> str:
    if not _LOGS:
        return "No operations logged yet."
    lines = ["=" * 60,
             "SMART TASK ESCALATION ENGINE — OPERATION LOG",
             f"Exported: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
             f"Total entries: {len(_LOGS)}", "=" * 60, ""]
    for e in _LOGS:
        ts = e["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
        lines.append(f"[{ts}] [{e['level']:7}] [{e['operation']}] {e['message']}")
        if e["detail"]:
            lines.append(f"          ↳ {e['detail']}")
    return "\n".join(lines)


def clear_logs():
    _LOGS.clear()
    try:
        open(_LOG_FILE, "w").close()
    except Exception:
        pass


def _write(entry: dict):
    try:
        ts   = entry["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{ts}] [{entry['level']:7}] [{entry['operation']}] {entry['message']}"
        if entry["detail"]:
            line += f" | {entry['detail']}"
        with open(_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass
