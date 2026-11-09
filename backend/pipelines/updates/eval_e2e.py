"""메모 분석부터 카드까지 끝까지 평가 (memos_kospi). DB는 읽기만, 결과는 results/updates/e2e_<시각>/ 파일로만.

    PYTHONPATH=backend python -m pipelines.updates.eval_e2e --sample 100 --dry-sample     # 표본만 뽑아 보기 (LLM·GPU 없음)
    PYTHONPATH=backend python -m pipelines.updates.eval_e2e --sample 100                   # 전체 (OpenAI 호출)

① 메모 분석: tracking 로직 판정 + 메모당 1회 LLM 판정 → 추적 항목. 문장 라벨(intended_type, expected_decision)과 비교해 정확도.
   memos_kospi 문장에는 위치(span)가 없어 문장 글을 메모에서 찾아 가장 많이 겹치는 판정 문장과 맞춘다.
   정답 문장은 오타를 고친 memo_body_clean 기준이라, clean에서 찾은 위치를 오타가 든 memo_body 위치로 옮겨 맞춘다.
메모 파일: --memos에 파일·폴더·glob을 줄 수 있다. 폴더면 batch_*.jsonl만 읽는다 (memos.jsonl은 같은 내용의 모음이라 뺀다).
   symbol이 없는 세트(memos_long)는 company_primary를 stocks 이름으로 찾아 채운다 (못 찾으면 표본에서 빠진다).
② 후보 검색 ③ 근거·LLM 카드 ④ 코드 검사를 조건별로 돌린다. 메모 분석 결과(추적 항목)는 조건끼리 같다.
   - baseline: 제목+요약 뉴스 검색, 근거 legacy(공시 2·뉴스 3), 같은 사건 묶기 꺼짐, 추가 규칙·예측 검사 없음
   - new: 원문 청크 뉴스 검색(보정 전 임시 임계값), 같은 사건 묶기, 근거 all(공시 5건·청크 2개, 전체 15), 추가 규칙, 예측 검사
   기간은 --since ~ --until (기본 2026-11-01 ~ 2026-11-09, 뉴스·공시 같게). 검색 뒤 --until보다 늦은 후보는 뺀다.
표본: 종목을 다양하게(종목당 처음엔 1개씩), 11-01 이후 기사 연결이 충분한 종목(--rich-min건 이상) 위주로 섞는다.
   기사 연결 수는 news_stocks + 태그 확대(stock_tagger) dry-run을 합쳐 센다 (태그를 아직 쓰지 않았어도 같은 표본이 나오게).
"""

from __future__ import annotations

import argparse
import difflib
import glob
import json
import random
import time
from collections import Counter, defaultdict
from dataclasses import replace
from datetime import date, datetime, timedelta
from pathlib import Path

from ..common.config import load_config, resolve_path
from .models import TrackingItem

MEMOS_PATH = "results/memo_personas/memos_kospi/memos.jsonl"
GOLD_DECISION = {"추적": "normal", "일부 추적": "partial", "추적 안 함": "full_fallback", "확인 필요": "needs_confirmation"}
TRACKED = {"normal", "partial"}


def bucket(decision: str) -> str:
    return "tracked" if decision in TRACKED else decision


# ---------------------------------------------------------------- 표본

def memo_files(path: str = MEMOS_PATH) -> list[Path]:
    """파일 하나 / 폴더(batch_*.jsonl) / glob 패턴."""
    if any(ch in path for ch in "*?["):
        files = [Path(p) for p in sorted(glob.glob(str(resolve_path(path))))]
    else:
        p = resolve_path(path)
        files = sorted(p.glob("batch_*.jsonl")) if p.is_dir() else [p]
    files = [f for f in files if f.name != "memos.jsonl" or len(files) == 1]
    if not files:
        raise FileNotFoundError(f"메모 파일이 없습니다: {path}")
    return files


def load_memos(path: str = MEMOS_PATH) -> list[dict]:
    memos = [json.loads(line) for f in memo_files(path) for line in f.read_text(encoding="utf-8").splitlines() if line.strip()]
    ids = Counter(m["memo_id"] for m in memos)
    dup = [i for i, n in ids.items() if n > 1]
    if dup:
        raise ValueError(f"memo_id가 겹칩니다 (파일을 두 번 읽었는지 확인): {dup[:5]}")
    return memos


def fill_symbols(memos: list[dict], names: dict[str, str]) -> int:
    """symbol이 없는 메모에 company_primary → 종목코드를 채운다. 반환: 못 찾은 메모 수."""
    missing = 0
    for m in memos:
        if not m.get("symbol"):
            m["symbol"] = names.get((m.get("company_primary") or "").strip())
            missing += not m["symbol"]
    return missing


def stock_names(conn) -> dict[str, str]:
    with conn.cursor() as cur:
        cur.execute("SELECT name, symbol FROM stocks")
        return {name.strip(): symbol.strip() for name, symbol in cur.fetchall()}


def sample_memos(memos: list[dict], news_counts: dict[str, int], n: int = 100, rich_min: int = 5,
                 rich_share: float = 0.7, seed: int = 7) -> list[dict]:
    """종목이 있는 메모에서 n개. rich(기사 rich_min건 이상) 종목 메모 rich_share, 나머지는 기사가 적은 종목.
    종목당 1개씩 먼저 고르고 모자라면 같은 종목에서 더 고른다."""
    rng = random.Random(seed)
    with_symbol = [m for m in memos if m.get("symbol")]
    rich = [m for m in with_symbol if news_counts.get(m["symbol"], 0) >= rich_min]
    poor = [m for m in with_symbol if news_counts.get(m["symbol"], 0) < rich_min]

    def pick(pool: list[dict], k: int) -> list[dict]:
        pool = pool[:]
        rng.shuffle(pool)
        out, seen = [], set()
        for m in pool:                                          # 종목당 1개
            if len(out) < k and m["symbol"] not in seen:
                out.append(m)
                seen.add(m["symbol"])
        for m in pool:                                          # 모자라면 더
            if len(out) < k and m not in out:
                out.append(m)
        return out

    k_rich = min(len(rich), round(n * rich_share))
    chosen = pick(rich, k_rich)
    chosen += pick(poor, min(len(poor), n - len(chosen)))
    if len(chosen) < n:
        chosen += pick([m for m in rich if m not in chosen], n - len(chosen))
    return sorted(chosen, key=lambda m: m["memo_id"])


def news_counts(conn, since: datetime, until: datetime) -> dict[str, int]:
    """종목별 기사 수 (11-01 이후): news_stocks + 태그 확대 dry-run (DB에 쓰지 않는다)."""
    from ..news.stock_tagger import load_rules, tag_window

    with conn.cursor() as cur:
        cur.execute("""SELECT ns.symbol, count(DISTINCT ns.news_id) FROM news_stocks ns JOIN news_articles a ON a.id = ns.news_id
                       WHERE a.published_at >= %s AND a.published_at < %s GROUP BY 1""", (since, until))
        counts = Counter({s.strip(): n for s, n in cur.fetchall()})
    stats = tag_window(conn, load_rules(conn), since, until, write=False)
    counts.update(Counter(h.symbol for *_, h in stats["_new"]))
    conn.rollback()
    return dict(counts)


# ---------------------------------------------------------------- ① 메모 분석

def span_mapper(clean: str, raw: str):
    """clean 글의 위치 → raw 글의 위치 (오타로 글자가 바뀌거나 늘고 준 메모)."""
    if clean == raw:
        return lambda pos: pos
    ops = difflib.SequenceMatcher(None, clean, raw, autojunk=False).get_opcodes()

    def conv(pos: int) -> int:
        for tag, i1, i2, j1, j2 in ops:
            if i1 <= pos <= i2:
                if tag == "equal":
                    return j1 + (pos - i1)
                return j1 if pos == i1 else j2
        return len(raw)
    return conv


def align(memo_text: str, gold: list[dict], pred: list, clean_text: str | None = None) -> list[tuple[dict, object | None]]:
    """정답 문장 → 가장 많이 겹치는 판정 문장 (못 찾으면 None).
    clean_text(오타 고친 글)를 주면 정답 문장을 거기서 찾고 위치를 memo_text(판정한 원문) 위치로 옮긴다."""
    base = clean_text if clean_text is not None else memo_text
    conv = span_mapper(base, memo_text)
    out, cursor = [], 0
    for g in gold:
        start = base.find(g["text"], cursor)
        if start < 0:
            start = base.find(g["text"])
        if start < 0:
            out.append((g, None))
            continue
        cursor = start + len(g["text"])
        start, end = conv(start), conv(cursor)
        best, overlap = None, 0
        for p in pred:
            o = min(end, p.span[1]) - max(start, p.span[0])
            if o > overlap:
                best, overlap = p, o
        out.append((g, best))
    return out


def score_analysis(rows: list[dict]) -> dict:
    """rows: {"gold": 정답 문장, "pred": 판정 dict 또는 None}. 지표는 tracking.evaluate_llm과 같은 뜻."""
    c = Counter()
    confusion = Counter()
    for r in rows:
        g, p = r["gold"], r["pred"]
        c["sentences"] += 1
        if p is None:
            continue
        c["aligned"] += 1
        gd = GOLD_DECISION.get(g["expected_decision"], "needs_confirmation")
        confusion[(gd, p["decision"])] += 1
        c["decision_ok"] += p["decision"] == gd
        c["tracking_ok"] += bucket(p["decision"]) == bucket(gd)
        if p.get("category"):
            c["category_scored"] += 1
            c["category_ok"] += p["category"] == g["intended_type"]
        c["missed"] += gd in TRACKED and p["decision"] == "full_fallback"
        c["over"] += gd == "full_fallback" and p["decision"] in TRACKED
        c["confirm"] += p["decision"] == "needs_confirmation"
        c["gold_tracked"] += gd in TRACKED
        c["items"] += len(p.get("items") or [])

    def ratio(a, b):
        return round(c[a] / c[b], 4) if c[b] else None
    return {"sentences": c["sentences"], "aligned": c["aligned"], "tracking_agreement": ratio("tracking_ok", "aligned"),
            "decision_accuracy": ratio("decision_ok", "aligned"), "category_accuracy": ratio("category_ok", "category_scored"),
            "missed_tracking": c["missed"], "over_tracking": c["over"], "needs_confirmation": c["confirm"],
            "gold_tracked": c["gold_tracked"], "items": c["items"],
            "confusion": {f"{g}→{p}": n for (g, p), n in sorted(confusion.items())}}


def items_from(memo: dict, judgments: list, company: str) -> list[TrackingItem]:
    """추적(normal·partial) 문장의 항목 → TrackingItem. 앞 문장에 합친 문장(merge_into)은 새 항목을 만들지 않는다."""
    out = []
    for j in judgments:
        if j.decision not in TRACKED or j.merge_into:
            continue
        for i, it in enumerate(j.items):
            out.append(TrackingItem(
                item_id=f"{memo['memo_id']}:{j.sentence_index}:{i}", symbol=memo["symbol"], type=it["type"],
                description=it["description"], keywords=tuple(it.get("keywords") or ()),
                price_threshold=it.get("price_threshold"), category=j.category or "", memo_text=j.cleaned_text,
                company_name=company, time_hint=it.get("time_hint") or ""))
    return out


# ---------------------------------------------------------------- ②③④ 조건

def conditions(tcfg: dict, scfg: dict) -> dict[str, dict]:
    base = {**tcfg, "evidence_mode": "legacy", "extra_rules": [], "prediction_terms": []}
    new = {**tcfg, "evidence_mode": "all"}
    return {"baseline": {"news": "article", "same_event": False, "topic": base},
            "new": {"news": "chunks", "same_event": True, "topic": new, "same_event_cfg": scfg}}


def within(cands, until: date):
    return [c for c in cands if c.date <= until.isoformat()]


def outcome_row(item: TrackingItem, out, calls_before: int, client, seconds: float) -> dict:
    calls = client.calls[calls_before:] if client else []
    d, card = out.draft, out.card
    return {"item_id": item.item_id, "symbol": item.symbol, "type": item.type, "description": item.description,
            "category": item.category, "kind": out.kind, "fail_codes": out.fail_codes,
            "evidence": [{"eid": e.eid, "ref": e.candidate.ref, "kind": e.candidate.kind, "doc": e.candidate.doc,
                          "date": e.candidate.date, "similarity": round(e.candidate.similarity, 4), "title": e.candidate.title}
                         for e in out.evidence],
            "grouped": [{"ref": c.ref, "rcept_no": r, "title": c.title} for c, r in out.grouped],
            "llm_card": None if card is None else {"status": card.status, "title": card.title, "summary": card.summary,
                                                   "evidence": card.evidence, "confidence": card.confidence},
            "card": None if d is None else {"type": d.type, "origin": d.origin, "title": d.title, "summary": d.summary,
                                            "sources": [r for r, _ in d.sources], "supporting_news": d.supporting_news,
                                            "related_news": [r for r, _ in d.related_news]},
            "llm_calls": len(calls), "prompt_tokens": sum(r.prompt_tokens or 0 for r in calls),
            "output_tokens": sum(r.output_tokens or 0 for r in calls),
            "reasoning_tokens": sum(r.reasoning_tokens or 0 for r in calls), "seconds": round(seconds, 2)}


def summarize_condition(rows: list[dict]) -> dict:
    topic = [r for r in rows if r["type"] == "topic"]
    kinds = Counter(r["kind"] for r in rows)
    fails = Counter(code.split(":")[0] for r in rows for code in r["fail_codes"])
    ev = sorted(len(r["evidence"]) for r in topic)
    return {"items": len(rows), "topic_items": len(topic), "outcomes": dict(kinds),
            "cards": sum(1 for r in rows if r["card"]), "fail_codes": dict(fails),
            "evidence_per_item": {"median": ev[len(ev) // 2] if ev else None, "max": ev[-1] if ev else None,
                                  "zero": sum(1 for x in ev if x == 0)},
            "grouped_news": sum(len(r["grouped"]) for r in rows),
            "llm_calls": sum(r["llm_calls"] for r in rows), "prompt_tokens": sum(r["prompt_tokens"] for r in rows),
            "output_tokens": sum(r["output_tokens"] for r in rows),
            "reasoning_tokens": sum(r.get("reasoning_tokens", 0) for r in rows),
            "seconds": round(sum(r["seconds"] for r in rows), 1),
            "prediction_blocked": sum(1 for r in rows if "PREDICTION" in r["fail_codes"])}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="memos_kospi 메모 분석 → 카드 끝까지 평가 (DB 읽기 전용, 결과는 파일로만)")
    ap.add_argument("--memos", default=MEMOS_PATH)
    ap.add_argument("--config", default="configs/updates.yaml")
    ap.add_argument("--sample", type=int, default=100)
    ap.add_argument("--rich-min", type=int, default=5, help="기사 연결이 이 이상이면 '기사 충분' 종목")
    ap.add_argument("--rich-share", type=float, default=0.7)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--since", default="2026-11-01")
    ap.add_argument("--until", default="2026-11-09", help="이 날짜(포함)까지의 후보만")
    ap.add_argument("--conditions", default="baseline,new")
    ap.add_argument("--dry-sample", action="store_true", help="표본만 뽑아 파일로 쓰고 끝낸다 (LLM·GPU 없음)")
    ap.add_argument("--out-dir", help="결과 폴더 (기본: results/updates)")
    args = ap.parse_args(argv)

    import psycopg
    from zoneinfo import ZoneInfo

    from ..common.config import REPO_ROOT
    from ..common.db import get_read_dsn

    kst = ZoneInfo("Asia/Seoul")
    since_d, until_d = date.fromisoformat(args.since), date.fromisoformat(args.until)
    since_ts = datetime.combine(since_d, datetime.min.time(), kst)
    until_ts = datetime.combine(until_d + timedelta(days=1), datetime.min.time(), kst)
    run_dir = Path(args.out_dir or REPO_ROOT / "results/updates") / f"e2e_{datetime.now():%Y%m%d_%H%M%S}"
    run_dir.mkdir(parents=True, exist_ok=False)
    memos = load_memos(args.memos)
    with psycopg.connect(get_read_dsn()) as conn:
        conn.read_only = True
        if any(not m.get("symbol") for m in memos):
            no_symbol = fill_symbols(memos, stock_names(conn))
            print(f"symbol 채움: 메모 {len(memos)}개 중 종목을 못 찾은 메모 {no_symbol}개 (표본에서 빠짐)")
        counts = news_counts(conn, since_ts, until_ts)
    sample = sample_memos(memos, counts, args.sample, args.rich_min, args.rich_share, args.seed)
    rich_symbols = {s for s, n in counts.items() if n >= args.rich_min}
    with (run_dir / "sample.jsonl").open("w", encoding="utf-8") as f:
        for m in sample:
            f.write(json.dumps({"memo_id": m["memo_id"], "symbol": m["symbol"], "company": m["company_primary"],
                                "news_count": counts.get(m["symbol"], 0), "news_rich": m["symbol"] in rich_symbols,
                                "kind": m.get("kind"), "primary_type": m.get("primary_type")}, ensure_ascii=False) + "\n")
    print(f"표본 {len(sample)}개 (종목 {len({m['symbol'] for m in sample})}개, 기사 충분 {sum(m['symbol'] in rich_symbols for m in sample)}개)"
          f" → {run_dir / 'sample.jsonl'}")
    if args.dry_sample:
        return 0
    return run(args, sample, counts, rich_symbols, run_dir, since_d, until_d)


def run(args, sample, counts, rich_symbols, run_dir: Path, since_d: date, until_d: date) -> int:
    import psycopg

    from ..common.db import get_read_dsn
    from ..news.embedder import make_bge_m3_encoder
    from ..tracking.judge import judge_memo
    from ..tracking.lexicon import load_lexicon
    from ..tracking.llm import judge_with_llm
    from ..tracking.openai_client import OpenAIClient
    from .candidates import (company_terms, drop_news_without_company, news_company_lead, load_symbol_aliases,
                             recent_disclosure_candidates, recent_news_candidates, search_filters)
    from .experiment import PRICE_SQL
    from .models import TopicOutcome
    from .news_search import NewsChunkSearch, load_query_encoder, release_gpu
    from .price import check_price
    from .same_event import link_same_event
    from .topic import check_topic, thresholds

    cfg = load_config(args.config)
    lex = load_lexicon()
    banned = list(cfg["banned"])

    # ① 메모 분석 (메모당 LLM 1회)
    analyst = OpenAIClient.from_env()
    analyst.response_format = None                              # 문장 판정은 JSON 배열 응답
    memo_rows, items, analysis_rows = [], [], []
    t0 = time.perf_counter()
    for m in sample:
        text = m["memo_body"]
        before = len(analyst.calls)
        judged = judge_memo(text, m["symbol"], lex)
        judge_with_llm(judged, m["symbol"], m["company_primary"], analyst)
        calls = analyst.calls[before:]
        pairs = align(text, m["sentences"], judged, m.get("memo_body_clean"))
        for g, p in pairs:
            analysis_rows.append({"gold": g, "pred": None if p is None else p.to_dict()})
        its = items_from(m, judged, m["company_primary"])
        items += its
        memo_rows.append({"memo_id": m["memo_id"], "symbol": m["symbol"], "company": m["company_primary"],
                          "news_rich": m["symbol"] in rich_symbols, "text": text,
                          "sentences": [{"gold": g, "pred": None if p is None else
                                         {k: p.to_dict()[k] for k in ("sentence_index", "text", "decision", "category",
                                                                      "items", "merge_into", "judged_by", "confidence")}}
                                        for g, p in pairs],
                          "items": [it.item_id for it in its],
                          "llm_calls": len(calls), "prompt_tokens": sum(r.prompt_tokens or 0 for r in calls),
                          "output_tokens": sum(r.output_tokens or 0 for r in calls),
                          "reasoning_tokens": sum(r.reasoning_tokens or 0 for r in calls)})
    analysis = score_analysis(analysis_rows)
    analysis["seconds"] = round(time.perf_counter() - t0, 1)
    analysis["llm_calls"] = len(analyst.calls)
    analysis["prompt_tokens"] = sum(r.prompt_tokens or 0 for r in analyst.calls)
    analysis["output_tokens"] = sum(r.output_tokens or 0 for r in analyst.calls)
    analysis["reasoning_tokens"] = sum(r.reasoning_tokens or 0 for r in analyst.calls)
    with (run_dir / "memos.jsonl").open("w", encoding="utf-8") as f:
        for r in memo_rows:
            f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
    print("① 메모 분석:", json.dumps({k: v for k, v in analysis.items() if k != "confusion"}, ensure_ascii=False))

    # ②③④ 조건별
    topic_items = [it for it in items if it.type == "topic"]
    vectors = {}
    if topic_items:
        encode = make_bge_m3_encoder("dense")
        vectors = {it.item_id: d for it, (d, _) in zip(topic_items, encode([it.query_text for it in topic_items]))}
        del encode
    conds = conditions(cfg["topic"], cfg.get("same_event") or {})
    wanted = [c for c in args.conditions.split(",") if c]
    chunk_encoder = None
    if any(conds[c]["news"] == "chunks" for c in wanted) and topic_items:
        release_gpu()
        chunk_encoder = load_query_encoder()
    rcfg = cfg.get("recent", {})
    fetch_k = rcfg.get("fetch_k", 50)
    filters = search_filters(rcfg)
    news_lead = news_company_lead(filters)
    symbol_aliases = load_symbol_aliases() if news_lead is not None else {}
    card_client = OpenAIClient.from_env()
    results = {}
    with psycopg.connect(get_read_dsn()) as conn:
        conn.read_only = True
        searcher = NewsChunkSearch(conn, chunk_encoder, cfg["news"].get("chunks")) if chunk_encoder else None
        for name in wanted:
            spec = conds[name]
            tcfg = spec["topic"]
            floor, _ = thresholds(tcfg)
            rows = []
            for item in items:
                started, before = time.perf_counter(), len(card_client.calls)
                if item.type != "topic":
                    with conn.cursor() as cur:
                        cur.execute(PRICE_SQL, {"symbol": item.symbol})
                        prices = cur.fetchall()
                    draft = None
                    if prices:
                        (day, close), prev = prices[0], (float(prices[1][1]) if len(prices) > 1 else None)
                        draft = check_price(item, float(close), prev, str(day), cfg["price"]["near_pct"])
                    out = TopicOutcome("price_card" if draft else ("price_no_card" if prices else "price_no_data"),
                                       draft=draft)
                    rows.append(outcome_row(item, out, before, card_client, time.perf_counter() - started))
                    continue
                vec = vectors[item.item_id]
                if spec["news"] == "chunks":
                    news = searcher.recent(item.symbol, item.query_text, since_d, fetch_k, floor["news_chunks"],
                                           headline_vec=vec, headline_floor=floor["news"], variant=cfg["news"]["variant"])
                else:
                    news = recent_news_candidates(conn, item.symbol, vec, since_d, fetch_k, floor["news"],
                                                  cfg["news"]["variant"])
                if news_lead is not None:
                    news, _ = drop_news_without_company(
                        news, company_terms(item.company_name, item.symbol, rcfg, symbol_aliases),
                        news_lead)
                discs = recent_disclosure_candidates(conn, item.symbol, vec, since_d, fetch_k, floor["disclosure"],
                                                     floor["event"], rcfg.get("include_subsidiary", False), filters)
                cands = within(news + discs, until_d)
                links = {}
                if spec["same_event"]:
                    links = {ref: l.rcept_no for ref, l in link_same_event(conn, cands, spec["same_event_cfg"]).items()}
                out = check_topic(item, cands, card_client, banned, tcfg, links)
                rows.append(outcome_row(item, out, before, card_client, time.perf_counter() - started))
            conn.rollback()
            results[name] = rows
            with (run_dir / f"outcomes_{name}.jsonl").open("w", encoding="utf-8") as f:
                for r in rows:
                    f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
            print(f"{name}:", json.dumps(summarize_condition(rows), ensure_ascii=False))

    summary = {"sample": len(sample), "symbols": len({m["symbol"] for m in sample}),
               "news_rich_memos": sum(m["symbol"] in rich_symbols for m in sample), "since": str(since_d),
               "until": str(until_d), "analysis": analysis, "items": len(items), "topic_items": len(topic_items),
               "conditions": {n: {"spec": {k: v for k, v in conds[n].items() if k != "topic"}, **summarize_condition(r)}
                              for n, r in results.items()}}
    blocked = [{"condition": n, **{k: r[k] for k in ("item_id", "description", "llm_card", "evidence", "fail_codes")}}
               for n, rows in results.items() for r in rows if "PREDICTION" in r["fail_codes"]]
    (run_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    with (run_dir / "prediction_blocked.jsonl").open("w", encoding="utf-8") as f:
        for b in blocked:
            f.write(json.dumps(b, ensure_ascii=False, default=str) + "\n")
    print(f"결과 폴더: {run_dir} (sample, memos, outcomes_<조건>, prediction_blocked, summary) — DB에는 아무것도 쓰지 않았습니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
