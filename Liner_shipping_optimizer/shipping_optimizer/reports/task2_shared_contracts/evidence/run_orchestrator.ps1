param([Parameter(Mandatory=$true)][string]$Label)
# Reproducible runner for the primary integration test. Same command every time.
# - clean bytecode cache via PYTHONPYCACHEPREFIX (avoids the stale OneDrive co_filename pycs)
# - archives the generated artifacts, then restores the files the test overwrites
$ErrorActionPreference = 'Continue'
$root    = 'C:\Users\WINDOWS\Liner-Worldsmall\Liner_shipping_optimizer\shipping_optimizer'
$scratch = 'C:\Users\WINDOWS\AppData\Local\Temp\claude\C--Users-WINDOWS-Liner-Worldsmall-Liner-shipping-optimizer-shipping-optimizer\1df83a85-a271-48db-ab4f-f96eda995cfa\scratchpad'
$orig    = Join-Path $scratch 'baseline_side_effect_files'
$log     = Join-Path $scratch "$Label.log"
$meta    = Join-Path $scratch "$Label.meta.txt"
Set-Location $root
$env:PYTHONPYCACHEPREFIX = Join-Path $scratch 'pycache'
$start = Get-Date
"command: python -m pytest tests/test_orchestrator.py -v -s --tb=short -p no:cacheprovider" | Set-Content $meta
"env: PYTHONPYCACHEPREFIX=$env:PYTHONPYCACHEPREFIX" | Add-Content $meta
"python: $(python --version 2>&1)" | Add-Content $meta
"started: $start" | Add-Content $meta
cmd /c "python -m pytest tests/test_orchestrator.py -v -s --tb=short -p no:cacheprovider > `"$log`" 2>&1"
$code = $LASTEXITCODE
$end = Get-Date
"exit_code: $code" | Add-Content $meta
"ended: $end" | Add-Content $meta
"elapsed_s: $([int]($end-$start).TotalSeconds)" | Add-Content $meta
# archive generated artifacts
foreach ($f in 'pipeline_output.json','SYSTEM_TRUTH_REPORT.md','P2_DIAGNOSTIC_RUNTIME_VALIDATION_REPORT.md') {
  if (Test-Path (Join-Path $root $f)) { Copy-Item -Force (Join-Path $root $f) (Join-Path $scratch "$Label.$f") }
}
# restore the originals the test overwrote (pipeline_output.json did not exist before)
Copy-Item -Force (Join-Path $orig 'SYSTEM_TRUTH_REPORT.md') (Join-Path $root 'SYSTEM_TRUTH_REPORT.md')
Copy-Item -Force (Join-Path $orig 'P2_DIAGNOSTIC_RUNTIME_VALIDATION_REPORT.md') (Join-Path $root 'P2_DIAGNOSTIC_RUNTIME_VALIDATION_REPORT.md')
Copy-Item -Force (Join-Path $orig 'frontend__public__pipeline_output.json') (Join-Path $root 'frontend\public\pipeline_output.json')
Remove-Item -Force (Join-Path $root 'pipeline_output.json') -ErrorAction SilentlyContinue
# one-line verdict
$sc = Select-String -Path $log -Pattern 'Passed\s+:|Failed\s+:|Warnings:' | ForEach-Object { ($_.Line -replace '\x1b\[[0-9;]*m','').Trim() }
$fail = Select-String -Path $log -Pattern '91m-' -Context 0,1 | ForEach-Object { ($_.Line -replace '\x1b\[[0-9;]*m','').Trim() + ' | ' + (($_.Context.PostContext -join ' ') -replace '\x1b\[[0-9;]*m','').Trim() }
"--- scorecard ---" | Add-Content $meta; $sc | Add-Content $meta
"--- failed assertions ---" | Add-Content $meta; $fail | Add-Content $meta
Get-Content $meta
