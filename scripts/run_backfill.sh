#!/usr/bin/env bash
# 과거 뉴스 백필을 하루씩 거꾸로 돌린다: 목록+원문(backfill_list) → 남은 원문(fulltext) → 청크·임베딩 적재(fulltext_load) → 태그·제목요약 임베딩(pipeline daily)
#   scripts/run_backfill.sh 2026-10-27 2026-10-27                   # 하루
#   scripts/run_backfill.sh 2026-10-25 2026-08-01                   # 10-25부터 08-01까지 거꾸로
#   LIST_ARGS=--allow-recent FULLTEXT_SOURCES=sedaily,hankyung,mk,yonhap scripts/run_backfill.sh 2026-11-12 2026-11-11
#   DRY_RUN=1 scripts/run_backfill.sh 2026-10-27 2026-10-27         # 쓰기 없이 연결만 확인 (목록 5건, 원문·적재 dry-run, daily 생략)
# 백그라운드(터미널을 닫아도 계속): systemd-run --user --unit=memos-news-backfill --setenv=DATA_ROOT=... scripts/run_backfill.sh A B
#   또는 nohup scripts/run_backfill.sh A B >/dev/null 2>&1 &
#
# 환경변수
#   DATA_ROOT   data/news_raw·data/news_backfill·logs가 있는 저장소 (기본: 이 스크립트의 저장소). worktree에서 돌릴 때는
#               실시간 수집과 같은 폴더(~/projects/AI_investment_memo)를 줘야 원문 기록·지연 확인이 맞는다
#   PYTHON_BIN  (기본 ~/miniforge3/envs/ai_memo/bin/python)   TARGET  적재 대상 host:port (기본 192.168.0.105:15432)
#   SOURCES     목록 매체 (기본 hankyung,mk)   FULLTEXT_SOURCES  원문 매체 (기본 SOURCES)   LIST_ARGS  backfill_list 추가 인자
#   FORCE_DAYS=1  days_done.txt에 있는 날짜도 다시   GPU_MIN_FREE_MB  GPU 단계 시작에 필요한 남은 메모리 (기본 2868 = 2.8GB)
#
# 대기 (2026-11-12 B):
#   - 모든 단계 전: 06:00~07:30 KST (06:30 AI 업데이트)
#   - GPU 단계(적재·daily) 전에만: 매시 05~25분 (매시 10분 원문 타이머와 GPU 겹침 방지). 목록·원문은 네트워크만 써서 기다리지 않는다
#   - GPU 단계 전 남은 GPU 메모리가 GPU_MIN_FREE_MB보다 적으면 5분 간격으로 최대 1시간(12번) 기다린다. 넘으면 멈춘다(종료 코드 6)
# 멈춤: backfill_list가 3(403·429) 또는 4(실시간 임베딩 지연)로 끝나면 멈춘다. 다른 단계 오류도 멈춘다.
# 이어서: 끝난 날짜는 data/news_backfill/days_done.txt에 남아 다시 실행하면 건너뛴다 (목록은 progress.json으로도 건너뜀).
# 수동 정지: touch $DATA_ROOT/data/news_backfill/STOP  → 다음 단계 전에 멈춘다 (지우고 다시 시작). 급하면 systemctl --user stop memos-news-backfill
# 로그: $DATA_ROOT/logs/news_backfill.log (하루마다 "하루 통계" 한 줄), 하루 통계 JSON: $DATA_ROOT/data/news_backfill/daily_stats.jsonl
set -uo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
data_root="$(cd "${DATA_ROOT:-$repo_root}" && pwd)"
py="${PYTHON_BIN:-$HOME/miniforge3/envs/ai_memo/bin/python}"
target="${TARGET:-192.168.0.105:15432}"
sources="${SOURCES:-hankyung,mk}"
ft_sources="${FULLTEXT_SOURCES:-$sources}"
list_args="${LIST_ARGS:-}"
dry="${DRY_RUN:-0}"
force_days="${FORCE_DAYS:-0}"
gpu_need_mb="${GPU_MIN_FREE_MB:-2868}"
gpu_tries=12; gpu_wait_sec=300
raw_dir="$data_root/data/news_raw"
state_dir="$data_root/data/news_backfill"
log_file="$data_root/logs/news_backfill.log"
days_done="$state_dir/days_done.txt"

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
# systemd-run·nohup 환경에서도 nvidia-smi(WSL GPU 도구)를 찾게
[[ -d /usr/lib/wsl/lib ]] && export PATH="/usr/lib/wsl/lib:$PATH"
export PYTHONUNBUFFERED=1 PYTHONPATH="$repo_root"

say() { echo "$(date '+%F %T') [run_backfill] $*"; }

wait_pause() {   # 06:00~07:30 KST면 기다린다 (모든 단계)
  [[ "$dry" == "1" ]] && return 0
  local hm
  while :; do
    hm=$(TZ=Asia/Seoul date +%H%M)
    if [[ "$hm" > "0559" && "$hm" < "0730" ]]; then
      say "대기: 06:00~07:30 정지 구간 ($hm)"; sleep 300; continue
    fi
    return 0
  done
}

wait_gpu_slot() {   # GPU 단계 전: 매시 05~25분(원문 타이머 :10)이면 기다린다
  [[ "$dry" == "1" ]] && return 0
  local min logged=0
  while :; do
    wait_pause
    min=$(TZ=Asia/Seoul date +%M)
    if [[ "$min" > "04" && "$min" < "25" ]]; then
      [[ $logged -eq 0 ]] && say "대기: 매시 05~25분 (원문 타이머와 GPU 겹침 방지, 지금 $min분)"
      logged=1; sleep 60; continue
    fi
    return 0
  done
}

gpu_free_mb() {   # 남은 GPU 메모리(MiB). 확인 못 하면 빈 값
  nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits 2>/dev/null | head -n 1 | tr -dc '0-9'
}

wait_gpu_memory() {   # wait_gpu_memory <단계 이름>: 남은 메모리가 부족하면 5분 간격 최대 1시간. 끝내 부족하면 1
  [[ "$dry" == "1" ]] && return 0
  local name="$1" try free
  for ((try = 1; try <= gpu_tries; try++)); do
    wait_gpu_slot
    free=$(gpu_free_mb)
    if [[ -z "$free" ]]; then
      say "GPU 메모리를 확인하지 못했습니다 (nvidia-smi). $name 단계가 직접 확인합니다."
      return 0
    fi
    if (( free >= gpu_need_mb )); then
      return 0
    fi
    say "대기: GPU 남은 메모리 ${free}MB < 필요 ${gpu_need_mb}MB — $name ${try}/${gpu_tries}, $((gpu_wait_sec / 60))분 뒤 다시 ($(nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader 2>/dev/null | tr '\n' ' '))"
    sleep "$gpu_wait_sec"
  done
  say "GPU 메모리가 1시간 동안 부족해 멈춥니다 ($name)."
  return 1
}

check_stop() {
  if [[ -f "$state_dir/STOP" ]]; then
    say "STOP 파일이 있어 멈춥니다 ($state_dir/STOP). 지우고 다시 실행하면 이어서 합니다."
    rm -f "$state_dir/run_backfill.pid"
    exit 0
  fi
}

declare -A took   # 단계별 걸린 시간(초)
run_step() {   # run_step <키> <이름> <명령...>: 실행하고 걸린 시간을 took[키]에 더한다
  local key="$1" name="$2"; shift 2
  say "$name 시작: $*"
  local t0=$SECONDS
  "$@"
  local rc=$?
  took[$key]=$(( ${took[$key]:-0} + SECONDS - t0 ))
  say "$name 끝: 종료 코드 $rc, $((SECONDS - t0))초"
  return $rc
}

gpu_step() {   # gpu_step <키> <이름> <명령...>: 시간대·GPU 메모리 대기 후 실행. 명령이 2(GPU 부족)로 끝나도 같은 규칙으로 다시
  local key="$1" name="$2"; shift 2
  local try rc t0
  for ((try = 1; try <= gpu_tries; try++)); do
    check_stop
    t0=$SECONDS
    wait_gpu_memory "$name" || return 6
    took[wait]=$(( ${took[wait]:-0} + SECONDS - t0 ))
    run_step "$key" "$name" "$@"
    rc=$?
    [[ $rc -ne 2 ]] && return $rc
    say "대기: $name이 GPU 메모리 부족(종료 코드 2)으로 시작하지 않음 — ${try}/${gpu_tries}, $((gpu_wait_sec / 60))분 뒤 다시"
    sleep "$gpu_wait_sec"
  done
  say "GPU 메모리가 1시간 동안 부족해 멈춥니다 ($name)."
  return 6
}

say "시작: $start → $end, 목록 $sources, 원문 $ft_sources, 대상 $target, 데이터 $data_root, dry-run $dry (pid $$)"
day="$start"
while [[ ! "$day" < "$end" ]]; do
  if [[ "$dry" != "1" && "$force_days" != "1" && -f "$days_done" ]] && grep -qx "$day" "$days_done"; then
    say "$day 은(는) 이미 끝났습니다 (days_done.txt) — 건너뜁니다"
    day=$(date -d "$day -1 day" +%F); continue
  fi
  day_t0=$SECONDS
  took=()
  size_before=$("$py" -m backend.pipelines.news.backfill_check stats --date "$day" --sources "$sources" --raw-dir "$raw_dir" --json 2>/dev/null | "$py" -c 'import json,sys; print(json.load(sys.stdin)["db_size_bytes"])' 2>/dev/null || echo 0)

  # 1) 목록 + 원문 기록 (같은 페이지로)
  check_stop; t0=$SECONDS; wait_pause; took[wait]=$(( ${took[wait]:-0} + SECONDS - t0 ))
  if [[ "$dry" == "1" ]]; then
    run_step list "목록($day, dry-run)" "$py" -m backend.pipelines.news.backfill_list --date "$day" --sources "$sources" \
      --state-dir "$state_dir" --raw-dir "$raw_dir" --dry-run --limit 5 $list_args
  else
    run_step list "목록($day)" "$py" -m backend.pipelines.news.backfill_list --date "$day" --sources "$sources" \
      --state-dir "$state_dir" --raw-dir "$raw_dir" $list_args
  fi
  rc=$?
  if [[ $rc -eq 3 ]]; then say "403·429로 매체가 멈췄습니다. 백필을 멈춥니다 ($day)."; exit 3; fi
  if [[ $rc -eq 4 ]]; then say "실시간 원문 임베딩 지연으로 멈춥니다 ($day)."; exit 4; fi
  if [[ $rc -ne 0 ]]; then say "목록 단계 오류(종료 코드 $rc)로 멈춥니다 ($day)."; exit $rc; fi

  # 2) 남은 원문 (목록 단계가 못 받은 것·본문 비어 있음 등만. DB 읽기만)
  check_stop; t0=$SECONDS; wait_pause; took[wait]=$(( ${took[wait]:-0} + SECONDS - t0 ))
  if [[ "$dry" == "1" ]]; then
    run_step fulltext "원문($day, dry-run)" "$py" -m backend.pipelines.news.fulltext --date "$day" --sources "$ft_sources" --out "$raw_dir" --dry-run
  else
    run_step fulltext "원문($day)" "$py" -m backend.pipelines.news.fulltext --date "$day" --sources "$ft_sources" --out "$raw_dir" --yes
  fi
  rc=$?
  if [[ $rc -ne 0 ]]; then say "원문 단계 오류(종료 코드 $rc)로 멈춥니다 ($day)."; exit $rc; fi

  # 3) 청크·임베딩 적재 (GPU)
  if [[ ! -f "$raw_dir/$day.jsonl" ]]; then
    say "원문 파일이 없어 적재를 건너뜁니다 ($raw_dir/$day.jsonl)"
  else
    if [[ "$dry" == "1" ]]; then
      run_step load "적재($day, dry-run)" "$py" -m backend.pipelines.news.fulltext_load --date "$day" --raw-dir "$raw_dir"
    else
      gpu_step load "적재($day)" "$py" -m backend.pipelines.news.fulltext_load --date "$day" --raw-dir "$raw_dir" --load --target "$target"
    fi
    rc=$?
    if [[ $rc -ne 0 ]]; then say "적재 단계 오류(종료 코드 $rc)로 멈춥니다 ($day)."; exit $rc; fi
  fi

  # 4) 4종목 태그 + 제목·요약 임베딩 (GPU, 종목 없는 기사도, 기사를 지우지 않음)
  if [[ "$dry" == "1" ]]; then
    say "daily($day) dry-run이라 건너뜁니다"
  else
    gpu_step daily "daily($day)" "$py" -m backend.pipelines.news.pipeline daily --date "$day" --skip-naver --include-untagged --keep-days 0
    rc=$?
    if [[ $rc -ne 0 ]]; then say "daily 단계 오류(종료 코드 $rc)로 멈춥니다 ($day)."; exit $rc; fi
  fi

  # 하루 통계: JSON 한 줄(daily_stats.jsonl) + 로그에 사람이 읽는 한 줄
  stats=$("$py" -m backend.pipelines.news.backfill_check stats --date "$day" --sources "$sources" --raw-dir "$raw_dir" --json 2>/dev/null)
  if [[ -n "$stats" ]]; then
    line=$("$py" - "$stats" "$size_before" "$((SECONDS - day_t0))" "$dry" "${took[list]:-0}" "${took[fulltext]:-0}" \
      "${took[load]:-0}" "${took[daily]:-0}" "${took[wait]:-0}" "$state_dir/daily_stats.jsonl" <<'EOF'
import json, sys
st = json.loads(sys.argv[1]); before = int(sys.argv[2] or 0)
st["db_growth_bytes"] = st["db_size_bytes"] - before if before else None
st["seconds"] = int(sys.argv[3]); st["dry_run"] = sys.argv[4] == "1"
st["step_seconds"] = dict(zip(["list", "fulltext", "load", "daily", "wait"], map(int, sys.argv[5:10])))
with open(sys.argv[10], "a", encoding="utf-8") as fh:
    fh.write(json.dumps(st, ensure_ascii=False) + "\n")
parts = []
for code, r in st["sources"].items():
    parts.append(f"{code} 기사 {r['articles']} 원문 ok {r['raw_ok']}/실패 {r['raw_failed']}({r['fail_rate']*100:.1f}%) "
                 f"청크 {r['chunks_embedded']} 제목임베딩 {r['title_embedded']} 태그 {r['stock_tags']}")
s = st["step_seconds"]; g = st["db_growth_bytes"]
print(" | ".join(parts) + f" | DB +{(g or 0) / 2**20:.1f}MiB | 목록 {s['list']//60}분 원문 {s['fulltext']//60}분 "
      f"적재 {s['load']//60}분 daily {s['daily']//60}분 대기 {s['wait']//60}분 합계 {st['seconds']//60}분")
EOF
)
    say "하루 통계 $day: $line"
  fi
  [[ "$dry" != "1" ]] && echo "$day" >>"$days_done"
  say "$day 완료 ($((SECONDS - day_t0))초)"
  day=$(date -d "$day -1 day" +%F)
done
say "모두 끝났습니다: $start → $end"
rm -f "$state_dir/run_backfill.pid"
