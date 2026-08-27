@echo off
setlocal EnableExtensions
cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python launcher "py" nije pronadjen.
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  py -3 -m venv .venv
  if errorlevel 1 exit /b 1
)

set "VPY=%CD%\.venv\Scripts\python.exe"
"%VPY%" -m pip install --upgrade pip
if errorlevel 1 exit /b 1
"%VPY%" -m pip install -r requirements-validation.txt -c constraints-validation.txt
if errorlevel 1 exit /b 1
"%VPY%" -m pip install -e .
if errorlevel 1 exit /b 1

"%VPY%" -c "import pa800_optimizer"
exit /b %ERRORLEVEL%