"""
Escalation Service
──────────────────
Core business logic for the Smart Task Escalation Engine.

Task lifecycle:  on_track → overdue → done
Escalation path: overdue task → auto-escalation created →
                 pending → acknowledged → resolved (task = done)
"""

from datetime import datetime
from typing import Optional
from data.mock_data import TASKS, EMPLOYEES, ESCALATIONS, new_id
from services.audit_service import log_event
from services.notification_service import queue_notification
from services.operation_logger import log_operation

VALID_TRANSITIONS = {
    "pending":      ["acknowledged", "cancelled"],
    "acknowledged": ["resolved",     "cancelled"],
    "resolved":     [],
    "cancelled":    [],
}


# ── Hierarchy ─────────────────────────────────────────────────────────────────

def resolve_manager_hierarchy(employee_id: str, max_levels: int = 3) -> list:
    """Walks up reporting chain. Returns manager dicts L1→L3. Safe on circular refs."""
    managers, visited = [], {employee_id}
    current_id = EMPLOYEES.get(employee_id, {}).get("manager_id")
    while current_id and len(managers) < max_levels:
        if current_id in visited:
            break
        mgr = EMPLOYEES.get(current_id)
        if not mgr:
            break
        managers.append(mgr)
        visited.add(current_id)
        current_id = mgr.get("manager_id")
    return managers


# ── Detection ─────────────────────────────────────────────────────────────────

def detect_overdue_tasks() -> list:
    """
    Returns tasks with status == 'overdue' that have no active escalation.
    (Status is maintained by sync_task_statuses() in mock_data.)
    """
    overdue = []
    for task in TASKS.values():
        if task["status"] != "overdue":
            continue
        already = any(
            e for e in ESCALATIONS.values()
            if e["task_id"] == task["id"] and e["status"] in ("pending", "acknowledged")
        )
        if not already:
            overdue.append(task)

    log_operation(
        "DETECT_OVERDUE",
        f"Detected {len(overdue)} overdue task(s) without active escalation",
        detail=", ".join(t["title"] for t in overdue) if overdue else "None",
        level="INFO" if overdue else "SUCCESS",
    )
    return overdue


# ── Create escalation ─────────────────────────────────────────────────────────

def create_escalation(task_id: str, escalated_from_id: str, escalation_reason: str,
                      target_level: int = 1, triggered_by: str = "auto") -> dict:
    """
    Creates an escalation for an overdue task.
    Only called automatically — no manual escalation in this version.
    Raises ValueError on any business rule violation.
    """
    if not task_id or not escalation_reason:
        raise ValueError("task_id and escalation_reason are required.")
    if len(escalation_reason.strip()) < 10:
        raise ValueError("Escalation reason must be at least 10 characters.")
    if target_level not in (1, 2, 3):
        raise ValueError("target_level must be 1, 2, or 3.")

    task = TASKS.get(task_id)
    if not task:
        raise ValueError(f"Task not found: {task_id}")
    if task["status"] == "done":
        raise ValueError("Cannot escalate a completed task.")

    if any(e for e in ESCALATIONS.values()
           if e["task_id"] == task_id and e["status"] in ("pending", "acknowledged")):
        raise ValueError("An active escalation already exists for this task.")

    managers = resolve_manager_hierarchy(task["assigned_to"], max_levels=target_level)
    if not managers:
        raise ValueError("No manager found in hierarchy.")
    if len(managers) < target_level:
        raise ValueError(
            f"Only {len(managers)} manager level(s) found; level {target_level} requested."
        )
    target_manager = managers[target_level - 1]

    esc_id = new_id("esc")
    escalation = {
        "id":                esc_id,
        "task_id":           task_id,
        "task_title":        task["title"],
        "escalated_from":    escalated_from_id,
        "escalated_to":      target_manager["id"],
        "escalated_to_name": target_manager["name"],
        "escalation_level":  target_level,
        "status":            "pending",
        "escalation_reason": escalation_reason,
        "triggered_by":      triggered_by,
        "created_at":        datetime.now(),
        "acknowledged_at":   None,
        "resolved_at":       None,
    }
    ESCALATIONS[esc_id] = escalation

    log_operation("CREATE_ESCALATION",
                  f"'{task['title']}' → {target_manager['name']} (L{target_level})",
                  detail=f"ID: {esc_id} | Reason: {escalation_reason[:60]}",
                  level="SUCCESS", actor=escalated_from_id)

    log_event(esc_id, "escalation_created",
              {"task": task["title"], "reason": escalation_reason,
               "to": target_manager["name"], "level": target_level},
              escalated_from_id)

    queue_notification(esc_id, target_manager["id"], target_manager["name"],
                       task["title"], escalation_reason)

    return escalation


# ── Update status ─────────────────────────────────────────────────────────────

def update_escalation_status(escalation_id: str, new_status: str,
                              updated_by: str, note: Optional[str] = None) -> dict:
    """
    Updates escalation status following the state machine.

    When resolved → task status is set to 'done'.
    When cancelled → task stays overdue (can be re-escalated).
    """
    esc = ESCALATIONS.get(escalation_id)
    if not esc:
        raise ValueError(f"Escalation not found: {escalation_id}")

    current = esc["status"]
    allowed = VALID_TRANSITIONS.get(current, [])
    if new_status not in allowed:
        raise ValueError(
            f"Invalid transition: {current} → {new_status}. Allowed: {allowed}"
        )

    esc["status"] = new_status
    now = datetime.now()

    if new_status == "acknowledged":
        esc["acknowledged_at"] = now

    elif new_status == "resolved":
        esc["resolved_at"] = now
        # Mark the task as done — it will no longer appear as overdue
        if esc["task_id"] in TASKS:
            TASKS[esc["task_id"]]["status"] = "done"
            log_operation("TASK_DONE",
                          f"Task '{esc['task_title']}' marked as done after escalation resolved",
                          level="SUCCESS", actor=updated_by)

    log_operation("UPDATE_STATUS",
                  f"Escalation '{esc['task_title']}': {current} → {new_status}",
                  detail=f"Note: {note}" if note else "",
                  level="SUCCESS", actor=updated_by)

    log_event(escalation_id, f"escalation_{new_status}",
              {"from": current, "to": new_status, "note": note}, updated_by)

    return esc


# ── Mark task done directly ───────────────────────────────────────────────────

def mark_task_done(task_id: str, marked_by: str) -> dict:
    """
    Marks a task as done directly (without going through escalation).
    Also cancels any active escalation for the task.
    """
    task = TASKS.get(task_id)
    if not task:
        raise ValueError(f"Task not found: {task_id}")
    if task["status"] == "done":
        raise ValueError("Task is already done.")

    task["status"] = "done"

    # Cancel any active escalation for this task
    for esc in ESCALATIONS.values():
        if esc["task_id"] == task_id and esc["status"] in ("pending", "acknowledged"):
            esc["status"] = "cancelled"
            log_event(esc["id"], "escalation_cancelled",
                      {"reason": "Task marked done directly"}, marked_by)

    log_operation("TASK_DONE",
                  f"Task '{task['title']}' marked as done",
                  level="SUCCESS", actor=marked_by)

    log_event("system", "task_done",
              {"task_id": task_id, "title": task["title"]}, marked_by)

    return task


# ── Auto-escalate ─────────────────────────────────────────────────────────────

def run_auto_escalation() -> list:
    """Detects all overdue tasks and creates L1 escalations automatically."""
    overdue = detect_overdue_tasks()
    created = []
    log_operation("AUTO_ESCALATE", f"Job started — {len(overdue)} candidate(s)", level="INFO")

    for task in overdue:
        try:
            esc = create_escalation(
                task_id=task["id"],
                escalated_from_id="system",
                escalation_reason=(
                    f"Task overdue since {task['due_date'].strftime('%Y-%m-%d')}. "
                    "Auto-escalated by system."
                ),
                target_level=1,
                triggered_by="auto",
            )
            created.append(esc)
        except ValueError:
            pass

    log_operation("AUTO_ESCALATE", f"Complete — {len(created)} escalation(s) created",
                  level="SUCCESS" if created else "INFO")
    return created


# ── Read helpers ──────────────────────────────────────────────────────────────

def get_all_escalations() -> list:
    return sorted(ESCALATIONS.values(), key=lambda e: e["created_at"], reverse=True)

def get_escalation_history(task_id: str) -> list:
    return [e for e in ESCALATIONS.values() if e["task_id"] == task_id]

def get_pending_for_manager(manager_id: str) -> list:
    return [e for e in ESCALATIONS.values()
            if e["escalated_to"] == manager_id and e["status"] in ("pending", "acknowledged")]
