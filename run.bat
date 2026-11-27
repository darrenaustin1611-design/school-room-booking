@echo off
title School Room Booking System
echo ===================================================
echo Starting School Room Booking System...
echo ===================================================

cd /d "%~dp0"

echo Detecting Python installation...
set "PYTHON_CMD="

if exist "%LOCALAPPDATA%\Python\bin\python.exe" (
    set "PYTHON_CMD=%LOCALAPPDATA%\Python\bin\python.exe"
) else if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    set "PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
) else if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    set "PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
) else (
    where py >nul 2>&1
    if not errorlevel 1 (
        set "PYTHON_CMD=py"
    ) else (
        set "PYTHON_CMD=python"
    )
)

echo Using Python: %PYTHON_CMD%
echo Verifying dependencies...
"%PYTHON_CMD%" -m pip install flask werkzeug requests openpyxl sqlite_web --quiet

echo.
echo ===================================================
echo Server starting at http://127.0.0.1:5000
echo Opening browser once server is ready...
echo Press Ctrl+C to stop the server.
echo ===================================================
echo.

:: Open browser after a 2-second delay so Flask server starts first
start /b "" powershell -NoProfile -Command "Start-Sleep -Seconds 2; Start-Process 'http://127.0.0.1:5000'"

start "%PYTHON_CMD%" app.py
sqlite_web school_booking.db
pause

