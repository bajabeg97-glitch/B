@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if "%~1"=="" (
  call RUN_GUI.bat
  exit /b %ERRORLEVEL%
)
call ENSURE_VALIDATION_DEPS.bat
if errorlevel 1 goto :fail
set "VPY=%CD%\.venv\Scripts\python.exe"
call ENSURE_FACTORY_DATA.bat
if errorlevel 1 goto :data_fail
"%VPY%" -m pa800_optimizer.cli %*
exit /b %ERRORLEVEL%
:fail
echo [ERROR] AUTO PILOT setup failed.
pause
exit /b 1
:data_fail
echo [ERROR] Factory data validation/restore failed.
pause
exit /b 1
