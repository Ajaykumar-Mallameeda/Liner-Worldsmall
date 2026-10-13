param(
  [Parameter(Mandatory=$true)][string]$Tree,
  [Parameter(Mandatory=$true)][string]$Label,
  [Parameter(Mandatory=$true)][ValidateSet('orch','suite')][string]$Kind,
  [Parameter(Mandatory=$true)][string]$OutDir
)
# Same interpreter, same commands for every tree.
#   orch : python -m pytest tests/test_orchestrator.py -v -s --tb=short -p no:cacheprovider
#   suite: python -m pytest tests --ignore=tests/test_orchestrator.py -q --tb=line -p no:cacheprovider --junitxml=<xml>
$ErrorActionPreference = 'Continue'
$py = 'C:\Users\WINDOWS\Liner-Worldsmall\Liner_shipping_optimizer\shipping_optimizer\venv\Scripts\python.exe'
New-Item -ItemType Directory -Force $OutDir | Out-Null
$log  = Join-Path $OutDir "$Label.log"
$meta = Join-Path $OutDir "$Label.meta.txt"
$xml  = Join-Path $OutDir "$Label.junit.xml"
Set-Location $Tree
$env:PYTHONPYCACHEPREFIX = Join-Path $OutDir "pycache_$Label"
$start = Get-Date
if ($Kind -eq 'orch') {
  $cmd = "tests/test_orchestrator.py -v -s --tb=short -p no:cacheprovider"
} else {
  $cmd = "tests --ignore=tests/test_orchestrator.py -q --tb=line -p no:cacheprovider --junitxml=`"$xml`""
}
"tree: $Tree"                                   | Set-Content $meta
"command: python -m pytest $cmd"               | Add-Content $meta
"python: $(& $py --version 2>&1)"              | Add-Content $meta
"resolved src: $(& $py -c 'import src,sys;print(src.__file__)' 2>&1)" | Add-Content $meta
"started: $start"                              | Add-Content $meta
cmd /c "`"$py`" -m pytest $cmd > `"$log`" 2>&1"
$code = $LASTEXITCODE
$end = Get-Date
"exit_code: $code"                             | Add-Content $meta
"ended: $end"                                  | Add-Content $meta
"elapsed_s: $([int]($end-$start).TotalSeconds)" | Add-Content $meta
if ($Kind -eq 'orch') {
  $sc   = Select-String -Path $log -Pattern 'Passed\s+:|Failed\s+:|Warnings:' | ForEach-Object { ($_.Line -replace '\x1b\[[0-9;]*m','').Trim() }
  $fail = Select-String -Path $log -Pattern '91m-' -Context 0,1 | ForEach-Object { ($_.Line -replace '\x1b\[[0-9;]*m','').Trim() + ' | ' + (($_.Context.PostContext -join ' ') -replace '\x1b\[[0-9;]*m','').Trim() }
  "--- scorecard ---" | Add-Content $meta; $sc | Add-Content $meta
  "--- failed assertions ---" | Add-Content $meta; $fail | Add-Content $meta
  # keep a copy of the generated artifact for KPI extraction
  if (Test-Path (Join-Path $Tree 'pipeline_output.json')) { Copy-Item -Force (Join-Path $Tree 'pipeline_output.json') (Join-Path $OutDir "$Label.pipeline_output.json") }
} else {
  "--- tail ---" | Add-Content $meta
  Get-Content $log -Tail 4 | Add-Content $meta
}
