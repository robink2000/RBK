@echo off
rem Starts NeuraNova PA and opens it in your browser. It then runs in the system tray, next to the clock.
cd /d "%~dp0"
start "" "NeuraNova PA\NeuraNova PA.exe" %*
