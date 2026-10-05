@echo off
rem Shared by the start scripts: create .venv the first time, then keep packages up to date.
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
)
echo Checking for updates to the agent's packages...
.venv\Scripts\python -m pip install --quiet --disable-pip-version-check -e . || goto :error
exit /b 0
:error
echo Setup failed. Scroll up for the message, or ask for help with it.
pause
exit /b 1
