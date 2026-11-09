#!/usr/bin/env bash
# 뉴스 원문 1시간 회차(backend.pipelines.news.fulltext_hourly)를 systemd user timer로 설치한다.
#   FULLTEXT_TARGET=192.168.0.105:15432 scripts/install_fulltext_hourly_timer.sh            # 유닛 파일만 쓴다
#   FULLTEXT_TARGET=192.168.0.105:15432 scripts/install_fulltext_hourly_timer.sh --enable   # 쓰고 timer를 켠다
# 매시 10분(Asia/Seoul)에 최근 FULLTEXT_RECENT_HOURS(기본 6)시간분을 처리한다. 처음 한 번 넓게 채울 때는 timer와 별도로
#   python -m backend.pipelines.news.fulltext_hourly --recent-hours 24 --target 192.168.0.105:15432
# 를 직접 돌린다 (같은 잠금을 쓰므로 timer 회차와 겹치지 않는다).
# 확인: systemctl --user list-timers memos-news-fulltext.timer / journalctl --user -u memos-news-fulltext.service
#       회차 요약은 logs/fulltext_hourly.log (한 줄 = 한 회차, JSON)
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
target="${FULLTEXT_TARGET:-}"
recent_hours="${FULLTEXT_RECENT_HOURS:-6}"
# FULLTEXT_TAG_STOCKS=1이면 적재 뒤 종목 태그도 더한다 (news_stocks에 씀, 승인 후에만)
tag_flag=""
if [[ "${FULLTEXT_TAG_STOCKS:-0}" == "1" ]]; then
  tag_flag=" --tag-stocks"
fi
unit_dir="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
# systemd 서비스의 PATH에는 WSL GPU 도구 경로가 없어 nvidia-smi를 못 찾는다 (GPU 여유 확인 실패). 있으면 앞에 붙인다
service_path="/usr/local/bin:/usr/bin:/bin"
if [[ -d /usr/lib/wsl/lib ]]; then
  service_path="/usr/lib/wsl/lib:$service_path"
fi
service="$unit_dir/memos-news-fulltext.service"
timer="$unit_dir/memos-news-fulltext.timer"

if [[ -z "$python_bin" ]]; then
  echo "python 실행 파일을 찾지 못했습니다. PYTHON_BIN을 지정하세요." >&2
  exit 1
fi
if [[ -z "$target" ]]; then
  echo "FULLTEXT_TARGET(접속 대상 host:port, 예: 192.168.0.105:15432)을 지정하세요. 실제 대상과 다르면 회차가 멈춥니다." >&2
  exit 1
fi

mkdir -p "$unit_dir"

cat >"$service" <<EOF
[Unit]
Description=MEMO'S news fulltext: collect recent ${recent_hours}h articles and load bodies/chunks
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory=$repo_root
Environment=PYTHONPATH=$repo_root
Environment=PATH=$service_path
ExecStart=$python_bin -m backend.pipelines.news.fulltext_hourly --recent-hours $recent_hours --target $target$tag_flag
TimeoutStartSec=50min
EOF

cat >"$timer" <<'EOF'
[Unit]
Description=Run MEMO'S news fulltext collection and load hourly at :10 Asia/Seoul

[Timer]
OnCalendar=*-*-* *:10:00 Asia/Seoul
Persistent=true
AccuracySec=1min
Unit=memos-news-fulltext.service

[Install]
WantedBy=timers.target
EOF

systemctl --user daemon-reload
echo "유닛 파일을 썼습니다: $service, $timer"
echo "  PATH: $service_path"
echo "  ExecStart: $python_bin -m backend.pipelines.news.fulltext_hourly --recent-hours $recent_hours --target $target$tag_flag"

if [[ "${1:-}" == "--enable" ]]; then
  systemctl --user enable --now memos-news-fulltext.timer
  systemctl --user is-enabled --quiet memos-news-fulltext.timer
  systemctl --user is-active --quiet memos-news-fulltext.timer
  echo "설치 완료: 매시 10분 (Asia/Seoul)"
  systemctl --user list-timers memos-news-fulltext.timer --no-pager
else
  echo "timer는 켜지 않았습니다. 켜려면 --enable을 붙여 다시 실행하거나: systemctl --user enable --now memos-news-fulltext.timer"
fi
