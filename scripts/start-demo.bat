@echo off
rem NeuraNova console on this computer with sample data (Windows).
cd /d "%~dp0\.."
call scripts\_prepare.bat || exit /b 1
.venv\Scripts\neuranova demo %*
