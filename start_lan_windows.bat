@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Please run start_windows.bat first to install and configure the owner.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" setup_owner.py
if errorlevel 1 (pause & exit /b 1)
echo.
echo WARNING: LAN mode serves the app to devices on your same Wi-Fi.
echo Do NOT expose this HTTP service directly to the public internet.
echo Use a secure HTTPS hosting setup for internet sharing.
echo.
echo Visit http://YOUR-PC-LAN-IP:8765 from another device on the same Wi-Fi.
echo Find your PC's local IP using ipconfig in Command Prompt.
echo.
".venv\Scripts\python.exe" -m uvicorn app:app --host 0.0.0.0 --port 8765
if errorlevel 1 pause
endlocal
