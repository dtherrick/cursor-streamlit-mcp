#!/bin/bash
# Script to run the FastAPI backend

# Load environment variables if .env exists
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Run the backend
echo "Starting FastAPI backend..."
uv run uvicorn backend.main:app --reload --host "${FASTAPI_HOST:-localhost}" --port "${FASTAPI_PORT:-8000}"

