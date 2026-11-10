"""정답 메모 세트의 응답 유형 분포 (LLM 호출 없음, DB 읽기 전용). 결과는 파일로만.

    PYTHONPATH=backend python -m pipelines.updates.response_dist                       # memos_long_v2, 기준일 2026-11-09
    PYTHONPATH=backend python -m pipelines.updates.response_dist --saved <judgments.jsonl 또는 sentences.jsonl>

메모 분석: 지금 코드의 로직 판정(judge_memo) + 로직이 LLM으로 넘긴 조각은 저장된 LLM 판정을 쓴다.
- --saved가 tracking.evaluate_long의 judgments.jsonl이면 조각 위치(span)가 같은 판정을 쓴다 (모든 조각, 항목 포함).
- sentences.jsonl(2026-11-09 이전 형식)이면 pred_text가 같은 조각만 찾는다. 정답 문장마다 한 조각만 저장돼 있어
  못 찾는 조각은 '판정 없음'으로 따로 세고, 그런 메모는 메모 단위 범위 밖을 정하지 않는다. 항목도 없다.
추적 항목이 저장돼 있지 않은 추적 문장은 '항목 미저장' 주제 항목 하나로 본다. 카드 단계(LLM)는 돌리지 않으므로
주제 항목은 no_data(조회 기간 뉴스·공시 없음)가 아니면 'topic_card_not_run'(no_new_info 또는 update_card)으로 센다.
가격 항목은 experiment와 같은 PRICE_SQL·price_outcome(오래된 종가는 no_data)으로 판정한다.
no_data (b)는 기준일에서 recent.lookback_days(365일) 전까지 전체에 뉴스·공시가 없을 때만. 2026-11-10 저장소 밖 resp_dist.py를 옮겼다.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import date, datetime
from pathlib import Path

from ..common.config import REPO_ROOT, load_config, resolve_path
from .models import TrackingItem

DEFAULT_MEMOS = "results/memo_personas/memos_long_v2"
DEFAULT_SAVED = "results/tracking_eval/memos_long_20261109_161350/sentences.jsonl"
TRACKED = {"normal", "partial"}


def load_saved(path: Path) -> tuple[str, dict]:
    """("judgments", {(memo_id, (start, end)): dict}) 또는 ("sentences", {(memo_id, 조각 글): (판정, 분류)})."""
    lines = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if lines and "judged" in lines[0]:
        return "judgments", {(m["memo_id"], tuple(d["span"])): d for m in lines for d in m["judged"]
                             if d.get("judged_by") == "llm"}
    return "sentences", {(r["memo_id"], r["pred_text"]): (r["pred"], r["pred_category"]) for r in lines
                         if r.get("pred_text") is not None and r.get("judged_by") == "llm"}


def apply_saved(j, mid: str, fmt: str, saved: dict) -> bool:
    """로직이 LLM으로 넘긴 조각에 저장된 판정을 덮는다. 못 찾으면 False."""
    if fmt == "judgments":
        d = saved.get((mid, tuple(j.span)))
        if d is None:
            return False
        j.decision, j.category, j.reason_code = d["decision"], d.get("category"), d.get("reason_code")
        j.items, j.merge_into = list(d.get("items") or []), d.get("merge_into")
    else:
        hit = saved.get((mid, j.text))
        if hit is None:
            return False
        j.decision, j.category = hit
    j.judged_by = "llm(saved)"
    return True


def memo_items(mid: str, sym: str, judged: list) -> list[tuple[TrackingItem, str]]:
    items = []
    for j in judged:
        if j.decision not in TRACKED or j.merge_into:
            continue
        kept = [it for it in j.items if it.get("type") in ("topic", "price_below", "price_above")]
        if kept:
            for i, it in enumerate(kept):
                items.append((TrackingItem(f"{mid}:{j.sentence_index}:{i}", sym, it["type"], it["description"],
                                           keywords=tuple(it.get("keywords") or ()),
                                           price_threshold=it.get("price_threshold")), "saved"))
        else:
            items.append((TrackingItem(f"{mid}:{j.sentence_index}:0", sym, "topic", j.text), "unsaved"))
    return items


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="응답 유형 분포 (LLM 없음, DB 읽기 전용, 결과는 파일로만)")
    ap.add_argument("--memos", default=DEFAULT_MEMOS)
    ap.add_argument("--saved", default=DEFAULT_SAVED, help="저장된 LLM 판정 (evaluate_long의 judgments.jsonl 또는 sentences.jsonl)")
    ap.add_argument("--until", default="2026-11-09")
    ap.add_argument("--config", default="configs/updates.yaml")
    ap.add_argument("--out", help="결과 폴더 (기본: results/updates/responses_<세트>_<시각>)")
    args = ap.parse_args(argv)

    import psycopg

    from ..common.db import get_read_dsn
    from ..tracking.judge import PENDING, judge_memo
    from ..tracking.lexicon import load_lexicon
    from .confirm import confirmation, price_window
    from .eval_e2e import fill_symbols, load_memos, stock_names
    from .experiment import PRICE_SQL
    from .price import market_dates, price_outcome
    from .response import (data_need_check, item_response, lookback_since, memo_response, order_key, sentence_responses,
                           source_data, summarize, to_dict)
    from .results import draft_to_dict

    until = date.fromisoformat(args.until)
    memos = load_memos(args.memos)
    fmt, saved = load_saved(resolve_path(args.saved))
    lex = load_lexicon()
    cfg = load_config(args.config)
    near_pct = cfg["price"]["near_pct"]
    stamp = datetime.now().astimezone().isoformat(timespec="seconds")
    stat = Counter({"saved_format_" + fmt: 1})
    responses, checks = [], []
    with psycopg.connect(get_read_dsn()) as conn:
        conn.read_only = True
        no_symbol = fill_symbols(memos, stock_names(conn))
        memos = [m for m in memos if m.get("symbol")]
        stat["memos_without_symbol"] = no_symbol
        symbols = sorted({m["symbol"] for m in memos})
        nd_since = lookback_since(cfg, until)                 # no_data (b): 조회 기간 전체 (2026-11-10)
        has_data = {s: any(source_data(conn, s, nd_since, until).values()) for s in symbols}
        dates = market_dates(conn)
        windows = {s: price_window(conn, s) for s in symbols}
        prices = {}
        for s in symbols:
            with conn.cursor() as cur:
                cur.execute(PRICE_SQL, {"symbol": s})
                prices[s] = cur.fetchall()
        conn.rollback()
    for m in memos:
        mid, sym = m["memo_id"], m["symbol"]
        judged, unknown = [], 0
        for j in judge_memo(m["memo_body"], sym, lex):
            stat["fragments"] += 1
            if j.decision == PENDING:
                if not apply_saved(j, mid, fmt, saved):
                    unknown += 1
                    stat["fragments_no_judgment"] += 1
                    continue
                stat["fragments_saved_llm"] += 1
            else:
                stat["fragments_rule"] += 1
            judged.append(j)
        mine = sentence_responses(mid, judged, lambda j, s=sym: confirmation(j.cleaned_text or j.text, j.reason_code,
                                                                           windows.get(s, [])), stamp)
        items = memo_items(mid, sym, judged)
        whole = memo_response(mid, judged, len(items), stamp)
        if whole and unknown:                                  # 판정 없는 조각이 추적 문장일 수 있어 정하지 않는다
            stat["memo_out_of_scope_undetermined"] += 1
            whole = None
        if whole:
            mine.append(whole)
        for item, src in items:
            if item.type == "topic":
                stat[f"topic_items_{src}"] += 1
                if has_data.get(sym) is False:
                    mine.append(item_response(item, "no_candidates", [], None, False, mid, stamp))
                else:
                    stat["topic_card_not_run"] += 1
                continue
            stat["price_items"] += 1
            pkind, draft, _ = price_outcome(item, prices.get(sym) or [], dates, near_pct)
            mine.append(item_response(item, pkind, [], draft_to_dict(draft) if draft else None, None, mid, stamp))
        mine.sort(key=order_key)
        responses += mine
        nd = [x.reason for x in mine if x.type == "no_data"]
        checks.append({"memo_id": mid, "data_need": m.get("data_need"), "no_data": bool(nd), "no_data_reasons": nd,
                       "out_of_scope": whole is not None})

    tab = Counter()
    for c in checks:
        need = set(c["data_need"] or [])
        key = "news_or_disclosure" if need & {"뉴스", "공시"} else ("empty" if not need else "other_only")
        tab[f"{key}/{'no_data' if c['no_data'] else 'no_no_data'}"] += 1
    summ = {"memos": args.memos, "saved": args.saved, "window": [str(nd_since), args.until], "symbols": len(symbols),
            "symbols_without_news_or_disclosure": sorted(s for s, v in has_data.items() if not v),
            "analysis": dict(stat), "responses": summarize(responses), "data_need": data_need_check(checks),
            "data_need_table": dict(tab)}
    out = Path(args.out) if args.out else REPO_ROOT / "results/updates" / (
        f"responses_{Path(args.memos).name}_{datetime.now():%Y%m%d_%H%M%S}")
    out.mkdir(parents=True, exist_ok=True)
    with (out / "responses.jsonl").open("w", encoding="utf-8") as f:
        for r in responses:
            f.write(json.dumps(to_dict(r), ensure_ascii=False, default=str) + "\n")
    (out / "summary.json").write_text(json.dumps(summ, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    rs = summ["responses"]
    print(f"메모 {len(memos)} · 조각 {json.dumps(dict(stat), ensure_ascii=False)}")
    print(f"응답 {json.dumps(rs['by_type'], ensure_ascii=False)} · 사용자 표시 {rs['user_visible']}"
          f" {json.dumps(rs['user_visible_by_type'], ensure_ascii=False)}")
    print(f"확인 필요 {json.dumps(rs['needs_confirmation'], ensure_ascii=False)}")
    print(f"data_need × no_data (메모 단위): {json.dumps(summ['data_need_table'], ensure_ascii=False)}")
    for r in responses:
        if r.type == "needs_confirmation" and any(o.get("status") == "already_reached" for o in r.options):
            print(f"  이미 도달 선택지: {r.memo_id} {r.text[:40]} → {r.question}")
    print(f"결과: {out} — DB에는 아무것도 쓰지 않았습니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
