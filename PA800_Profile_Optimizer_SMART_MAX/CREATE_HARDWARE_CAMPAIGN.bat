@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" call INSTALL.bat
if errorlevel 1 exit /b 1
set "VPY=%CD%\.venv\Scripts\python.exe"
"%VPY%" tools\create_hardware_campaign.py --output PA800_HARDWARE_CAMPAIGN
if errorlevel 1 pause & exit /b 1
echo.
echo Paket je kreiran u PA800_HARDWARE_CAMPAIGN
pause
