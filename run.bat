@echo off
setlocal

set "PROJECT_DIR=C:\Users\Ryan\Documents\Projects\hw-monior"

REM Check if already admin
net session >nul 2>&1
if %errorlevel% neq 0 (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath 'pyw' -ArgumentList '-3.12','main.py' -WorkingDirectory '%PROJECT_DIR%' -Verb RunAs"
    exit /b
)

cd /d "%PROJECT_DIR%"
start "" pyw -3.12 main.py
exit /b