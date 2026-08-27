@echo off
setlocal EnableExtensions
cd /d "%~dp0"

call RUN_GUI.bat
exit /b %ERRORLEVEL%
