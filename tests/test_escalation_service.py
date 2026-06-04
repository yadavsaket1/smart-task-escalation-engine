"""
Unit Tests — Escalation Service
================================
Run:  pytest tests/ -v --cov=services --cov-report=term-missing
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch

from data.mock_data import (
    TASKS, EMPLOYEES, ESCALATIONS, AUDIT_LOG, NOTIFICATIONS,
    reset_demo_data
)
from services.escalation_service import (
    create_escalation,
    update_escalation_status,
    run_auto_escalation,
    detect_overdue_tasks,
    resolve_manager_hierarchy,
    get_all_escalations,
    get_pending_for_manager,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def clean_state():
    """Wipe runtime stores before every test so tests are isolated."""
    reset_demo_data()
    yield
    reset_demo_data()


# ── resolve_manager_hierarchy ─────────────────────────────────────────────────

class TestResolveManagerHierarchy:

    def test_returns_l1_manager_for_employee(self):
        # emp-001 reports to mgr-001
        managers = resolve_manager_hierarchy("emp-001", max_levels=1)
        assert len(managers) == 1
        assert managers[0]["id"] == "mgr-001"

    def test_returns_multiple_levels(self):
        # emp-001 → mgr-001 → dir-001
        managers = resolve_manager_hierarchy("emp-001", max_levels=2)
        assert len(managers) == 2
        assert managers[0]["id"] == "mgr-001"
        assert managers[1]["id"] == "dir-001"

    def test_stops_at_top_of_hierarchy(self):
        # dir-001 has no manager (manager_id = None)
        managers = resolve_manager_hierarchy("emp-001", max_levels=5)
        assert len(managers) == 2  # only 2 levels exist

    def test_returns_empty_for_employee_without_manager(self):
        managers = resolve_manager_hierarchy("dir-001", max_levels=3)
        assert managers == []

    def test_detects_circular_reference(self, monkeypatch):
        # Create a circular reporting chain
        monkeypatch.setitem(EMPLOYEES, "emp-001", {**EMPLOYEES["emp-001"], "manager_id": "emp-002"})
        monkeypatch.setitem(EMPLOYEES, "emp-002", {**EMPLOYEES["emp-002"], "manager_id": "emp-001"})
        managers = resolve_manager_hierarchy("emp-001", max_levels=5)
        # Should break on circular reference, not loop forever
        assert len(managers) <= 2


# ── detect_overdue_tasks ──────────────────────────────────────────────────────

class TestDetectOverdueTasks:

    def test_detects_overdue_in_progress_tasks(self):
        overdue = detect_overdue_tasks()
        task_ids = [t["id"] for t in overdue]
        assert "task-001" in task_ids   # due 3 days ago
        assert "task-002" in task_ids   # due 1 day ago

    def test_ignores_future_tasks(self):
        overdue = detect_overdue_tasks()
        task_ids = [t["id"] for t in overdue]
        assert "task-003" not in task_ids   # due in future

    def test_ignores_completed_tasks(self):
        overdue = detect_overdue_tasks()
        task_ids = [t["id"] for t in overdue]
        assert "task-004" not in task_ids   # completed

    def test_excludes_tasks_with_active_escalation(self):
        # Create an active escalation for task-001
        create_escalation("task-001", "emp-001", "Already escalated manually", 1)
        overdue = detect_overdue_tasks()
        task_ids = [t["id"] for t in overdue]
        assert "task-001" not in task_ids


# ── create_escalation ─────────────────────────────────────────────────────────

class TestCreateEscalation:

    def test_creates_escalation_successfully(self):
        esc = create_escalation("task-001", "emp-001", "Task is critically overdue.", 1)
        assert esc["task_id"] == "task-001"
        assert esc["status"] == "pending"
        assert esc["escalation_level"] == 1
        assert esc["escalated_to"] == "mgr-001"
        assert esc["id"] in ESCALATIONS

    def test_escalation_stored_in_memory(self):
        create_escalation("task-001", "emp-001", "Must be escalated now.", 1)
        assert len(ESCALATIONS) == 1

    def test_triggers_audit_event(self):
        create_escalation("task-001", "emp-001", "Need manager attention.", 1)
        assert len(AUDIT_LOG) >= 1
        event = next(e for e in AUDIT_LOG if e["event_type"] == "escalation_created")
        assert event is not None

    def test_triggers_notification(self):
        create_escalation("task-001", "emp-001", "Urgent escalation needed.", 1)
        assert len(NOTIFICATIONS) >= 1
        notif = NOTIFICATIONS[0]
        assert notif["recipient_id"] == "mgr-001"

    def test_raises_for_missing_task_id(self):
        with pytest.raises(ValueError, match="required"):
            create_escalation("", "emp-001", "Some reason here.", 1)

    def test_raises_for_short_reason(self):
        with pytest.raises(ValueError, match="10 characters"):
            create_escalation("task-001", "emp-001", "Short", 1)

    def test_raises_for_invalid_level_zero(self):
        with pytest.raises(ValueError, match="1, 2, or 3"):
            create_escalation("task-001", "emp-001", "Valid reason here.", 0)

    def test_raises_for_invalid_level_four(self):
        with pytest.raises(ValueError, match="1, 2, or 3"):
            create_escalation("task-001", "emp-001", "Valid reason here.", 4)

    def test_raises_for_nonexistent_task(self):
        with pytest.raises(ValueError, match="not found"):
            create_escalation("task-999", "emp-001", "Task does not exist.", 1)

    def test_raises_for_completed_task(self):
        with pytest.raises(ValueError, match="completed"):
            create_escalation("task-004", "emp-001", "Task is already done.", 1)

    def test_raises_for_duplicate_active_escalation(self):
        create_escalation("task-001", "emp-001", "First escalation for this task.", 1)
        with pytest.raises(ValueError, match="already exists"):
            create_escalation("task-001", "emp-001", "Second escalation attempt.", 1)

    def test_raises_when_level_exceeds_hierarchy_depth(self):
        # dir-001 has no manager; emp-001 → mgr-001 → dir-001 (2 levels max)
        with pytest.raises(ValueError, match="level 3 was requested"):
            # task-001 is assigned to emp-001 who only has 2 levels up
            create_escalation("task-001", "emp-001", "Requesting too deep a level.", 3)

    def test_l2_escalation_goes_to_director(self):
        esc = create_escalation("task-001", "emp-001", "Skip-level escalation needed.", 2)
        assert esc["escalated_to"] == "dir-001"
        assert esc["escalation_level"] == 2

    def test_auto_triggered_escalation_records_source(self):
        esc = create_escalation(
            "task-001", "system", "Auto-detected overdue.", 1, triggered_by="auto"
        )
        assert esc["triggered_by"] == "auto"


# ── update_escalation_status ──────────────────────────────────────────────────

class TestUpdateEscalationStatus:

    def _make_escalation(self):
        return create_escalation("task-001", "emp-001", "Needs manager attention.", 1)

    def test_pending_to_acknowledged(self):
        esc = self._make_escalation()
        updated = update_escalation_status(esc["id"], "acknowledged", "mgr-001")
        assert updated["status"] == "acknowledged"
        assert updated["acknowledged_at"] is not None

    def test_acknowledged_to_resolved(self):
        esc = self._make_escalation()
        update_escalation_status(esc["id"], "acknowledged", "mgr-001")
        resolved = update_escalation_status(esc["id"], "resolved", "mgr-001", "Fixed!")
        assert resolved["status"] == "resolved"
        assert resolved["resolved_at"] is not None

    def test_pending_to_cancelled(self):
        esc = self._make_escalation()
        cancelled = update_escalation_status(esc["id"], "cancelled", "mgr-001")
        assert cancelled["status"] == "cancelled"

    def test_acknowledged_to_cancelled(self):
        esc = self._make_escalation()
        update_escalation_status(esc["id"], "acknowledged", "mgr-001")
        cancelled = update_escalation_status(esc["id"], "cancelled", "mgr-001")
        assert cancelled["status"] == "cancelled"

    def test_invalid_transition_resolved_to_acknowledged(self):
        esc = self._make_escalation()
        update_escalation_status(esc["id"], "acknowledged", "mgr-001")
        update_escalation_status(esc["id"], "resolved", "mgr-001")
        with pytest.raises(ValueError, match="Invalid transition"):
            update_escalation_status(esc["id"], "acknowledged", "mgr-001")

    def test_invalid_transition_pending_to_resolved(self):
        esc = self._make_escalation()
        with pytest.raises(ValueError, match="Invalid transition"):
            update_escalation_status(esc["id"], "resolved", "mgr-001")

    def test_raises_for_nonexistent_escalation(self):
        with pytest.raises(ValueError, match="not found"):
            update_escalation_status("esc-999", "acknowledged", "mgr-001")

    def test_status_update_logged_to_audit(self):
        esc = self._make_escalation()
        initial_audit_count = len(AUDIT_LOG)
        update_escalation_status(esc["id"], "acknowledged", "mgr-001")
        assert len(AUDIT_LOG) > initial_audit_count


# ── run_auto_escalation ───────────────────────────────────────────────────────

class TestRunAutoEscalation:

    def test_escalates_all_overdue_tasks(self):
        created = run_auto_escalation()
        # task-001 and task-002 are overdue; task-003 is not; task-004 is completed
        assert len(created) == 2

    def test_skips_tasks_with_existing_escalation(self):
        create_escalation("task-001", "emp-001", "Pre-existing manual escalation.", 1)
        created = run_auto_escalation()
        # Only task-002 should be auto-escalated now
        assert len(created) == 1
        assert created[0]["task_id"] == "task-002"

    def test_auto_escalation_marked_as_auto_triggered(self):
        created = run_auto_escalation()
        for esc in created:
            assert esc["triggered_by"] == "auto"

    def test_idempotent_on_second_run(self):
        run_auto_escalation()
        second_run = run_auto_escalation()
        assert len(second_run) == 0   # nothing new to escalate


# ── get_pending_for_manager ───────────────────────────────────────────────────

class TestGetPendingForManager:

    def test_returns_pending_for_correct_manager(self):
        create_escalation("task-001", "emp-001", "Needs manager attention.", 1)
        pending = get_pending_for_manager("mgr-001")
        assert len(pending) == 1

    def test_returns_empty_for_wrong_manager(self):
        create_escalation("task-001", "emp-001", "Escalated to mgr-001.", 1)
        pending = get_pending_for_manager("mgr-002")
        assert len(pending) == 0

    def test_excludes_resolved_escalations(self):
        esc = create_escalation("task-001", "emp-001", "Needs attention.", 1)
        update_escalation_status(esc["id"], "acknowledged", "mgr-001")
        update_escalation_status(esc["id"], "resolved", "mgr-001")
        pending = get_pending_for_manager("mgr-001")
        assert len(pending) == 0
