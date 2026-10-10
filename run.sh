#!/bin/bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

# Prefer virtualenv if present
if [ -d ".venv" ]; then
    echo "Using local virtual environment..."
    UVICORN_EXEC=".venv/bin/uvicorn"
else
    UVICORN_EXEC="uvicorn"
fi

echo "Starting Elara Multimodal Live Backend on port 8000..."
exec "$UVICORN_EXEC" app.main:app --host 0.0.0.0 --port 8000
