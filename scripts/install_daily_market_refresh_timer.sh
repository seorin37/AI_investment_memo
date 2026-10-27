#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -n "${PYTHON_BIN:-}" ]]; then
  python_bin="$PYTHON_BIN"
elif command -v python >/dev/null 2>&1; then
  python_bin="$(command -v python)"
elif command -v python3 >/dev/null 2>&1; then
  python_bin="$(command -v python3)"
else
  python_bin=""
fi
unit_dir="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
service_file="$unit_dir/memos-market-refresh.service"
timer_file="$unit_dir/memos-market-refresh.timer"

if [[ -z "$python_bin" ]]; then
  echo "python 실행 파일을 찾지 못했습니다. PYTHON_BIN을 지정하세요." >&2
  exit 1
fi

mkdir -p "$unit_dir"

cat >"$service_file" <<EOF
[Unit]
Description=MEMO'S daily KRX, ECOS and FRED incremental refresh
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory=$repo_root
Environment=PYTHONPATH=$repo_root/backend
ExecStart=$python_bin -m pipelines.daily_refresh
TimeoutStartSec=45min
EOF

cat >"$timer_file" <<'EOF'
[Unit]
Description=Run MEMO'S market refresh daily at 09:00 Asia/Seoul

[Timer]
OnCalendar=*-*-* 09:00:00 Asia/Seoul
Persistent=true
AccuracySec=1min
Unit=memos-market-refresh.service

[Install]
WantedBy=timers.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now memos-market-refresh.timer

echo "설치 완료: 매일 09:00 Asia/Seoul"
systemctl --user list-timers memos-market-refresh.timer --no-pager
