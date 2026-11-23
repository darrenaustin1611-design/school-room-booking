# School Room Booking System Runner for PowerShell
Set-Location -Path $PSScriptRoot

$pythonCmd = "python"
if (Test-Path "$env:LOCALAPPDATA\Python\bin\python.exe") {
    $pythonCmd = "$env:LOCALAPPDATA\Python\bin\python.exe"
} elseif (Test-Path "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe") {
    $pythonCmd = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
}

Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "Starting School Room Booking System..." -ForegroundColor Green
Write-Host "Using Python: $pythonCmd" -ForegroundColor Gray
Write-Host "===================================================" -ForegroundColor Cyan

# Open browser automatically after 2 seconds
Start-Job -ScriptBlock {
    Start-Sleep -Seconds 2
    Start-Process "http://127.0.0.1:5000"
} | Out-Null

Write-Host "Server running at http://127.0.0.1:5000" -ForegroundColor Yellow
Write-Host "Press Ctrl+C to stop the server." -ForegroundColor Gray
Write-Host ""

& $pythonCmd app.py
