@echo off
setlocal
title Proxy Scraper and Checker

REM Force UTF-8 terminal code page and Python UTF-8 environment
chcp 65001 >nul 2>nul
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"

cd /d "%~dp0"

REM 1. If local .venv exists AND is genuinely working on this machine, launch it
if exist ".venv\Scripts\python.exe" (
    .\.venv\Scripts\python.exe -c "import aiohttp, aiohttp_socks, rich" >nul 2>nul
    if %errorlevel% equ 0 (
        .\.venv\Scripts\python.exe main.py
        goto :END
    )
)

REM 2. Find Python executable on system
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

REM 3. If system Python has requirements, launch directly with zero overhead!
%PYTHON_CMD% -c "import aiohttp, aiohttp_socks, rich" >nul 2>nul
if %errorlevel% equ 0 (
    %PYTHON_CMD% main.py
    goto :END
)

REM 4. Check if Windows 'py' launcher has it (in case 'python' is a WindowsApps alias)
where py >nul 2>nul
if %errorlevel% equ 0 (
    py -c "import aiohttp, aiohttp_socks, rich" >nul 2>nul
    if %errorlevel% equ 0 (
        py main.py
        goto :END
    )
)

REM 5. Requirements are missing: Show clean diagnostic to user
echo ===============================================================================
echo [!] Missing required Python libraries in current Python environment.
echo.
if exist ".venv" (
    echo NOTE: A '.venv' folder was found. If you copied this folder from another PC,
    echo please delete the '.venv' folder first!
    echo.
)
echo To install all requirements into your Python engine, open CMD here and run:
echo.
echo     %PYTHON_CMD% -m pip install -r requirements.txt
echo.
echo ===============================================================================
goto :FAIL

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
