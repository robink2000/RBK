@echo off
rem Your real NeuraNova console (Windows). The first time, it asks a few setup questions.
cd /d "%~dp0\.."
call scripts\_prepare.bat || exit /b 1
findstr /r /c:"^DASHBOARD_PASSWORD=." .env >nul 2>nul
if errorlevel 1 (
  .venv\Scripts\neuranova setup
) else (
  .venv\Scripts\neuranova run %*
)
pause
