@echo off
setlocal EnableExtensions
rem ---------------------------------------------------------------------------------------------------------------
rem  Launch the dashboard (FastAPI backend + Vite frontend) on the newest pipeline run.
rem
rem    launch_dashboard.bat                  newest pipeline_output.json among: the repository root (WorldSmall runs),
rem                                          reports\dataset_runs\*\ (other datasets) and runs_extra\*\
rem    launch_dashboard.bat <file|folder>    that run instead (a pipeline_output.json, or a folder holding one)
rem
rem  Nothing is copied or overwritten: the backend serves the chosen run as "current" (PIPELINE_OUTPUT) and the dev
rem  server routes /pipeline_output.json to it. Backend and frontend each open in their own window; close them to stop.
rem ---------------------------------------------------------------------------------------------------------------
cd /d "%~dp0"

set "PY=python"
if exist "venv\Scripts\python.exe" set "PY=%CD%\venv\Scripts\python.exe"

rem --- 1. which run -----------------------------------------------------------------------------------------------
set "RUN=%~f1"
if not defined RUN goto find_latest
if exist "%RUN%\pipeline_output.json" set "RUN=%RUN%\pipeline_output.json"
goto check_run

:find_latest
for /f "usebackq delims=" %%F in (`powershell -NoProfile -Command "@(Get-ChildItem -Path 'pipeline_output.json','reports\dataset_runs\*\pipeline_output.json','runs_extra\*\pipeline_output.json' -File -ErrorAction SilentlyContinue) | Sort-Object LastWriteTime -Descending | Select-Object -First 1 -ExpandProperty FullName"`) do set "RUN=%%F"

:check_run
if not defined RUN (
  echo No pipeline_output.json found. Run the pipeline first:  "%PY%" tests\test_orchestrator.py
  goto fail
)
if not exist "%RUN%" (
  echo Run not found: "%RUN%"
  goto fail
)
echo.
echo  Run:
powershell -NoProfile -Command "$f = Get-Item -LiteralPath $env:RUN; $j = Get-Content -Raw -LiteralPath $f.FullName | ConvertFrom-Json; $ds = if ($j.dataset_run) { $j.dataset_run.dataset } elseif ($j.test_scorecard.dataset_run) { $j.test_scorecard.dataset_run.dataset } else { 'WorldSmall' }; '   file     ' + $f.FullName; '   dataset  ' + $ds; '   modified ' + $f.LastWriteTime.ToString('yyyy-MM-dd HH:mm')"

rem --- 2. backend port: first free one (Windows/Hyper-V can reserve ranges around 8000) -------------------------------
for /f "usebackq delims=" %%P in (`powershell -NoProfile -Command "foreach ($p in 8000,8090,8100,8180,8280,8380) { if (Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue) { continue }; try { $l = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, $p); $l.ExclusiveAddressUse = $true; $l.Start(); $l.Stop(); $p; break } catch {} }"`) do set "API_PORT=%%P"
if not defined API_PORT (
  echo No free backend port among 8000, 8090, 8100, 8180, 8280, 8380.
  goto fail
)

rem --- 3. frontend dependencies -------------------------------------------------------------------------------------
if not exist "frontend\node_modules\.bin\vite.cmd" (
  echo Installing frontend dependencies ^(first launch only^)...
  pushd frontend
  call npm install
  popd
  if not exist "frontend\node_modules\.bin\vite.cmd" (
    echo npm install failed.
    goto fail
  )
)

rem --- 4. backend -----------------------------------------------------------------------------------------------------
set "PIPELINE_OUTPUT=%RUN%"
set "PYTHONPATH=%CD%"
echo.
echo  Starting backend on http://127.0.0.1:%API_PORT% ...
start "Liner backend :%API_PORT%" /D "%CD%" cmd /k ""%PY%" -m uvicorn backend.server:app --host 127.0.0.1 --port %API_PORT%"

powershell -NoProfile -Command "for ($i = 0; $i -lt 90; $i++) { try { Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 ('http://127.0.0.1:' + $env:API_PORT + '/api/health') | Out-Null; exit 0 } catch { Start-Sleep -Seconds 1 } }; exit 1"
if errorlevel 1 (
  echo Backend did not answer within 90 s - see the "Liner backend" window for the error.
  goto fail
)
echo  Backend is up.

rem --- 5. frontend (opens the browser itself, on 5173 or the next free port) -------------------------------------------
set "DASHBOARD_RUN_FROM_API=1"
echo  Starting dashboard ...
start "Liner dashboard" /D "%CD%\frontend" cmd /k "node_modules\.bin\vite.cmd --open"
echo.
echo  Done. The browser opens on the dashboard; close the two windows to stop it.
endlocal
exit /b 0

:fail
echo.
pause
endlocal
exit /b 1
