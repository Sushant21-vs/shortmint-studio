@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" local_import.py
) else (
  echo Please run start_windows.bat once to install ShortMint's Python environment.
  echo After setup, run LOCAL_IMPORT_WINDOWS.bat again.
)
echo.
pause
