. (Join-Path $PSScriptRoot "setup_common.ps1")

$taskName = "AutoAbsenMaganghub"
$workDir = $PSScriptRoot
$scriptPath = Join-Path $PSScriptRoot "main.py"
$pythonPath = Get-PythonPath $workDir

$clockInTime = Get-EnvValue (Join-Path $workDir ".env") "CLOCK_IN_TIME"
$span = ConvertTo-TimeOfDay $clockInTime
if ($null -eq $span) {
    if ($clockInTime) {
        Write-Host "[WARN] CLOCK_IN_TIME '$clockInTime' tidak valid, pakai 16:00."
    }
    $span = ConvertTo-TimeOfDay "16:00"
}

$action = New-ScheduledTaskAction -Execute $pythonPath -Argument "$scriptPath absen" -WorkingDirectory $workDir
$trigger = New-ScheduledTaskTrigger -Daily -At ((Get-Date).Date + $span)

$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType S4U -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -WakeToRun

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force

Write-Host "[OK] Task '$taskName' berhasil dibuat: clock in setiap $($span.ToString('hh\:mm'))"
Write-Host "Cek: Get-ScheduledTask -TaskName '$taskName'"
Write-Host "Hapus: Unregister-ScheduledTask -TaskName '$taskName' -Confirm:`$false"
