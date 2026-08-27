@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "VPY=%CD%\.venv\Scripts\python.exe"
if not exist "%VPY%" (
  echo [ERROR] Pokreni RUN_GUI.bat jednom da se pripremi okruzenje.
  pause
  exit /b 1
)
if "%~1"=="" (
  echo Upotreba: WORKSTATION_SESSION.bat PUTANJA_DO_PA800_WORKSTATION_SESSION.json [status^|undo^|redo]
  pause
  exit /b 2
)
set "ACTION=%~2"
if "%ACTION%"=="" set "ACTION=status"
"%VPY%" tools\workstation_session.py "%~1" "%ACTION%"
pause
exit /b %ERRORLEVEL%