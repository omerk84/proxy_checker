@echo off
setlocal
title Proxy Scraper and Checker

REM Force UTF-8 terminal code page and Python UTF-8 environment for clean styling & boxes
chcp 65001 >nul 2>nul
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"

cd /d "%~dp0"

echo ===================================================
echo   Proxy Scraper and Checker - Startup
echo ===================================================
echo.

REM 1. Find Python executable (python or py)
set "PYTHON_CMD="
where python >nul 2>nul
if %errorlevel% equ 0 set "PYTHON_CMD=python"

if not defined PYTHON_CMD (
    where py >nul 2>nul
    if %errorlevel% equ 0 set "PYTHON_CMD=py"
)

if not defined PYTHON_CMD (
    echo [ERROR] Python is not installed or not in your PATH!
    echo Please install Python 3.10+ from https://www.python.org/downloads/
    echo IMPORTANT: Make sure to check "Add python.exe to PATH" during installation.
    echo.
    goto :FAIL
)

REM 2. Check if System Python already has requirements installed
%PYTHON_CMD% -c "import aiohttp, aiohttp_socks, rich" >nul 2>nul
if %errorlevel% equ 0 (
    echo [+] Dependencies verified in system Python.
    goto :LAUNCH_SYS
)

REM 3. Check if local .venv exists and has dependencies
if exist ".venv\Scripts\python.exe" (
    .\.venv\Scripts\python.exe -c "import aiohttp, aiohttp_socks, rich" >nul 2>nul
    if %errorlevel% equ 0 (
        echo [+] Dependencies verified in .venv.
        goto :LAUNCH_VENV
    )
)

REM 4. If neither has dependencies, try installing cleanly
echo [*] Setting up dependencies...
if exist ".venv" rmdir /s /q .venv >nul 2>nul
%PYTHON_CMD% -m venv .venv 2>nul
if exist ".venv\Scripts\python.exe" (
    echo [*] Installing required packages into .venv...
    .\.venv\Scripts\python.exe -m pip install --upgrade pip >nul 2>nul
    .\.venv\Scripts\pip.exe install -r requirements.txt
    if %errorlevel% equ 0 goto :LAUNCH_VENV
)

echo [*] Installing required packages into system Python...
%PYTHON_CMD% -m pip install -r requirements.txt
if %errorlevel% equ 0 goto :LAUNCH_SYS

echo [!] Pip install via requirements failed. Attempting direct launch with auto-installer...
goto :LAUNCH_SYS

:LAUNCH_VENV
echo [*] Launching application via virtual environment...
echo.
.\.venv\Scripts\python.exe main.py
goto :END

:LAUNCH_SYS
echo [*] Launching application via Python...
echo.
%PYTHON_CMD% main.py
goto :END

:END
if %errorlevel% neq 0 (
    echo.
    echo [!] Program exited with code %errorlevel%.
)
echo.
pause
exit /b 0

:FAIL
echo.
echo Press any key to close this window.
pause
exit /b 1
