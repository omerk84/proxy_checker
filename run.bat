@echo off
setlocal
title Proxy Scraper and Checker
cd /d "%~dp0"

echo ===================================================
echo   Proxy Scraper and Checker - Startup
echo ===================================================
echo.

REM 1. Check if Python is installed and available in PATH
set "PYTHON_EXE="

where python >nul 2>nul
if %errorlevel% equ 0 set "PYTHON_EXE=python"

if not defined PYTHON_EXE (
    where py >nul 2>nul
    if %errorlevel% equ 0 set "PYTHON_EXE=py"
)

if not defined PYTHON_EXE (
    echo [ERROR] Python is not installed or not in your PATH!
    echo.
    echo Please install Python 3.10 or newer from https://www.python.org/downloads/
    echo IMPORTANT: During installation, make sure to check "Add python.exe to PATH".
    echo.
    goto :FAIL
)

REM 2. Validate if virtual environment exists and is healthy
set "REBUILD_VENV=0"

if not exist ".venv\Scripts\python.exe" (
    set "REBUILD_VENV=1"
) else (
    .\.venv\Scripts\python.exe -c "import aiohttp, aiohttp_socks, rich" >nul 2>nul
    if %errorlevel% neq 0 (
        echo [!] Existing virtual environment is invalid or missing packages.
        echo Re-creating clean environment for this machine...
        rmdir /s /q .venv >nul 2>nul
        set "REBUILD_VENV=1"
    )
)

if "%REBUILD_VENV%"=="0" goto :LAUNCH

REM 3. Create fresh virtual environment and install packages
echo [*] Creating virtual environment...
%PYTHON_EXE% -m venv .venv
if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Failed to create .venv using %PYTHON_EXE%!
    goto :FAIL
)

echo [*] Installing dependencies from requirements.txt...
.\.venv\Scripts\python.exe -m pip install --upgrade pip >nul 2>nul
.\.venv\Scripts\pip.exe install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install dependencies! Please check your internet connection.
    goto :FAIL
)
echo [+] Environment setup complete!
echo.

:LAUNCH
echo [*] Starting Proxy Scraper and Checker...
echo.
.\.venv\Scripts\python.exe main.py
if %errorlevel% neq 0 (
    echo.
    echo [!] Program finished with exit code %errorlevel%.
)
echo.
pause
exit /b 0

:FAIL
echo.
echo Setup cannot continue. Press any key to close this window.
pause
exit /b 1
