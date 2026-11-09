@echo off
setlocal EnableExtensions
cd /d "%~dp0"

rem Prefer the already-built local executable when it exists.
if exist "%~dp0dist\universal_text_refiner.exe" (
    start "" "%~dp0dist\universal_text_refiner.exe"
    exit /b 0
)

rem Find the Python launcher, falling back to the python command.
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

rem Create a project-local virtual environment on first run.
if not exist ".venv\Scripts\python.exe" (
    echo Creating local virtual environment...
    %PYTHON_CMD% -m venv .venv
    if errorlevel 1 (
        echo Could not create the virtual environment.
        pause
        exit /b 1
    )
)

rem Install dependencies once per virtual environment.
if not exist ".venv\.dependencies-installed" (
    echo Installing dependencies...
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo Could not install dependencies.
        pause
        exit /b 1
    )
    type nul > ".venv\.dependencies-installed"
)

".venv\Scripts\python.exe" universal_text_refiner.py
if errorlevel 1 pause

endlocal
