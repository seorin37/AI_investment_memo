"""뉴스 원문 1시간 회차: 최근 N시간 새 기사 원문 수집 → data/news_raw/*.jsonl → 공용 DB 적재 (news_article_bodies·news_chunks).

  python -m backend.pipelines.news.fulltext_hourly --recent-hours 6 --target 192.168.0.105:15432
  python -m backend.pipelines.news.fulltext_hourly --recent-hours 24 --target 192.168.0.105:15432   # 처음 한 번 채울 때

- 한 번 실행하면 한 회차만 돌고 끝난다. 주기 실행은 systemd timer가 맡는다 (scripts/install_fulltext_hourly_timer.sh).
- 회차가 겹치지 않게 data/news_raw/.fulltext_hourly.lock을 잡는다. 이전 회차가 아직 돌고 있으면 기록만 남기고 0으로 끝난다.
- 수집은 fulltext.collect 그대로다 (DB 읽기만, 요청 규칙·403/429 멈춤·failed 재시도는 fulltext_max_runs회까지).
- 적재는 이번 기간 발행일 파일의 ok 기사 중 아직 DB에 없는 것만 넣는다. 지난 회차에 적재가 빠진 기사도 여기서 채워진다.
  남은 GPU 메모리가 --min-free-gb보다 적으면 이번 회차는 수집만 하고 적재는 다음 회차로 미룬다 (정상, 0).
  GPU 확인 자체가 실패하면(nvidia-smi 없음 등) 적재를 건너뛰고 오류로 끝낸다 (5). 미뤄 둔 기사는 다음 회차가 채운다.
- --target(host:port)이 실제 접속 대상과 다르면 수집도 하지 않고 멈춘다 (종료 코드 3).
- --tag-stocks(기본 꺼짐)면 적재 뒤 같은 기간 기사에 종목 태그를 더한다 (stock_tagger, configs/stock_aliases.yaml).
  공용 DB(news_stocks)에 쓰므로 승인 후 timer에 켠다 (FULLTEXT_TAG_STOCKS=1로 설치 스크립트를 다시 실행).
- 회차마다 logs/fulltext_hourly.log에 요약 한 줄(JSON)을 남긴다: 기간, 수집 건수(성공·제외·실패·포기), 403/429 매체,
  적재 건수(본문·청크), 소요 시간, GPU 최대.
- 종료 코드: 0 정상(잠금 때문에 건너뛴 회차, GPU 부족으로 적재를 미룬 회차 포함), 1 오류, 3 접속 대상 불일치,
  4 403/429를 받은 매체 있음, 5 GPU 확인 실패로 적재 못 함.
"""
from __future__ import annotations

import argparse
import json
import logging
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

from ..common.file_lock import LockUnavailable, acquire_file_lock
from . import fulltext as ft
from . import fulltext_load as fl
from . import lead_fetcher as lf

log = logging.getLogger("fulltext_hourly")

LOCK_NAME = ".fulltext_hourly.lock"
LOG_PATH = Path("logs/fulltext_hourly.log")
COLLECT_KEYS = ("already", "ok", "skipped", "failed", "gave_up", "not_ready", "stopped")


def collect_summary(stats: dict[str, Counter]) -> dict:
    total = Counter()
    for s in stats.values():
        total.update({k: s[k] for k in COLLECT_KEYS})
    reasons = Counter()
    for s in stats.values():
        reasons.update({k[7:]: v for k, v in s.items() if k.startswith("reason:")})
    return {**{k: total[k] for k in COLLECT_KEYS}, "reasons": dict(reasons.most_common()),
            "blocked": ft.blocked_sources(stats)}


def write_summary(summary: dict, path: Path = LOG_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(summary, ensure_ascii=False, default=str) + "\n")
    log.info("회차 요약: %s", json.dumps(summary, ensure_ascii=False, default=str))


def run_once(hours: float, *, read_rows, http_get, config: lf.LeadConfig, store, load_fn, raw_dir: Path,
             codes: list[str], sleep=time.sleep, clock=time.monotonic, now=None, tag_fn=None) -> dict:
    """한 회차 (잠금 밖의 순수 처리). load_fn(todo, store) → embed_and_load 결과 dict.
    tag_fn(start, end) → 종목 태그 결과 dict (없으면 태그하지 않는다)."""
    started = clock()
    start, end = ft.recent_window(hours, now)
    summary: dict = {"started_at": datetime.now().astimezone().isoformat(timespec="seconds"), "hours": hours,
                     "window": [start.isoformat(timespec="minutes"), end.isoformat(timespec="minutes")]}
    rows = read_rows(start, end, codes)
    done = ft.load_done(raw_dir, ft.window_days(start, end))
    stats = ft.collect(rows, config, http_get, raw_dir, done, sleep=sleep)
    summary["collect"] = {"rows": len(rows), **collect_summary(stats)}
    summary["collect_seconds"] = round(clock() - started, 1)

    load_started = clock()
    records = fl.recent_records(raw_dir, start, end)
    p = fl.plan(records, store)
    summary["load"] = {"ok_records": len(records), "already": p.already, "missing": len(p.missing),
                       "url_mismatch": len(p.url_mismatch), "todo": len(p.todo)}
    if p.todo:
        result = load_fn(p.todo, store)
        summary["load"].update({k: (len(v) if k == "bad" else v) for k, v in result.items() if k != "news_ids"})
    else:
        summary["load"].update(status="nothing", articles=0, chunks=0)
    summary["load_seconds"] = round(clock() - load_started, 1)
    if tag_fn is not None:
        tag_started = clock()
        summary["tag"] = tag_fn(start, end)
        summary["tag_seconds"] = round(clock() - tag_started, 1)
    summary["total_seconds"] = round(clock() - started, 1)
    return summary


def exit_code(summary: dict) -> int:
    if summary["load"].get("status") == "gpu_check_failed":
        log.error("GPU 확인 실패로 적재하지 못했습니다: %s", summary["load"].get("error"))
        return 5
    if summary["collect"]["blocked"]:
        log.warning("403/429를 받은 매체: %s — 그 매체는 이번 회차에서 멈췄습니다.", summary["collect"]["blocked"])
        return 4
    return 0


def main(argv=None) -> int:
    from ..common.db import get_dsn, get_read_dsn, load_env

    ap = argparse.ArgumentParser(description="뉴스 원문 1시간 회차: 최근 N시간 수집 → jsonl → 공용 DB 적재")
    ap.add_argument("--recent-hours", type=float, default=6.0, help="최근 몇 시간 발행분을 볼지 (기본 6)")
    ap.add_argument("--target", required=True, help="접속 대상 host:port. 실제 대상과 다르면 아무것도 하지 않고 멈춘다")
    ap.add_argument("--sources", default="sedaily,hankyung,mk,yonhap")
    ap.add_argument("--raw-dir", type=Path, default=ft.OUT_DIR)
    ap.add_argument("--log-file", type=Path, default=LOG_PATH)
    ap.add_argument("--device", choices=["cpu", "cuda"], default="cuda")
    ap.add_argument("--batch-size", type=int, default=4)
    ap.add_argument("--group-size", type=int, default=32)
    ap.add_argument("--gpu-cap-gb", type=float, default=2.5)
    ap.add_argument("--min-free-gb", type=float, default=2.8)
    ap.add_argument("--tag-stocks", action="store_true", help="적재 뒤 같은 기간 기사에 종목 태그를 더한다 (news_stocks에 씀)")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    load_env()
    dsn, read_dsn = get_dsn(), get_read_dsn()
    if not dsn or not read_dsn:
        log.error("DB 접속 정보가 없습니다 (.env의 DATABASE_URL).")
        return 1
    target = fl.dsn_target(dsn)
    log.info("접속 대상: %s (적재) / 최근 %g시간", target, args.recent_hours)
    if not target.startswith(args.target + "/"):
        log.error("--target(%s)이 실제 접속 대상(%s)과 달라 아무것도 하지 않고 멈춥니다.", args.target, target)
        return 3
    try:
        lock = acquire_file_lock(args.raw_dir / LOCK_NAME, timeout=0)
    except LockUnavailable:
        write_summary({"started_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                       "skipped": "이전 회차가 아직 돌고 있어 건너뜀"}, args.log_file)
        return 0
    try:
        config = lf.load_config()
        model_cfg = fl.model_config(args.device, args.batch_size)
        ident = fl.embedding_identity(model_cfg)
        store = fl.PgStore(dsn, read_only=False)
        tag_fn = None
        if args.tag_stocks:
            from .stock_tagger import load_rules, tag_window
            rules = load_rules(store.conn)

            def tag_fn(start, end):
                stats = tag_window(store.conn, rules, start, end, write=True)
                stats.pop("_new")
                store.conn.commit()
                return stats
        summary = run_once(
            args.recent_hours,
            read_rows=lambda start, end, codes: ft.read_rows(read_dsn, start, end, codes, None),
            http_get=lf._requests_get(config.user_agent), config=config, store=store,
            load_fn=lambda todo, st: fl.embed_and_load(
                todo, st, model_cfg, ident, device=args.device, batch_size=args.batch_size,
                group_size=args.group_size, gpu_cap_gb=args.gpu_cap_gb, min_free_gb=args.min_free_gb,
                out=log.info),
            raw_dir=args.raw_dir, codes=[c.strip() for c in args.sources.split(",") if c.strip()], tag_fn=tag_fn)
        summary["target"] = target
        write_summary(summary, args.log_file)
    except Exception as exc:
        log.exception("회차 실패")
        write_summary({"started_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                       "error": f"{type(exc).__name__}: {exc}"}, args.log_file)
        return 1
    finally:
        lock.release()
    return exit_code(summary)


if __name__ == "__main__":
    raise SystemExit(main())
