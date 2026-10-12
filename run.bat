@echo off
title Proxy Scraper & Checker
echo Starting Proxy Scraper & Checker...

IF NOT EXIST ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    python -m venv .venv
    echo Installing dependencies...
    .\.venv\Scripts\pip.exe install -r requirements.txt
)

.\.venv\Scripts\python.exe main.py
pause
