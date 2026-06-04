@echo off
echo ================================
echo  Task Escalation Engine — MCP
echo ================================
if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
)
call .venv\Scripts\activate.bat
pip install -r requirements.txt -q
echo.
echo MCP server running (stdio transport)
echo Connect via VS Code Claude extension settings.
echo Press Ctrl+C to stop.
python mcp_server.py
pause
