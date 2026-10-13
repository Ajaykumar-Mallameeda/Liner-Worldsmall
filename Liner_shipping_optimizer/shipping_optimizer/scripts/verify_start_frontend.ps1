Set-Location "C:/Users/M AJAY KUMAR/Liner_shipping_optimizer/shipping_optimizer/frontend"
& "node_modules/.bin/vite.cmd" --host 127.0.0.1 --port 5173 2>&1 | Out-File -FilePath "../logs/frontend_verify.log" -Append
