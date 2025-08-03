#!/bin/bash
# install.sh
# The NorTrans translation API server.
#
# Usage: bash install.sh

set -e

# Determine project root (directory containing this script)
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Create virtual environment in ./venv if it doesn't exist
if [ ! -d "$PROJECT_DIR/venv" ]; then
  python3 -m venv "$PROJECT_DIR/venv"
fi

# Activate the virtual environment
source "$PROJECT_DIR/venv/bin/activate"

# Upgrade pip and install dependencies
pip install --upgrade pip
pip install -r "$PROJECT_DIR/requirements.txt"

# Create a startup script to run the server
cat > "$PROJECT_DIR/run_server.sh" <<'RUN_EOF'
#!/bin/bash
# run_server.sh
# Activate virtual environment and run the NorTrans server
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$DIR/venv/bin/activate"
python "$DIR/server.py" --host 0.0.0.0 --port 8000
RUN_EOF

chmod +x "$PROJECT_DIR/run_server.sh"

echo "Installation complete. Use ./run_server.sh to start the subtitle translation API."
