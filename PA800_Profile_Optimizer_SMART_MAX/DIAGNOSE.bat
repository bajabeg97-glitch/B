@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" call INSTALL.bat
if errorlevel 1 exit /b 1
set "VPY=%CD%\.venv\Scripts\python.exe"
"%VPY%" --version
"%VPY%" -c "import tkinter,mido,numpy,pa800_optimizer; print('imports: PASS')"
"%VPY%" tools\build_factory_gold_manifest.py
"%VPY%" -m compileall -q pa800_optimizer tools
if errorlevel 1 (echo [ERROR] DIAGNOSE FAIL) else (echo [OK] DIAGNOSE PASS)
pause
