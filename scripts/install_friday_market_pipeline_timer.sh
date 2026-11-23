#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python_bin="${PYTHON_BIN:-$repo_root/.venv/bin/python}"
unit_dir="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"

if [[ "${1:-}" != "--apply" ]]; then
  cat <<EOF
검토 전용: 아직 systemd를 변경하지 않았습니다.

설치 대상:
  memos-friday-krx-raw.service/.timer       Sat 08:00, Persistent=false
  memos-friday-kis-adjusted.service/.timer Mon 08:00, Persistent=false

승인 후 실행:
  bash $repo_root/scripts/install_friday_market_pipeline_timer.sh --apply
EOF
  exit 0
fi

if [[ ! -x "$python_bin" ]]; then
  echo "Python 실행 파일이 없습니다: $python_bin" >&2
  exit 1
fi

mkdir -p "$unit_dir"

cat >"$unit_dir/memos-friday-krx-raw.service" <<EOF
[Unit]
Description=MEMO'S Saturday verified KRX Friday raw prices
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory=$repo_root
Environment=PYTHONPATH=$repo_root/backend
Environment=PYTHONUNBUFFERED=1
Environment=FRIDAY_MARKET_PIPELINE_ENABLED=true
ExecStart=$python_bin $repo_root/scripts/collect_friday_market_data.py saturday-auto
TimeoutStartSec=20min
StandardOutput=append:$repo_root/logs/market/friday_finality_v1/saturday-auto.log
StandardError=append:$repo_root/logs/market/friday_finality_v1/saturday-auto.log
EOF

cat >"$unit_dir/memos-friday-krx-raw.timer" <<'EOF'
[Unit]
Description=Run verified Friday KRX raw stage Saturday at 08:00 KST

[Timer]
OnCalendar=Sat *-*-* 08:00:00 Asia/Seoul
Persistent=false
AccuracySec=1s
Unit=memos-friday-krx-raw.service

[Install]
WantedBy=timers.target
EOF

cat >"$unit_dir/memos-friday-kis-adjusted.service" <<EOF
[Unit]
Description=MEMO'S Monday KIS adjusted Friday finalization
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory=$repo_root
Environment=PYTHONPATH=$repo_root/backend
Environment=PYTHONUNBUFFERED=1
Environment=FRIDAY_MARKET_PIPELINE_ENABLED=true
Environment=KIS_REQUEST_INTERVAL=0.5
ExecStart=$python_bin $repo_root/scripts/collect_friday_market_data.py monday-auto
TimeoutStartSec=55min
StandardOutput=append:$repo_root/logs/market/friday_finality_v1/monday-auto.log
StandardError=append:$repo_root/logs/market/friday_finality_v1/monday-auto.log
EOF

cat >"$unit_dir/memos-friday-kis-adjusted.timer" <<'EOF'
[Unit]
Description=Run KIS adjusted Friday finalization Monday at 08:00 KST

[Timer]
OnCalendar=Mon *-*-* 08:00:00 Asia/Seoul
Persistent=false
AccuracySec=1s
Unit=memos-friday-kis-adjusted.service

[Install]
WantedBy=timers.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now \
  memos-friday-krx-raw.timer \
  memos-friday-kis-adjusted.timer
systemctl --user is-enabled --quiet memos-friday-krx-raw.timer
systemctl --user is-active --quiet memos-friday-krx-raw.timer
systemctl --user is-enabled --quiet memos-friday-kis-adjusted.timer
systemctl --user is-active --quiet memos-friday-kis-adjusted.timer
systemctl --user list-timers \
  memos-friday-krx-raw.timer \
  memos-friday-kis-adjusted.timer \
  --no-pager
