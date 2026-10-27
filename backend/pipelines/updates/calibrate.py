"""임계값 정하기: 사람이 '관련 있음/없음'을 표시한 후보로 유사도 구간별 정답률을 계산한다.

사용법
  1) python -m pipelines.updates.experiment --llm none --limit 30   → results/updates/run_*/candidates.csv
  2) candidates.csv 마지막 열 '관련(O/X)'에 O(이 후보는 이 메모 항목에 대한 업데이트로 보여 줄 만하다) / X(아니다)를 적는다.
     (엑셀에서 열어 수정하고 csv 또는 xlsx로 저장. 비워 둔 줄은 무시한다)
  3) python -m pipelines.updates.calibrate --labels results/updates/run_*/candidates.csv [--min-precision 0.8]

읽기만 하는 도구다. DB에 접속하지 않고, 같은 폴더에 calibration.md만 쓴다.
기준은 정밀도 우선이다: 엉뚱한 근거를 내느니 기준을 넘는 후보가 없으면 카드를 만들지 않는다.
주의: 표시한 후보는 검색 상위 k건 안에서만 정해진다. 검색에서 아예 빠진 자료는 알 수 없으므로 재현율은 '후보 안에서의' 값이다.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

LABEL_COL = "관련(O/X)"
LLM_COL = "LLM관련(O/X)"
SIM_COL = "유사도"
KIND_COL = "종류"
YES = {"o", "y", "1", "yes", "true", "관련", "있음", "○", "ㅇ"}
NO = {"x", "n", "0", "no", "false", "무관", "없음", "×", "ㅌ"}
STEP = 0.01
BIN = 0.05
MIN_ROWS_PER_KIND = 20
MIN_RELEVANT_PER_KIND = 3
MIN_KEPT = 5                 # 통과 건수가 이보다 적은 임계값은 우연일 수 있어 추천하지 않는다
DEFAULT_MIN_PRECISION = 0.8


def parse_label(value) -> bool | None:
    v = str(value or "").strip().lower()
    if v in YES:
        return True
    if v in NO:
        return False
    return None


def load_rows(path: str | Path, source: str = "merged") -> list[dict]:
    """표시된 줄을 {kind, similarity, relevant, human, llm}로 읽는다. csv(utf-8-sig/utf-8/cp949)와 xlsx를 지원한다.

    source: human(사람 표시만) | llm(LLM 표시만) | merged(사람 표시가 있으면 사람, 없으면 LLM). 선택한 표시가 없는 줄은 뺀다."""
    path = Path(path)
    if path.suffix.lower() == ".xlsx":
        from openpyxl import load_workbook
        sheet = load_workbook(path, read_only=True, data_only=True).active
        data = [[("" if c is None else c) for c in row] for row in sheet.iter_rows(values_only=True)]
    else:
        text = None
        for enc in ("utf-8-sig", "utf-8", "cp949"):
            try:
                text = path.read_text(encoding=enc)
                break
            except UnicodeDecodeError:
                continue
        if text is None:
            raise ValueError("csv 인코딩을 읽을 수 없습니다 (utf-8 또는 cp949로 저장하세요)")
        data = list(csv.reader(text.splitlines()))
    if not data:
        return []
    header = [str(h).strip() for h in data[0]]
    for col in (LABEL_COL, SIM_COL, KIND_COL):
        if col not in header:
            raise ValueError(f"'{col}' 열이 없습니다. candidates.csv의 첫 줄(머리글)을 바꾸지 마세요.")
    li, si, ki = header.index(LABEL_COL), header.index(SIM_COL), header.index(KIND_COL)
    mi = header.index(LLM_COL) if LLM_COL in header else None
    if source == "llm" and mi is None:
        raise ValueError(f"'{LLM_COL}' 열이 없습니다. 먼저 autolabel을 실행하세요.")
    rows = []
    for r in data[1:]:
        if len(r) <= max(li, si, ki):
            continue
        human = parse_label(r[li])
        llm = parse_label(r[mi]) if mi is not None and len(r) > mi else None
        label = {"human": human, "llm": llm, "merged": human if human is not None else llm}[source]
        if label is None:
            continue
        rows.append({"kind": str(r[ki]).strip(), "similarity": float(r[si]), "relevant": label, "human": human, "llm": llm})
    return rows


def agreement(rows: list[dict]) -> dict | None:
    """사람과 LLM이 둘 다 표시한 줄에서 일치율. 없으면 None."""
    both = [r for r in rows if r.get("human") is not None and r.get("llm") is not None]
    if not both:
        return None
    n = len(both)
    agree = sum(r["human"] == r["llm"] for r in both)
    llm_o = [r for r in both if r["llm"]]
    return {"n": n, "agree": agree / n, "human_o": sum(r["human"] for r in both) / n, "llm_o": len(llm_o) / n,
            "llm_o_precision": (sum(r["human"] for r in llm_o) / len(llm_o)) if llm_o else None,
            "llm_x_missed": sum(r["human"] for r in both if not r["llm"])}


def combine_with_floor(rec: dict | None, floor: float | None) -> float | None:
    """종합 임계값 = 정밀도 기준 추천과 하한선 중 큰 값. 추천이 없으면 None (사용하지 않음)."""
    if rec is None:
        return None
    return max(rec["t"], floor) if floor is not None else rec["t"]


def _bin_index(sim: float, width: float) -> int:
    return int(sim / width + 1e-9)          # 0.70이 0.7000000000000001 같은 부동소수점 때문에 아래 구간으로 밀리지 않게


def bin_table(rows: list[dict], width: float = BIN) -> list[dict]:
    if not rows:
        return []
    idx = [_bin_index(r["similarity"], width) for r in rows]
    out = []
    for b in range(min(idx), max(idx) + 1):
        part = [r for r, i in zip(rows, idx) if i == b]
        n = len(part)
        rel = sum(r["relevant"] for r in part)
        out.append({"from": round(b * width, 2), "to": round((b + 1) * width, 2), "n": n, "relevant": rel,
                    "rate": rel / n if n else None})
    return out


def sweep(rows: list[dict], lo: float = 0.30, hi: float = 0.90, step: float = STEP) -> list[dict]:
    """임계값 t마다: 통과 건수, 정밀도(통과한 것 중 관련 비율), 재현율(관련 중 통과한 비율)."""
    total_rel = sum(r["relevant"] for r in rows)
    out = []
    t = lo
    while t <= hi + 1e-9:
        kept = [r for r in rows if r["similarity"] >= t - 1e-9]
        rel = sum(r["relevant"] for r in kept)
        out.append({"t": round(t, 2), "kept": len(kept), "kept_share": len(kept) / len(rows) if rows else 0,
                    "precision": rel / len(kept) if kept else None,
                    "recall": rel / total_rel if total_rel else None})
        t += step
    return out


def recommend(rows: list[dict], min_recall: float = 0.9) -> dict | None:
    """재현율이 min_recall 이상인 가장 높은 임계값 (관련 있는 것을 놓치지 않는 범위에서 최대한 거른다)."""
    ok = [s for s in sweep(rows) if s["recall"] is not None and s["recall"] >= min_recall]
    return ok[-1] if ok else None


def recommend_precision(rows: list[dict], min_precision: float = DEFAULT_MIN_PRECISION, min_kept: int = MIN_KEPT) -> dict | None:
    """통과한 후보의 정밀도가 min_precision 이상이 되는 가장 낮은 임계값 (엉뚱한 근거를 내지 않는 범위에서 최대한 살린다).
    통과 건수가 min_kept 미만인 임계값은 우연일 수 있어 제외한다. 없으면 None = 이 데이터로는 안전한 기준이 없다."""
    for s in sweep(rows):
        if s["kept"] >= min_kept and s["precision"] is not None and s["precision"] >= min_precision:
            return s
    return None


def _pct(x) -> str:
    return "-" if x is None else f"{x * 100:.0f}%"


def build_report(rows: list[dict], min_recall: float | None = None, min_precision: float = DEFAULT_MIN_PRECISION,
                 noise: dict | None = None, noise_key: str = "p95", source: str = "merged") -> str:
    lines = ["# 임계값 보정 결과", ""]
    rel = sum(r["relevant"] for r in rows)
    goal = f"정밀도 목표 {_pct(min_precision)} (통과한 후보 중 관련 있는 비율)" + (f", 재현율 참고 {_pct(min_recall)}" if min_recall else "")
    src = {"human": "사람 표시", "llm": "LLM 표시", "merged": "사람 표시 + (없는 줄은) LLM 표시"}[source]
    ag = agreement(rows)
    lines += [f"- 표시 출처: {src}"]
    if ag:
        lines += [f"- 사람·LLM 일치율: {_pct(ag['agree'])} ({ag['n']}건 비교). LLM이 O로 본 것 중 사람도 O인 비율 {_pct(ag['llm_o_precision'])}, "
                  f"LLM이 X로 봤지만 사람은 O인 후보 {ag['llm_x_missed']}건"]
        if ag["n"] < 30:
            lines += ["  - 비교 건수가 30건 미만이라 일치율은 참고용입니다. 사람이 30~50건을 표시해 확인하세요."]
    elif source != "human" and any(r.get("llm") is not None for r in rows):
        lines += ["- 사람이 표시한 줄이 없어 LLM 표시의 정확도는 확인되지 않았습니다. 30~50건만 사람이 표시하면 일치율이 나옵니다."]
    lines += [f"- 표시된 후보 {len(rows)}건 (관련 O {rel}건, 무관 X {len(rows) - rel}건), {goal}"]
    if len(rows) < 100 or rel < 10:
        lines += ["- **주의: 표본이 작습니다.** 후보 100건 이상, 관련 O 10건 이상을 권합니다. 지금 값은 참고용입니다."]
    lines += ["", "## 구간별 정답률 (전체)", "", "| 유사도 구간 | 후보 수 | 관련 O | 정답률 |", "|---|---|---|---|"]
    for b in bin_table(rows):
        lines.append(f"| {b['from']:.2f} ~ {b['to']:.2f} | {b['n']} | {b['relevant']} | {_pct(b['rate'])} |")
    groups = [("전체", rows)] + [(k, [r for r in rows if r["kind"] == k]) for k in ("disclosure", "news")]
    lines += ["", "## 임계값별 통과량·정밀도·재현율", ""]
    recs = {}
    for name, g in groups:
        if name != "전체" and (len(g) < MIN_ROWS_PER_KIND or sum(r["relevant"] for r in g) < MIN_RELEVANT_PER_KIND):
            lines += [f"- {name}: 표시된 후보 {len(g)}건, 관련 {sum(r['relevant'] for r in g)}건 — 따로 정하기엔 부족해서 전체 값을 씁니다."]
            continue
        rec = recommend_precision(g, min_precision)
        recs[name] = rec
        lines += [f"### {name}", "", "| 임계값 | 통과 건수 | 통과 비율 | 정밀도 | 재현율 |", "|---|---|---|---|---|"]
        for s in sweep(g, step=0.05):
            lines.append(f"| {s['t']:.2f} | {s['kept']} | {_pct(s['kept_share'])} | {_pct(s['precision'])} | {_pct(s['recall'])} |")
        lines += [""]
    lines += [f"## 추천 (정밀도 {_pct(min_precision)} 이상이 되는 가장 낮은 임계값)", ""]
    finals = {}
    for name, rec in recs.items():
        floor = None
        if noise and name in ("news", "disclosure"):
            v = (noise.get(name) or {}).get(noise_key)
            floor = None if v is None else math.ceil(v * 100 - 1e-9) / 100
        final = combine_with_floor(rec, floor)
        finals[name] = final
        if rec is None:
            lines.append(f"- {name}: 정밀도 {_pct(min_precision)}를 만족하는 임계값이 없습니다. "
                         f"이 종류는 지금 데이터로는 근거로 쓸 만한 후보가 부족하니 높은 값(예: 0.99)으로 막고 '근거 없음'으로 처리하는 편이 안전합니다.")
            continue
        note = ""
        if floor is not None:
            note = f" / 하한선({noise_key}) {floor:.2f}" + (" → 하한선이 더 높아 하한선을 씁니다" if floor > rec["t"] else " → 추천값이 하한선 이상이라 그대로 씁니다")
        lines.append(f"- {name}: **{final:.2f}** (정밀도 기준 {rec['t']:.2f}{note}; 통과 {_pct(rec['kept_share'])}, 정밀도 {_pct(rec['precision'])}, 놓치는 관련 후보 {_pct(1 - rec['recall'])})")
    if min_recall:
        lines += ["", f"참고: 재현율 {_pct(min_recall)} 이상을 지키는 가장 높은 임계값(관련 후보를 덜 놓치지만 엉뚱한 후보가 늘어납니다)"]
        for name, g in groups:
            if name in recs:
                r = recommend(g, min_recall)
                lines.append(f"- {name}: " + ("없음" if r is None else f"{r['t']:.2f} (정밀도 {_pct(r['precision'])}, 통과 {_pct(r['kept_share'])})"))
    lines += ["", "`configs/updates.yaml`의 topic 항목에 반영:", "```yaml", "topic:"]
    if finals.get("전체") is not None:
        lines.append(f"  min_similarity: {finals['전체']:.2f}")
    for name, key in (("news", "min_similarity_news"), ("disclosure", "min_similarity_disclosure")):
        if name in finals:
            lines.append(f"  {key}: {finals[name]:.2f}" if finals[name] is not None else f"  {key}: 0.99   # 정밀도 목표를 만족하는 값이 없어 사실상 사용하지 않음")
    lines += ["```", "", "임계값은 LLM에 넘길 후보를 거르는 첫 문턱입니다. 낮을수록 엉뚱한 근거와 LLM 호출(크레딧)이 늘고, 높을수록 관련 소식을 놓칩니다.",
              "기준을 넘는 후보가 없으면 카드를 만들지 않습니다 (억지로 근거를 만들지 않는다).",
              "표시한 후보는 검색 상위 k건 안에서만 정해졌으므로, 재현율은 '후보 안에서의' 값입니다."]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="사람이 표시한 후보로 유사도 임계값을 정한다 (DB 접속 없음)")
    ap.add_argument("--labels", required=True, help="'관련(O/X)' 열을 채운 candidates.csv 또는 .xlsx")
    ap.add_argument("--min-precision", type=float, default=DEFAULT_MIN_PRECISION,
                    help="통과한 후보 중 관련 있는 비율 목표 (기본 0.8). 엉뚱한 근거를 줄이려면 올린다")
    ap.add_argument("--min-recall", type=float, help="(참고용) 관련 후보를 놓치지 않을 비율. 주면 이 기준의 임계값도 함께 보여 준다")
    ap.add_argument("--source", choices=["merged", "human", "llm"], default="merged",
                    help="어느 표시를 쓸지: merged(사람 표시 우선, 없으면 LLM) | human | llm (기본 merged)")
    ap.add_argument("--noise-floor", help="noise_floor.json (다른 종목 자료 기반 하한선). 주면 정밀도 기준 추천과 큰 쪽을 쓴다")
    ap.add_argument("--noise-percentile", default="p95", choices=["p90", "p95", "p99"], help="하한선으로 쓸 백분위 (기본 p95)")
    ap.add_argument("--out", help="보고서 경로 (기본: 라벨 파일 옆 calibration.md)")
    args = ap.parse_args(argv)
    rows = load_rows(args.labels, args.source)
    noise = json.loads(Path(args.noise_floor).read_text(encoding="utf-8")) if args.noise_floor else None
    if not rows:
        print("표시된 줄이 없습니다. '관련(O/X)' 열에 O 또는 X를 적었는지 확인하세요.")
        return 1
    report = build_report(rows, args.min_recall, args.min_precision, noise, args.noise_percentile, args.source)
    out = Path(args.out) if args.out else Path(args.labels).with_name("calibration.md")
    out.write_text(report, encoding="utf-8")
    print(report)
    print(f"보고서: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())