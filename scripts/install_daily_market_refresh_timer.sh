#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -n "${PYTHON_BIN:-}" ]]; then
  python_bin="$PYTHON_BIN"
elif [[ -x "$repo_root/.venv/bin/python" ]]; then
  python_bin="$repo_root/.venv/bin/python"
elif command -v python >/dev/null 2>&1; then
  python_bin="$(command -v python)"
elif command -v python3 >/dev/null 2>&1; then
  python_bin="$(command -v python3)"
else
  python_bin=""
fi
unit_dir="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
morning_service="$unit_dir/memos-market-refresh-morning.service"
morning_timer="$unit_dir/memos-market-refresh-morning.timer"
capture_service="$unit_dir/memos-kis-two-stage-capture.service"
capture_timer="$unit_dir/memos-kis-two-stage-capture.timer"
finalize_service="$unit_dir/memos-kis-two-stage-finalize.service"
finalize_timer="$unit_dir/memos-kis-two-stage-finalize.timer"

if [[ -z "$python_bin" ]]; then
  echo "python 실행 파일을 찾지 못했습니다. PYTHON_BIN을 지정하세요." >&2
  exit 1
fi

mkdir -p "$unit_dir"

cat >"$morning_service" <<EOF
[Unit]
Description=MEMO'S 09:00 KRX metadata/indices/gold, ECOS and FRED refresh
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory=$repo_root
Environment=PYTHONPATH=$repo_root/backend
Environment=DAILY_REFRESH_KIS_ENABLED=true
ExecStart=$python_bin -m pipelines.daily_refresh --profile morning
TimeoutStartSec=45min
EOF

cat >"$morning_timer" <<'EOF'
[Unit]
Description=Run MEMO'S KRX and economic refresh daily at 09:00 Asia/Seoul

[Timer]
OnCalendar=*-*-* 09:00:00 Asia/Seoul
Persistent=true
AccuracySec=1min
Unit=memos-market-refresh-morning.service

[Install]
WantedBy=timers.target
EOF

cat >"$capture_service" <<EOF
[Unit]
Description=MEMO'S KIS fundamentals raw capture at 20:00 KST
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory=$repo_root
Environment=PYTHONPATH=$repo_root/backend
Environment=PYTHONUNBUFFERED=1
ExecStart=$python_bin $repo_root/scripts/collect_kis_fundamentals_snapshots.py capture-auto
TimeoutStartSec=30min
StandardOutput=append:$repo_root/logs/diagnostics/kis_fundamentals_two_stage/capture-auto.log
StandardError=append:$repo_root/logs/diagnostics/kis_fundamentals_two_stage/capture-auto.log
EOF

cat >"$capture_timer" <<'EOF'
[Unit]
Description=Run MEMO'S KIS fundamentals capture at 20:00 KST on weekdays

[Timer]
OnCalendar=Mon..Fri *-*-* 20:00:00 Asia/Seoul
Persistent=false
AccuracySec=1s
Unit=memos-kis-two-stage-capture.service

[Install]
WantedBy=timers.target
EOF

cat >"$finalize_service" <<EOF
[Unit]
Description=MEMO'S verified KIS OHLCV and fundamentals finalization at 08:00 KST
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory=$repo_root
Environment=PYTHONPATH=$repo_root/backend
Environment=PYTHONUNBUFFERED=1
ExecStart=$python_bin $repo_root/scripts/collect_kis_fundamentals_snapshots.py finalize-auto --recovery-days 10 --krx-warning-only
TimeoutStartSec=50min
StandardOutput=append:$repo_root/logs/diagnostics/kis_fundamentals_two_stage/finalize-auto.log
StandardError=append:$repo_root/logs/diagnostics/kis_fundamentals_two_stage/finalize-auto.log
EOF

cat >"$finalize_timer" <<'EOF'
[Unit]
Description=Run verified MEMO'S KIS finalization Tue-Fri at 08:00 KST

[Timer]
OnCalendar=Tue..Fri *-*-* 08:00:00 Asia/Seoul
Persistent=false
AccuracySec=1s
Unit=memos-kis-two-stage-finalize.service

[Install]
WantedBy=timers.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now \
  memos-market-refresh-morning.timer \
  memos-kis-two-stage-capture.timer \
  memos-kis-two-stage-finalize.timer
systemctl --user is-enabled --quiet memos-market-refresh-morning.timer
systemctl --user is-active --quiet memos-market-refresh-morning.timer
systemctl --user is-enabled --quiet memos-kis-two-stage-capture.timer
systemctl --user is-active --quiet memos-kis-two-stage-capture.timer
systemctl --user is-enabled --quiet memos-kis-two-stage-finalize.timer
systemctl --user is-active --quiet memos-kis-two-stage-finalize.timer

# Disable legacy timers only after all replacements are live.
systemctl --user disable --now memos-market-refresh-evening.timer 2>/dev/null || true
systemctl --user disable --now memos-market-refresh.timer 2>/dev/null || true

echo "설치 완료: 08:00 KIS Finalize / 09:00 KRX·경제 / 20:00 KIS Capture"
systemctl --user list-timers \
  memos-market-refresh-morning.timer \
  memos-kis-two-stage-capture.timer \
  memos-kis-two-stage-finalize.timer \
  --no-pager
