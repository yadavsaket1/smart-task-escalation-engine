"""
Smart Task Escalation Engine — MCP Server
==========================================
Exposes escalation engine tools to Claude (VS Code extension) via
the Model Context Protocol (MCP).

Claude in VS Code can call these tools directly:
  - detect_overdue_tasks
  - create_escalation
  - update_escalation_status
  - get_escalation_history
  - get_audit_log
  - run_auto_escalation
  - get_all_escalations

Setup (add to VS Code Claude extension settings):
  {
    "mcpServers": {
      "escalation-engine": {
        "command": "python",
        "args": ["mcp_server.py"],
        "cwd": "<absolute path to this folder>"
      }
    }
  }

Run standalone to test:
  python mcp_server.py
"""

import sys
import os
import json

# ── Ensure imports resolve from this file's folder ────────────────────────────
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

from services.escalation_service import (
    detect_overdue_tasks,
    create_escalation,
    update_escalation_status,
    run_auto_escalation,
    get_all_escalations,
    get_escalation_history,
)
from services.audit_service import get_audit_log
from data.mock_data import TASKS, EMPLOYEES

# ── Helpers ───────────────────────────────────────────────────────────────────

def _fmt_dt(dt):
    return dt.strftime("%Y-%m-%d %H:%M") if dt else None


def _serialise(obj):
    """Make any escalation/task/audit dict JSON-safe (datetime → string)."""
    if isinstance(obj, list):
        return [_serialise(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _fmt_dt(v) if hasattr(v, "strftime") else v for k, v in obj.items()}
    return obj


# ── MCP Server ────────────────────────────────────────────────────────────────

app = Server("escalation-engine")


@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="detect_overdue_tasks",
            description=(
                "Scans all tasks and returns those that are overdue "
                "(past due date, still in progress, no active escalation)."
            ),
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        types.Tool(
            name="create_escalation",
            description=(
                "Creates a new escalation for a task. "
                "Validates task eligibility, resolves manager hierarchy, "
                "creates the escalation record, and queues an email notification."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "ID of the task to escalate (e.g. task-001)",
                    },
                    "escalated_from_id": {
                        "type": "string",
                        "description": "ID of the user triggering the escalation (e.g. emp-001)",
                    },
                    "escalation_reason": {
                        "type": "string",
                        "description": "Reason for escalation (minimum 10 characters)",
                    },
                    "target_level": {
                        "type": "integer",
                        "description": "Hierarchy level: 1=direct manager, 2=skip-level, 3=executive",
                        "enum": [1, 2, 3],
                        "default": 1,
                    },
                },
                "required": ["task_id", "escalated_from_id", "escalation_reason"],
            },
        ),
        types.Tool(
            name="update_escalation_status",
            description=(
                "Updates the status of an escalation. "
                "Valid transitions: pending→acknowledged, acknowledged→resolved, any→cancelled."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "escalation_id": {
                        "type": "string",
                        "description": "ID of the escalation to update",
                    },
                    "new_status": {
                        "type": "string",
                        "enum": ["acknowledged", "resolved", "cancelled"],
                        "description": "New status to set",
                    },
                    "updated_by": {
                        "type": "string",
                        "description": "ID of the user making the update",
                    },
                    "note": {
                        "type": "string",
                        "description": "Optional resolution note",
                    },
                },
                "required": ["escalation_id", "new_status", "updated_by"],
            },
        ),
        types.Tool(
            name="get_escalation_history",
            description="Returns all escalations for a specific task, newest first.",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "ID of the task",
                    }
                },
                "required": ["task_id"],
            },
        ),
        types.Tool(
            name="get_all_escalations",
            description="Returns all escalations across all tasks, newest first.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        types.Tool(
            name="run_auto_escalation",
            description=(
                "Automatically detects all overdue tasks and creates "
                "L1 escalations for each one. Returns list of created escalations."
            ),
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        types.Tool(
            name="get_audit_log",
            description=(
                "Returns the full audit trail. "
                "Optionally filter by escalation_id."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "escalation_id": {
                        "type": "string",
                        "description": "Filter by escalation ID (optional)",
                    }
                },
                "required": [],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:

    try:
        if name == "detect_overdue_tasks":
            result = detect_overdue_tasks()
            if not result:
                text = "✅ No overdue tasks found. All tasks are on track."
            else:
                lines = [f"⚠️ Found {len(result)} overdue task(s):\n"]
                for t in result:
                    lines.append(
                        f"  • [{t['id']}] {t['title']}\n"
                        f"    Assigned to: {t['assigned_to']} | "
                        f"Due: {_fmt_dt(t['due_date'])} | "
                        f"Priority: {t['priority']}"
                    )
                text = "\n".join(lines)

        elif name == "create_escalation":
            esc = create_escalation(
                task_id=arguments["task_id"],
                escalated_from_id=arguments["escalated_from_id"],
                escalation_reason=arguments["escalation_reason"],
                target_level=arguments.get("target_level", 1),
                triggered_by="mcp",
            )
            text = (
                f"✅ Escalation created successfully!\n\n"
                f"  ID:          {esc['id']}\n"
                f"  Task:        {esc['task_title']}\n"
                f"  Escalated to: {esc['escalated_to_name']} (Level {esc['escalation_level']})\n"
                f"  Status:      {esc['status']}\n"
                f"  Reason:      {esc['escalation_reason']}\n"
                f"  Created at:  {_fmt_dt(esc['created_at'])}\n\n"
                f"📧 Email notification queued for {esc['escalated_to_name']}."
            )

        elif name == "update_escalation_status":
            esc = update_escalation_status(
                escalation_id=arguments["escalation_id"],
                new_status=arguments["new_status"],
                updated_by=arguments["updated_by"],
                note=arguments.get("note"),
            )
            text = (
                f"✅ Status updated!\n\n"
                f"  Escalation: {esc['id']}\n"
                f"  Task:       {esc['task_title']}\n"
                f"  New status: {esc['status']}\n"
                f"  Updated by: {arguments['updated_by']}"
            )

        elif name == "get_escalation_history":
            history = get_escalation_history(arguments["task_id"])
            if not history:
                text = f"No escalations found for task {arguments['task_id']}."
            else:
                lines = [f"📋 {len(history)} escalation(s) for task {arguments['task_id']}:\n"]
                for e in history:
                    lines.append(
                        f"  • [{e['id']}] {e['status'].upper()}\n"
                        f"    → {e['escalated_to_name']} (L{e['escalation_level']}) | "
                        f"Created: {_fmt_dt(e['created_at'])}\n"
                        f"    Reason: {e['escalation_reason'][:80]}"
                    )
                text = "\n".join(lines)

        elif name == "get_all_escalations":
            all_esc = get_all_escalations()
            if not all_esc:
                text = "No escalations exist yet."
            else:
                lines = [f"📋 {len(all_esc)} total escalation(s):\n"]
                for e in all_esc:
                    lines.append(
                        f"  • [{e['id']}] {e['task_title']} — {e['status'].upper()}\n"
                        f"    → {e['escalated_to_name']} (L{e['escalation_level']}) | "
                        f"{_fmt_dt(e['created_at'])}"
                    )
                text = "\n".join(lines)

        elif name == "run_auto_escalation":
            created = run_auto_escalation()
            if not created:
                text = "✅ Auto-escalation complete. No new overdue tasks to escalate."
            else:
                lines = [f"🚀 Auto-escalation complete! {len(created)} escalation(s) created:\n"]
                for e in created:
                    lines.append(
                        f"  • {e['task_title']}\n"
                        f"    → {e['escalated_to_name']} (L{e['escalation_level']})"
                    )
                text = "\n".join(lines)

        elif name == "get_audit_log":
            eid = arguments.get("escalation_id")
            events = get_audit_log(escalation_id=eid)
            if not events:
                text = "No audit events found."
            else:
                lines = [f"🔍 {len(events)} audit event(s):\n"]
                for ev in events[:20]:  # cap at 20 for readability
                    lines.append(
                        f"  • [{_fmt_dt(ev['timestamp'])}] {ev['event_type']}\n"
                        f"    Actor: {ev['actor_name']} | "
                        f"Escalation: {ev['escalation_id']}"
                    )
                text = "\n".join(lines)

        else:
            text = f"Unknown tool: {name}"

    except ValueError as e:
        text = f"❌ Error: {e}"
    except Exception as e:
        text = f"❌ Unexpected error in {name}: {e}"

    return [types.TextContent(type="text", text=text)]


# ── Entry point ───────────────────────────────────────────────────────────────

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
