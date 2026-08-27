@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if not defined VPY set "VPY=%CD%\.venv\Scripts\python.exe"
"%VPY%" tools\release_audit.py >nul
if not errorlevel 1 exit /b 0

echo [INFO] Factory podaci nisu validni. Pokrecem atomic restore iz ugradjenog bundle-a...
"%VPY%" tools\repair_profile_data.py
if errorlevel 1 goto :fail
"%VPY%" tools\release_audit.py >nul
if errorlevel 1 goto :fail
echo [OK] Factory podaci su obnovljeni i verificirani.
exit /b 0

:fail
echo [ERROR] Ugradjeni Factory bundle nedostaje, nije validan ili restore nije uspio.
exit /b 1