@echo off
echo ================================
echo  Task Escalation Engine — UI
echo ================================
if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
)
call .venv\Scripts\activate.bat
pip install -r requirements.txt -q
echo.
echo Opening http://localhost:8501
streamlit run streamlit_app.py
pause
