@echo off
rem NeuraNova console on this computer with sample data (Windows).
rem First run installs everything into .venv; later runs start in a few seconds.
cd /d "%~dp0\.."
where py >nul 2>nul
if errorlevel 1 (
  echo Python 3.11 or newer is needed: https://www.python.org/downloads/
  echo During install, tick "Add python.exe to PATH".
  pause
  exit /b 1
)
if not exist .venv (
  echo First run: setting up, about a minute...
  py -3 -m venv .venv || goto :error
  .venv\Scripts\python -m pip install --quiet --upgrade pip
  .venv\Scripts\python -m pip install --quiet -e . || goto :error
)
.venv\Scripts\neuranova demo %*
goto :eof
:error
echo Setup failed. Scroll up for the message, or ask for help with it.
pause
