@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" call INSTALL.bat
if errorlevel 1 exit /b 1
set "VPY=%CD%\.venv\Scripts\python.exe"
"%VPY%" tools\build_factory_gold_manifest.py
if errorlevel 1 goto :corpus_fail
"%VPY%" -m pa800_optimizer.gui
exit /b %ERRORLEVEL%
:corpus_fail
echo [ERROR] Factory/Gold corpus gate nije prosao. Arhive moraju imati Factory 252 i Gold 182 MIDI fajla.
pause
exit /b 1
