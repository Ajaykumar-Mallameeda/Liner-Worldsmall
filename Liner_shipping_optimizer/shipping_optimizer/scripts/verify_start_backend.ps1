Set-Location "C:/Users/M AJAY KUMAR/Liner_shipping_optimizer/shipping_optimizer"
$env:PYTHONPATH = "."
& "venv/Scripts/python.exe" -m uvicorn backend.server:app --host 127.0.0.1 --port 8000 --log-level info 2>&1 | Out-File -FilePath "logs/backend_verify.log" -Append
