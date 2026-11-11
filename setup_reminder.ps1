. (Join-Path $PSScriptRoot "setup_common.ps1")

$taskName = "AutoAbsenMaganghubReminder"
$workDir = $PSScriptRoot
$scriptPath = Join-Path $PSScriptRoot "main.py"
$pythonPath = Get-PythonPath $workDir

$rawTimes = Get-EnvValue (Join-Path $workDir ".env") "REMINDER_TIMES"
if (-not $rawTimes) {
    $rawTimes = "16:00,21:00"
}

$triggers = @()
$validTimes = @()
foreach ($value in ($rawTimes -split ',')) {
    $value = $value.Trim()
    if (-not $value) {
        continue
    }
    $span = ConvertTo-TimeOfDay $value
    if ($null -eq $span) {
        Write-Host "[WARN] REMINDER_TIMES '$value' tidak valid, dilewati."
        continue
    }
    $triggers += New-ScheduledTaskTrigger -Daily -At ((Get-Date).Date + $span)
    $validTimes += $span.ToString('hh\:mm')
}

if ($triggers.Count -eq 0) {
    Write-Host "[FAIL] Tidak ada jam pengingat valid di REMINDER_TIMES."
    exit 1
}

$action = New-ScheduledTaskAction -Execute $pythonPath -Argument "$scriptPath remind" -WorkingDirectory $workDir
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType S4U -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -WakeToRun

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $triggers -Principal $principal -Settings $settings -Force

Write-Host "[OK] Task '$taskName' berhasil dibuat: pengingat setiap $($validTimes -join ', ')"
Write-Host "Cek: Get-ScheduledTask -TaskName '$taskName'"
Write-Host "Hapus: Unregister-ScheduledTask -TaskName '$taskName' -Confirm:`$false"
