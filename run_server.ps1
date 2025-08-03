# run_server.ps1
# Activate virtual environment and run the NorTrans server
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
& "$ScriptDir\venv\Scripts\Activate.ps1"
python "$ScriptDir\server.py" --host 0.0.0.0 --port 8000
