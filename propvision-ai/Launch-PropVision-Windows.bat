@echo off
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo Python was not found. Install Python 3.11+ from https://www.python.org/downloads/ ^(tick "Add python.exe to PATH"^).
  pause
  exit /b 1
)
if not exist ".venv" (
  echo Creating virtual environment ^(first run only^)...
  python -m venv .venv
  if errorlevel 1 ( echo Could not create the virtual environment. & pause & exit /b 1 )
)
call .venv\Scripts\activate.bat
if not exist ".venv\.deps_installed" (
  echo Installing dependencies...
  python -m pip install --upgrade pip >nul 2>nul
  pip install -r requirements.txt
  if errorlevel 1 ( echo Dependency installation failed. & pause & exit /b 1 )
  echo done> .venv\.deps_installed
)
echo Starting PropVision AI - press Ctrl+C to stop.
streamlit run app.py
pause
