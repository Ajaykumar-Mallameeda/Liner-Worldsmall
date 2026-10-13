Set-Location "C:/Users/M AJAY KUMAR/Liner_shipping_optimizer/shipping_optimizer"
$env:PYTHONPATH = "."
$env:MARITIME_INTELLIGENCE_ENABLED = "1"
$env:MARITIME_TRAFFIC_ENABLED = "1"
$env:MARITIME_PORT_ENABLED = "1"
$env:MARITIME_WEATHER_ENABLED = "1"
$env:MARITIME_CONGESTION_ENABLED = "1"
$env:MARITIME_LIVE_ENABLED = "1"
& "venv/Scripts/python.exe" -m uvicorn backend.server:app --host 127.0.0.1 --port 8000 --log-level info 2>&1 | Out-File -FilePath "logs/backend_verify.log" -Append
