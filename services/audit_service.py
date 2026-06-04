"""Audit Service — appends immutable events to AUDIT_LOG."""

from datetime import datetime
from data.mock_data import AUDIT_LOG, EMPLOYEES, new_id


def log_event(escalation_id: str, event_type: str, event_data: dict, triggered_by: str) -> dict:
    actor = EMPLOYEES.get(triggered_by, {})
    event = {
        "id":            new_id("audit"),
        "escalation_id": escalation_id,
        "event_type":    event_type,
        "event_data":    event_data,
        "triggered_by":  triggered_by,
        "actor_name":    actor.get("name", triggered_by),
        "timestamp":     datetime.now(),
    }
    AUDIT_LOG.append(event)
    return event


def get_audit_log(escalation_id: str = None) -> list:
    if escalation_id:
        return [e for e in AUDIT_LOG if e["escalation_id"] == escalation_id]
    return list(reversed(AUDIT_LOG))
