@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" call INSTALL.bat
if errorlevel 1 exit /b 1
set "VPY=%CD%\.venv\Scripts\python.exe"
"%VPY%" tools\evaluate_hardware_campaign.py PA800_HARDWARE_CAMPAIGN\CAMPAIGN.json PA800_HARDWARE_CAMPAIGN\RESULTS.csv --output HARDWARE_EVALUATION.json
if errorlevel 1 goto :fail
"%VPY%" tools\final_release_gate.py --hardware-evaluation HARDWARE_EVALUATION.json --output FINAL_RELEASE_GATE.json
if errorlevel 1 goto :fail
echo [OK] Hardware evaluation i final gate su zavrseni.
pause
exit /b 0
:fail
echo [ERROR] Hardware evaluacija nije uspjela.
pause
exit /b 1
