#!/bin/bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

# Prefer virtualenv if present
if [ -d ".venv" ]; then
    echo "Using local virtual environment..."
    PYTHON_EXEC=".venv/bin/python"
else
    PYTHON_EXEC="python"
fi

echo "Starting Hugback Multimodal Live Backend on port 8000..."
exec "$PYTHON_EXEC" -m uvicorn app.main:app --host 0.0.0.0 --port 8000
