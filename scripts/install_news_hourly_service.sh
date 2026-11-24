#!/usr/bin/env bash
# 실시간 뉴스 수집(backend.pipelines.news.pipeline hourly --loop)을 systemd user 서비스로 설치한다.
#   PYTHON_BIN=~/miniforge3/envs/ai_memo/bin/python scripts/install_news_hourly_service.sh            # 유닛 파일만 쓴다
#   PYTHON_BIN=~/miniforge3/envs/ai_memo/bin/python scripts/install_news_hourly_service.sh --enable   # 쓰고 서비스를 켠다
# 30분마다 RSS 수집 + 새 기사 임베딩, 2시간마다 네이버 보강(최근 3시간분). 기사를 지우지 않는다(--keep-days 0).
# Restart=always: 프로세스가 죽어도 60초 뒤 다시 뜬다. WSL이 켜져 있는 동안만 돈다 (꺼지지 않게 하는 설정은 HANDOFF 참고).
# 코드는 MEMOS_REPO_ROOT(기본: 이 스크립트가 있는 저장소)의 체크아웃을 쓴다. 다른 worktree에서 설치할 때는
#   MEMOS_REPO_ROOT=~/projects/AI_investment_memo 처럼 실행할 저장소를 지정한다.
# 확인: systemctl --user status memos-news-hourly.service / tail -f logs/news_hourly.log
# 멈춤: systemctl --user stop memos-news-hourly.service (다시 켜기: start, 부팅 시 자동 시작 끄기: disable)
set -euo pipefail

script_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
repo_root="${MEMOS_REPO_ROOT:-$script_root}"
repo_root="$(cd "$repo_root" && pwd)"
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
# 임베딩(BGE-M3)이 GPU를 쓰므로 WSL GPU 도구 경로를 앞에 붙인다 (memos-news-fulltext와 같게)
service_path="/usr/local/bin:/usr/bin:/bin"
if [[ -d /usr/lib/wsl/lib ]]; then
  service_path="/usr/lib/wsl/lib:$service_path"
fi
service="$unit_dir/memos-news-hourly.service"
log_file="$repo_root/logs/news_hourly.log"
args="hourly --embed --keep-days 0 --loop 1800 --naver-every 7200 --naver-hours 3"

if [[ -z "$python_bin" ]]; then
  echo "python 실행 파일을 찾지 못했습니다. PYTHON_BIN을 지정하세요." >&2
  exit 1
fi
if [[ ! -f "$repo_root/backend/pipelines/news/pipeline.py" ]]; then
  echo "$repo_root 에 backend/pipelines/news/pipeline.py가 없습니다. MEMOS_REPO_ROOT를 확인하세요." >&2
  exit 1
fi

mkdir -p "$unit_dir" "$repo_root/logs"

cat >"$service" <<EOF
[Unit]
Description=MEMO'S news realtime collection (RSS every 30min + embed, Naver every 2h)
After=network-online.target
Wants=network-online.target
StartLimitIntervalSec=0

[Service]
Type=simple
WorkingDirectory=$repo_root
Environment=PYTHONPATH=$repo_root
Environment=PATH=$service_path
Environment=PYTHONUNBUFFERED=1
ExecStart=$python_bin -m backend.pipelines.news.pipeline $args
Restart=always
RestartSec=60
KillSignal=SIGINT
TimeoutStopSec=60
StandardOutput=append:$log_file
StandardError=append:$log_file

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
echo "유닛 파일을 썼습니다: $service"
echo "  WorkingDirectory: $repo_root"
echo "  ExecStart: $python_bin -m backend.pipelines.news.pipeline $args"
echo "  로그: $log_file"

if [[ "${1:-}" == "--enable" ]]; then
  systemctl --user enable --now memos-news-hourly.service
  systemctl --user is-enabled --quiet memos-news-hourly.service
  systemctl --user is-active --quiet memos-news-hourly.service
  echo "설치 완료: memos-news-hourly.service 실행 중"
  systemctl --user status memos-news-hourly.service --no-pager | head -5
else
  echo "서비스는 켜지 않았습니다. 켜려면 --enable을 붙여 다시 실행하거나: systemctl --user enable --now memos-news-hourly.service"
fi
