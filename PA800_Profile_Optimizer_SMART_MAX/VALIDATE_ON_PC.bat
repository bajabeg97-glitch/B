@echo off
setlocal EnableExtensions
cd /d "%~dp0"
call ENSURE_VALIDATION_DEPS.bat
if errorlevel 1 goto :fail
set "VPY=%CD%\.venv\Scripts\python.exe"
"%VPY%" tools\release_audit.py
if errorlevel 1 goto :fail
if "%~1"=="" (
  echo Otvara se izbor foldera. Izaberi folder sa stvarnim MIDI/KAR pjesmama.
  "%VPY%" tools\pc_validation.py --pick-folder --require-user-midis
) else (
  "%VPY%" tools\pc_validation.py --input-folder "%~1" --require-user-midis
)
set "RC=%ERRORLEVEL%"
echo Send validation_results\SEND_ME_PA800_VALIDATION_*.zip
pause
exit /b %RC%
:fail
echo [ERROR] Setup or Factory data validation failed.
pause
exit /b 1