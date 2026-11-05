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
morning_service="$unit_dir/memos-market-refresh-morning.service"
morning_timer="$unit_dir/memos-market-refresh-morning.timer"
evening_service="$unit_dir/memos-market-refresh-evening.service"
evening_timer="$unit_dir/memos-market-refresh-evening.timer"

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

cat >"$evening_service" <<EOF
[Unit]
Description=MEMO'S 18:30 KIS prices and fundamentals refresh
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory=$repo_root
Environment=PYTHONPATH=$repo_root/backend
Environment=DAILY_REFRESH_KIS_ENABLED=true
ExecStart=$python_bin -m pipelines.daily_refresh --profile evening
TimeoutStartSec=infinity
EOF

cat >"$evening_timer" <<'EOF'
[Unit]
Description=Run MEMO'S KIS refresh daily at 18:30 Asia/Seoul

[Timer]
OnCalendar=*-*-* 18:30:00 Asia/Seoul
Persistent=true
AccuracySec=1min
Unit=memos-market-refresh-evening.service

[Install]
WantedBy=timers.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now \
  memos-market-refresh-morning.timer \
  memos-market-refresh-evening.timer
systemctl --user is-enabled --quiet memos-market-refresh-morning.timer
systemctl --user is-active --quiet memos-market-refresh-morning.timer
systemctl --user is-enabled --quiet memos-market-refresh-evening.timer
systemctl --user is-active --quiet memos-market-refresh-evening.timer

# Disable the previous combined timer only after both replacements are live.
systemctl --user disable --now memos-market-refresh.timer 2>/dev/null || true

echo "설치 완료: 09:00 KRX·경제 / 18:30 KIS (Asia/Seoul)"
systemctl --user list-timers \
  memos-market-refresh-morning.timer \
  memos-market-refresh-evening.timer \
  --no-pager
