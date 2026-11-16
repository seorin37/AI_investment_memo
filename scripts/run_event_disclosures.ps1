<#
코스피 수시공시 수집(run_events)을 한 번 실행한다. 작업 스케줄러가 하루 2번 부른다.

- 기간: 어제 ~ 오늘(KST). 하루 마지막 실행 뒤에 나온 공시를 다음 날 받기 위해 어제도 다시 본다.
  이미 저장한 공시는 건너뛰므로 어제를 다시 봐도 비용은 목록 조회 정도다.
- DB: 저장소 루트 .env의 DATABASE_URL. 로그 첫 줄 근처의 [DB] 줄에 접속 대상이 나온다.
- 임베딩: GPU, 모델은 로컬 캐시에서만(--offline).
- 로그: logs\event_disclosures\run_*.log(출력), run_*.err.log(경고·오류), history.log(실행마다 한 줄).
- 종료 코드: run_events 그대로. 0 정상, 1 실패 있음, 2 사용법, 3 DART 한도(다음 실행에서 이어 받음), 4 API 키 없음.
  같은 작업이 이미 돌고 있으면 바로 끝낸다(10).

예)
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_event_disclosures.ps1 -DryRun
#>
param(
    [switch]$DryRun,
    [string]$Python = "",
    [int]$LookbackDays = 1,
    [int]$KeepLogDays = 30
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
if (-not $Python) { $Python = Join-Path $env:USERPROFILE "miniforge3\envs\ai_memo\python.exe" }
if (-not (Test-Path $Python)) { Write-Error "python을 찾지 못했습니다: $Python (-Python으로 지정)"; exit 2 }

$LogDir = Join-Path $RepoRoot "logs\event_disclosures"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

# 같은 실행이 겹치지 않게 (수동 실행과 예약 실행이 동시에 도는 경우)
$mutex = New-Object System.Threading.Mutex($false, "Local\memo_event_disclosures")
if (-not $mutex.WaitOne(0)) {
    Add-Content -Path (Join-Path $LogDir "history.log") -Encoding UTF8 -Value "$(Get-Date -Format s) 건너뜀: 이미 실행 중"
    exit 10
}

try {
    $kst = [System.TimeZoneInfo]::ConvertTimeBySystemTimeZoneId([DateTime]::UtcNow, "Korea Standard Time")
    $until = $kst.ToString("yyyy-MM-dd")
    $since = $kst.AddDays(-$LookbackDays).ToString("yyyy-MM-dd")
    $stamp = $kst.ToString("yyyyMMdd_HHmmss")
    $outLog = Join-Path $LogDir "run_$stamp.log"
    $errLog = Join-Path $LogDir "run_$stamp.err.log"

    $runArgs = @("-m", "pipelines.disclosures.run_events", "--since", $since, "--until", $until, "--offline")
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
        2 { "사용법 오류" }
        3 { "DART 한도 - 다음 실행에서 이어 받음" }
        4 { "DART API 키 없음" }
        default { "알 수 없는 종료 코드" }
    }
    $mode = if ($DryRun) { "dry-run" } else { "저장" }
    Add-Content -Path (Join-Path $LogDir "history.log") -Encoding UTF8 `
        -Value "$(Get-Date -Format s) $mode $since~$until 종료=$code($meaning) ${minutes}분 로그=run_$stamp.log"

    # 오래된 실행 로그 정리 (history.log는 남긴다)
    Get-ChildItem -Path $LogDir -Filter "run_*.log" |
        Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-$KeepLogDays) } |
        Remove-Item -Force

    exit $code
}
finally {
    $mutex.ReleaseMutex()
    $mutex.Dispose()
}
