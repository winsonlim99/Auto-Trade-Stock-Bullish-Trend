@echo off
setlocal
cd /d "%~dp0"
py -3 -m venv .venv
if errorlevel 1 (pause & exit /b 1)
.venv\Scripts\python.exe -m pip install -e ".[dev]"
if errorlevel 1 (pause & exit /b 1)
.venv\Scripts\python.exe -m app.check
pause
