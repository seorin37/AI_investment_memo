#!/usr/bin/env bash
# AI 업데이트 매일 실행(pipelines.updates.daily)을 systemd user timer로 설치한다 (memos-news-fulltext.timer와 같은 방식).
#   PYTHON_BIN=~/miniforge3/envs/ai_memo/bin/python scripts/install_updates_daily_timer.sh            # 유닛 파일만 쓴다
#   PYTHON_BIN=~/miniforge3/envs/ai_memo/bin/python scripts/install_updates_daily_timer.sh --enable   # 쓰고 timer를 켠다
# 매일 06:30(Asia/Seoul)에 AI가 켜진 메모의 active 항목을 처리해 공용 DB에 카드를 쓴다 (--allow-shared-write).
# 전날 18:30 종가·저녁 공시·밤사이 뉴스(매시 10분 원문 수집·임베딩)가 들어온 뒤, 장 시작 전에 끝나게 06:30.
# Persistent=true: 06:30에 PC가 꺼져 있었으면 켜질 때 한 번 돈다. 중복 실행은 Postgres advisory lock이 막는다.
# 확인: systemctl --user list-timers memos-updates-daily.timer / journalctl --user -u memos-updates-daily.service
#       실행 상태는 logs/updates_daily/latest.json, 출력은 logs/updates_daily/daily.log, 비용은 results/updates/usage_log.jsonl
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
# 질의 임베딩(BGE-M3)이 GPU를 쓰므로 WSL GPU 도구 경로를 앞에 붙인다 (memos-news-fulltext와 같게)
service_path="/usr/local/bin:/usr/bin:/bin"
if [[ -d /usr/lib/wsl/lib ]]; then
  service_path="/usr/lib/wsl/lib:$service_path"
fi
service="$unit_dir/memos-updates-daily.service"
timer="$unit_dir/memos-updates-daily.timer"
log_dir="$repo_root/logs/updates_daily"

if [[ -z "$python_bin" ]]; then
  echo "python 실행 파일을 찾지 못했습니다. PYTHON_BIN을 지정하세요." >&2
  exit 1
fi

mkdir -p "$unit_dir" "$log_dir"

cat >"$service" <<EOF
[Unit]
Description=MEMO'S AI updates daily run (AI-linked memos, cards to shared DB)
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory=$repo_root
Environment=PYTHONPATH=$repo_root/backend
Environment=PATH=$service_path
ExecStart=$python_bin -m pipelines.updates.daily --allow-shared-write
StandardOutput=append:$log_dir/daily.log
StandardError=append:$log_dir/daily.log
TimeoutStartSec=3h
EOF

cat >"$timer" <<'EOF'
[Unit]
Description=Run MEMO'S AI updates daily at 06:30 Asia/Seoul

[Timer]
OnCalendar=*-*-* 06:30:00 Asia/Seoul
Persistent=true
AccuracySec=1min
Unit=memos-updates-daily.service

[Install]
WantedBy=timers.target
EOF

systemctl --user daemon-reload
echo "유닛 파일을 썼습니다: $service, $timer"
echo "  PATH: $service_path"
echo "  ExecStart: $python_bin -m pipelines.updates.daily --allow-shared-write"

if [[ "${1:-}" == "--enable" ]]; then
  systemctl --user enable --now memos-updates-daily.timer
  systemctl --user is-enabled --quiet memos-updates-daily.timer
  systemctl --user is-active --quiet memos-updates-daily.timer
  echo "설치 완료: 매일 06:30 (Asia/Seoul)"
  systemctl --user list-timers memos-updates-daily.timer --no-pager
else
  echo "timer는 켜지 않았습니다. 켜려면 --enable을 붙여 다시 실행하거나: systemctl --user enable --now memos-updates-daily.timer"
fi
