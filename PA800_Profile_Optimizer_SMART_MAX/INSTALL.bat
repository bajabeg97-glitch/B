@echo off
setlocal EnableExtensions
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 goto :no_python
if not exist ".venv\Scripts\python.exe" (
  py -3.10 -m venv .venv 2>nul
  if errorlevel 1 py -3 -m venv .venv
  if errorlevel 1 goto :fail
)
set "VPY=%CD%\.venv\Scripts\python.exe"
"%VPY%" -m pip install --upgrade pip
if errorlevel 1 goto :fail
"%VPY%" -m pip install -r requirements-gui.txt
if errorlevel 1 goto :fail
"%VPY%" -m pip install -e .
if errorlevel 1 goto :fail
"%VPY%" -c "import tkinter,mido,numpy,pa800_optimizer; print('PA800 GUI READY')"
if errorlevel 1 goto :fail
echo [OK] Instalacija je zavrsena.
exit /b 0
:no_python
echo [ERROR] Instaliraj Python 3.10 ili noviji i ukljuci Python Launcher.
pause
exit /b 1
:fail
echo [ERROR] Instalacija nije uspjela.
pause
exit /b 1
