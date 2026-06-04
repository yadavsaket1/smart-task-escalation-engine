"""
Unit Tests — Smart Task Escalation Engine
Run: pytest tests/ -v --cov=services --cov-report=term-missing
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from datetime import datetime, timedelta
from data.mock_data import (
    TASKS, EMPLOYEES, ESCALATIONS, AUDIT_LOG, NOTIFICATIONS,
    reset_all, add_task, sync_task_statuses
)
from services.escalation_service import (
    create_escalation, update_escalation_status,
    run_auto_escalation, detect_overdue_tasks,
    resolve_manager_hierarchy, get_all_escalations,
    get_pending_for_manager, mark_task_done,
)
from services.audit_service import get_audit_log
from services.operation_logger import log_operation, get_logs, get_log_stats, clear_logs


@pytest.fixture(autouse=True)
def clean():
    reset_all()
    sync_task_statuses()
    clear_logs()
    yield
    reset_all()
    clear_logs()


# ── Task lifecycle ────────────────────────────────────────────────────────────

class TestTaskLifecycle:
    def test_seed_overdue_tasks_have_overdue_status(self):
        assert TASKS["task-001"]["status"] == "overdue"
        assert TASKS["task-002"]["status"] == "overdue"

    def test_seed_future_task_is_on_track(self):
        assert TASKS["task-003"]["status"] == "on_track"

    def test_seed_done_task(self):
        assert TASKS["task-004"]["status"] == "done"

    def test_add_task_starts_as_on_track(self):
        t = add_task("New Task", "emp-001", datetime.now() + timedelta(days=3), "low")
        assert t["status"] == "on_track"

    def test_add_task_past_due_becomes_overdue_after_sync(self):
        t = add_task("Late Task", "emp-001", datetime.now() - timedelta(days=1), "medium")
        sync_task_statuses()
        assert TASKS[t["id"]]["status"] == "overdue"

    def test_mark_task_done_directly(self):
        mark_task_done("task-001", "mgr-001")
        assert TASKS["task-001"]["status"] == "done"

    def test_mark_task_done_cancels_active_escalation(self):
        esc = create_escalation("task-001", "system", "Auto-escalated overdue task.", 1)
        mark_task_done("task-001", "mgr-001")
        assert ESCALATIONS[esc["id"]]["status"] == "cancelled"

    def test_mark_already_done_raises(self):
        with pytest.raises(ValueError, match="already done"):
            mark_task_done("task-004", "mgr-001")

    def test_done_task_not_in_overdue_list(self):
        mark_task_done("task-001", "mgr-001")
        ids = [t["id"] for t in detect_overdue_tasks()]
        assert "task-001" not in ids

    def test_reset_restores_task_statuses(self):
        mark_task_done("task-001", "mgr-001")
        reset_all()
        sync_task_statuses()
        assert TASKS["task-001"]["status"] == "overdue"


# ── Hierarchy ─────────────────────────────────────────────────────────────────

class TestHierarchy:
    def test_l1_manager(self):
        mgrs = resolve_manager_hierarchy("emp-001", 1)
        assert len(mgrs) == 1 and mgrs[0]["id"] == "mgr-001"

    def test_two_levels(self):
        mgrs = resolve_manager_hierarchy("emp-001", 2)
        assert mgrs[1]["id"] == "dir-001"

    def test_stops_at_top(self):
        assert len(resolve_manager_hierarchy("emp-001", 5)) == 2

    def test_no_manager_for_director(self):
        assert resolve_manager_hierarchy("dir-001", 3) == []

    def test_circular_reference_safe(self, monkeypatch):
        monkeypatch.setitem(EMPLOYEES, "emp-001", {**EMPLOYEES["emp-001"], "manager_id": "emp-002"})
        monkeypatch.setitem(EMPLOYEES, "emp-002", {**EMPLOYEES["emp-002"], "manager_id": "emp-001"})
        assert len(resolve_manager_hierarchy("emp-001", 5)) <= 2


# ── Detect overdue ────────────────────────────────────────────────────────────

class TestDetect:
    def test_finds_overdue_tasks(self):
        ids = [t["id"] for t in detect_overdue_tasks()]
        assert "task-001" in ids
        assert "task-002" in ids

    def test_ignores_on_track(self):
        assert "task-003" not in [t["id"] for t in detect_overdue_tasks()]

    def test_ignores_done(self):
        assert "task-004" not in [t["id"] for t in detect_overdue_tasks()]

    def test_skips_already_escalated(self):
        create_escalation("task-001", "system", "Already escalated this task.", 1)
        assert "task-001" not in [t["id"] for t in detect_overdue_tasks()]


# ── Create escalation ─────────────────────────────────────────────────────────

class TestCreate:
    def test_creates_successfully(self):
        e = create_escalation("task-001", "system", "Task is critically overdue now.", 1)
        assert e["status"] == "pending"
        assert e["escalated_to"] == "mgr-001"
        assert e["id"] in ESCALATIONS

    def test_stores_in_escalations(self):
        create_escalation("task-001", "system", "Task needs attention immediately.", 1)
        assert len(ESCALATIONS) == 1

    def test_audit_event_created(self):
        create_escalation("task-001", "system", "Escalation audit test entry.", 1)
        assert any(ev["event_type"] == "escalation_created" for ev in get_audit_log())

    def test_notification_sent_to_manager(self):
        create_escalation("task-001", "system", "Notification test for manager.", 1)
        assert NOTIFICATIONS[0]["recipient_id"] == "mgr-001"

    def test_missing_task_id_raises(self):
        with pytest.raises(ValueError, match="required"):
            create_escalation("", "system", "Some reason here for test.", 1)

    def test_short_reason_raises(self):
        with pytest.raises(ValueError, match="10 characters"):
            create_escalation("task-001", "system", "Short", 1)

    def test_invalid_level_raises(self):
        with pytest.raises(ValueError, match="1, 2, or 3"):
            create_escalation("task-001", "system", "Valid reason here please.", 0)

    def test_task_not_found_raises(self):
        with pytest.raises(ValueError, match="not found"):
            create_escalation("task-999", "system", "Task does not exist here.", 1)

    def test_done_task_raises(self):
        with pytest.raises(ValueError, match="completed"):
            create_escalation("task-004", "system", "Task already done today.", 1)

    def test_duplicate_raises(self):
        create_escalation("task-001", "system", "First escalation for this task.", 1)
        with pytest.raises(ValueError, match="already exists"):
            create_escalation("task-001", "system", "Second escalation attempt now.", 1)

    def test_l2_escalates_to_director(self):
        e = create_escalation("task-001", "system", "Director needs to see this.", 2)
        assert e["escalated_to"] == "dir-001"

    def test_exceeds_depth_raises(self):
        with pytest.raises(ValueError, match="level 3"):
            create_escalation("task-001", "system", "Requesting too deep level.", 3)


# ── Update status ─────────────────────────────────────────────────────────────

class TestUpdate:
    def _esc(self):
        return create_escalation("task-001", "system", "Test escalation for status update.", 1)

    def test_pending_to_acknowledged(self):
        e = self._esc()
        u = update_escalation_status(e["id"], "acknowledged", "mgr-001")
        assert u["status"] == "acknowledged"
        assert u["acknowledged_at"] is not None

    def test_acknowledged_to_resolved(self):
        e = self._esc()
        update_escalation_status(e["id"], "acknowledged", "mgr-001")
        u = update_escalation_status(e["id"], "resolved", "mgr-001")
        assert u["status"] == "resolved"
        assert u["resolved_at"] is not None

    def test_resolve_marks_task_done(self):
        e = self._esc()
        update_escalation_status(e["id"], "acknowledged", "mgr-001")
        update_escalation_status(e["id"], "resolved", "mgr-001")
        assert TASKS["task-001"]["status"] == "done"

    def test_resolve_removes_from_overdue(self):
        e = self._esc()
        update_escalation_status(e["id"], "acknowledged", "mgr-001")
        update_escalation_status(e["id"], "resolved", "mgr-001")
        assert "task-001" not in [t["id"] for t in detect_overdue_tasks()]

    def test_cancel_from_pending(self):
        e = self._esc()
        u = update_escalation_status(e["id"], "cancelled", "mgr-001")
        assert u["status"] == "cancelled"

    def test_cancel_does_not_mark_task_done(self):
        e = self._esc()
        update_escalation_status(e["id"], "cancelled", "mgr-001")
        assert TASKS["task-001"]["status"] != "done"

    def test_invalid_transition_raises(self):
        e = self._esc()
        with pytest.raises(ValueError, match="Invalid transition"):
            update_escalation_status(e["id"], "resolved", "mgr-001")

    def test_terminal_state_raises(self):
        e = self._esc()
        update_escalation_status(e["id"], "acknowledged", "mgr-001")
        update_escalation_status(e["id"], "resolved", "mgr-001")
        with pytest.raises(ValueError, match="Invalid transition"):
            update_escalation_status(e["id"], "acknowledged", "mgr-001")

    def test_not_found_raises(self):
        with pytest.raises(ValueError, match="not found"):
            update_escalation_status("esc-999", "acknowledged", "mgr-001")


# ── Auto-escalation ───────────────────────────────────────────────────────────

class TestAuto:
    def test_escalates_overdue_tasks(self):
        assert len(run_auto_escalation()) == 2

    def test_skips_already_escalated(self):
        create_escalation("task-001", "system", "Pre-existing escalation today.", 1)
        assert len(run_auto_escalation()) == 1

    def test_all_marked_auto(self):
        for e in run_auto_escalation():
            assert e["triggered_by"] == "auto"

    def test_idempotent_second_run(self):
        run_auto_escalation()
        assert len(run_auto_escalation()) == 0


# ── Logger ────────────────────────────────────────────────────────────────────

class TestLogger:
    def test_logs_entry(self):
        log_operation("TEST", "message here")
        assert any(l["operation"] == "TEST" for l in get_logs())

    def test_filter_operation(self):
        log_operation("OP_A", "a"); log_operation("OP_B", "b")
        assert all(l["operation"] == "OP_A" for l in get_logs(operation_filter="OP_A"))

    def test_filter_level(self):
        log_operation("X", "m", level="ERROR"); log_operation("Y", "m", level="INFO")
        assert all(l["level"] == "ERROR" for l in get_logs(level_filter="ERROR"))

    def test_stats(self):
        log_operation("A", "m", level="SUCCESS"); log_operation("B", "m", level="ERROR")
        s = get_log_stats()
        assert s["SUCCESS"] >= 1 and s["ERROR"] >= 1

    def test_clear(self):
        log_operation("A", "msg"); clear_logs()
        assert get_log_stats()["TOTAL"] == 0
