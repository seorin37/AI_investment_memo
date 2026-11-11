#!/usr/bin/env bash
# 과거 뉴스 백필을 하루씩 거꾸로 돌린다: 목록(backfill_list) → 원문(fulltext) → 청크·임베딩 적재(fulltext_load) → 태그·제목요약 임베딩(pipeline daily)
#   scripts/run_backfill.sh 2026-10-27 2026-10-27                   # 하루
#   scripts/run_backfill.sh 2026-10-26 2026-08-01                   # 10-26부터 08-01까지 거꾸로
#   LIST_ARGS=--allow-recent FULLTEXT_SOURCES=sedaily,hankyung,mk,yonhap scripts/run_backfill.sh 2026-11-12 2026-11-11
#   DRY_RUN=1 scripts/run_backfill.sh 2026-10-27 2026-10-27         # 쓰기 없이 연결만 확인 (목록 5건, 원문·적재 dry-run, daily 생략)
# 백그라운드: nohup scripts/run_backfill.sh 2026-10-26 2026-08-01 >/dev/null 2>&1 &
#
# 환경변수
#   DATA_ROOT   data/news_raw·data/news_backfill·logs가 있는 저장소 (기본: 이 스크립트의 저장소). worktree에서 돌릴 때는
#               실시간 수집과 같은 폴더(~/projects/AI_investment_memo)를 줘야 원문 기록·지연 확인이 맞는다
#   PYTHON_BIN  (기본 ~/miniforge3/envs/ai_memo/bin/python)   TARGET  적재 대상 host:port (기본 192.168.0.105:15432)
#   SOURCES     목록 매체 (기본 hankyung,mk)   FULLTEXT_SOURCES  원문 매체 (기본 SOURCES)   LIST_ARGS  backfill_list 추가 인자
#
# 대기: 각 단계 전에 06:00~07:30 KST(06:30 AI 업데이트), 매시 05~25분(매시 10분 원문 타이머와 GPU 겹침 방지)이면 기다린다.
# 멈춤: backfill_list가 3(403·429) 또는 4(실시간 임베딩 지연)로 끝나면 멈춘다. 다른 단계 오류도 멈춘다 (다시 돌리면 완료된 날짜는 건너뜀).
# 수동 정지: touch $DATA_ROOT/data/news_backfill/STOP  → 다음 단계 전에 멈춘다 (지우고 다시 시작). 급하면 kill $(cat .../run_backfill.pid)
# 로그: $DATA_ROOT/logs/news_backfill.log, 하루 통계: $DATA_ROOT/data/news_backfill/daily_stats.jsonl
set -uo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
data_root="$(cd "${DATA_ROOT:-$repo_root}" && pwd)"
py="${PYTHON_BIN:-$HOME/miniforge3/envs/ai_memo/bin/python}"
target="${TARGET:-192.168.0.105:15432}"
sources="${SOURCES:-hankyung,mk}"
ft_sources="${FULLTEXT_SOURCES:-$sources}"
list_args="${LIST_ARGS:-}"
dry="${DRY_RUN:-0}"
raw_dir="$data_root/data/news_raw"
state_dir="$data_root/data/news_backfill"
log_file="$data_root/logs/news_backfill.log"

if [[ $# -ne 2 ]]; then
  echo "사용법: scripts/run_backfill.sh <시작일> <끝일>   (시작일 >= 끝일, 하루씩 거꾸로)" >&2
  exit 2
fi
start="$1"; end="$2"
if ! date -d "$start" >/dev/null 2>&1 || ! date -d "$end" >/dev/null 2>&1 || [[ "$start" < "$end" ]]; then
  echo "날짜를 확인하세요: 시작일($start)이 끝일($end)보다 같거나 늦어야 합니다." >&2
  exit 2
fi

mkdir -p "$state_dir" "$(dirname "$log_file")"
exec >>"$log_file" 2>&1
exec 9>"$state_dir/run_backfill.lock"
if ! flock -n 9; then
  echo "$(date '+%F %T') 다른 run_backfill.sh가 이미 돌고 있습니다. 끝냅니다."
  exit 1
fi
echo $$ >"$state_dir/run_backfill.pid"
cd "$repo_root"
export PYTHONUNBUFFERED=1 PYTHONPATH="$repo_root"

say() { echo "$(date '+%F %T') [run_backfill] $*"; }

wait_window() {   # 06:00~07:30 KST, 매시 05~25분이면 기다린다 (dry-run은 기다리지 않는다)
  [[ "$dry" == "1" ]] && return 0
  while :; do
    local hm min
    hm=$(TZ=Asia/Seoul date +%H%M); min=$(TZ=Asia/Seoul date +%M)
    if [[ "$hm" > "0559" && "$hm" < "0730" ]]; then
      say "06:00~07:30 정지 구간 — 기다립니다 ($hm)"; sleep 300; continue
    fi
    if [[ "$min" > "04" && "$min" < "25" ]]; then
      sleep 60; continue
    fi
    return 0
  done
}

check_stop() {
  if [[ -f "$state_dir/STOP" ]]; then
    say "STOP 파일이 있어 멈춥니다 ($state_dir/STOP). 지우고 다시 실행하면 이어서 합니다."
    exit 0
  fi
}

step() {   # step <이름> <명령...>: 정지 확인 → 시간대 대기 → 실행, 종료 코드를 돌려준다
  local name="$1"; shift
  check_stop
  wait_window
  say "$name 시작: $*"
  local t0=$SECONDS
  "$@"
  local rc=$?
  say "$name 끝: 종료 코드 $rc, $((SECONDS - t0))초"
  return $rc
}

say "시작: $start → $end, 목록 $sources, 원문 $ft_sources, 대상 $target, 데이터 $data_root, dry-run $dry (pid $$)"
day="$start"
while [[ ! "$day" < "$end" ]]; do
  day_t0=$SECONDS
  size_before=$("$py" -m backend.pipelines.news.backfill_check stats --date "$day" --sources "$sources" --raw-dir "$raw_dir" --json 2>/dev/null | "$py" -c 'import json,sys; print(json.load(sys.stdin)["db_size_bytes"])' 2>/dev/null || echo 0)

  # 1) 목록
  if [[ "$dry" == "1" ]]; then
    step "목록($day, dry-run)" "$py" -m backend.pipelines.news.backfill_list --date "$day" --sources "$sources" \
      --state-dir "$state_dir" --raw-dir "$raw_dir" --dry-run --limit 5 $list_args
  else
    step "목록($day)" "$py" -m backend.pipelines.news.backfill_list --date "$day" --sources "$sources" \
      --state-dir "$state_dir" --raw-dir "$raw_dir" $list_args
  fi
  rc=$?
  if [[ $rc -eq 3 ]]; then say "403·429로 매체가 멈췄습니다. 백필을 멈춥니다 ($day)."; exit 3; fi
  if [[ $rc -eq 4 ]]; then say "실시간 원문 임베딩 지연으로 멈춥니다 ($day)."; exit 4; fi
  if [[ $rc -ne 0 ]]; then say "목록 단계 오류(종료 코드 $rc)로 멈춥니다 ($day)."; exit $rc; fi

  # 2) 원문 (DB 읽기만, data/news_raw/<날짜>.jsonl에 덧붙임)
  if [[ "$dry" == "1" ]]; then
    step "원문($day, dry-run)" "$py" -m backend.pipelines.news.fulltext --date "$day" --sources "$ft_sources" --out "$raw_dir" --dry-run
  else
    step "원문($day)" "$py" -m backend.pipelines.news.fulltext --date "$day" --sources "$ft_sources" --out "$raw_dir" --yes
  fi
  rc=$?
  if [[ $rc -ne 0 ]]; then say "원문 단계 오류(종료 코드 $rc)로 멈춥니다 ($day)."; exit $rc; fi

  # 3) 청크·임베딩 적재 (GPU가 바쁘면(2) 10분 뒤 다시, 최대 6번)
  if [[ ! -f "$raw_dir/$day.jsonl" ]]; then
    say "원문 파일이 없어 적재를 건너뜁니다 ($raw_dir/$day.jsonl)"
  else
    for try in 1 2 3 4 5 6; do
      if [[ "$dry" == "1" ]]; then
        step "적재($day, dry-run)" "$py" -m backend.pipelines.news.fulltext_load --date "$day" --raw-dir "$raw_dir"
      else
        step "적재($day)" "$py" -m backend.pipelines.news.fulltext_load --date "$day" --raw-dir "$raw_dir" --load --target "$target"
      fi
      rc=$?
      [[ $rc -ne 2 ]] && break
      say "GPU 메모리 부족 — 10분 뒤 다시 ($try/6)"; sleep 600
    done
    if [[ $rc -ne 0 ]]; then say "적재 단계 오류(종료 코드 $rc)로 멈춥니다 ($day)."; exit $rc; fi
  fi

  # 4) 4종목 태그 + 제목·요약 임베딩 (종목 없는 기사도, 기사를 지우지 않음)
  if [[ "$dry" == "1" ]]; then
    say "daily($day) dry-run이라 건너뜁니다"
  else
    step "daily($day)" "$py" -m backend.pipelines.news.pipeline daily --date "$day" --skip-naver --include-untagged --keep-days 0
    rc=$?
    if [[ $rc -ne 0 ]]; then say "daily 단계 오류(종료 코드 $rc)로 멈춥니다 ($day)."; exit $rc; fi
  fi

  # 하루 통계 (기사·원문·실패율·청크·제목요약 임베딩·태그·DB 용량 증가·걸린 시간)
  stats=$("$py" -m backend.pipelines.news.backfill_check stats --date "$day" --sources "$sources" --raw-dir "$raw_dir" --json 2>/dev/null)
  if [[ -n "$stats" ]]; then
    "$py" - "$stats" "$size_before" "$((SECONDS - day_t0))" "$dry" >>"$state_dir/daily_stats.jsonl" <<'EOF'
import json, sys
st = json.loads(sys.argv[1]); before = int(sys.argv[2] or 0)
st["db_growth_bytes"] = st["db_size_bytes"] - before if before else None
st["seconds"] = int(sys.argv[3]); st["dry_run"] = sys.argv[4] == "1"
print(json.dumps(st, ensure_ascii=False))
EOF
    say "통계($day): $(tail -n 1 "$state_dir/daily_stats.jsonl")"
  fi
  say "$day 완료 ($((SECONDS - day_t0))초)"
  day=$(date -d "$day -1 day" +%F)
done
say "모두 끝났습니다: $start → $end"
rm -f "$state_dir/run_backfill.pid"
