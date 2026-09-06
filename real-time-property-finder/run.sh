#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

echo "Real-Time Property Finder"
echo "=========================="
echo

PYTHON_BIN=""
for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
        PYTHON_BIN="$candidate"
        break
    fi
done

if [ -z "$PYTHON_BIN" ]; then
    echo "Python 3.10+ was not found. Please install it from https://www.python.org/downloads/"
    exit 1
fi

if [ ! -x ".venv/bin/python" ]; then
    echo "Creating a local virtual environment..."
    "$PYTHON_BIN" -m venv .venv
fi

echo "Installing/updating dependencies..."
".venv/bin/python" -m pip install --quiet --upgrade pip
".venv/bin/python" -m pip install --quiet -r requirements.txt

echo
echo "Starting the application..."
echo "(Press Ctrl+C to stop the server.)"
echo

".venv/bin/python" backend/run_server.py
