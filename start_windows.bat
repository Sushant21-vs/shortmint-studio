@echo off
setlocal
cd /d "%~dp0"
title ShortMint Studio v3
where python >nul 2>nul
if errorlevel 1 (
    echo Python was not found. Install Python 3.11+ from https://www.python.org/downloads/
    echo Tick "Add python.exe to PATH" when installing.
    pause
    exit /b 1
)
where ffmpeg >nul 2>nul
if errorlevel 1 (
    echo FFmpeg missing. Run: winget install Gyan.FFmpeg
    echo Restart your Command Prompt and try again.
    pause
    exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
    echo Creating local environment...
    python -m venv .venv
    if errorlevel 1 (pause & exit /b 1)
)
echo Checking dependencies...
".venv\Scripts\python.exe" -m pip install -r requirements.txt --disable-pip-version-check -q
if errorlevel 1 (echo Dependency installation failed. & pause & exit /b 1)
echo Checking site owner...
".venv\Scripts\python.exe" setup_owner.py
if errorlevel 1 (pause & exit /b 1)
echo Starting ShortMint Studio v3 at http://127.0.0.1:8765
".venv\Scripts\python.exe" launch.py
if errorlevel 1 pause
endlocal
