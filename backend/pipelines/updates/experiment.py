"""AI 업데이트 후보 검색·카드 생성 실험.  DB에는 읽기만 하고, 결과는 results/updates/run_<시각>/ 폴더에만 저장한다.

- DB 접속은 get_read_dsn()(READONLY_DATABASE_URL, 없으면 DATABASE_URL) + 세션 읽기 전용(read_only=True).
  SELECT만 쓰며 INSERT/UPDATE/DELETE, Alembic, SQL 파일은 건드리지 않는다.
- 항목은 평가 메모(jsonl)의 정답 판정(gold)을 쓴다: 주제 항목은 후보 검색 → LLM 카드, 가격 항목은 종가 비교(코드).
- 후보 검색은 최신순 하향식이다: recent.lookback_days 안에서 종류별 임계값을 넘은 후보를 날짜 최신순으로 가져오고,
  topic.check_topic(pick_recent)이 오늘 → 전날 → 전전날 순으로 거슬러 가며 고른다.

    # 1) 검색만 (API 비용 없음): 유사도 분포와 후보 제목을 눈으로 확인
    PYTHONPATH=backend python -m pipelines.updates.experiment --llm none
    # 2) LLM 카드 + 코드 검사까지 (OpenAI 호출, .env의 LLM_API_KEY 필요)
    PYTHONPATH=backend python -m pipelines.updates.experiment --llm openai --limit 10
"""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

from ..common.config import load_config, resolve_path
from .candidates import drop_other_company_news, listed_names, recent_disclosure_candidates, recent_news_candidates
from .models import TrackingItem
from .preview import write_preview
from .price import check_price
from .results import new_run_dir, write_candidates_csv, write_results
from .evidence import threshold_key
from .topic import check_topic, thresholds

PILOT = ("005930", "000660", "035420", "105560")

PRICE_SQL = "SELECT trade_date, close FROM prices_daily WHERE symbol = %(symbol)s ORDER BY trade_date DESC LIMIT 2"


def load_items(gold_path: Path, symbols: tuple[str, ...] = PILOT) -> list[TrackingItem]:
    """평가 메모의 추적 항목(주제 + 가격)을 TrackingItem으로 바꾼다."""
    items = []
    with gold_path.open(encoding="utf-8") as handle:
        memos = [json.loads(line) for line in handle if line.strip()]
    for memo in memos:
        if memo["symbol"] not in symbols:
            continue
        for sent in memo["sentences"]:
            for i, it in enumerate(sent["items"]):
                if it["type"] not in ("topic", "price_below", "price_above"):
                    continue
                items.append(TrackingItem(
                    item_id=f"{memo['memo_id']}:{sent['sentence_index']}:{i}", symbol=memo["symbol"], type=it["type"],
                    description=it["description"], keywords=tuple(it.get("keywords") or ()),
                    price_threshold=it.get("price_threshold"),
                    category=str(sent.get("category") or it.get("category") or ""),
                    memo_text=sent.get("cleaned_text") or sent["text"]))
    return items


def _empty(item, kind: str) -> dict:
    return {"item_id": item.item_id, "symbol": item.symbol, "company_name": item.company_name,
            "description": item.description, "memo_text": item.memo_text, "kind": kind}


def _fmt(out) -> list[str]:
    rows = ["| 유사도 | 종류 | 날짜 | 제목 |", "|---|---|---|---|"]
    for e in out.evidence:
        c = e.candidate
        rows.append(f"| {c.similarity:.3f} | {e.eid} {c.kind} | {c.date} | {c.title[:60].replace('|', '/')} |")
    rows.append("")
    rows.append(f"결과: **{out.kind}**" + (f" · 검사 실패: {', '.join(out.fail_codes)}" if out.fail_codes else "") + (" · 형식 재요청 1회" if out.retried else ""))
    if out.raw and (out.fail_codes or out.retried):
        rows.append("- LLM 원문(앞 700자):")
        rows.append("```")
        rows.append(out.raw[:700])
        rows.append("```")
    for note in out.verify_notes:
        rows.append(f"- 검수가 막은 문장: {note}")
    if out.card and out.card.status == "update":
        rows.append(f"- LLM 카드: {out.card.title} / {' '.join(out.card.summary)} / {out.card.reason} (확신 {out.card.confidence})")
    if out.draft:
        rows.append(f"- 최종({out.draft.origin}): {out.draft.title} / {out.draft.summary}")
        for _, title in out.draft.related_news:
            rows.append(f"  - 관련 기사: {title}")
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="후보 검색·카드 생성 실험 (DB 읽기 전용, 결과는 파일로만 저장)")
    ap.add_argument("--gold", default="eval/memo_eval_v0/memo_eval_v0.jsonl")
    ap.add_argument("--config", default="configs/updates.yaml")
    ap.add_argument("--symbols", default=",".join(PILOT))
    ap.add_argument("--since", help="뉴스 시작일 YYYY-MM-DD (기본: 설정의 recent.lookback_days 전)")
    ap.add_argument("--disclosure-since", help="공시 시작일 YYYY-MM-DD (기본: 설정의 recent.lookback_days 전)")
    ap.add_argument("--llm", choices=["none", "openai"], default="none")
    ap.add_argument("--limit", type=int, help="앞에서 N개 항목만")
    ap.add_argument("--out-dir", help="결과 폴더 (기본: results/updates)")
    ap.add_argument("--response-schema", action="store_true", help="OpenAI Structured Outputs(json_schema) 사용 (미검증, 기본 꺼짐)")
    args = ap.parse_args(argv)

    import psycopg

    from ..common.db import get_read_dsn
    from ..news.embedder import make_bge_m3_encoder
    from ..tracking.openai_client import OpenAIClient

    cfg = load_config(args.config)
    tcfg = cfg["topic"]
    banned = list(cfg["banned"])
    items = load_items(resolve_path(args.gold), tuple(args.symbols.split(",")))
    if args.limit:
        items = items[:args.limit]
    topic_items = [it for it in items if it.type == "topic"]
    rcfg = cfg.get("recent", {})
    lookback = date.today() - timedelta(days=rcfg.get("lookback_days", 365))
    since = date.fromisoformat(args.since) if args.since else lookback
    d_since = date.fromisoformat(args.disclosure_since) if args.disclosure_since else lookback
    fetch_k = rcfg.get("fetch_k", 50)
    floor, strong = thresholds(tcfg)

    vectors = {}
    if topic_items:
        encode = make_bge_m3_encoder("dense")
        vectors = {it.item_id: d for it, (d, _) in zip(topic_items, encode([it.query_text for it in topic_items]))}
    client = None
    if args.llm == "openai":
        if args.response_schema:
            from .openai_schema import SchemaOpenAIClient
            client = SchemaOpenAIClient.from_env()
        else:
            client = OpenAIClient.from_env()

    names: dict[str, str] = {}
    sims: list[float] = []
    kind_sims: dict[str, list[float]] = {"news": [], "disclosure": [], "event": []}   # disclosure=정기보고서, event=수시공시
    cand_rows = []
    other_news = []                                             # 다른 회사 이름으로 시작해 뺀 기사 (항목, 후보)
    status_count: dict[str, int] = {}
    fail_count: dict[str, int] = {}
    drafts = []
    empties = []                                                # 카드가 없는 항목 (미리보기의 '근거 없음' 목록)
    sections = []
    with psycopg.connect(get_read_dsn()) as conn:
        conn.read_only = True                                   # 이 연결은 쓰기를 시도하면 DB가 거부한다
        with conn.cursor() as cur:
            cur.execute("SELECT symbol, name FROM stocks WHERE symbol = ANY(%(s)s)", {"s": sorted({i.symbol for i in items})})
            names = {sym.strip(): name for sym, name in cur.fetchall()}
            cur.execute("SELECT name FROM stocks")
            stock_names = [n for (n,) in cur.fetchall() if n]     # 다른 회사 기사 제목을 알아보는 데 쓴다
        # 코스닥 회사(파트론 등)는 stocks에 없어 DART 회사 목록 파일에서 이름을 더한다. 파일이 없으면 stocks 이름만 쓴다
        file_names = (listed_names(resolve_path(rcfg["company_names_file"]))
                      if rcfg.get("drop_other_company_news", True) and rcfg.get("company_names_file") else [])
        all_names = sorted(set(stock_names) | set(file_names))
        aliases = rcfg.get("company_aliases") or {}
        items = [replace(i, company_name=names.get(i.symbol, "")) for i in items]
        for item in items:
            if item.type == "topic":
                vec = vectors[item.item_id]
                cands = (recent_news_candidates(conn, item.symbol, vec, since, fetch_k, floor["news"], cfg["news"]["variant"])
                         + recent_disclosure_candidates(conn, item.symbol, vec, d_since, fetch_k, floor["disclosure"],
                                                        floor["event"], rcfg.get("include_subsidiary", False)))
                if rcfg.get("drop_other_company_news", True):
                    cands, dropped = drop_other_company_news(cands, item.company_name, all_names,
                                                             aliases.get(item.company_name, []))
                    other_news += [(item, c) for c in dropped]
                sims += [c.similarity for c in cands]
                for c in cands:
                    kind_sims[threshold_key(c)].append(c.similarity)
                    cand_rows.append((item, c))
                out = check_topic(item, cands, client, banned, tcfg)
                status_count[out.kind] = status_count.get(out.kind, 0) + 1
                for code in out.fail_codes:                     # 원본 LLM 출력이 어떤 검사에 걸렸는지 (평가 지표)
                    key = code.split(":")[0]
                    fail_count[key] = fail_count.get(key, 0) + 1
                if out.draft:
                    drafts.append(out.draft)
                else:
                    empties.append(_empty(item, out.kind))
                sections += [f"### {item.item_id} · {item.symbol} · [{item.category or '-'}] {item.description}",
                             f"메모: {item.memo_text}", "", *_fmt(out), ""]
            else:
                with conn.cursor() as cur:
                    cur.execute(PRICE_SQL, {"symbol": item.symbol})
                    rows = cur.fetchall()
                sections += [f"### {item.item_id} · {item.symbol} · [{item.category or '-'}] {item.description}",
                             f"메모: {item.memo_text}", ""]
                if not rows:
                    status_count["price_no_data"] = status_count.get("price_no_data", 0) + 1
                    empties.append(_empty(item, "price_no_data"))
                    sections += ["결과: **price_no_data** (prices_daily에 종가 없음)", ""]
                    continue
                (day, close), prev = rows[0], (float(rows[1][1]) if len(rows) > 1 else None)
                draft = check_price(item, float(close), prev, str(day), cfg["price"]["near_pct"])
                key = f"price_{draft.price_state}" if draft else "price_no_card"
                status_count[key] = status_count.get(key, 0) + 1
                if draft:
                    drafts.append(draft)
                else:
                    empties.append(_empty(item, "price_no_card"))
                sections += [f"기준일 {day} 종가 {float(close):,.0f}원 → " + (f"**{draft.title}** / {draft.summary}" if draft else "**카드 없음**"), ""]

    sims.sort()
    q = lambda p: round(sims[int(p * (len(sims) - 1))], 3) if sims else None

    def dist(xs):
        xs = sorted(xs)
        pick = lambda p: round(xs[int(p * (len(xs) - 1))], 3) if xs else None
        return {"n": len(xs), "min": pick(0), "p25": pick(.25), "median": pick(.5), "p75": pick(.75), "max": pick(1)}
    summary = {"items": len(items), "topic_items": len(topic_items), "candidates": len(sims), "news_since": str(since),
               "llm": args.llm, "similarity": {"min": q(0), "p25": q(.25), "median": q(.5), "p75": q(.75), "max": q(1)},
               "similarity_by_kind": {k: dist(v) for k, v in kind_sims.items()},
               "outcomes": status_count, "llm_check_failures": fail_count, "cards": len(drafts)}
    summary["search"] = {"mode": "recent_first", "news_since": str(since), "disclosure_since": str(d_since),
                         "floor": floor, "strong": strong, "stop_window_days": tcfg.get("stop_window_days", 0),
                         "include_subsidiary": rcfg.get("include_subsidiary", False), "config": args.config}
    head = ["# AI 업데이트 후보 검색·카드 생성 실험", f"- 항목 {len(items)}개 (주제 {len(topic_items)}), 후보 {len(sims)}건, 뉴스 시작일 {since}, LLM {args.llm}",
            f"- 검색: 최신순 하향식 (설정 {args.config}) · 공시 시작일 {d_since} · 최소 유사도 {floor} · 강한 후보(멈춤 기준) {strong}"
            f" · 멈춘 날부터 {tcfg.get('stop_window_days', 0)}일 전까지 포함 · 자회사 공시 {'포함' if rcfg.get('include_subsidiary') else '제외'}",
            f"- 유사도 분포: 최소 {q(0)} / 25% {q(.25)} / 중앙 {q(.5)} / 75% {q(.75)} / 최대 {q(1)}",
            *[f"  - {k}: {json.dumps(dist(v), ensure_ascii=False)}" for k, v in kind_sims.items()],
            f"- 처리 결과: {json.dumps(status_count, ensure_ascii=False)}",
            f"- 코드 검사 실패 코드(LLM 원본 기준): {json.dumps(fail_count, ensure_ascii=False)}",
            f"- 다른 회사 이름으로 시작해 뺀 기사: {len(other_news)}건 (항목·기사 쌍, 목록은 보고서 맨 끝)"
            + (f" · 회사 이름 {len(all_names)}개 (stocks {len(stock_names)}, 파일 {len(file_names)})"
               if rcfg.get("drop_other_company_news", True) else " · 꺼짐")]
    summary["other_company_news"] = len(other_news)
    titles: dict[str, list[str]] = {}
    for item, c in other_news:
        titles.setdefault(f"{c.date} {c.title}", []).append(item.item_id)
    sections += ["## 다른 회사 이름으로 시작해 뺀 기사", *[f"- {t} ← {', '.join(ids)}" for t, ids in titles.items()], ""]
    if client and client.calls:
        pt = sum(c.prompt_tokens or 0 for c in client.calls)
        ot = sum(c.output_tokens or 0 for c in client.calls)
        head.append(f"- LLM 호출 {len(client.calls)}회, 입력 토큰 {pt}, 출력 토큰 {ot}")
        summary["llm_calls"], summary["prompt_tokens"], summary["output_tokens"] = len(client.calls), pt, ot
    run_dir = new_run_dir(args.out_dir)
    write_results(run_dir, drafts, "\n".join(head + [""] + sections) + "\n", summary)
    csv_path = write_candidates_csv(run_dir, cand_rows)
    preview_path = write_preview(run_dir, drafts, cand_rows, empties, f"{run_dir.name} · LLM {args.llm}")
    print("\n".join(head))
    print(f"결과 폴더: {run_dir}  (cards.jsonl, report.md, summary.json, candidates.csv) — DB에는 아무것도 쓰지 않았습니다.")
    print(f"미리보기(사용자 화면처럼): {preview_path}")
    print(f"임계값 정하기: {csv_path} 의 마지막 열 '관련(O/X)'을 채운 뒤 python -m pipelines.updates.calibrate --labels {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())