# Smart Task Escalation Engine 🚨

SDLR Phases 5–7 Assignment — Python + MCP Server + Streamlit

---

## ▶️ Run the Streamlit UI

Double-click **`run_app.bat`** OR run in terminal:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run streamlit_app.py
```

Opens at **http://localhost:8501**

---

## 🔌 Connect MCP Server to VS Code (Claude Extension)

This tells Claude in VS Code to use your escalation engine as a live tool.

### Step 1 — Find your folder path
Open terminal in this folder and run:
```
cd
```
Copy the full path shown (e.g. `D:\Projects\smart_task_escalation`)

### Step 2 — Open VS Code Claude settings
- Press `Ctrl+Shift+P`
- Type: `Claude: Open MCP Settings`
- Or: File → Preferences → Settings → search "Claude MCP"

### Step 3 — Add this JSON (replace the path)
```json
{
  "mcpServers": {
    "escalation-engine": {
      "command": "python",
      "args": ["mcp_server.py"],
      "cwd": "D:\\Projects\\smart_task_escalation"
    }
  }
}
```

**Important:** Use double backslashes `\\` in the path on Windows.

### Step 4 — Restart VS Code
Close and reopen VS Code completely.

### Step 5 — Verify it works
Open Claude chat in VS Code and type:
```
Use the escalation-engine tool to detect overdue tasks
```

Claude will call `detect_overdue_tasks` and return live results from your engine.

---

## 🛠️ Available MCP Tools

| Tool | What it does |
|------|-------------|
| `detect_overdue_tasks` | Scans tasks, returns overdue ones |
| `create_escalation` | Creates escalation with notification |
| `update_escalation_status` | Acknowledge / Resolve / Cancel |
| `get_escalation_history` | All escalations for a task |
| `get_all_escalations` | Full escalation list |
| `run_auto_escalation` | Auto-escalates all overdue tasks |
| `get_audit_log` | Full audit trail |

---

## 🧪 Run Tests

```bash
pip install pytest pytest-cov
pytest tests/ -v --cov=services
```

Expected: **38 tests, ~92% coverage**

---

## 📁 Structure

```
smart_task_escalation/
├── mcp_server.py          ← MCP server for VS Code Claude
├── streamlit_app.py       ← Streamlit demo UI
├── run_app.bat            ← Launch UI (double-click)
├── run_mcp.bat            ← Launch MCP standalone
├── requirements.txt
├── services/
│   ├── escalation_service.py
│   ├── audit_service.py
│   ├── notification_service.py
│   └── operation_logger.py
├── data/
│   └── mock_data.py
├── docs/                  ← Architecture docs (shown in Docs tab)
└── tests/
    └── test_escalation.py
```

---

## 📋 Log Files

| File | Contents |
|------|---------|
| `operation_logs.txt` | All engine operations (auto-created) |
| `crash.log` | Startup/runtime errors |

---

## ⚠️ Common Mistakes

| Wrong | Right |
|-------|-------|
| `python streamlit_app.py` | `streamlit run streamlit_app.py` |
| Running from wrong folder | Must be inside `smart_task_escalation/` |
| Single `\` in MCP path | Use `\\` in JSON |
