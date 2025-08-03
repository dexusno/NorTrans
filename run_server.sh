#!/bin/bash
# run_server.sh
# Activate virtual environment and run the NorTrans server
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$DIR/venv/bin/activate"
python "$DIR/server.py" --host 0.0.0.0 --port 8000
