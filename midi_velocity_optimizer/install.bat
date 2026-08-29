@echo off
REM MIDI Velocity Optimizer - Installation Script
REM ================================================

echo.
echo ========================================
echo MIDI Velocity Optimizer - Instalacija
echo ========================================
echo.

REM Provjeri da li je Python instaliran
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo [GRESKA] Python nije instaliran!
    echo.
    echo Molim instaluraj Python sa: https://www.python.org/downloads/
    echo Obavezno oznaci opciju "Add Python to PATH" pri instalaciji!
    echo.
    pause
    exit /b 1
)

echo [OK] Python je pronađen
echo.

REM Provjeri da li je pip instaliran
pip --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo [GRESKA] pip nije instaliran!
    echo.
    pause
    exit /b 1
)

echo [OK] pip je pronađen
echo.

REM Upgrade pip
echo [*] Ažuriranje pip...
python -m pip install --upgrade pip

echo.
echo [*] Instaliranje zavisnosti...
echo.

REM Instaluraj requirements
pip install -r requirements.txt

if errorlevel 1 (
    echo.
    echo [GRESKA] Greska pri instalaciji zavisnosti!
    echo.
    pause
    exit /b 1
)

echo.
echo ========================================
echo [OK] INSTALACIJA USPJESNA!
echo ========================================
echo.
echo Sada mozes pokrenuti aplikaciju sa:
echo   - Dvoklik na gui.bat
echo   - Ili: python main.py
echo.
pause
