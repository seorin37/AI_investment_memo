"""항목당 하루 평균 LLM 비용 (usage_log.jsonl, 파일만 읽음).

    PYTHONPATH=backend python -m pipelines.updates.usage_daily [--runs-per-day 24] [--since 2026-11-11]

- 실행마다: 비용 ÷ 항목 수 = 항목당 실행 1회 비용. 첫 확인(새 자료만 받기 없음)과 이어 확인(fresh_items > 0)을 따로 본다.
  첫 확인은 조회 기간 전체를 보므로 비싸고, 이어 확인은 새 자료가 있는 항목만 LLM을 부른다.
- 하루 평균: (1) 실제 기록 — 날짜별로 그날 실행 비용 합 ÷ 그날 실행의 최대 항목 수.
  (2) 추정 — 이어 확인 1회 평균 비용 × --runs-per-day (매시 돌면 24).
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


def load(path: Path, since: str | None = None) -> list[dict]:
    if not path.exists():
        return []
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    return [r for r in rows if not since or r["run_at"][:10] >= since]


def summarize(rows: list[dict], runs_per_day: int = 24) -> dict:
    per_run = []
    for r in rows:
        cost = (r.get("total") or {}).get("usd")
        if cost is None or not r.get("items"):
            continue
        per_run.append({"run_at": r["run_at"], "day": r["run_at"][:10], "items": r["items"], "usd": cost,
                        "per_item": cost / r["items"], "follow_up": (r.get("fresh_items") or 0) > 0})
    days = defaultdict(lambda: {"usd": 0.0, "items": 0, "runs": 0})
    for p in per_run:
        d = days[p["day"]]
        d["usd"] += p["usd"]
        d["items"] = max(d["items"], p["items"])
        d["runs"] += 1
    mean = lambda xs: sum(xs) / len(xs) if xs else None
    first = [p["per_item"] for p in per_run if not p["follow_up"]]
    follow = [p["per_item"] for p in per_run if p["follow_up"]]
    return {"runs": len(per_run),
            "per_item_per_run": {"first_check": mean(first), "follow_up": mean(follow)},
            "observed_daily": {day: {**v, "per_item": v["usd"] / v["items"] if v["items"] else None} for day, v in days.items()},
            "estimated_daily_per_item": None if not follow else mean(follow) * runs_per_day,
            "runs_per_day": runs_per_day}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="항목당 하루 평균 LLM 비용 (usage_log.jsonl)")
    ap.add_argument("--log", default="results/updates/usage_log.jsonl")
    ap.add_argument("--runs-per-day", type=int, default=24, help="하루에 이어 확인을 몇 번 도는지 (추정용)")
    ap.add_argument("--since", help="이 날짜(YYYY-MM-DD)부터의 실행만")
    args = ap.parse_args(argv)
    from ..common.config import resolve_path

    s = summarize(load(resolve_path(args.log), args.since), args.runs_per_day)
    fmt = lambda v: "-" if v is None else f"${v:.4f}"
    print(f"실행 {s['runs']}회 · 항목당 실행 1회 비용: 첫 확인 {fmt(s['per_item_per_run']['first_check'])} · "
          f"이어 확인 {fmt(s['per_item_per_run']['follow_up'])}")
    for day, v in sorted(s["observed_daily"].items()):
        print(f"- {day}: 실행 {v['runs']}회 · 합계 ${v['usd']:.4f} · 항목 {v['items']}개 · 항목당 {fmt(v['per_item'])}")
    print(f"추정 항목당 하루 비용 (이어 확인 × 하루 {s['runs_per_day']}회): {fmt(s['estimated_daily_per_item'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
