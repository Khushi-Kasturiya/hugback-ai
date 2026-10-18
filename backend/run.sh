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

echo "Starting Hugback backend using HOST and PORT from Settings..."
# app.main's entry point honors .env; do not override loopback configuration.
exec "$PYTHON_EXEC" -m app.main
