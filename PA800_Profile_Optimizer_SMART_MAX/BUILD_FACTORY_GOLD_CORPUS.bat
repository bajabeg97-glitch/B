@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" call INSTALL.bat
if errorlevel 1 exit /b 1
set "VPY=%CD%\.venv\Scripts\python.exe"
"%VPY%" tools\build_factory_gold_manifest.py
if errorlevel 1 (
  echo Factory/Gold provjera nije prosla.
  pause
  exit /b 1
)
echo Factory 252 i Gold 182: manifest je spreman.
pause
