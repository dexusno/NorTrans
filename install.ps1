# install.ps1
# This script sets up the NorTrans translation API server on Windows.

Param()

# Determine project root (directory containing this script)
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Definition

# Create virtual environment in .\venv if it doesn't exist
if (-Not (Test-Path "$ProjectDir\venv")) {
    python -m venv "$ProjectDir\venv"
}

# Activate the virtual environment
& "$ProjectDir\venv\Scripts\Activate.ps1"

# Upgrade pip and install dependencies
pip install --upgrade pip
pip install -r "$ProjectDir\requirements.txt"

# Create a startup script to run the server
$runScript = @"
# run_server.ps1
# Activate virtual environment and run the NorTrans server
\$ScriptDir = Split-Path -Parent \$MyInvocation.MyCommand.Definition
& "\$ScriptDir\venv\Scripts\Activate.ps1"
python "\$ScriptDir\server.py" --host 0.0.0.0 --port 8000
"@
Set-Content -Path "$ProjectDir\run_server.ps1" -Value $runScript -NoNewline

Write-Host "Installation complete. Use .\run_server.ps1 to start the subtitle translation API."
