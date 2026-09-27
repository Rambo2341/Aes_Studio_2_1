@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul && (set PY=py) || (set PY=python)
%PY% -m pip install --upgrade pip
%PY% -m pip install -r requirements-base.txt
%PY% -m pip install -r requirements-local-model.txt
if errorlevel 1 (
  echo.
  echo llama-cpp-python build failed. On NVIDIA systems you may need a CUDA-specific wheel/build.
  echo See the llama-cpp-python installation instructions for your CUDA version.
  pause
  exit /b 1
)
echo Aes local runtime is ready. Open Models and choose your .gguf file.
pause
endlocal
