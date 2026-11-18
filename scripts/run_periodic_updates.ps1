<#
정기보고서 증분 업데이트(run_periodic_updates)를 한 번 실행한다. 작업 스케줄러가 매일 새벽 1회 부른다.

- 기간: run_periodic_updates 기본값 (지난 실행 종료일 - 3일 ~ 오늘, 첫 실행은 2026-07-01부터).
- DB: 저장소 루트 .env의 DATABASE_URL.
- 임베딩: GPU, 모델은 로컬 캐시에서만(--offline). 보고서 시즌에는 몇 시간 걸린다.
- 로그: logs\periodic_updates\run_*.log(출력), run_*.err.log(경고·오류), history.log(실행마다 한 줄).
- 종료 코드: run_periodic_updates 그대로. 0 정상, 1 실패 있음, 3 DART 한도(다음 실행에서 이어 감), 4 API 키 없음.
  같은 작업이 이미 돌고 있으면 바로 끝낸다(10).

예)
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_periodic_updates.ps1 -DryRun
#>
param(
    [switch]$DryRun,
    [string]$Python = "",
    [int]$KeepLogDays = 60
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
if (-not $Python) { $Python = Join-Path $env:USERPROFILE "miniforge3\envs\ai_memo\python.exe" }
if (-not (Test-Path $Python)) { Write-Error "python을 찾지 못했습니다: $Python (-Python으로 지정)"; exit 2 }

$LogDir = Join-Path $RepoRoot "logs\periodic_updates"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$mutex = New-Object System.Threading.Mutex($false, "Local\memo_periodic_updates")
if (-not $mutex.WaitOne(0)) {
    Add-Content -Path (Join-Path $LogDir "history.log") -Encoding UTF8 -Value "$(Get-Date -Format s) 건너뜀: 이미 실행 중"
    exit 10
}

try {
    $kst = [System.TimeZoneInfo]::ConvertTimeBySystemTimeZoneId([DateTime]::UtcNow, "Korea Standard Time")
    $stamp = $kst.ToString("yyyyMMdd_HHmmss")
    $outLog = Join-Path $LogDir "run_$stamp.log"
    $errLog = Join-Path $LogDir "run_$stamp.err.log"

    $runArgs = @("-m", "pipelines.disclosures.run_periodic_updates", "--offline")
    if ($DryRun) { $runArgs += "--dry-run" }

    $env:PYTHONPATH = Join-Path $RepoRoot "backend"
    $env:PYTHONUTF8 = "1"
    $env:PYTHONIOENCODING = "utf-8"

    $started = Get-Date
    $proc = Start-Process -FilePath $Python -ArgumentList $runArgs -WorkingDirectory $RepoRoot `
        -RedirectStandardOutput $outLog -RedirectStandardError $errLog -NoNewWindow -Wait -PassThru
    $code = $proc.ExitCode
    $minutes = [math]::Round(((Get-Date) - $started).TotalMinutes, 1)

    $meaning = switch ($code) {
        0 { "정상" }
        1 { "실패 있음 (로그 확인)" }
        3 { "DART 한도 - 다음 실행에서 이어 감" }
        4 { "DART API 키 없음" }
        default { "알 수 없는 종료 코드" }
    }
    $mode = if ($DryRun) { "dry-run" } else { "저장" }
    Add-Content -Path (Join-Path $LogDir "history.log") -Encoding UTF8 `
        -Value "$(Get-Date -Format s) $mode 종료=$code($meaning) ${minutes}분 로그=run_$stamp.log"

    Get-ChildItem -Path $LogDir -Filter "run_*.log" |
        Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-$KeepLogDays) } |
        Remove-Item -Force

    exit $code
}
finally {
    $mutex.ReleaseMutex()
    $mutex.Dispose()
}
