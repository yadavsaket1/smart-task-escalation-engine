"""
Smart Task Escalation Engine — Streamlit Demo
Run: streamlit run streamlit_app.py
"""

import sys, os, logging

ROOT = os.path.dirname(os.path.abspath(__file__))
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(ROOT, "crash.log"), encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logging.getLogger("streamlit.runtime.scriptrunner_utils.script_run_context").setLevel(logging.ERROR)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import streamlit as st
st.set_page_config(page_title="Task Escalation Engine", page_icon="🚨",
                   layout="wide", initial_sidebar_state="expanded")

st.markdown("""<style>
.main .block-container{padding:1rem 1.5rem;max-width:1300px}
h1{font-size:1.35rem!important;font-weight:700!important;margin:0 0 .1rem!important}
h2{font-size:1.05rem!important;font-weight:600!important;margin:0 0 .1rem!important}
html,body,[class*="css"]{font-size:13px}
[data-testid="metric-container"]{background:#f8f9fc;border:1px solid #e8eaf0;border-radius:8px;padding:.35rem .5rem!important}
[data-testid="metric-container"] label{font-size:.68rem!important;color:#666}
[data-testid="metric-container"] [data-testid="stMetricValue"]{font-size:1.15rem!important;font-weight:700}
.stButton>button{padding:.22rem .65rem!important;font-size:.76rem!important;border-radius:6px!important;height:auto!important}
.stTabs [data-baseweb="tab"]{font-size:.8rem!important;padding:.3rem .75rem!important}
hr{margin:.4rem 0!important;border-color:#eee}
.stCaption,[data-testid="stCaptionContainer"]{font-size:.7rem!important;color:#999}
[data-testid="stSidebar"] .block-container{padding:.75rem!important}

/* task card */
.tcard{border-radius:8px;padding:.5rem .7rem;margin-bottom:.4rem;font-size:.8rem;
       border:1px solid #e0e0e0}

/* lifecycle pill */
.pill{display:inline-block;padding:2px 10px;border-radius:12px;font-size:.67rem;
      font-weight:700;letter-spacing:.04em;text-transform:uppercase}
.p-on_track {background:#e8f5e9;color:#2e7d32;border:1px solid #a5d6a7}
.p-overdue  {background:#fff3e0;color:#e65100;border:1px solid #ffcc80}
.p-escalated{background:#fce4ec;color:#c62828;border:1px solid #ef9a9a}
.p-done     {background:#e3f2fd;color:#1565c0;border:1px solid #90caf9}

/* escalation row */
.erow{border-radius:0 8px 8px 0;padding:.45rem .65rem;margin-bottom:.35rem;
      font-size:.79rem;border:1px solid #e0e0e0}

/* notification */
.notif{background:#f0f4ff;border-left:3px solid #4c7ef3;border-radius:0 6px 6px 0;
       padding:.35rem .55rem;margin-bottom:.3rem;font-size:.76rem}

/* ops log */
.logbox{background:#1a1a2e;border-radius:8px;padding:.6rem .8rem;
        max-height:450px;overflow-y:auto;font-family:'Courier New',monospace;font-size:.72rem}
.ls{color:#4caf50}.li{color:#4fc3f7}.lw{color:#ffb74d}.le{color:#ef5350}.lg{color:#666}

.lbl{font-size:.68rem;font-weight:700;text-transform:uppercase;letter-spacing:.05em;
     color:#888;margin-bottom:.3rem}
</style>""", unsafe_allow_html=True)

# ── Imports ───────────────────────────────────────────────────────────────────
try:
    import pandas as pd
    from datetime import datetime, date, timedelta
    from data.mock_data import (
        TASKS, EMPLOYEES, ESCALATIONS, NOTIFICATIONS,
        reset_all, add_task, sync_task_statuses
    )
    from services.escalation_service import (
        create_escalation, update_escalation_status,
        run_auto_escalation, detect_overdue_tasks,
        get_all_escalations, mark_task_done,
    )
    from services.audit_service import get_audit_log
    from services.notification_service import get_all_notifications
    from services.operation_logger import (
        log_operation, get_logs, clear_logs, export_logs_as_text, get_log_stats,
    )
except Exception as exc:
    logging.exception("STARTUP ERROR")
    st.error(f"❌ {exc}")
    st.caption("Check crash.log for full traceback.")
    st.stop()

# ── Sync statuses on every page load ─────────────────────────────────────────
sync_task_statuses()

# ── Helpers ───────────────────────────────────────────────────────────────────
def fdt(dt):
    return "—" if dt is None else dt.strftime("%d %b, %H:%M")

def ename(eid):
    return EMPLOYEES.get(eid, {}).get("name", eid)

PDOT  = {"high": "🔴", "medium": "🟡", "low": "🟢"}
LCOL  = {"SUCCESS": "ls", "INFO": "li", "WARNING": "lw", "ERROR": "le"}

ESC_BORDER = {"pending": "#e74c3c", "acknowledged": "#f39c12",
              "resolved": "#27ae60", "cancelled": "#aaa"}

def task_pill(task):
    """Returns the correct lifecycle pill HTML for a task."""
    status = task["status"]
    # Check if task has an active escalation — show escalated pill
    has_active_esc = any(
        e for e in ESCALATIONS.values()
        if e["task_id"] == task["id"] and e["status"] in ("pending", "acknowledged")
    )
    if has_active_esc:
        return '<span class="pill p-escalated">escalated</span>'
    labels = {"on_track": "on track", "overdue": "overdue", "done": "done"}
    css    = {"on_track": "p-on_track", "overdue": "p-overdue", "done": "p-done"}
    lbl = labels.get(status, status)
    cls = css.get(status, "p-on_track")
    return f'<span class="pill {cls}">{lbl}</span>'

def task_border_color(task):
    if task["status"] == "done":          return "#90caf9"
    has_esc = any(e for e in ESCALATIONS.values()
                  if e["task_id"] == task["id"] and e["status"] in ("pending","acknowledged"))
    if has_esc:                            return "#e74c3c"
    if task["status"] == "overdue":       return "#ff9800"
    return "#66bb6a"

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🚨 Escalation Engine")
    st.caption("SDLR Demo · Powerweave HRMS")
    st.divider()

    actors = {v["name"]: k for k, v in EMPLOYEES.items()}
    sel    = st.selectbox("👤 Acting as", list(actors.keys()), index=3)
    actor_id   = actors[sel]
    actor_role = EMPLOYEES[actor_id]["role"]
    st.caption(f"Role: `{actor_role}`")
    st.divider()

    total   = len(TASKS)
    on_t    = sum(1 for t in TASKS.values() if t["status"] == "on_track")
    ov      = sum(1 for t in TASKS.values() if t["status"] == "overdue")
    done_c  = sum(1 for t in TASKS.values() if t["status"] == "done")
    c1,c2   = st.columns(2)
    c1.metric("Total",    total)
    c2.metric("On Track", on_t)
    c3,c4   = st.columns(2)
    c3.metric("Overdue",  ov)
    c4.metric("Done",     done_c)

    st.divider()
    stats = get_log_stats()
    st.caption("**Ops log**")
    l1,l2,l3 = st.columns(3)
    l1.metric("✅", stats["SUCCESS"])
    l2.metric("⚠️", stats["WARNING"])
    l3.metric("❌", stats["ERROR"])
    st.divider()

    if st.button("🔄 Reset Demo", use_container_width=True):
        reset_all(); clear_logs()
        sync_task_statuses()
        log_operation("RESET_DEMO", "Demo reset", level="INFO", actor=sel)
        st.rerun()

# ── Tabs ──────────────────────────────────────────────────────────────────────
t1, t2, t3 = st.tabs(["🚨 Live Demo", "📋 Ops Log", "📄 Docs"])

# ═══════════════════════════════════════════════════════════
# TAB 1 — LIVE DEMO
# ═══════════════════════════════════════════════════════════
with t1:
    # ── Top bar ───────────────────────────────────────────────────────────────
    hc1,hc2,hc3,hc4,hc5,hc6 = st.columns(6)
    hc1.markdown("## 🚨 Task Escalation Engine")
    all_esc = get_all_escalations()
    active  = [e for e in all_esc if e["status"] in ("pending","acknowledged")]
    hc2.metric("Tasks",       total)
    hc3.metric("On Track",    on_t)
    hc4.metric("Overdue",     ov)
    hc5.metric("Escalations", len(active))
    hc6.metric("Done",        done_c)
    st.divider()

    # ── 3-column layout: Tasks | Add Task + Auto | Active Escalations ─────────
    col_a, col_b, col_c = st.columns([1.2, 0.9, 1.2], gap="medium")

    # ── Col A: Task list ──────────────────────────────────────────────────────
    with col_a:
        st.markdown('<div class="lbl">All Tasks</div>', unsafe_allow_html=True)
        for tid, task in TASKS.items():
            bc   = task_border_color(task)
            pill = task_pill(task)
            st.markdown(f"""
            <div class="tcard" style="border-left:3px solid {bc}">
              <div style="display:flex;justify-content:space-between;align-items:center">
                <span style="font-weight:600">{PDOT[task['priority']]} {task['title']}</span>
                {pill}
              </div>
              <div style="color:#777;font-size:.7rem;margin-top:3px">
                👤 {ename(task['assigned_to'])}
                &nbsp;·&nbsp; 📅 Due: {fdt(task['due_date'])}
              </div>
            </div>""", unsafe_allow_html=True)

            # Mark Done — hidden once task is escalated; resolve via Ack → Resolve
            has_active_esc = any(
                e for e in ESCALATIONS.values()
                if e["task_id"] == tid and e["status"] in ("pending", "acknowledged")
            )
            if task["status"] != "done" and not has_active_esc:
                if st.button("✅ Mark Done", key=f"done_{tid}", use_container_width=False):
                    try:
                        mark_task_done(tid, actor_id)
                        st.success(f"'{task['title']}' marked as done.")
                        st.rerun()
                    except ValueError as err:
                        st.error(str(err))

    # ── Col B: Add Task + Auto-Escalate ──────────────────────────────────────
    with col_b:
        # Auto-escalate
        st.markdown('<div class="lbl">Auto-Escalate</div>', unsafe_allow_html=True)
        st.caption("Finds all overdue tasks and raises L1 escalations.")
        if st.button("🚀 Run Auto-Escalation", use_container_width=True, type="primary"):
            try:
                created = run_auto_escalation()
                if created:
                    st.success(f"✅ {len(created)} escalation(s) created")
                    for e in created:
                        st.caption(f"↗ {e['task_title']} → {e['escalated_to_name']}")
                else:
                    st.info("No new overdue tasks to escalate.")
                st.rerun()
            except Exception as ex:
                st.error(str(ex))

        st.divider()

        # Add Task form
        st.markdown('<div class="lbl">Add Task</div>', unsafe_allow_html=True)
        employee_names = {
            v["name"]: k for k, v in EMPLOYEES.items() if v["role"] == "employee"
        }
        with st.form("add_task_form", clear_on_submit=True):
            t_title    = st.text_input("Task title", placeholder="e.g. Review HR Policy")
            t_assignee = st.selectbox("Assign to", list(employee_names.keys()))
            t_due      = st.date_input("Due date",
                                       value=date.today() + timedelta(days=3),
                                       min_value=date.today() - timedelta(days=30))
            t_priority = st.select_slider("Priority", ["low", "medium", "high"], value="medium")

            if st.form_submit_button("➕ Add Task", use_container_width=True):
                if not t_title.strip():
                    st.error("Task title is required.")
                else:
                    due_dt = datetime.combine(t_due, datetime.min.time()).replace(
                        hour=18, minute=0)
                    new_t = add_task(
                        title=t_title.strip(),
                        assigned_to=employee_names[t_assignee],
                        due_date=due_dt,
                        priority=t_priority,
                    )
                    log_operation("ADD_TASK",
                                  f"Task added: '{new_t['title']}' → {t_assignee}",
                                  level="SUCCESS", actor=actor_id)
                    st.success(f"✅ Task added!")
                    st.rerun()

    # ── Col C: Active escalations ─────────────────────────────────────────────
    with col_c:
        st.markdown('<div class="lbl">Active Escalations</div>', unsafe_allow_html=True)
        if not active:
            st.caption("No active escalations. Run auto-escalation to detect overdue tasks.")
        for esc in active:
            bc = ESC_BORDER.get(esc["status"], "#ccc")
            st.markdown(f"""
            <div class="erow" style="border-left:4px solid {bc}">
              <div style="display:flex;justify-content:space-between;align-items:center">
                <b style="font-size:.8rem">{esc['task_title']}</b>
                <span class="pill {'p-escalated' if esc['status']=='pending' else 'p-overdue'}">{esc['status']}</span>
              </div>
              <div style="color:#555;font-size:.7rem;margin-top:2px">
                → {esc['escalated_to_name']} &nbsp;·&nbsp; L{esc['escalation_level']}
                &nbsp;·&nbsp; {fdt(esc['created_at'])}
              </div>
              <div style="color:#888;font-size:.7rem;font-style:italic;margin-top:1px">
                {esc['escalation_reason'][:70]}{'…' if len(esc['escalation_reason'])>70 else ''}
              </div>
            </div>""", unsafe_allow_html=True)

            b1, b2, b3 = st.columns(3)
            if esc["status"] == "pending":
                if b1.button("✅ Ack", key=f"a_{esc['id']}", use_container_width=True):
                    update_escalation_status(esc["id"], "acknowledged", actor_id)
                    st.rerun()
            if esc["status"] == "acknowledged":
                if b2.button("🟢 Resolve", key=f"r_{esc['id']}", use_container_width=True):
                    update_escalation_status(esc["id"], "resolved", actor_id)
                    st.rerun()
            if b3.button("✖ Cancel", key=f"c_{esc['id']}", use_container_width=True):
                update_escalation_status(esc["id"], "cancelled", actor_id)
                st.rerun()

    st.divider()

    # ── Bottom row: History | Notifications | Audit ───────────────────────────
    bc1, bc2, bc3 = st.columns([1, 1, 2], gap="medium")

    with bc1:
        st.markdown('<div class="lbl">Escalation History</div>', unsafe_allow_html=True)
        closed = [e for e in all_esc if e["status"] in ("resolved","cancelled")]
        if not closed:
            st.caption("No closed escalations yet.")
        for e in closed:
            ic = "🟢" if e["status"] == "resolved" else "⚫"
            st.markdown(f"""<div style="font-size:.77rem;padding:.25rem 0;border-bottom:1px solid #f0f0f0">
              {ic} <b>{e['task_title']}</b><br>
              <span style="color:#888">→ {e['escalated_to_name']} · {fdt(e['created_at'])}</span>
            </div>""", unsafe_allow_html=True)

    with bc2:
        st.markdown('<div class="lbl">Notifications Sent</div>', unsafe_allow_html=True)
        notifs = get_all_notifications()
        if not notifs:
            st.caption("None yet.")
        for n in notifs[:4]:
            status_icon = "✅" if n.get("status") == "sent" else "❌"
            st.markdown(f"""<div class="notif">
              <b>{n['recipient_name']}</b>
              <span style="color:#888;font-size:.7rem"> → {n.get('recipient_email','')}</span><br>
              <span style="color:#555">{n['subject'][:52]}…</span><br>
              <span style="color:#aaa;font-size:.67rem">{status_icon} {fdt(n['sent_at'])}</span>
            </div>""", unsafe_allow_html=True)

    with bc3:
        st.markdown('<div class="lbl">Audit Log</div>', unsafe_allow_html=True)
        evts = get_audit_log()
        if not evts:
            st.caption("No audit events yet.")
        else:
            rows = [{"Time":  e["timestamp"].strftime("%H:%M:%S"),
                     "Event": e["event_type"].replace("_"," ").title(),
                     "Actor": e["actor_name"],
                     "Ref":   e["escalation_id"]} for e in evts[:12]]
            st.dataframe(pd.DataFrame(rows), use_container_width=True,
                         hide_index=True, height=200)

# ═══════════════════════════════════════════════════════════
# TAB 2 — OPS LOG
# ═══════════════════════════════════════════════════════════
with t2:
    st.markdown("## 📋 Operations Log")
    st.caption("Every engine operation recorded in real time. Download for submission.")

    stats = get_log_stats()
    m1,m2,m3,m4,m5 = st.columns(5)
    m1.metric("Total",      stats["TOTAL"])
    m2.metric("✅ Success",  stats["SUCCESS"])
    m3.metric("🔵 Info",    stats["INFO"])
    m4.metric("⚠️ Warning", stats["WARNING"])
    m5.metric("❌ Error",   stats["ERROR"])
    st.divider()

    fc1,fc2,_,dl,cl = st.columns([1.1,1,1.5,1,.6])
    op_f = fc1.selectbox("Op",  ["All","CREATE_ESCALATION","UPDATE_STATUS","AUTO_ESCALATE",
                                  "DETECT_OVERDUE","NOTIFICATION_SENT","TASK_DONE",
                                  "ADD_TASK","RESET_DEMO","ERROR"],
                          label_visibility="collapsed")
    lv_f = fc2.selectbox("Lvl", ["All","SUCCESS","INFO","WARNING","ERROR"],
                          label_visibility="collapsed")
    logs = get_logs(None if op_f=="All" else op_f, None if lv_f=="All" else lv_f)

    dl.download_button("⬇️ Download",
        data=export_logs_as_text(),
        file_name=f"ops_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
        mime="text/plain", use_container_width=True)
    if cl.button("🗑️", use_container_width=True, help="Clear log"):
        clear_logs(); st.rerun()

    st.divider()
    if not logs:
        st.info("No operations yet. Use the Live Demo tab.")
    else:
        html = ""
        for e in logs:
            cls  = LCOL.get(e["level"], "lg")
            ts   = e["timestamp"].strftime("%H:%M:%S")
            act  = f" <span class='lg'>· {e['actor']}</span>" if e["actor"] != "system" else ""
            det  = (f"<br><span class='lg' style='padding-left:1rem'>↳ {e['detail']}</span>"
                    if e["detail"] else "")
            html += (f"<div style='padding:.15rem 0;border-bottom:1px solid #222'>"
                     f"<span class='lg'>[{ts}]</span> "
                     f"<span class='{cls}'>[{e['operation']}]</span> "
                     f"<span style='color:#ddd'>{e['message']}</span>{act}{det}</div>")
        st.markdown(f'<div class="logbox">{html}</div>', unsafe_allow_html=True)
    st.caption("Auto-saved to operation_logs.txt · Errors → crash.log")

# ═══════════════════════════════════════════════════════════
# TAB 3 — DOCS
# ═══════════════════════════════════════════════════════════
with t3:
    st.markdown("## 📄 SDLR Docs Viewer")
    st.caption("Assignment planning and architecture documents.")
    DOCS = {
        "📐 Architecture Design":  "docs/architecture-design.md",
        "📋 PLAN.md":              "docs/PLAN.md",
        "🟢 STATUS.md":            "docs/STATUS.md",
        "🔌 MCP Server Selection": "docs/mcp-selection.md",
        "📡 API Schema (YAML)":    "docs/api-schema.yaml",
    }
    dc1, dc2 = st.columns([.9, 3.1])
    doc_sel  = dc1.selectbox("Doc", list(DOCS.keys()), label_visibility="collapsed")
    path     = os.path.join(ROOT, DOCS[doc_sel])
    try:
        content = open(path, encoding="utf-8").read()
        dc2.code(content, language="yaml") if path.endswith(".yaml") else dc2.markdown(content)
    except FileNotFoundError:
        st.error(f"File not found: {path}")
