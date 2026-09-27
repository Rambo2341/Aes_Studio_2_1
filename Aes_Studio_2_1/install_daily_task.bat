@echo off
rem Registers a Windows scheduled task that runs Aes daily training every night at 02:00.
rem Change the time with:  install_daily_task.bat 03:30
rem Remove it with:        schtasks /Delete /TN "Aes Daily Training" /F
setlocal
set T=%1
if "%T%"=="" set T=02:00
schtasks /Create /F /SC DAILY /ST %T% /TN "Aes Daily Training" /TR "\"%~dp0run_daily_training.bat\""
if errorlevel 1 (echo Failed to create the task. & pause & exit /b 1)
echo Aes will train every night at %T%. Reports: Aes data folder\reports
pause
endlocal
