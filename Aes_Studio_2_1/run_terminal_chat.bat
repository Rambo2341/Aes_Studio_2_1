@echo off
rem Chat with Aes in the terminal (approvals are asked here with y/N).
setlocal
cd /d "%~dp0"
where py >nul 2>nul && (set PY=py) || (set PY=python)
%PY% main.py --chat %*
endlocal
