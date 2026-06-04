"""
Notification Service
─────────────────────
Sends real emails via Gmail API.
Falls back gracefully if Gmail is unavailable — app keeps running.

Email address format: firstname.lastname.powerweave@yopmail.com
"""

from datetime import datetime
from data.mock_data import NOTIFICATIONS, new_id
from services.audit_service import log_event
from services.gmail_service import send_email, name_to_email
from services.operation_logger import log_operation


def queue_notification(escalation_id: str, recipient_id: str, recipient_name: str,
                        task_title: str, escalation_reason: str) -> dict:
    """
    Builds the notification record, sends the real email via Gmail,
    and appends to the in-memory NOTIFICATIONS list.

    Email is sent to:  firstname.lastname.powerweave@yopmail.com

    If Gmail fails (credentials missing, network error etc.) the notification
    is still recorded with status='failed' — the app does not crash.
    """
    to_email = name_to_email(recipient_name)
    subject  = f"[Escalation] Action Required: {task_title}"
    body     = (
        f"Hi {recipient_name},\n\n"
        f"A task assigned to your team has been escalated to you.\n\n"
        f"  Task   : {task_title}\n"
        f"  Reason : {escalation_reason}\n\n"
        f"Please log in to the Powerweave HRMS portal to acknowledge "
        f"and take action on this escalation.\n\n"
        f"If you have already resolved this, you can ignore this email.\n\n"
        f"— Smart Task Escalation Engine\n"
        f"  Powerweave HRMS\n"
    )

    # ── Send real email ───────────────────────────────────────────────────────
    result = send_email(to_name=recipient_name, subject=subject, body=body)

    # ── Build notification record ─────────────────────────────────────────────
    notif = {
        "id":                new_id("notif"),
        "escalation_id":     escalation_id,
        "recipient_id":      recipient_id,
        "recipient_name":    recipient_name,
        "recipient_email":   to_email,
        "task_title":        task_title,
        "escalation_reason": escalation_reason,
        "channel":           "email",
        "status":            "sent" if result["success"] else "failed",
        "error":             result.get("error"),
        "sent_at":           datetime.now(),
        "subject":           subject,
        "body":              body,
    }
    NOTIFICATIONS.append(notif)

    # ── Log to audit trail ────────────────────────────────────────────────────
    log_event(
        escalation_id,
        "notification_sent",
        {
            "recipient":  recipient_name,
            "email":      to_email,
            "channel":    "email",
            "subject":    subject,
            "status":     notif["status"],
            "error":      result.get("error"),
        },
        "system",
    )

    # ── Log to ops log ────────────────────────────────────────────────────────
    if result["success"]:
        log_operation(
            "NOTIFICATION_SENT",
            f"Email sent → {to_email}",
            detail=f"Subject: {subject}",
            level="SUCCESS",
            actor="system",
        )
    else:
        log_operation(
            "NOTIFICATION_SENT",
            f"Email FAILED → {to_email}",
            detail=f"Error: {result.get('error')}",
            level="ERROR",
            actor="system",
        )

    return notif


def get_all_notifications() -> list:
    return list(reversed(NOTIFICATIONS))
