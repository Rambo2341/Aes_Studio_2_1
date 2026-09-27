@echo off
rem Aes Autopilot: works through the queued goals (Autopilot page) while you sleep.
rem Trust mode "auto" follows your per-tool policies; use "full" for no prompts at all.
rem Emergency stop: create a file named STOP in the Aes data folder, or press Ctrl+C here.
setlocal
cd /d "%~dp0"
where py >nul 2>nul && (set PY=py) || (set PY=python)
%PY% main.py --autopilot --mode auto %*
pause
endlocal
