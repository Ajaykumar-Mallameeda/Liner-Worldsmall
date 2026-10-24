# Start the Vite dev server from this checkout (paths are relative to this script).
# The dev server proxies /api, /data and /ws to http://127.0.0.1:$env:API_PORT (default 8000); use the same API_PORT as the backend.
$root = Split-Path -Parent $PSScriptRoot
Set-Location (Join-Path $root "frontend")
New-Item -ItemType Directory -Force "../logs" | Out-Null
& "node_modules/.bin/vite.cmd" --host 127.0.0.1 --port 5173 2>&1 | Out-File -FilePath "../logs/frontend_verify.log" -Append
