@echo off
echo Starting Shipping Optimizer Live Dashboard...
echo =============================================

echo.
echo 1. Starting Backend Server...
cd /d "%~dp0backend"
start "Backend Server" cmd /k "python main.py"
timeout /t 3 /nobreak >nul

echo.
echo 2. Starting Frontend Server...
cd /d "%~dp0frontend"
start "Frontend Server" cmd /k "npm run dev"
timeout /t 5 /nobreak >nul

echo.
echo 3. Opening Dashboard...
start http://localhost:5173

echo.
echo =============================================
echo Dashboard is running!
echo.
echo Backend: http://localhost:8000
echo Frontend: http://localhost:5173 (or higher ports)
echo.
echo The dashboard will connect to the real pipeline
echo when you click "Start Pipeline" with "Use Real Pipeline" checked.
echo =============================================
echo.
echo Press any key to exit...
pause >nul