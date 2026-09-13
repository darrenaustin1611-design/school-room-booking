@echo off
title School Room Booking System
echo ===================================================
echo Starting School Room Booking System...
echo ===================================================

cd /d "%~dp0"

echo Checking Python...
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo Python is not in PATH. Trying default install location...
    set "PATH=%LOCALAPPDATA%\Programs\Python\Python312;%LOCALAPPDATA%\Programs\Python\Python312\Scripts;%PATH%"
)

echo Verifying dependencies...
python -m pip install flask werkzeug requests --quiet

echo.
echo ===================================================
echo Server starting at http://127.0.0.1:5000
echo Opening browser once server is ready...
echo Press Ctrl+C to stop the server.
echo ===================================================
echo.

:: Open browser after a 2-second delay so Flask server starts first
start /b "" powershell -NoProfile -Command "Start-Sleep -Seconds 2; Start-Process 'http://127.0.0.1:5000'"

python app.py
pause

