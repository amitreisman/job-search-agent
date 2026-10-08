# Registers the two Windows scheduled tasks for the job agent (runs as the current user, no password needed).
#   JobAgent-Scout : 07:30, 09:30, 11:30, 13:30 daily (runs a missed scan when the PC comes back on)
#   JobAgent-Bot   : starts at logon and stays running; restarts itself if it dies
$dir = $PSScriptRoot
$py = "C:\Python314\python.exe"
$user = "$env:USERDOMAIN\$env:USERNAME"

function Hidden($script, $log) {
    $cmd = "`$env:PYTHONIOENCODING='utf-8'; Set-Location '$dir'; & '$py' $script *>> '$dir\data\$log'"
    New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -WindowStyle Hidden -Command `"$cmd`""
}

# --- Scout ---
$times = "07:30", "09:30", "11:30", "13:30"
$triggers = $times | ForEach-Object { New-ScheduledTaskTrigger -Daily -At $_ }
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName "JobAgent-Scout" -Action (Hidden "scout.py" "scout.log") -Trigger $triggers `
    -Settings $settings -User $user -RunLevel Limited -Force | Out-Null

# --- Bot ---
$botSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 99 -RestartInterval (New-TimeSpan -Minutes 1) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName "JobAgent-Bot" -Action (Hidden "bot.py" "bot.log") `
    -Trigger (New-ScheduledTaskTrigger -AtLogOn -User $user) -Settings $botSettings -User $user -RunLevel Limited -Force | Out-Null

Get-ScheduledTask -TaskName "JobAgent-*" | Select-Object TaskName, State | Format-Table -AutoSize
