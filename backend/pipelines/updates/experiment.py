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
    # 3) 뉴스를 원문 청크로 검색 (news_search). min_similarity_news_chunks 보정 전에는 --uncalibrated-chunks로만 (시험 비교)
    PYTHONPATH=backend python -m pipelines.updates.experiment --llm none --news-search chunks --uncalibrated-chunks
    # 4) 같은 사건 묶기 (same_event): 공시와 같은 사건 기사를 근거에서 빼고 공시 카드의 보조 기사로 (기본 꺼짐)
    PYTHONPATH=backend python -m pipelines.updates.experiment --llm none --news-search chunks --uncalibrated-chunks --same-event
"""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

from ..common.config import load_config, resolve_path
from .candidates import (FRESH_PUBLISHED_DAYS, company_terms, drop_news_without_company, news_company_lead, drop_other_company_news, listed_names,
                         load_symbol_aliases, recent_disclosure_candidates, recent_news_candidates, search_filters)
from .models import TrackingItem
from .preview import write_preview
from .results import new_run_dir, write_candidates_csv, write_results
from .evidence import threshold_key
from .news_search import check_mode, release_gpu
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
                    memo_text=sent.get("cleaned_text") or sent["text"], time_hint=it.get("time_hint") or ""))
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
    for c, rcept in out.grouped:
        rows.append(f"- 같은 사건으로 묶어 근거에서 뺀 기사 (공시 {rcept}): {c.date} {c.source} {c.title}")
    for note in out.verify_notes:
        rows.append(f"- 검수가 막은 문장: {note}")
    if out.card and out.card.status == "update":
        rows.append(f"- LLM 카드: {out.card.title} / {' '.join(out.card.summary)} / {out.card.reason} (확신 {out.card.confidence})")
    if out.draft:
        rows.append(f"- 최종({out.draft.origin}): {out.draft.title} / {out.draft.summary}")
        for _, title in out.draft.related_news:
            rows.append(f"  - 관련 기사: {title}")
        for s in out.draft.supporting_news:
            rows.append(f"  - 같은 사건 기사: {s['date']} {s['source']} {s['title']}")
    return rows


def _outcome(item, out) -> dict:
    ev = [{"eid": e.eid, "ref": e.candidate.ref, "kind": e.candidate.kind, "doc": e.candidate.doc, "date": e.candidate.date,
           "similarity": round(e.candidate.similarity, 4), "title": e.candidate.title} for e in out.evidence]
    d = out.draft
    return {"item_id": item.item_id, "symbol": item.symbol, "description": item.description, "kind": out.kind,
            "fail_codes": out.fail_codes, "evidence": ev,
            "grouped": [{"ref": c.ref, "rcept_no": r, "title": c.title} for c, r in out.grouped],
            "card": None if d is None else {"type": d.type, "origin": d.origin, "title": d.title, "summary": d.summary,
                                            "sources": [r for r, _ in d.sources], "supporting_news": d.supporting_news,
                                            "related_news": [r for r, _ in d.related_news]}}


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
    ap.add_argument("--news-search", choices=["article", "chunks"], help="뉴스 검색 방식 (기본: 설정 news.search, 없으면 article)")
    ap.add_argument("--same-event", action=argparse.BooleanOptionalAction, default=None,
                    help="같은 사건 묶기를 켜거나(--same-event) 끈다(--no-same-event). 기본: 설정 same_event.enabled (없으면 꺼짐)")
    ap.add_argument("--evidence-mode", choices=["legacy", "all"], help="근거 고르기 (기본: 설정 topic.evidence_mode)")
    ap.add_argument("--uncalibrated-chunks", action="store_true",
                    help="min_similarity_news_chunks가 없어도 chunks로 돈다 (기존 뉴스 임계값을 임시로 씀, 시험 비교용)")
    ap.add_argument("--used-refs", help="이미 카드에 쓴 근거 기록 파일 (used_refs.FileUsedRefStore). 주면 그 근거를 후보에서 빼고, "
                                        "이번 카드가 쓴 근거를 더해 적는다. 기본: 쓰지 않음")
    ap.add_argument("--used-refs-match", choices=["ref", "doc"], default="ref",
                    help="ref: 같은 ref만 뺀다 (기본) · doc: 같은 공시의 다른 청크도 뺀다")
    ap.add_argument("--item-state", help="항목 상태 파일 (item_state.FileItemStateStore). 주면 항목별 마지막 확인 시각·응답 유형을 적는다")
    args = ap.parse_args(argv)

    import psycopg

    from ..common.db import get_read_dsn
    from ..news.embedder import make_bge_m3_encoder
    from ..tracking.openai_client import OpenAIClient

    cfg = load_config(args.config)
    tcfg = cfg["topic"]
    if args.evidence_mode:
        tcfg = {**tcfg, "evidence_mode": args.evidence_mode}
    news_mode = args.news_search or cfg["news"].get("search", "article")
    check_mode(news_mode, tcfg, args.uncalibrated_chunks)
    scfg = cfg.get("same_event") or {}
    same_event_on = scfg.get("enabled", False) if args.same_event is None else args.same_event
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
    filters = search_filters(rcfg)
    news_lead = news_company_lead(filters)
    symbol_aliases = load_symbol_aliases() if news_lead is not None else {}
    floor, strong = thresholds(tcfg)
    used_store = None
    if args.used_refs:
        from .used_refs import FileUsedRefStore
        used_store = FileUsedRefStore(resolve_path(args.used_refs))
    used_skipped = 0                                            # 이미 카드에 쓴 근거라 뺀 후보 수 (항목·후보 쌍)
    from .response import item_response, source_data
    from .results import draft_to_dict
    state_store = None
    if args.item_state:
        from .item_state import FileItemStateStore
        state_store = FileItemStateStore(resolve_path(args.item_state))
    responses = []                                              # 항목별 응답 유형 (responses.jsonl, response.py)
    has_data: dict[str, bool] = {}                              # 종목별 조회 기간 뉴스·공시 유무 (no_data b)

    vectors = {}
    if topic_items:
        encode = make_bge_m3_encoder("dense")
        vectors = {it.item_id: d for it, (d, _) in zip(topic_items, encode([it.query_text for it in topic_items]))}
        del encode
    chunk_encoder = None
    if news_mode == "chunks" and topic_items:
        from .news_search import load_query_encoder
        release_gpu()                                            # 제목+요약 인코더를 내린 뒤 원문 청크용 인코더를 올린다 (GPU 메모리)
        chunk_encoder = load_query_encoder()
    client = None
    if args.llm == "openai":
        if args.response_schema:
            from .openai_schema import SchemaOpenAIClient
            client = SchemaOpenAIClient.from_env()
        else:
            client = OpenAIClient.from_env()

    names: dict[str, str] = {}
    sims: list[float] = []
    kind_sims: dict[str, list[float]] = {"news": [], "news_chunks": [], "disclosure": [], "event": []}   # disclosure=정기보고서, event=수시공시
    cand_rows = []
    other_news = []                                             # 다른 회사 이름으로 시작해 뺀 기사 (항목, 후보)
    no_company_news = []                                        # 제목·앞부분에 종목명이 없어 뺀 기사 (recent.filters.news_require_company)
    status_count: dict[str, int] = {}
    fail_count: dict[str, int] = {}
    drafts = []
    outcomes = []                                               # 항목별 근거·결과 (outcomes.jsonl, 방식끼리 나란히 비교할 때)
    empties = []                                                # 카드가 없는 항목 (미리보기의 '근거 없음' 목록)
    sections = []
    with psycopg.connect(get_read_dsn()) as conn:
        conn.read_only = True                                   # 이 연결은 쓰기를 시도하면 DB가 거부한다
        from .preferred import load_map, source_symbol
        pref_map = load_map(conn)                               # 우선주 → 보통주 (공시·뉴스는 보통주로 조회, 가격은 우선주 그대로)
        with conn.cursor() as cur:
            wanted_syms = {i.symbol for i in items} | {source_symbol(i.symbol, pref_map) for i in items}
            cur.execute("SELECT symbol, name FROM stocks WHERE symbol = ANY(%(s)s)", {"s": sorted(wanted_syms)})
            names = {sym.strip(): name for sym, name in cur.fetchall()}
            cur.execute("SELECT name FROM stocks")
            stock_names = [n for (n,) in cur.fetchall() if n]     # 다른 회사 기사 제목을 알아보는 데 쓴다
        # 코스닥 회사(파트론 등)는 stocks에 없어 DART 회사 목록 파일에서 이름을 더한다. 파일이 없으면 stocks 이름만 쓴다
        file_names = (listed_names(resolve_path(rcfg["company_names_file"]))
                      if rcfg.get("drop_other_company_news", True) and rcfg.get("company_names_file") else [])
        all_names = sorted(set(stock_names) | set(file_names))
        aliases = rcfg.get("company_aliases") or {}
        items = [replace(i, company_name=names.get(i.symbol, "")) for i in items]
        searcher = None
        if chunk_encoder is not None:
            from .news_search import NewsChunkSearch
            searcher = NewsChunkSearch(conn, chunk_encoder, cfg["news"].get("chunks"))
        from datetime import datetime

        from .candidates import drop_not_ready, fresh_window
        from .item_state import last_checked
        from .price import market_dates, price_outcome
        from .response import now_iso
        dates = market_dates(conn)                              # 오래된 종가 판단용 시장 거래일 (stale_price)
        fresh_items, not_ready = 0, 0                           # 새 자료만 받은 항목 수, 마지막 확인 전에 이미 검색 가능했던 후보 수
        for item in items:
            checked = now_iso()                                 # 확인 시각 = 이 항목을 검색하기 시작한 때 (검색 중 들어온 자료를 놓치지 않게)
            if item.type == "topic":
                vec = vectors[item.item_id]
                src = source_symbol(item.symbol, pref_map)      # 우선주면 보통주로 공시·뉴스를 찾는다
                src_name = names.get(src, item.company_name)
                # 새 자료만 받기 (2026-11-10, 수집 시각 기준): 마지막 확인 이후 검색 가능해진 자료 중 발행 3일 안.
                # 첫 확인(기록 없음)은 조회 기간 전체.
                fresh = last_checked(state_store, item.item_id)
                fresh_items += fresh is not None
                n_since, d_from = fresh_window(fresh, datetime.fromisoformat(checked), since)
                news = (searcher.recent(src, item.query_text, n_since, fetch_k, floor["news_chunks"], headline_vec=vec,
                                        headline_floor=floor["news"], variant=cfg["news"]["variant"]) if searcher else
                        recent_news_candidates(conn, src, vec, n_since, fetch_k, floor["news"], cfg["news"]["variant"]))
                if news_lead is not None:
                    news, dropped = drop_news_without_company(
                        news, company_terms(src_name, src, rcfg, symbol_aliases),
                        news_lead)
                    no_company_news += [(item, c) for c in dropped]
                cands = (news + recent_disclosure_candidates(conn, src, vec, d_from or d_since, fetch_k, floor["disclosure"],
                                                        floor["event"], rcfg.get("include_subsidiary", False), filters,
                                                        fresh_since=fresh, pub_since=d_from))
                if fresh is not None:
                    cands, late = drop_not_ready(conn, cands, fresh, cfg["news"]["variant"])
                    not_ready += len(late)
                if rcfg.get("drop_other_company_news", True):
                    cands, dropped = drop_other_company_news(cands, src_name, all_names,
                                                             aliases.get(src_name, []))
                    other_news += [(item, c) for c in dropped]
                sims += [c.similarity for c in cands]
                for c in cands:
                    kind_sims[threshold_key(c)].append(c.similarity)
                    cand_rows.append((item, c))
                if used_store is not None:                      # candidates.csv(보정용)에는 남기고 카드 근거에서만 뺀다
                    from .used_refs import drop_used
                    cands, skipped = drop_used(cands, used_store.used(item.item_id), args.used_refs_match)
                    used_skipped += len(skipped)
                links = {}
                if same_event_on:
                    from .same_event import link_same_event
                    links = {ref: link.rcept_no for ref, link in link_same_event(conn, cands, scfg).items()}
                out = check_topic(item, cands, client, banned, tcfg, links)
                if used_store is not None:
                    from .used_refs import card_refs
                    used_store.record(item.item_id, card_refs(out.draft))
                if src not in has_data:
                    has_data[src] = any(source_data(conn, src, since, date.today(), d_since).values())
                responses.append(item_response(item, out.kind, out.fail_codes,
                                               draft_to_dict(out.draft) if out.draft else None, has_data[src],
                                               checked_at=checked))
                outcomes.append({**_outcome(item, out), "fresh_since": fresh.isoformat() if fresh is not None else None})
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
                    responses.append(item_response(item, "price_no_data", [], None, None, checked_at=checked))
                    empties.append(_empty(item, "price_no_data"))
                    sections += ["결과: **price_no_data** (prices_daily에 종가 없음)", ""]
                    continue
                pkind, draft, pinfo = price_outcome(item, rows, dates, cfg["price"]["near_pct"])
                key = f"price_{draft.price_state}" if draft else pkind
                status_count[key] = status_count.get(key, 0) + 1
                responses.append(item_response(item, pkind, [], draft_to_dict(draft) if draft else None, None, checked_at=checked))
                if draft:
                    drafts.append(draft)
                else:
                    empties.append(_empty(item, pkind))
                if pkind == "price_stale":
                    sections += [f"결과: **price_stale** (마지막 종가 {pinfo['trade_date']}, 시장 최근 거래일 "
                                 f"{pinfo['market_latest']}보다 {pinfo['lag_trading_days']}거래일 오래됨 → 가격 카드 안 만듦)", ""]
                    continue
                sections += [f"기준일 {pinfo['trade_date']} 종가 {pinfo['close']:,.0f}원 → "
                             + (f"**{draft.title}** / {draft.summary}" if draft else "**카드 없음**"), ""]

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
    news_search = {"mode": news_mode}
    if news_mode == "chunks":
        ms = searcher.timings_ms if searcher else []
        news_search.update(uncalibrated="min_similarity_news_chunks" not in tcfg, chunks=cfg["news"].get("chunks"),
                           ms_per_item=round(sum(ms) / len(ms)) if ms else None, ms_max=round(max(ms)) if ms else None)
    summary["search"] = {"mode": "recent_first", "news_search": news_search,
                         "same_event": {"enabled": bool(same_event_on), **({**scfg, "enabled": True} if same_event_on else {})}, "news_since": str(since), "disclosure_since": str(d_since),
                         "floor": floor, "strong": strong, "stop_window_days": tcfg.get("stop_window_days", 0),
                         "include_subsidiary": rcfg.get("include_subsidiary", False), "config": args.config}
    head = ["# AI 업데이트 후보 검색·카드 생성 실험", f"- 항목 {len(items)}개 (주제 {len(topic_items)}), 후보 {len(sims)}건, 뉴스 시작일 {since}, LLM {args.llm}",
            f"- 검색: 최신순 하향식 (설정 {args.config}) · 공시 시작일 {d_since} · 최소 유사도 {floor} · 강한 후보(멈춤 기준) {strong}"
            f" · 멈춘 날부터 {tcfg.get('stop_window_days', 0)}일 전까지 포함 · 자회사 공시 {'포함' if rcfg.get('include_subsidiary') else '제외'}",
            f"- 뉴스 검색: {json.dumps(news_search, ensure_ascii=False)}"
            + (" · **원문 청크 임계값 보정 전 (min_similarity_news 값을 임시로 씀)**" if news_search.get("uncalibrated") else ""),
            f"- 근거 고르기: {tcfg.get('evidence_mode', 'legacy')}"
            + (f" (공시 {tcfg.get('max_disclosure_docs', 5)}건·공시당 청크 {tcfg.get('max_chunks_per_disclosure', 2)}개, 전체 {tcfg.get('max_total', 15)})"
               if tcfg.get("evidence_mode") == "all" else "")
            + f" · 예측 검사 {'켬' if tcfg.get('prediction_terms') else '꺼짐'} · 추가 규칙 {len(tcfg.get('extra_rules') or [])}줄",
            f"- 같은 사건 묶기: {'켬 ' + json.dumps({**scfg, 'enabled': True}, ensure_ascii=False) if same_event_on else '꺼짐'}",
            f"- 유사도 분포: 최소 {q(0)} / 25% {q(.25)} / 중앙 {q(.5)} / 75% {q(.75)} / 최대 {q(1)}",
            *[f"  - {k}: {json.dumps(dist(v), ensure_ascii=False)}" for k, v in kind_sims.items()],
            f"- 처리 결과: {json.dumps(status_count, ensure_ascii=False)}",
            f"- 코드 검사 실패 코드(LLM 원본 기준): {json.dumps(fail_count, ensure_ascii=False)}",
            f"- 다른 회사 이름으로 시작해 뺀 기사: {len(other_news)}건 (항목·기사 쌍, 목록은 보고서 맨 끝)"
            + (f" · 회사 이름 {len(all_names)}개 (stocks {len(stock_names)}, 파일 {len(file_names)})"
               if rcfg.get("drop_other_company_news", True) else " · 꺼짐")]
    summary["other_company_news"] = len(other_news)
    summary["search_filters"] = filters
    summary["no_company_news"] = len(no_company_news)
    summary["fresh_items"], summary["fresh_not_ready"] = fresh_items, not_ready
    if state_store is not None:
        head.append(f"- 새 자료만 받기(마지막 확인 이후 검색 가능해진 자료, 발행 {FRESH_PUBLISHED_DAYS}일 안): 주제 항목 {fresh_items}개"
                    f" · 확인 전에 이미 있던 후보라 뺀 것 {not_ready}건 · 나머지 항목은 첫 확인이라 조회 기간 전체")
    summary["preferred_items"] = sorted({i.item_id for i in items if i.symbol in pref_map})
    summary["used_refs"] = None if used_store is None else {"file": str(used_store.path), "match": args.used_refs_match,
                                                            "skipped": used_skipped}
    from .response import summarize, to_dict
    summary["responses"] = summarize(responses)
    head.append(f"- 응답 유형: {json.dumps(summary['responses']['by_type'], ensure_ascii=False)}"
                f" · 사용자 표시 {summary['responses']['user_visible']}건"
                f" · 이유별: {json.dumps(summary['responses']['reasons'], ensure_ascii=False)}")
    if state_store is not None:
        for r in responses:
            state_store.record(r)
    if used_store is not None:
        head.append(f"- 이미 카드에 쓴 근거 빼기: {used_skipped}건 (파일 {used_store.path}, 기준 {args.used_refs_match})")
    head.append(f"- 후보 거르기(recent.filters): {json.dumps(filters, ensure_ascii=False)}"
                f" · 종목명 없어 뺀 기사 {len(no_company_news)}건 (항목·기사 쌍)")
    titles: dict[str, list[str]] = {}
    for item, c in other_news:
        titles.setdefault(f"{c.date} {c.title}", []).append(item.item_id)
    sections += ["## 다른 회사 이름으로 시작해 뺀 기사", *[f"- {t} ← {', '.join(ids)}" for t, ids in titles.items()], ""]
    if client and client.calls:
        from ..tracking.openai_client import usage_totals

        u = usage_totals(client.calls)
        head.append(f"- LLM 호출 {u['llm_calls']}회, 입력 토큰 {u['prompt_tokens']}, 출력 토큰 {u['output_tokens']}"
                    f" (그중 추론 {u['reasoning_tokens']}) · 모델 {client.model}"
                    + (f" · 추론 강도 {client.reasoning_effort}" if client.reasoning_effort else ""))
        summary.update(u)
        summary["model"], summary["reasoning_effort"] = client.model, client.reasoning_effort
    run_dir = new_run_dir(args.out_dir)
    write_results(run_dir, drafts, "\n".join(head + [""] + sections) + "\n", summary)
    csv_path = write_candidates_csv(run_dir, cand_rows)
    with (run_dir / "outcomes.jsonl").open("w", encoding="utf-8") as f:
        for o in outcomes:
            f.write(json.dumps(o, ensure_ascii=False, default=str) + "\n")
    with (run_dir / "responses.jsonl").open("w", encoding="utf-8") as f:
        for r in responses:
            f.write(json.dumps(to_dict(r), ensure_ascii=False, default=str) + "\n")
    preview_path = write_preview(run_dir, drafts, cand_rows, empties, f"{run_dir.name} · LLM {args.llm}")
    print("\n".join(head))
    print(f"결과 폴더: {run_dir}  (cards.jsonl, report.md, summary.json, candidates.csv, outcomes.jsonl) — DB에는 아무것도 쓰지 않았습니다.")
    print(f"미리보기(사용자 화면처럼): {preview_path}")
    print(f"임계값 정하기: {csv_path} 의 마지막 열 '관련(O/X)'을 채운 뒤 python -m pipelines.updates.calibrate --labels {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())