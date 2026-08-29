@echo off
REM MIDI Velocity Optimizer - GUI Launcher
REM =========================================

echo.
echo ========================================
echo MIDI Velocity Optimizer - Pokretanje
echo ========================================
echo.

REM Provjeri da li je Python instaliran
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo [GRESKA] Python nije instaliran!
    echo.
    echo Prvo pokreni install.bat!
    echo.
    pause
    exit /b 1
)

echo [OK] Pokretanje aplikacije...
echo.

REM Pokreni aplikaciju
python main.py

if errorlevel 1 (
    echo.
    echo [GRESKA] Greska pri pokretanju aplikacije!
    echo.
    pause
    exit /b 1
)
