@echo off
setlocal

cd /d "%~dp0"

echo Real-Time Property Finder
echo ==========================
echo.

where python >nul 2>nul
if errorlevel 1 (
    where py >nul 2>nul
    if errorlevel 1 (
        echo Python was not found on this computer.
        echo Please install Python 3.10 or newer from https://www.python.org/downloads/
        echo and make sure to check "Add Python to PATH" during installation.
        pause
        exit /b 1
    )
    set PYTHON=py
) else (
    set PYTHON=python
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating a local virtual environment...
    %PYTHON% -m venv .venv
    if errorlevel 1 (
        echo Failed to create the virtual environment.
        pause
        exit /b 1
    )
)

echo Installing/updating dependencies...
".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
".venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt
if errorlevel 1 (
    echo Failed to install dependencies. Check your internet connection.
    pause
    exit /b 1
)

echo.
echo Starting the application...
echo (Close this window to stop the server.)
echo.

".venv\Scripts\python.exe" backend\run_server.py

pause
