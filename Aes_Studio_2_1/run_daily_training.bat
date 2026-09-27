@echo off
rem Aes daily training: curriculum (study+practice) -> verified drills -> evals -> brain growth -> report.
rem Emergency stop: create a file named STOP in the Aes data folder, or press Ctrl+C here.
setlocal
cd /d "%~dp0"
where py >nul 2>nul && (set PY=py) || (set PY=python)
%PY% main.py --daily --mode auto %*
endlocal
