@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "MIDI_FOLDER=%~1"
if "%MIDI_FOLDER%"=="" (
  echo PA800 P0 REAL VALIDATION
  echo Unesi punu putanju foldera sa test MIDI/KAR fajlovima.
  set /p "MIDI_FOLDER=Folder: "
)
if not exist "%MIDI_FOLDER%\" (
  echo [ERROR] Folder ne postoji: %MIDI_FOLDER%
  pause
  exit /b 1
)
call VALIDATE_ON_PC.bat "%MIDI_FOLDER%"
exit /b %ERRORLEVEL%