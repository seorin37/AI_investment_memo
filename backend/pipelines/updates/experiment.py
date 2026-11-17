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
    # 3) 뉴스 검색 방식 (기본 설정 news.search: chunks, 2026-11-10). 기존 방식은 --news-search article.
    #    min_similarity_news_chunks 보정 전에는 min_similarity_news 값을 임시로 쓰고 경고·summary(uncalibrated)에 남긴다
    PYTHONPATH=backend python -m pipelines.updates.experiment --llm none --news-search article
    # 4) 같은 사건 묶기 (same_event): 공시와 같은 사건 기사를 근거에서 빼고 공시 카드의 보조 기사로 (기본 꺼짐)
    PYTHONPATH=backend python -m pipelines.updates.experiment --llm none --news-search chunks --same-event
"""

from __future__ import annotations

import argparse
import json
import sys
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


def _cited(checks: list[dict]) -> set[str]:
    """검사 기록의 카드들이 쓴 근거 번호 (facts의 evidence_id와 sources)."""
    out = set()
    for row in checks:
        card = row.get("card") or {}
        out |= {f.get("evidence_id") for f in card.get("facts") or []} | set(card.get("sources") or [])
    return out - {"", None}


def _outcome(item, out) -> dict:
    """outcomes.jsonl 한 줄. checks(검사 기록: 카드 JSON·걸린 코드)가 있으면 함께 쓰고, 그 카드들이 쓴 근거에는
    검사에 쓴 원문 shown_text를 붙인다 (검사 대상 글 = title + shown_text + date, checks._ev_text). 2026-11-17."""
    checks = getattr(out, "checks", None) or []
    cited = _cited(checks)
    ev = [{"eid": e.eid, "ref": e.candidate.ref, "kind": e.candidate.kind, "doc": e.candidate.doc, "date": e.candidate.date,
           "similarity": round(e.candidate.similarity, 4), "title": e.candidate.title,
           **({"shown_text": e.shown_text} if e.eid in cited else {})} for e in out.evidence]
    d = out.draft
    return {"item_id": item.item_id, "symbol": item.symbol, "description": item.description, "kind": out.kind,
            "fail_codes": out.fail_codes, "evidence": ev, **({"checks": checks} if checks else {}),
            "grouped": [{"ref": c.ref, "rcept_no": r, "title": c.title} for c, r in out.grouped],
            "card": None if d is None else {"type": d.type, "origin": d.origin, "title": d.title, "summary": d.summary,
                                            "explanation": d.explanation, "memo_link": d.reason, "when": d.when,
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
    ap.add_argument("--store", choices=["file", "db"],
                    help="카드·이미 쓴 근거·마지막 확인 시각 저장 (기본: 설정 updates.store, 없으면 file). db: 기존 테이블에 쓴다 "
                         "(db_store.py). 항목도 DB(tracking_items)에서 읽는다. 쓰기 대상은 환경변수 TEST_DATABASE_URL의 "
                         "로컬 테스트 DB(127.0.0.1:5433, 이름에 test)만 허용")
    ap.add_argument("--allow-shared-write", action="store_true",
                    help="--store db에서 공용 DB(db_store.SHARED_TARGETS)에 쓰기를 허용한다. 없으면 로컬 테스트 DB만. "
                         "--symbols로 범위를 좁힐 수 있다 (ALL이면 전체 활성 항목)")
    ap.add_argument("--max-usd", type=float,
                    help="이번 실행 LLM 비용 상한. 넘으면 남은 항목은 건너뛴다(확인 시각 그대로 → 다음 실행에서 처리). 매일 실행기가 준다")
    ap.add_argument("--job", default="experiment", help="usage_log의 작업 이름 (매일 실행기는 daily, 하루 한도는 daily만 센다)")
    ap.add_argument("--no-cards", action="store_true",
                    help="--llm openai여도 카드 생성은 부르지 않는다 (후보 검색·관련성 판정까지만, 검수 표본용)")
    ap.add_argument("--relevance", action=argparse.BooleanOptionalAction, default=None,
                    help="뉴스 후보 관련성 판정을 켜거나(--relevance) 끈다(--no-relevance). 기본: 설정 relevance.enabled (기본 켬). "
                         "LLM을 부를 때만 돈다")
    ap.add_argument("--card-schema", choices=["v1", "v2"],
                    help="카드 모양 (기본: 설정 topic.card_schema, 없으면 v1). v2: 사건 하나·문장마다 근거·직전 같은 기간 비교 근거")
    ap.add_argument("--uncalibrated-chunks", action="store_true",   # 2026-11-10부터 없어도 돈다 (경고만). 예전 명령 호환
                    help="min_similarity_news_chunks가 없어도 chunks로 돈다 (기존 뉴스 임계값을 임시로 씀, 시험 비교용)")
    ap.add_argument("--used-refs", help="이미 카드에 쓴 근거 기록 파일 (used_refs.FileUsedRefStore). 주면 그 근거를 후보에서 빼고, "
                                        "이번 카드가 쓴 근거를 더해 적는다. 기본: 쓰지 않음")
    ap.add_argument("--used-refs-match", choices=["ref", "doc"], default="ref",
                    help="ref: 같은 ref만 뺀다 (기본) · doc: 같은 공시의 다른 청크도 뺀다")
    ap.add_argument("--item-ids", help="이 tracking_items id(쉼표 구분)만 처리한다. --store db: 다른 항목의 확인 시각·카드를 건드리지 않는다. "
                                       "--store file: 공용 DB에서 그 활성 항목을 읽기만 하고(첫 확인으로) 결과는 파일로")
    ap.add_argument("--save-llm-io", action="store_true", help="LLM 프롬프트·응답 원문을 실행 폴더 llm_io.jsonl에 남긴다")
    ap.add_argument("--item-state",help="항목 상태 파일 (item_state.FileItemStateStore). 주면 항목별 마지막 확인 시각·응답 유형을 적는다")
    args = ap.parse_args(argv)

    import psycopg

    from ..common.db import get_read_dsn
    from ..news.embedder import make_bge_m3_encoder
    from ..tracking.openai_client import OpenAIClient

    cfg = load_config(args.config)
    tcfg = cfg["topic"]
    if args.evidence_mode:
        tcfg = {**tcfg, "evidence_mode": args.evidence_mode}
    if args.card_schema:
        tcfg = {**tcfg, "card_schema": args.card_schema}
    card_schema = tcfg.get("card_schema", "v1")
    news_since_db = None                                        # 자료 범위: DB의 가장 오래된 뉴스 발행일 (v2 카드 coverage, 연결 뒤 채운다)
    news_mode = args.news_search or cfg["news"].get("search", "article")
    if check_mode(news_mode, tcfg, args.uncalibrated_chunks):
        print("경고: news.search=chunks인데 topic.min_similarity_news_chunks가 없어 min_similarity_news 값을 임시로 씁니다 "
              "(calibrate·noise_floor로 보정 전)", file=sys.stderr)
    scfg = cfg.get("same_event") or {}
    same_event_on = scfg.get("enabled", False) if args.same_event is None else args.same_event
    banned = list(cfg["banned"])
    store_kind = args.store or (cfg.get("store") or "file")
    if args.allow_shared_write and store_kind != "db":
        raise SystemExit("--allow-shared-write는 --store db와 함께만 씁니다")
    wconn = None
    shared = False
    from datetime import datetime as _dt
    run_started = _dt.now()
    run_id = f"run_{run_started:%Y%m%d_%H%M%S}"                 # 실행 폴더 이름과 같다 (DB 행의 details.run_id)
    if store_kind == "db":
        import os

        import psycopg as _pg

        from .db_store import check_test_target, load_items as db_items, shared_write_dsn
        shared = args.allow_shared_write
        dsn = shared_write_dsn() if shared else os.environ.get("TEST_DATABASE_URL", "")
        if not dsn:
            raise SystemExit("--store db: 환경변수 TEST_DATABASE_URL(로컬 테스트 DB)이 없습니다")
        store_target = check_test_target(dsn, shared)            # 허용한 DB가 아니면 여기서 멈춘다
        print(f"DB 저장 대상: {store_target}" + (" (공용 DB 쓰기 허용)" if shared else ""))
        wconn = _pg.connect(dsn)
        items = db_items(wconn, None if args.symbols.upper() == "ALL" else tuple(args.symbols.split(",")))
        if args.item_ids:                                       # 이 항목만 (다른 사용자 항목의 확인 시각·카드를 건드리지 않게)
            keep = {s.strip() for s in args.item_ids.split(",") if s.strip()}
            items = [i for i in items if i.item_id in keep]
        from .db_store import item_memos
        memo_by_item = item_memos(wconn, [i.item_id for i in items])
    elif args.item_ids:                                         # 파일 저장 + DB 항목 (읽기 전용, 확인 시각 없이 = 첫 확인으로)
        from .db_store import load_items as db_items
        keep = {s.strip() for s in args.item_ids.split(",") if s.strip()}
        with psycopg.connect(get_read_dsn()) as rconn:
            rconn.read_only = True
            items = [i for i in db_items(rconn, tuple(args.symbols.split(","))) if i.item_id in keep]
            rconn.rollback()
    else:
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
    writer = None
    if wconn is not None:                                       # DB 저장: 이미 쓴 근거 = update_sources, 마지막 확인 = tracking_items
        from .db_store import DbCardWriter, DbItemStateStore, DbUsedRefStore
        writer = DbCardWriter(wconn, run_id, allow_shared=shared)
        used_store = DbUsedRefStore(wconn)
    elif args.used_refs:
        from .used_refs import FileUsedRefStore
        used_store = FileUsedRefStore(resolve_path(args.used_refs))
    used_skipped = 0                                            # 이미 카드에 쓴 근거라 뺀 후보 수 (항목·후보 쌍)
    from .response import item_response, source_data
    from .results import draft_to_dict
    state_store = None
    if wconn is not None:
        state_store = DbItemStateStore(wconn, writer.manifest, allow_shared=shared)
    elif args.item_state:
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
            from .openai_schema import SchemaOpenAIClient, response_format
            client = SchemaOpenAIClient.from_env()
            if card_schema == "v2":                              # 검수 호출도 이 형식을 받게 되므로 v2 + 스키마 모드는 미검증
                from .judge import RESPONSE_SCHEMA_V2
                client.response_format = response_format(RESPONSE_SCHEMA_V2, "update_card_v2")
        else:
            client = OpenAIClient.from_env()
    from .usage import UsageTracker
    tracker = UsageTracker(keep_io=args.save_llm_io)            # LLM 호출을 항목·단계별로 센다 (usage_by_item.csv, usage_log.jsonl)
    rel_cfg = None
    rel_client = None
    if client is not None:
        from .relevance import config as relevance_config
        rel_cfg = relevance_config(cfg.get("relevance"))
        if args.relevance is not None:
            rel_cfg["enabled"] = args.relevance
        if not rel_cfg["enabled"]:
            rel_cfg = None
        else:
            from .autolabel import load_prompt
            rel_prompt = load_prompt(rel_cfg["prompt"])
            # 실험(2026-11-17): 한 번 답하기(ask) 질문은 "질문에 답이 되는 자료인가"로 판정 (configs/ask_relevance_prompt.md)
            rel_prompt_ask = load_prompt(rel_cfg["prompt_ask"]) if rel_cfg.get("prompt_ask") else None
            rel_client = client
            if args.response_schema or (rel_cfg.get("model") and rel_cfg["model"] != client.model):
                rel_client = OpenAIClient.from_env()            # 카드 응답 형식을 강제하지 않는 판정용 클라이언트
                if rel_cfg.get("model"):
                    rel_client.model = rel_cfg["model"]
    relevance_rows: dict[tuple[str, str], tuple[str, str, str]] = {}   # (항목, ref) → (O/X, 이유 코드, 범위): candidates.csv
    verify_client = None                                        # topic.verify_model이 있을 때 처음 쓸 때 만든다 (실험 2026-11-17)
    relevance_items: list[dict] = []

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
    # DB 저장이면 검색도 같은 테스트 DB에서 한다 (update_sources·tracking_matches가 그 DB의 기사·공시를 참조한다)
    # 테스트 DB 저장이면 검색도 같은 테스트 DB에서 (update_sources·tracking_matches가 그 DB의 기사·공시를 참조). 공용 DB는 읽기 계정으로
    with psycopg.connect(os.environ["TEST_DATABASE_URL"] if wconn is not None and not shared else get_read_dsn()) as conn:
        conn.read_only = True                                   # 이 연결은 쓰기를 시도하면 DB가 거부한다
        from .preferred import load_map, source_symbol
        pref_map = load_map(conn)                               # 우선주 → 보통주 (공시·뉴스는 보통주로 조회, 가격은 우선주 그대로)
        if card_schema == "v2":
            from .candidates import news_coverage
            news_since_db = news_coverage(conn)
            tcfg = {**tcfg, "coverage": {"news_since": news_since_db}}
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
        dsearch = None                                          # 공시 하이브리드 검색 (실험, disclosure.search: hybrid, 기본 dense)
        if chunk_encoder is not None and (cfg.get("disclosure") or {}).get("search") == "hybrid":
            from .disclosure_search import DisclosureHybridSearch
            dsearch = DisclosureHybridSearch(conn, chunk_encoder, (cfg.get("disclosure") or {}).get("hybrid"))
        from datetime import datetime

        from .candidates import drop_not_ready, fresh_window
        from .item_state import last_checked
        from .price import market_dates, price_outcome
        from .response import now_iso
        dates = market_dates(conn)                              # 오래된 종가 판단용 시장 거래일 (stale_price)
        fresh_items, not_ready, late_chunks, fresh_news = 0, 0, 0, 0                           # 새 자료만 받은 항목 수, 마지막 확인 전에 이미 검색 가능했던 후보 수
        budget_stopped, skipped_items = False, 0
        for item in items:
            if args.max_usd is not None and tracker.usd() >= args.max_usd:   # 비용 상한: 항목 단위로 멈춘다
                budget_stopped = True
                skipped_items += 1
                continue
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
                if dsearch is not None and fresh is None:       # 하이브리드는 첫 확인(조회 기간 전체)에만. 새 자료만 받기는 기존 함수
                    from .disclosure_search import section_hints
                    discs = dsearch.recent(src, item.query_text, d_from or d_since, filters=filters,
                                           include_subsidiary=rcfg.get("include_subsidiary", False),
                                           hints=section_hints(item.memo_text) if item.category == "ask" else None)
                else:
                    discs = recent_disclosure_candidates(conn, src, vec, d_from or d_since, fetch_k, floor["disclosure"],
                                                         floor["event"], rcfg.get("include_subsidiary", False), filters,
                                                         fresh_since=fresh, pub_since=d_from)
                cands = news + discs
                if fresh is not None:
                    cands, late, late_chunk = drop_not_ready(
                        conn, cands, fresh, cfg["news"]["variant"], late_chunk_since=n_since,
                        used=used_store.used(item.item_id) if used_store is not None else None)
                    not_ready += len(late)
                    late_chunks += len(late_chunk)
                if rcfg.get("drop_other_company_news", True):
                    cands, dropped = drop_other_company_news(cands, src_name, all_names,
                                                             aliases.get(src_name, []))
                    other_news += [(item, c) for c in dropped]
                if fresh is not None:                           # 새 자료로 잡힌 뉴스 후보 (회사 이름 거르기 뒤, 쓴 근거 빼기 전)
                    fresh_news += sum(c.kind == "news" for c in cands)
                sims += [c.similarity for c in cands]
                for c in cands:
                    kind_sims[threshold_key(c)].append(c.similarity)
                    cand_rows.append((item, c))
                if used_store is not None:                      # candidates.csv(보정용)에는 남기고 카드 근거에서만 뺀다
                    from .used_refs import drop_used
                    cands, skipped = drop_used(cands, used_store.used(item.item_id), args.used_refs_match)
                    used_skipped += len(skipped)
                rel, stop = None, None
                if rel_cfg is not None:                         # 관련성 판정 (뉴스만, 항목별 1회): O인 뉴스만 카드 생성에
                    from .relevance import filter_candidates
                    sim_before = {c.ref: c.similarity for c in cands}
                    cands, rel, stop = filter_candidates(item, cands, floor, tracker.caller(rel_client, item, "relevance"),
                                                         rel_cfg, rel_prompt_ask if (item.category == "ask" and rel_prompt_ask) else rel_prompt)
                    if writer is not None:                      # 판정한 후보 전체 → tracking_matches
                        writer.write_matches(item, rel.labels, sim_before)
                    for ref, (ok, code) in rel.labels.items():
                        relevance_rows[(item.item_id, ref)] = ("O" if ok else "X", code, rel.scope)
                    relevance_items.append({"item_id": item.item_id, **{k: v for k, v in rel.to_dict().items()
                                                                        if k != "labels"}, "stop": stop})
                links = {}
                if same_event_on:
                    from .same_event import link_same_event
                    links = {ref: link.rcept_no for ref, link in link_same_event(conn, cands, scfg).items()}
                extra = None
                if card_schema == "v2" and tcfg.get("compare_prior", True):
                    from .compare_prior import prior_evidence
                    extra = lambda ev: prior_evidence(conn, ev)          # 실적·배당 공시의 직전 같은 기간 값 (DB 읽기 전용)
                if item.category == "ask" and tcfg.get("ask_fin_table"):   # 실험(2026-11-16): ask 질문에 재무 표 근거 (fin_table.py)
                    from .fin_table import fin_evidence

                    def extra(ev, _item=item, _base=extra):
                        out = _base(ev) if _base else []
                        return out + fin_evidence(conn, _item.symbol, _item.company_name or _item.symbol,
                                                  f"{_item.memo_text} {_item.description}", len(ev) + len(out),
                                                  rcfg.get("company_aliases"))
                    if stop == "no_relevant_candidates":       # 관련 후보가 없어도 재무 표로 답해 본다
                        stop, cands = None, []
                if stop is not None:                            # 관련 후보가 없거나 판정 실패: 카드 생성 호출 없이
                    from .models import TopicOutcome
                    out = TopicOutcome(stop)                    # 실패 이유는 responses의 relevance.failed에 남는다
                else:
                    card_call = None if args.no_cards else tracker.caller(client, item)
                    if card_call is not None and tcfg.get("verify_model") and tcfg["verify_model"] != client.model:
                        # 실험(2026-11-17 비용): 검수 프롬프트만 더 싼 모델로 보낸다 (카드 생성은 그대로)
                        from .usage import stage_of
                        if verify_client is None:
                            verify_client = OpenAIClient.from_env()
                            verify_client.model = tcfg["verify_model"]
                        ver_call = tracker.caller(verify_client, item, "verify")
                        card_call = (lambda p, _c=card_call, _v=ver_call: _v(p) if stage_of(p) == "verify" else _c(p))
                    out = check_topic(item, cands, card_call, banned, tcfg, links,
                                      extra_evidence=extra)          # --no-cards: 근거 준비까지만 (not_called)
                if used_store is not None:
                    from .used_refs import card_refs
                    used_store.record(item.item_id, card_refs(out.draft))
                if src not in has_data:
                    has_data[src] = any(source_data(conn, src, since, date.today(), d_since).values())
                responses.append(item_response(item, out.kind, out.fail_codes,
                                               draft_to_dict(out.draft) if out.draft else None, has_data[src],
                                               checked_at=checked))
                if rel is not None:
                    responses[-1].relevance = rel.to_dict()
                outcomes.append({**_outcome(item, out), "fresh_since": fresh.isoformat() if fresh is not None else None,
                                 "relevance": rel.to_dict() if rel is not None else None})
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
                first = writer is not None and not writer.has_price_card(item)   # 그 항목·버전에 가격 카드가 없으면 처음 한 번
                pkind, draft, pinfo = price_outcome(item, rows, dates, cfg["price"]["near_pct"], first_time=first)
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

    merged: dict[str, str] = {}
    if card_schema == "v2":                                     # 같은 메모·같은 근거 카드는 하나로 (topic.merge_same_source)
        from .topic import merge_same_source
        drafts, merged = merge_same_source(drafts, (lambda iid: memo_by_item.get(iid, iid)) if wconn is not None else None)
        by_item = {d.item.item_id: d for d in drafts}
        for r in responses:
            if r.item_id in merged:
                r.user_visible, r.reason = False, f"merged_into:{merged[r.item_id]}"
            elif r.item_id in by_item and by_item[r.item_id].merged_items:
                r.card = draft_to_dict(by_item[r.item_id])
        for o in outcomes:
            if o["item_id"] in merged:
                o["merged_into"] = merged[o["item_id"]]

    sims.sort()
    q = lambda p: round(sims[int(p * (len(sims) - 1))], 3) if sims else None

    def dist(xs):
        xs = sorted(xs)
        pick = lambda p: round(xs[int(p * (len(xs) - 1))], 3) if xs else None
        return {"n": len(xs), "min": pick(0), "p25": pick(.25), "median": pick(.5), "p75": pick(.75), "max": pick(1)}
    summary = {"items": len(items), "topic_items": len(topic_items), "candidates": len(sims), "news_since": str(since),
               "llm": args.llm, "similarity": {"min": q(0), "p25": q(.25), "median": q(.5), "p75": q(.75), "max": q(1)},
               "similarity_by_kind": {k: dist(v) for k, v in kind_sims.items()},
               "outcomes": status_count, "llm_check_failures": fail_count, "cards": len(drafts),
               "card_schema": card_schema, "merged_cards": merged, "news_since_db": news_since_db}
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
    summary["fresh_news"], summary["fresh_late_chunks"] = fresh_news, late_chunks
    if state_store is not None:
        head.append(f"- 새 자료만 받기(마지막 확인 이후 검색 가능해진 자료, 마지막 확인 하루 전부터 발행·최대 14일): 주제 항목 {fresh_items}개"
                    f" · 새 자료 뉴스 후보 {fresh_news}건(그중 확인 전부터 있던 기사를 원문 청크로 찾은 것 {late_chunks}건)"
                    f" · 확인 전에 이미 있던 후보라 뺀 것 {not_ready}건 · 나머지 항목은 첫 확인이라 조회 기간 전체")
    summary["preferred_items"] = sorted({i.item_id for i in items if i.symbol in pref_map})
    summary["used_refs"] = None if used_store is None else {"file": str(getattr(used_store, "path", "db")), "match": args.used_refs_match,
                                                            "skipped": used_skipped}
    from .response import summarize, to_dict
    summary["responses"] = summarize(responses)
    summary["budget"] = {"max_usd": args.max_usd, "stopped": budget_stopped, "skipped_items": skipped_items}
    if budget_stopped:
        head.append(f"- 비용 상한 ${args.max_usd}에 닿아 항목 {skipped_items}개를 건너뜀 (다음 실행에서 처리)")
    head.append(f"- 응답 유형: {json.dumps(summary['responses']['by_type'], ensure_ascii=False)}"
                f" · 사용자 표시 {summary['responses']['user_visible']}건"
                f" · 이유별: {json.dumps(summary['responses']['reasons'], ensure_ascii=False)}")
    failed_items: set[str] = set()                              # 카드 저장이 실패한 항목 (last_checked_at을 갱신하지 않는다)
    if writer is not None:                                      # 카드 → tracking_updates·update_sources (합친 카드는 남은 카드 하나만)
        for d in drafts:
            if d.origin == "llm" or d.type == "price_condition":
                try:
                    writer.write(d.item, d, draft_to_dict(d))
                except Exception as exc:                        # 그 카드만 되돌리고(savepoint) 계속한다
                    writer.written["failed"] += 1
                    failed_items.add(d.item.item_id)
                    failed_items.update(m["item_id"] for m in d.merged_items)
                    print(f"카드 저장 실패 {d.item.item_id}: {type(exc).__name__}: {str(exc)[:200]}", file=sys.stderr)
        summary["db_store"] = {"target": store_target, "run_id": run_id, "shared": shared, **writer.written,
                               "failed_items": sorted(failed_items)}
        head.append(f"- DB 저장 ({store_target}, run_id {run_id}): {json.dumps(writer.written, ensure_ascii=False)}")
    from .response import marks_checked
    checked_count = 0
    if state_store is not None:                                 # 카드 저장 성공 · 정상 '새 소식 없음'만 확인 시각 갱신
        for r in responses:
            if marks_checked(r, failed_items):
                state_store.record(r)
                checked_count += 1
        summary["last_checked_updated"] = checked_count
        head.append(f"- 마지막 확인 시각 갱신 {checked_count}개 항목 (오류·미확인 항목은 그대로)")
    if wconn is not None:
        from .db_store import finish
        finish(wconn, shared)                                   # 쓰기 확정 (허용한 DB인지 다시 확인한 뒤)
    if used_store is not None:
        head.append(f"- 이미 카드에 쓴 근거 빼기: {used_skipped}건 ({getattr(used_store, 'path', 'DB update_sources')}, 기준 {args.used_refs_match})")
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
    if rel_cfg is not None:
        from ..tracking.openai_client import usage_totals as _usage
        ru = _usage(rel_client.calls) if rel_client is not client else None
        if ru is not None and rel_client.model == client.model:   # 같은 모델이면 비용 계산(compare_runs)이 함께 세게 더한다
            for k in ("llm_calls", "prompt_tokens", "output_tokens", "reasoning_tokens"):
                summary[k] = summary.get(k, 0) + ru.get(k, 0)
        judged = sum(r["judged"] for r in relevance_items)
        summary["relevance"] = {
            "prompt": rel_cfg["prompt"], "model": rel_client.model, "separate_client": rel_client is not client,
            "items_called": sum(1 for r in relevance_items if r["judged"]), "judged": judged,
            "relevant": sum(r["relevant"] for r in relevance_items), "dropped": sum(r["dropped"] for r in relevance_items),
            "no_relevant_candidates": sum(1 for r in relevance_items if r["stop"] == "no_relevant_candidates"),
            "failed": sum(1 for r in relevance_items if r["failed"]),
            "scope": {s: sum(1 for r in relevance_items if r["judged"] and r["scope"] == s) for s in ("company", "industry", "")},
            "codes": {c: sum(r["codes"].get(c, 0) for r in relevance_items)
                      for c in sorted({c for r in relevance_items for c in r["codes"]})},
            "usage_separate": ru}
        head.append(f"- 관련성 판정(뉴스, {rel_client.model}): 판정 {judged}건 · O {summary['relevance']['relevant']} · "
                    f"X {summary['relevance']['dropped']} · 관련 후보가 없어 카드 생성을 안 부른 항목 "
                    f"{summary['relevance']['no_relevant_candidates']}개 · 범위 {summary['relevance']['scope']}")
    elif client is not None:
        summary["relevance"] = {"enabled": False}
    run_dir = new_run_dir(args.out_dir, now=run_started)
    if writer is not None:                                      # 이번 실행이 넣거나 바꾼 DB 행 (db_cleanup.py가 읽는다)
        (run_dir / "db_rows.json").write_text(json.dumps(writer.manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    write_results(run_dir, drafts, "\n".join(head + [""] + sections) + "\n", summary)
    csv_path = write_candidates_csv(run_dir, cand_rows, relevance_rows if rel_cfg is not None else None)
    with (run_dir / "outcomes.jsonl").open("w", encoding="utf-8") as f:
        for o in outcomes:
            f.write(json.dumps(o, ensure_ascii=False, default=str) + "\n")
    with (run_dir / "responses.jsonl").open("w", encoding="utf-8") as f:
        for r in responses:
            f.write(json.dumps(to_dict(r), ensure_ascii=False, default=str) + "\n")
    if tracker.io is not None:                                  # --save-llm-io: 프롬프트·응답 원문
        with (run_dir / "llm_io.jsonl").open("w", encoding="utf-8") as f:
            for row in tracker.io:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
    preview_path = write_preview(run_dir, drafts, cand_rows, empties, f"{run_dir.name} · LLM {args.llm}")
    if client is not None:                                      # 사용량 기록 (결정 (다): DB가 아니라 파일)
        from .usage import LOG_PATH, write_usage
        uline = write_usage(tracker, run_dir, resolve_path(LOG_PATH), items=len(items), topic_items=len(topic_items),
                            cards=len(drafts), fresh_items=fresh_items,
                            extra={"news_search": news_mode, "card_schema": card_schema, "store": store_kind,
                                   "relevance": rel_cfg is not None, "no_cards": args.no_cards, "job": args.job,
                                   "run_id": run_id, "budget_stopped": budget_stopped, "skipped_items": skipped_items,
                                   "shared": shared})
        print(f"사용량: 합계 {json.dumps(uline['total'], ensure_ascii=False)} · 단계별 "
              f"{json.dumps({k: v['calls'] for k, v in uline['stages'].items()}, ensure_ascii=False)} → {run_dir / 'usage_by_item.csv'}")
    print("\n".join(head))
    print(f"결과 폴더: {run_dir}  (cards.jsonl, report.md, summary.json, candidates.csv, outcomes.jsonl) — "
          + (f"카드·판정·확인 시각은 {store_target}에 썼습니다 ({'공용 DB, --allow-shared-write' if shared else '테스트 DB, 공용 DB에는 쓰지 않음'})."
             if wconn is not None
             else "DB에는 아무것도 쓰지 않았습니다."))
    print(f"미리보기(사용자 화면처럼): {preview_path}")
    print(f"임계값 정하기: {csv_path} 의 마지막 열 '관련(O/X)'을 채운 뒤 python -m pipelines.updates.calibrate --labels {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())