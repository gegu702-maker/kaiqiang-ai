@echo off
cd /d "%~dp0apps\api"
if not exist ".venv\Scripts\activate.bat" (
  echo Virtual environment not found. Run: setup_backend.bat
  exit /b 1
)
call .venv\Scripts\activate.bat
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
