@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Project Python environment is missing. Recreate it with:
    echo D:\python312\python.exe -m venv .venv
    echo .venv\Scripts\python.exe -m pip install -r requirements-board.txt
    pause
    exit /b 1
)
".venv\Scripts\python.exe" host\gui.py
if errorlevel 1 pause
