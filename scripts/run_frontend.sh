#!/bin/bash
# Script to run the Streamlit frontend

# Load environment variables if .env exists
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Run the frontend
echo "Starting Streamlit frontend..."
uv run streamlit run frontend/app.py --server.port "${STREAMLIT_SERVER_PORT:-8501}" --server.address "${STREAMLIT_SERVER_ADDRESS:-localhost}"

