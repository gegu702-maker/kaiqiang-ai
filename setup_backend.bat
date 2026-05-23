@echo off
where py >nul 2>nul
if errorlevel 1 (
  echo Python is not installed or not in PATH.
  echo Download Python 3.11+ from https://www.python.org/downloads/
  echo IMPORTANT: Check "Add Python to PATH" during installation.
  exit /b 1
)

cd /d "%~dp0apps\api"
py -3.11 --version
py -3.11 -m pip --version

if not exist ".venv" (
  py -3.11 -m venv .venv
)

call .venv\Scripts\activate.bat
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
