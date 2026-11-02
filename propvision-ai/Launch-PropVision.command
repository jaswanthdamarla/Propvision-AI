#!/bin/bash
# Double-click to start PropVision AI on macOS.
cd "$(dirname "$0")" || exit 1
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 was not found. Install Python 3.11+ from https://www.python.org/downloads/ and run this again."
  read -r -p "Press Enter to close..."; exit 1
fi
if [ ! -d ".venv" ]; then
  echo "Creating virtual environment (first run only)..."
  python3 -m venv .venv || { echo "Could not create the virtual environment."; read -r -p "Press Enter to close..."; exit 1; }
fi
source .venv/bin/activate
if [ ! -f ".venv/.deps_installed" ] || [ requirements.txt -nt .venv/.deps_installed ]; then
  echo "Installing dependencies..."
  pip install --upgrade pip >/dev/null 2>&1
  pip install -r requirements.txt || { echo "Dependency installation failed."; read -r -p "Press Enter to close..."; exit 1; }
  touch .venv/.deps_installed
fi
echo "Starting PropVision AI - your browser will open shortly. Press Ctrl+C to stop."
streamlit run app.py
