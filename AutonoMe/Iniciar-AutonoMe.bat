@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Iniciar-AutonoMe.ps1"
if errorlevel 1 (
    echo.
    pause
)
