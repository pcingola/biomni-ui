#!/bin/bash -eu
set -o pipefail

# Default configuration values
CHAINLIT_HOST="${CHAINLIT_HOST:-0.0.0.0}"
CHAINLIT_PORT="${CHAINLIT_PORT:-8002}"
LOG_LEVEL="${LOG_LEVEL:-INFO}"

# Activate virtual environment
if [ ! -d ".venv" ]; then
    echo "Error: Virtual environment not found. Please run 'uv venv' first."
    exit 1
fi

source .venv/bin/activate

echo "Starting Biomni UI..."
echo "Host: $CHAINLIT_HOST"
echo "Port: $CHAINLIT_PORT"
echo "Log level: $LOG_LEVEL"
echo "Python: $(which python)"

# Run the Chainlit application
python -m chainlit run biomni_ui/app.py --host "$CHAINLIT_HOST" --port "$CHAINLIT_PORT"