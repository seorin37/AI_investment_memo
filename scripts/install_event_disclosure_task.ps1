<#
수시공시 수집을 Windows 작업 스케줄러에 등록한다 (매일 12:30, 19:30).

- 지금 로그인한 사용자로, 로그인해 있을 때만 돈다. 비밀번호를 저장하지 않는다.
- PC가 꺼져 있어 시간을 놓치면 켜진 뒤 바로 한 번 돈다(StartWhenAvailable).
- 앞 실행이 아직 돌고 있으면 새 실행은 건너뛴다. 2시간이 넘으면 멈춘다.
- 다시 실행하면 같은 이름의 작업을 새 설정으로 덮어쓴다.

등록:  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\install_event_disclosure_task.ps1
해제:  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\install_event_disclosure_task.ps1 -Uninstall
확인:  Get-ScheduledTask -TaskName MemoEventDisclosures | Get-ScheduledTaskInfo
지금 한 번:  Start-ScheduledTask -TaskName MemoEventDisclosures
#>
param(
    [string]$Python = "",
    [string[]]$Times = @("12:30", "19:30"),
    [switch]$Uninstall
)

$ErrorActionPreference = "Stop"
$TaskName = "MemoEventDisclosures"

if ($Uninstall) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "작업을 지웠습니다: $TaskName"
    exit 0
}

$RepoRoot = Split-Path -Parent $PSScriptRoot
$Runner = Join-Path $PSScriptRoot "run_event_disclosures.ps1"
if (-not $Python) { $Python = Join-Path $env:USERPROFILE "miniforge3\envs\ai_memo\python.exe" }
if (-not (Test-Path $Python)) { throw "python을 찾지 못했습니다: $Python (-Python으로 지정)" }

$action = New-ScheduledTaskAction -Execute "powershell.exe" -WorkingDirectory $RepoRoot `
    -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$Runner`" -Python `"$Python`""
$triggers = $Times | ForEach-Object { New-ScheduledTaskTrigger -Daily -At $_ }
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$principal = New-ScheduledTaskPrincipal -UserId ([Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $triggers -Settings $settings -Principal $principal `
    -Description "MEMO 코스피 수시공시 수집 (scripts\run_event_disclosures.ps1)" -Force | Out-Null

Write-Host "등록했습니다: $TaskName (매일 $($Times -join ', '))"
Write-Host "로그: $(Join-Path $RepoRoot 'logs\event_disclosures')"
