@echo off
setlocal enabledelayedexpansion
title Proxy Scraper & Checker
cd /d "%~dp0"

echo ===================================================
echo   Proxy Scraper & Checker - Environment Setup
echo ===================================================
echo.

:: 1. Check if Python is available on system
set "SYS_PYTHON="
where python >nul 2>nul
if %errorlevel% equ 0 (
    set "SYS_PYTHON=python"
) else (
    where py >nul 2>nul
    if %errorlevel% equ 0 (
        set "SYS_PYTHON=py"
    )
)

if "%SYS_PYTHON%"=="" (
    echo [ERROR] Python was not found on your system!
    echo Please install Python 3.10+ from https://www.python.org/downloads/
    echo IMPORTANT: Make sure to check the box "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

:: 2. Check if .venv exists and has all required libraries working
set "NEED_INSTALL=0"
if not exist ".venv\Scripts\python.exe" (
    set "NEED_INSTALL=1"
) else (
    .\.venv\Scripts\python.exe -c "import aiohttp, aiohttp_socks, rich" >nul 2>nul
    if %errorlevel% neq 0 (
        echo [!] Existing virtual environment is invalid or missing dependencies.
        echo Re-building clean environment for this machine...
        rmdir /s /q .venv >nul 2>nul
        set "NEED_INSTALL=1"
    )
)

:: 3. Setup Virtual Environment and Install Dependencies if needed
if "!NEED_INSTALL!"=="1" (
    echo [*] Creating virtual environment (.venv)...
    %SYS_PYTHON% -m venv .venv
    if not exist ".venv\Scripts\python.exe" (
        echo [ERROR] Failed to create virtual environment!
        echo Please ensure Python is properly installed.
        pause
        exit /b 1
    )
    echo [*] Installing required libraries (aiohttp, aiohttp-socks, rich)...
    .\.venv\Scripts\python.exe -m pip install --upgrade pip >nul 2>nul
    .\.venv\Scripts\pip.exe install -r requirements.txt
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install requirements! Please check your internet connection.
        pause
        exit /b 1
    )
    echo [+] Environment ready!
    echo.
)

:: 4. Launch the application
echo [*] Launching application...
echo.
.\.venv\Scripts\python.exe main.py
if %errorlevel% neq 0 (
    echo.
    echo [!] Program exited with an error.
)
pause
