@echo off
rem Starts NeuraNova PA in the background every time you sign in to Windows (run once).
cd /d "%~dp0"
powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Startup')+'\NeuraNova PA.lnk'); $s.TargetPath='%~dp0NeuraNova PA\NeuraNova PA.exe'; $s.Arguments='--no-browser'; $s.WindowStyle=7; $s.WorkingDirectory='%~dp0NeuraNova PA'; $s.Save()"
echo NeuraNova PA will now start automatically when you sign in. To undo, run "Remove from Windows startup.bat".
pause
