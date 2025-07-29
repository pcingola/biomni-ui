#!/bin/bash -eu
set -o pipefail

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd -P )"
PROJECT_DIR="$(cd $SCRIPT_DIR && pwd -P)"

# Activate virtual environment
echo "PROJECT_DIR: $PROJECT_DIR"
cd $PROJECT_DIR
source .venv/bin/activate

# Run the app
chainlit run zzz.py -w