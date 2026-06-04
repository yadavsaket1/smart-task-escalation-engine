"""
Mock Data Store
───────────────
In-memory data for the Smart Task Escalation Engine.
Task lifecycle: assigned → on_track → overdue → done
"""

from datetime import datetime, timedelta
import uuid

now = datetime.now()

EMPLOYEES = {
    "emp-001": {"id": "emp-001", "name": "Priya Sharma",  "email": "priya@demo.com",  "role": "employee", "manager_id": "mgr-001"},
    "emp-002": {"id": "emp-002", "name": "Rohan Mehta",   "email": "rohan@demo.com",  "role": "employee", "manager_id": "mgr-001"},
    "emp-003": {"id": "emp-003", "name": "Ananya Iyer",   "email": "ananya@demo.com", "role": "employee", "manager_id": "mgr-002"},
    "mgr-001": {"id": "mgr-001", "name": "Vikram Nair",   "email": "vikram@demo.com", "role": "manager",  "manager_id": "dir-001"},
    "mgr-002": {"id": "mgr-002", "name": "Sunita Rao",    "email": "sunita@demo.com", "role": "manager",  "manager_id": "dir-001"},
    "dir-001": {"id": "dir-001", "name": "Arjun Kapoor",  "email": "arjun@demo.com",  "role": "admin",    "manager_id": None},
}

# Seed tasks — status uses: on_track | overdue | done
# These are the ORIGINALS. reset_all() restores tasks to this exact state.
_SEED_TASKS = [
    {"id": "task-001", "title": "Complete Q3 Budget Report",  "assigned_to": "emp-001", "status": "overdue",   "due_date": now - timedelta(days=3), "priority": "high"},
    {"id": "task-002", "title": "Update Employee Handbook",   "assigned_to": "emp-002", "status": "overdue",   "due_date": now - timedelta(days=1), "priority": "medium"},
    {"id": "task-003", "title": "Prepare Onboarding Slides",  "assigned_to": "emp-003", "status": "on_track",  "due_date": now + timedelta(days=2), "priority": "low"},
    {"id": "task-004", "title": "Submit Compliance Audit",    "assigned_to": "emp-001", "status": "done",      "due_date": now - timedelta(days=5), "priority": "high"},
]

TASKS: dict = {t["id"]: dict(t) for t in _SEED_TASKS}

# Live stores
ESCALATIONS:   dict = {}
AUDIT_LOG:     list = []
NOTIFICATIONS: list = []


def new_id(prefix: str = "id") -> str:
    return f"{prefix}-{str(uuid.uuid4())[:8]}"


def reset_all():
    """Restore tasks to seed state and wipe all runtime stores."""
    TASKS.clear()
    for t in _SEED_TASKS:
        TASKS[t["id"]] = dict(t)   # fresh copy, not reference
    ESCALATIONS.clear()
    AUDIT_LOG.clear()
    NOTIFICATIONS.clear()


def add_task(title: str, assigned_to: str, due_date: datetime, priority: str) -> dict:
    """Creates a new task. Status starts as on_track."""
    tid = new_id("task")
    task = {
        "id":          tid,
        "title":       title,
        "assigned_to": assigned_to,
        "status":      "on_track",
        "due_date":    due_date,
        "priority":    priority,
    }
    TASKS[tid] = task
    return task


def compute_task_status(task: dict) -> str:
    """
    Derives the display status from task fields.
    done  → done
    due_date in past → overdue
    otherwise        → on_track
    """
    if task["status"] == "done":
        return "done"
    if task["due_date"] < datetime.now():
        return "overdue"
    return "on_track"


def sync_task_statuses():
    """
    Recalculates status for every non-done task based on due_date.
    Call this on each page load so newly overdue tasks appear correctly.
    """
    for task in TASKS.values():
        if task["status"] != "done":
            task["status"] = compute_task_status(task)
