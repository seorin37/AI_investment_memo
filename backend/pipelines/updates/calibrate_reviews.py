"""사람 검수 표본들로 검색 기준값(min_similarity_*) 추천값을 보고, 실행 결과의 후보 수가 어떻게 바뀌는지 센다 (LLM·DB 없음, 설정은 바꾸지 않음).

    PYTHONPATH=backend python -m pipelines.updates.calibrate_reviews

- 표본: (사람 판정 파일, 정답 파일[, 판정만 따로 저장한 파일]) 묶음. 종류는 사람 파일의 '종류', 유사도는 정답 파일의 '유사도'.
  기본: 1차 32건(run_20261109_133043, 판정은 review_human_labels.csv) · 뉴스 42건(chunks) · 페르소나 메모 40건(news4_memos).
- 합친 표를 결과 폴더의 labels_merged.csv로 쓰고 calibrate.build_report로 calibration.md를 만든다.
- 후보 수 변화: 주어진 실행 폴더들의 candidates.csv에서 종류별로 '지금 기준값 이상'과 '추천값 이상' 후보 수.
- 주의: 표본 후보는 검색 단계에서 이미 지금 기준값(뉴스 0.58)을 넘은 것만 있다. 그래서 기준값을 내리는 쪽은 이 표본으로 판단할 수 없고,
  추천값이 지금 값과 같으면 '지금 값 아래는 표본이 없어 모른다'는 뜻이다.
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path

from .calibrate import (DEFAULT_MIN_PRECISION, KIND_COL, LABEL_COL, SIM_COL, build_report, load_rows, parse_label,
                        recommend_precision, sweep)

DEFAULT_SETS = [
    ("results/updates/run_20261109_133043/review_human.csv", "results/updates/run_20261109_133043/review_key.csv",
     "results/updates/run_20261109_133043/review_human_labels.csv"),
    ("results/updates/run_20261109_173514/review_human_news2_chunks.csv",
     "results/updates/run_20261109_173514/review_key_news2_chunks.csv", None),
    ("results/updates/run_20261110_161734/review_human_news4_memos.csv",
     "results/updates/run_20261110_161734/review_key_news4_memos.csv", None),
]
DEFAULT_RUNS = ["results/updates/run_20261110_154307", "results/updates/run_20261110_133814"]   # chunks 통합 실행 · article 실행
KINDS = ("news", "news_chunks", "disclosure")
THRESHOLD_KEY = {"news": "min_similarity_news", "news_chunks": "min_similarity_news_chunks",
                 "disclosure": "min_similarity_disclosure"}


def merge_sets(sets, read) -> list[dict]:
    """[(human, key, labels|None)] → [{set, review_id, ref, 종류, 유사도, 관련(O/X)}] (사람 판정이 O/X인 줄만)."""
    out = []
    for human_p, key_p, labels_p in sets:
        human = {r["review_id"]: r for r in read(human_p)}
        key = {r["review_id"]: r for r in read(key_p)}
        labels = {r["review_id"]: r for r in read(labels_p)} if labels_p else human
        for rid, h in human.items():
            lab = parse_label((labels.get(rid) or {}).get(LABEL_COL))
            k = key.get(rid) or {}
            if lab is None or not k.get(SIM_COL):
                continue
            out.append({"set": Path(human_p).parent.name + "/" + Path(human_p).stem, "review_id": rid, "ref": h.get("ref", ""),
                        KIND_COL: h.get(KIND_COL) or k.get(KIND_COL) or "news", SIM_COL: k[SIM_COL],
                        LABEL_COL: "O" if lab else "X"})
    return out


def current_thresholds(topic_cfg: dict) -> dict[str, float]:
    from .topic import thresholds
    floor, _ = thresholds(topic_cfg)
    return {"news": floor["news"], "news_chunks": floor["news_chunks"], "disclosure": floor["disclosure"]}


def candidate_counts(rows: list[dict], kind: str, now: float, rec: float | None) -> dict:
    sims = [float(r[SIM_COL]) for r in rows if r[KIND_COL] == kind and kind != "disclosure"] if kind != "disclosure" else \
        [float(r[SIM_COL]) for r in rows if r[KIND_COL] == "disclosure"]
    return {"all": len(sims), "now": sum(s >= now - 1e-9 for s in sims),
            "rec": None if rec is None else sum(s >= rec - 1e-9 for s in sims)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="사람 검수 표본으로 기준값 추천과 후보 수 변화 (LLM·DB 없음, 설정 안 바꿈)")
    ap.add_argument("--runs", nargs="*", default=DEFAULT_RUNS, help="후보 수를 셀 experiment 실행 폴더")
    ap.add_argument("--min-precision", type=float, default=DEFAULT_MIN_PRECISION)
    ap.add_argument("--config", default="configs/updates.yaml")
    ap.add_argument("--out", help="결과 폴더 (기본: results/updates/calibration_<시각>)")
    args = ap.parse_args(argv)

    from ..common.config import REPO_ROOT, load_config, resolve_path
    from .relevance_compare import read_csv

    read = lambda p: read_csv(resolve_path(p))
    merged = merge_sets(DEFAULT_SETS, read)
    out = Path(args.out) if args.out else REPO_ROOT / "results/updates" / f"calibration_{datetime.now():%Y%m%d_%H%M%S}"
    out.mkdir(parents=True, exist_ok=True)
    path = out / "labels_merged.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["set", "review_id", "ref", KIND_COL, SIM_COL, LABEL_COL])
        w.writeheader()
        w.writerows(merged)
    rows = load_rows(path, source="human")
    (out / "calibration.md").write_text(build_report(rows, min_precision=args.min_precision, source="human"), encoding="utf-8")
    cfg = load_config(args.config)
    now = current_thresholds(cfg["topic"])
    runs = {r: read_csv(resolve_path(r) / "candidates.csv") for r in args.runs}
    summary = {"sets": [s[0] for s in DEFAULT_SETS], "labels": len(rows), "min_precision": args.min_precision, "kinds": {}}
    for kind in KINDS:
        g = [r for r in rows if r["kind"] == kind]
        if not g:
            continue
        rec = recommend_precision(g, args.min_precision)
        at_now = next((s for s in sweep(g) if abs(s["t"] - round(now[kind], 2)) < 1e-9), None)
        info = {"labels": len(g), "relevant": sum(r["relevant"] for r in g),
                "min_similarity_in_labels": round(min(r["similarity"] for r in g), 4),
                "current": {THRESHOLD_KEY[kind]: now[kind], "precision": at_now and at_now["precision"],
                            "recall": at_now and at_now["recall"]},
                "recommended": None if rec is None else {"t": rec["t"], "precision": rec["precision"], "recall": rec["recall"],
                                                         "kept_share": rec["kept_share"]},
                "candidates": {Path(r).name: candidate_counts(rs, kind, now[kind], rec and rec["t"]) for r, rs in runs.items()}}
        summary["kinds"][kind] = info
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    pct = lambda v: "-" if v is None else f"{v:.0%}"
    print(f"사람 라벨 {len(rows)}건 ({', '.join(Path(s[0]).parent.name for s in DEFAULT_SETS)}) · 정밀도 목표 {pct(args.min_precision)}")
    for kind, i in summary["kinds"].items():
        c, r = i["current"], i["recommended"]
        print(f"- {kind}: 라벨 {i['labels']}건(O {i['relevant']}), 라벨 중 최저 유사도 {i['min_similarity_in_labels']} · "
              f"지금 {THRESHOLD_KEY[kind]}={now[kind]:.2f} (정밀도 {pct(c['precision'])}, 재현율 {pct(c['recall'])}) → "
              + ("추천 없음 (정밀도 목표를 만족하는 값이 없음)" if r is None else
                 f"추천 {r['t']:.2f} (정밀도 {pct(r['precision'])}, 재현율 {pct(r['recall'])})"))
        for run, n in i["candidates"].items():
            print(f"    {run}: 후보 {n['all']}건 · 지금 기준 이상 {n['now']}건 · 추천 기준 이상 {n['rec']}건")
    print(f"결과: {out} (calibration.md, labels_merged.csv, summary.json) — 설정은 바꾸지 않았습니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
