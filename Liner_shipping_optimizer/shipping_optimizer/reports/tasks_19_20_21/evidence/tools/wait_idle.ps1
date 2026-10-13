# Wait until the machine is quiet (average CPU < 20 % over 3 two-second samples), at most 30 minutes.
# CBC at 120 s is CPU-load sensitive; a batch started while the machine is busy is not comparable.
param([int]$MaxMinutes = 30)
$deadline = (Get-Date).AddMinutes($MaxMinutes)
while ($true) {
    $s = (Get-Counter '\Processor(_Total)\% Processor Time' -SampleInterval 2 -MaxSamples 3).CounterSamples |
         ForEach-Object { $_.CookedValue }
    $avg = ($s | Measure-Object -Average).Average
    if ($avg -lt 20) { Write-Output ("idle: avg cpu {0:N1} %" -f $avg); break }
    if ((Get-Date) -gt $deadline) { Write-Output ("timeout: avg cpu {0:N1} % (proceeding)" -f $avg); break }
    Start-Sleep -Seconds 15
}
