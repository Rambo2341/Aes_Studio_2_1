@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul && (set PY=py) || (set PY=python)
%PY% -m pip install -r requirements-base.txt -r requirements-build.txt
%PY% -m PyInstaller --noconfirm AesStudio.spec
if errorlevel 1 exit /b 1
echo.
echo Built: dist\AesStudio\AesStudio.exe
echo One-folder mode is used so local runtime libraries can be upgraded more easily.
pause
endlocal
