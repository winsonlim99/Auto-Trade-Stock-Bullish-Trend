@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Run Install_AutoTrade.bat first.
  pause
  exit /b 1
)
.venv\Scripts\python.exe -m app.check
if errorlevel 1 (pause & exit /b 1)
echo Open http://127.0.0.1:8000 - PAPER ONLY, session OFF
.venv\Scripts\python.exe -m uvicorn app.web.main:app --host 127.0.0.1 --port 8000
pause
