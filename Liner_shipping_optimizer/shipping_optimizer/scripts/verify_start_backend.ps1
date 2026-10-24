# Start the FastAPI backend from this checkout (paths are relative to this script, not to one user's folder).
# Port: $env:API_PORT, default 8000. On machines where Windows reserves 8000 (see `netsh int ipv4 show excludedportrange tcp`),
# set e.g. $env:API_PORT = "8090" and start the frontend with the same value.
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$env:PYTHONPATH = "."
$port = if ($env:API_PORT) { $env:API_PORT } else { "8000" }
$python = if (Test-Path "venv/Scripts/python.exe") { "venv/Scripts/python.exe" } else { "python" }
New-Item -ItemType Directory -Force "logs" | Out-Null
& $python -m uvicorn backend.server:app --host 127.0.0.1 --port $port --log-level info 2>&1 | Out-File -FilePath "logs/backend_verify.log" -Append
