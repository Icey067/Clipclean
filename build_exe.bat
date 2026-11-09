@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "PYTHON_CMD="
where py >nul 2>nul
if not errorlevel 1 set "PYTHON_CMD=py"
if not defined PYTHON_CMD (
    where python >nul 2>nul
    if not errorlevel 1 set "PYTHON_CMD=python"
)
if not defined PYTHON_CMD (
    echo Python 3 was not found. Install it from https://www.python.org/downloads/
    pause
    exit /b 1
)

echo Installing or updating PyInstaller...
%PYTHON_CMD% -m pip install --upgrade pyinstaller
if errorlevel 1 (
    echo Could not install PyInstaller.
    pause
    exit /b 1
)

echo Building Universal Paste Refiner...
%PYTHON_CMD% -m PyInstaller --noconfirm --clean --noconsole --onefile --collect-all customtkinter universal_text_refiner.py
if errorlevel 1 (
    echo Build failed.
    pause
    exit /b 1
)

echo.
echo Build complete: dist\universal_text_refiner.exe
pause
endlocal
