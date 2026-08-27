@echo off
setlocal EnableExtensions
cd /d "%~dp0"
call FIX_DATA_AND_RUN_GUI.bat
exit /b %ERRORLEVEL%