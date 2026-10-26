"""2) 근거 자료 내보내기 — 팀 DB에서 기업 4곳의 주가·공시·재무·뉴스와 거시 지표를 읽어 JSON으로 저장한다.

    python -m eval.memo_personas.export_evidence

- DB는 읽기만 한다 (연결마다 default_transaction_read_only=on, commit 없음).
- 테이블·컬럼명은 레포의 Alembic 마이그레이션을 그대로 따른다. 쿼리마다 근거 위치를 주석으로 남겼다.
  기준 스키마: alembic/sql/0001_schema_full_v1_2.sql (+ alembic/versions/0004·0005·0007 변경)
- 계산값(수익률·52주 고저·거래량 급증·분기 단독값·증감률·영업이익률·ROE·부채비율)은 코드로 계산하고,
  모든 항목에 DB 원본 ID(테이블:기본키)를 붙인다. 공시 '핵심 청크'는 원문을 그대로 잘라 붙인다(수치 변형 없음).
- 출력: data/evidence_packs/{종목코드}.json, macro.json, coverage.md
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from .common import (FAIL, OK, WARN, company_codes, env_value, load_config, load_env, rpath, say, setup_console,
                     write_json, write_text)

KST = timezone(timedelta(hours=9))
NONE = "없음"
EVIDENCE_TYPES = ["공시", "뉴스", "주가·거래", "재무", "거시"]

# 필요한 테이블·컬럼 (preflight와 공유). 근거: alembic/sql/0001_schema_full_v1_2.sql 줄 번호 + 이후 변경
REQUIRED_COLUMNS = {
    # 0001 sql:197 (trading_value는 0004에서 추가됐다가 0005에서 trade_value로 합쳐 삭제)
    "prices_daily": ["symbol", "trade_date", "open", "high", "low", "close", "volume"],
    # 0001 sql:286
    "disclosures": ["rcept_no", "symbol", "title", "kind", "period_end", "rcept_dt", "source_url"],
    # 0001 sql:297 (embedding → dense_embedding은 0007, 여기서는 쓰지 않음)
    "disclosure_chunks": ["id", "rcept_no", "chunk_index", "section", "chunk_text"],
    # 0001 sql:251·266·279
    "news_sources": ["id", "name"],
    "news_articles": ["id", "source_id", "url", "title", "summary", "published_at"],
    "news_stocks": ["news_id", "symbol"],
    # 0001 sql:220 (fs_div는 0004에서 추가). 손익은 연초부터 누적값(0005 COMMENT ON TABLE financials)
    "financials": ["symbol", "period_end", "period_type", "fs_div", "revenue", "operating_income", "net_income",
                   "total_liabilities", "total_equity"],
    # 0001 sql:240
    "financials_fin": ["symbol", "period_end", "period_type", "net_interest_income", "fee_income",
                       "loan_loss_provision", "solvency_ratio"],
    # 0001 sql:520·533 (지표 코드는 sql:859 시드, 수집은 backend/pipelines/economic/pipeline.py ECOS_SERIES·FRED_SERIES)
    "economic_indicators": ["code", "name", "unit"],
    "economic_observations": ["indicator_code", "observation_date", "value"],
}
# backend/pipelines/economic/pipeline.py의 ECOS_SERIES·FRED_SERIES 코드
MACRO_CODES = {"KR_POLICY_RATE": "기준금리", "USD_KRW": "원/달러 환율", "KR_GOV_3Y": "국고채 3년",
               "KR_GOV_10Y": "국고채 10년", "WTI_SPOT": "WTI"}
RATE_CODES = {"KR_POLICY_RATE", "KR_GOV_3Y", "KR_GOV_10Y"}  # 변화는 %p로

# ─────────────────────────────────────────────────────────────
# SQL (읽기 전용)
# ─────────────────────────────────────────────────────────────
SQL_SCHEMA = """
SELECT table_name, column_name FROM information_schema.columns
WHERE table_schema = current_schema() AND table_name = ANY(:tables)
"""
SQL_ALEMBIC = "SELECT version_num FROM alembic_version"
# prices_daily (0001 sql:197): PK (symbol, trade_date)
SQL_LAST_TRADE = """
SELECT max(trade_date) AS last_trade FROM prices_daily
WHERE symbol = :symbol AND (CAST(:as_of AS date) IS NULL OR trade_date <= CAST(:as_of AS date))
"""
SQL_PRICES = """
SELECT trade_date, open, high, low, close, volume FROM prices_daily
WHERE symbol = :symbol AND trade_date BETWEEN :start AND :as_of
ORDER BY trade_date
"""
# disclosures (0001 sql:286): PK rcept_no, kind는 disclosure_kind enum
SQL_DISCLOSURES = """
SELECT rcept_no, title, kind::text AS kind, period_end, rcept_dt, source_url FROM disclosures
WHERE symbol = :symbol AND rcept_dt <= :as_of
ORDER BY rcept_dt DESC, rcept_no DESC
LIMIT :limit
"""
# disclosure_chunks (0001 sql:297, section 설명은 0004 COMMENT): 공시마다 핵심 항목을 우선해 k개
SQL_CHUNKS = """
SELECT id, rcept_no, chunk_index, section, chunk_text FROM (
  SELECT c.id, c.rcept_no, c.chunk_index, c.section, c.chunk_text,
         row_number() OVER (
           PARTITION BY c.rcept_no
           ORDER BY CASE
             WHEN length(c.chunk_text) < 80 THEN 9
             WHEN c.section ILIKE '%경영진단%' THEN 0
             WHEN c.section ILIKE '%사업의 내용%' THEN 1
             WHEN c.section ILIKE '%배당%' THEN 2
             WHEN c.section IS NULL THEN 3
             ELSE 4 END,
           c.chunk_index) AS rn
  FROM disclosure_chunks c
  WHERE c.rcept_no = ANY(:rcept_nos)
) x
WHERE rn <= :k
ORDER BY rcept_no, rn
"""
# news_articles·news_stocks·news_sources (0001 sql:251·266·279). published_at은 UTC 저장(backend/pipelines/news/rss.py)
SQL_NEWS = """
SELECT a.id, a.title, a.url, a.summary, a.published_at, s.name AS source_name
FROM news_stocks ns
JOIN news_articles a ON a.id = ns.news_id
JOIN news_sources s ON s.id = a.source_id
WHERE ns.symbol = :symbol AND a.published_at >= :since AND a.published_at < :until
ORDER BY a.published_at DESC, a.id DESC
LIMIT 300
"""
# financials (0001 sql:220, fs_div 0004): PK (symbol, period_end, period_type), 손익은 연초부터 누적(0005)
SQL_FINANCIALS = """
SELECT period_end, period_type::text AS period_type, fs_div, revenue, operating_income, net_income,
       total_liabilities, total_equity
FROM financials WHERE symbol = :symbol AND period_end <= :as_of
ORDER BY period_end
"""
# financials_fin (0001 sql:240): 금융권 전용
SQL_FINANCIALS_FIN = """
SELECT period_end, period_type::text AS period_type, net_interest_income, fee_income, loan_loss_provision,
       solvency_ratio
FROM financials_fin WHERE symbol = :symbol AND period_end <= :as_of
ORDER BY period_end
"""
# economic_indicators·economic_observations (0001 sql:520·533): 코드별로 기준일 이전 마지막 관측치
SQL_MACRO_LATEST = """
SELECT DISTINCT ON (o.indicator_code) o.indicator_code, o.observation_date, o.value, i.name, i.unit
FROM economic_observations o JOIN economic_indicators i ON i.code = o.indicator_code
WHERE o.indicator_code = ANY(:codes) AND o.observation_date <= :d
ORDER BY o.indicator_code, o.observation_date DESC
"""


def sqlalchemy_url(url: str) -> str:
    """postgres://·postgresql:// → postgresql+psycopg:// (레포는 psycopg 3만 설치)."""
    return re.sub(r"^postgres(?:ql)?(?:\+\w+)?://", "postgresql+psycopg://", url.strip())


def make_engine(url: str):
    from sqlalchemy import create_engine
    from sqlalchemy.pool import NullPool

    return create_engine(sqlalchemy_url(url), poolclass=NullPool, connect_args={
        "connect_timeout": 10,
        "options": "-c default_transaction_read_only=on -c statement_timeout=120000",
    })


def q(conn, sql: str, **params) -> list[dict]:
    from sqlalchemy import text

    return [dict(r._mapping) for r in conn.execute(text(sql), params)]


def check_schema(conn) -> dict[str, list[str]]:
    """없는 테이블·컬럼 {테이블: [컬럼…]} (테이블 자체가 없으면 ['(테이블 없음)'])."""
    have: dict[str, set] = {}
    for r in q(conn, SQL_SCHEMA, tables=list(REQUIRED_COLUMNS)):
        have.setdefault(r["table_name"], set()).add(r["column_name"])
    missing = {}
    for t, cols in REQUIRED_COLUMNS.items():
        if t not in have:
            missing[t] = ["(테이블 없음)"]
        elif [c for c in cols if c not in have[t]]:
            missing[t] = [c for c in cols if c not in have[t]]
    return missing


# ─────────────────────────────────────────────────────────────
# 숫자·날짜 표기
# ─────────────────────────────────────────────────────────────
def num(v):
    if v is None:
        return None
    if isinstance(v, Decimal):
        return int(v) if v == v.to_integral_value() else float(v)
    return v


def won(v) -> str:
    """원 단위 금액 → '74조 683억원' / '6,761억원' / '71,500원' (억 미만 버림, 원값은 numbers에 따로 보관)."""
    v = int(v)
    sign, v = ("-" if v < 0 else ""), abs(v)
    jo, eok = divmod(v // 10**8, 10**4)
    if jo:
        return f"{sign}{jo:,}조" + (f" {eok:,}억원" if eok else "원")
    if eok:
        return f"{sign}{eok:,}억원"
    return f"{sign}{v:,}원"


def price_txt(v) -> str:
    return f"{num(v):,.0f}원"


def pct(v) -> str:
    return f"{v:+.1f}%"


def sub_months(d: date, months: int) -> date:
    y, m = divmod(d.year * 12 + d.month - 1 - months, 12)
    m += 1
    for day in (d.day, 30, 29, 28):
        try:
            return date(y, m, day)
        except ValueError:
            continue
    raise ValueError(d)


def kst_date(ts) -> date:
    if isinstance(ts, datetime):
        return (ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)).astimezone(KST).date()
    return ts


def item(key, typ, kind, ids, text, hint, numbers=(), dates=(), **extra) -> dict:
    return {"key": key, "type": typ, "kind": kind, "ids": list(dict.fromkeys(ids)), "text": text, "memo_hint": hint,
            "numbers": [n for n in numbers if n is not None], "dates": [str(d) for d in dates if d], **extra}


# ─────────────────────────────────────────────────────────────
# 계산 (DB 없이 테스트 가능)
# ─────────────────────────────────────────────────────────────
def price_block(symbol: str, rows: list[dict], as_of: date, cfg: dict):
    """prices_daily 행 → 기준일 종가·수익률·52주 고저·거래량 급증일과 근거 항목."""
    ev = cfg["evidence"]
    rows = [{**r, "trade_date": r["trade_date"], "close": num(r["close"]), "high": num(r["high"]),
             "low": num(r["low"]), "volume": int(r["volume"])} for r in rows if r["trade_date"] <= as_of]
    if not rows:
        return NONE, [], [f"{symbol}: 기준일 {as_of} 이전 주가가 없습니다"]
    pid = lambda d: f"prices_daily:{symbol}:{d}"  # noqa: E731
    last = rows[-1]
    warnings, items = [], []
    returns = {}
    for label, base_day in (("1주", as_of - timedelta(days=7)), ("1개월", sub_months(as_of, 1)),
                            ("3개월", sub_months(as_of, 3)), ("1년", sub_months(as_of, 12))):
        base = next((r for r in reversed(rows) if r["trade_date"] <= base_day), None)
        if base is None:
            returns[label] = NONE
            warnings.append(f"{symbol}: {label} 수익률 계산에 필요한 과거 주가 없음")
            continue
        returns[label] = {"pct": round((last["close"] / base["close"] - 1) * 100, 2), "base_date": str(base["trade_date"]),
                          "base_close": base["close"], "base_id": pid(base["trade_date"])}
    ok_ret = {k: v for k, v in returns.items() if v != NONE}
    ret_txt = " · ".join(f"{k} {pct(v['pct'])}" for k, v in ok_ret.items()) or "수익률 계산 불가"
    hint_key = next((k for k in ("1개월", "3개월", "1주", "1년") if k in ok_ret), None)
    hint = (f"{hint_key} 새 {abs(ok_ret[hint_key]['pct']):.1f}% {'오름' if ok_ret[hint_key]['pct'] >= 0 else '빠짐'}"
            if hint_key else "요즘 주가 흐름")
    items.append(item(f"{symbol}/price", "주가·거래", "returns",
                      [pid(last["trade_date"])] + [v["base_id"] for v in ok_ret.values()],
                      f"기준일 {last['trade_date']} 종가 {price_txt(last['close'])} · {ret_txt}", hint,
                      [last["close"]] + [v["pct"] for v in ok_ret.values()] + [v["base_close"] for v in ok_ret.values()],
                      [last["trade_date"]] + [v["base_date"] for v in ok_ret.values()]))

    window = [r for r in rows if r["trade_date"] > as_of - timedelta(days=364)]
    if rows[0]["trade_date"] > as_of - timedelta(days=350):
        warnings.append(f"{symbol}: 52주치 주가가 다 없어 있는 기간({rows[0]['trade_date']}~)으로 고저를 계산")
    hi = max(window, key=lambda r: (r["high"], r["trade_date"]))
    lo = min(window, key=lambda r: (r["low"], r["trade_date"]))
    gap_hi = round((last["close"] / hi["high"] - 1) * 100, 2)
    gap_lo = round((last["close"] / lo["low"] - 1) * 100, 2)
    high_52w = {"price": hi["high"], "date": str(hi["trade_date"]), "id": pid(hi["trade_date"]), "gap_pct": gap_hi}
    low_52w = {"price": lo["low"], "date": str(lo["trade_date"]), "id": pid(lo["trade_date"]), "gap_pct": gap_lo}
    near_hi = gap_hi > -5
    items.append(item(f"{symbol}/high_52w", "주가·거래", "high_52w", [pid(hi["trade_date"]), pid(last["trade_date"])],
                      f"52주 최고 {price_txt(hi['high'])}(장중, {hi['trade_date']}) · 기준일 종가는 최고가 대비 {pct(gap_hi)}",
                      "52주 신고가 근처" if near_hi else f"고점 대비 {abs(gap_hi):.0f}% 빠진 상태",
                      [hi["high"], gap_hi, last["close"]], [hi["trade_date"], last["trade_date"]]))
    items.append(item(f"{symbol}/low_52w", "주가·거래", "low_52w", [pid(lo["trade_date"]), pid(last["trade_date"])],
                      f"52주 최저 {price_txt(lo['low'])}(장중, {lo['trade_date']}) · 기준일 종가는 최저가 대비 {pct(gap_lo)}",
                      "52주 신저가 근처" if gap_lo < 5 else f"바닥 대비 {gap_lo:.0f}% 올라온 상태",
                      [lo["low"], gap_lo, last["close"]], [lo["trade_date"], last["trade_date"]]))

    spikes = []
    start = sub_months(as_of, ev["volume_spike_months"])
    for i, r in enumerate(rows):
        if r["trade_date"] <= start or i < 20:
            continue
        avg20 = sum(x["volume"] for x in rows[i - 20:i]) / 20
        if avg20 and r["volume"] / avg20 >= ev["volume_spike_ratio"]:
            prev = rows[i - 1]["close"]
            spikes.append({"date": str(r["trade_date"]), "id": pid(r["trade_date"]), "volume": r["volume"],
                           "avg20": round(avg20), "ratio": round(r["volume"] / avg20, 2),
                           "change_pct": round((r["close"] / prev - 1) * 100, 2), "close": r["close"],
                           "prev_id": pid(rows[i - 1]["trade_date"])})
    spikes = sorted(spikes, key=lambda s: (-s["ratio"], s["date"]))[: ev["volume_spike_top"]]
    for k, s in enumerate(spikes):
        d = date.fromisoformat(s["date"])
        items.append(item(f"{symbol}/spike{k + 1}", "주가·거래", "volume_spike", [s["id"], s["prev_id"]],
                          f"{s['date']} 거래량 {s['volume']:,}주 (직전 20거래일 평균 {s['avg20']:,}주의 {s['ratio']:.1f}배)"
                          f" · 종가 {price_txt(s['close'])}, 전일 대비 {pct(s['change_pct'])}",
                          f"{d.month}월 {d.day}일 거래량 터진 날", [s["volume"], s["avg20"], s["ratio"], s["change_pct"], s["close"]],
                          [d]))
    block = {"as_of_date": str(last["trade_date"]), "close": last["close"], "close_id": pid(last["trade_date"]),
             "returns": returns, "high_52w": high_52w, "low_52w": low_52w, "volume_spikes": spikes or NONE,
             "rows_used": len(rows)}
    return block, items, warnings


def excerpt(text: str, limit: int) -> str:
    """원문 그대로 자른다(공백만 정리). 숫자 중간에서 끊기지 않게 마지막 공백에서 자른다."""
    t = re.sub(r"\s+", " ", text or "").strip()
    if len(t) <= limit:
        return t
    cut = t[:limit]
    return (cut[: cut.rfind(" ")] if " " in cut[limit // 2:] else cut) + " …"


DART_URL = "https://dart.fss.or.kr/dsaf001/main.do?rcpNo={}"


def disclosure_block(symbol: str, rows: list[dict], chunks: list[dict], cfg: dict):
    ev = cfg["evidence"]
    by_no: dict[str, list[dict]] = {}
    for c in chunks:
        by_no.setdefault(c["rcept_no"], []).append(c)
    out, items = [], []
    for r in rows:
        cs = [{"id": f"disclosure_chunks:{c['id']}", "section": c["section"],
               "excerpt": excerpt(c["chunk_text"], ev["excerpt_chars"])} for c in by_no.get(r["rcept_no"], [])]
        url = r["source_url"] or DART_URL.format(r["rcept_no"])
        d = {"id": f"disclosures:{r['rcept_no']}", "rcept_no": r["rcept_no"], "title": r["title"], "kind": r["kind"],
             "rcept_dt": str(r["rcept_dt"]), "period_end": str(r["period_end"]) if r["period_end"] else None,
             "url": url, "url_from_db": bool(r["source_url"]), "chunks": cs or NONE}
        out.append(d)
        rd = r["rcept_dt"]
        body = " / ".join(f"[{c['section'] or '본문'}] {c['excerpt']}" for c in cs) or "발췌 없음"
        items.append(item(f"{symbol}/disc/{r['rcept_no']}", "공시", "disclosure", [d["id"]] + [c["id"] for c in cs],
                          f"{rd} 접수 「{r['title'].strip()}」(접수번호 {r['rcept_no']}) — 원문 발췌: {body}",
                          f"{rd.month}월 {rd.day}일 올라온 {short_title(r['title'])} 공시",
                          numbers_in(r["title"] + " " + body), [rd] + ([r["period_end"]] if r["period_end"] else []),
                          url=url))
    return out or NONE, items


def short_title(title: str) -> str:
    t = re.sub(r"\[[^\]]*\]|\([^)]*\)", "", title).strip()
    return t[:18]


NEWS_NOISE = re.compile(r"\[[^\]]{0,12}\]|【[^】]{0,12}】|<[^>]{0,12}>|[\s\"'“”‘’…·,.!?]")


def dedupe_news(rows: list[dict], limit: int) -> list[dict]:
    seen, out = set(), []
    for r in rows:
        k = NEWS_NOISE.sub("", r["title"]).lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(r)
        if len(out) >= limit:
            break
    return out


def news_block(symbol: str, rows: list[dict], cfg: dict):
    out, items = [], []
    for r in dedupe_news(rows, cfg["evidence"]["news_max"]):
        d = kst_date(r["published_at"])
        n = {"id": f"news_articles:{r['id']}", "title": r["title"].strip(), "source": r["source_name"],
             "date": str(d), "url": r["url"], "summary": excerpt(r["summary"] or "", 160) or NONE}
        out.append(n)
        items.append(item(f"{symbol}/news/{r['id']}", "뉴스", "news", [n["id"]],
                          f"{d} {r['source_name']} 「{n['title']}」" + (f" — 요약: {n['summary']}" if n["summary"] != NONE else ""),
                          f"'{n['title'][:24]}' 기사", numbers_in(n["title"] + " " + (r["summary"] or "")), [d],
                          url=r["url"]))
    return out or NONE, items


QORDER = {"q1": 1, "half": 2, "q3": 3, "annual": 4}
FS_KO = {"consolidated": "연결", "separate": "별도"}  # financials.fs_div (0004)
FLOWS = ("revenue", "operating_income", "net_income")
FLOW_KO = {"revenue": "매출", "operating_income": "영업이익", "net_income": "순이익"}


def fin_id(symbol, r):
    return f"financials:{symbol}:{r['period_end']}:{r['period_type']}"


def financial_block(symbol: str, rows: list[dict], fin_rows: list[dict]):
    """누적값(q1·half·q3·annual) → 분기 단독값. Q2=반기−1분기, Q3=3분기누적−반기, Q4=연간−3분기누적."""
    rows = [{**r, **{k: num(r.get(k)) for k in FLOWS + ("total_liabilities", "total_equity")}} for r in rows]
    by = {(r["period_end"].year, r["period_type"]): r for r in rows}
    quarters = []
    for (year, ptype), r in sorted(by.items(), key=lambda kv: (kv[0][0], QORDER[kv[0][1]])):
        qn = QORDER[ptype]
        prev = by.get((year, {2: "q1", 3: "half", 4: "q3"}.get(qn))) if qn > 1 else None
        if qn > 1 and prev is None:
            continue
        vals = {}
        for f in FLOWS:
            cur, base = r.get(f), (prev.get(f) if prev else 0)
            vals[f] = None if cur is None or base is None else cur - base
        ids = [fin_id(symbol, r)] + ([fin_id(symbol, prev)] if prev else [])
        quarters.append({"year": year, "quarter": qn, "label": f"{year}년 {qn}분기", "period_end": str(r["period_end"]),
                         "fs_div": r.get("fs_div"), "ids": ids, **vals})
    qmap = {(x["year"], x["quarter"]): x for x in quarters}
    for x in quarters:
        ly = qmap.get((x["year"] - 1, x["quarter"]))
        for f in FLOWS:
            x[f"{f}_yoy_pct"] = (round((x[f] / ly[f] - 1) * 100, 2) if ly and x[f] is not None and ly.get(f)
                                 and ly[f] > 0 else None)
        if ly:
            x["yoy_ids"] = ly["ids"]
        x["op_margin_pct"] = (round(x["operating_income"] / x["revenue"] * 100, 2)
                              if x["revenue"] and x["operating_income"] is not None else None)
    recent = [x for x in quarters if any(x[f] is not None for f in FLOWS)][-4:]

    annual = []
    ann_rows = [r for r in rows if r["period_type"] == "annual"]
    for i, r in enumerate(ann_rows):
        prev = ann_rows[i - 1] if i and ann_rows[i - 1]["period_end"].year == r["period_end"].year - 1 else None
        a = {"year": r["period_end"].year, "label": f"{r['period_end'].year}년 연간", "period_end": str(r["period_end"]),
             "fs_div": r.get("fs_div"), "ids": [fin_id(symbol, r)] + ([fin_id(symbol, prev)] if prev else []),
             **{f: r.get(f) for f in FLOWS}}
        for f in FLOWS:
            a[f"{f}_yoy_pct"] = (round((r[f] / prev[f] - 1) * 100, 2) if prev and r.get(f) is not None and prev.get(f)
                                 and prev[f] > 0 else None)
        eq, li = r.get("total_equity"), r.get("total_liabilities")
        a["op_margin_pct"] = round(r["operating_income"] / r["revenue"] * 100, 2) if r.get("revenue") and r.get("operating_income") is not None else None
        a["roe_pct"] = round(r["net_income"] / eq * 100, 2) if eq and r.get("net_income") is not None and eq > 0 else None
        a["debt_ratio_pct"] = round(li / eq * 100, 2) if eq and li is not None and eq > 0 else None
        annual.append(a)
    annual = annual[-2:]

    fin_extra = []
    for r in fin_rows[-4:]:
        fin_extra.append({"id": f"financials_fin:{symbol}:{r['period_end']}:{r['period_type']}",
                          "period_end": str(r["period_end"]), "period_type": r["period_type"], "cumulative": True,
                          **{k: num(r.get(k)) for k in ("net_interest_income", "fee_income", "loan_loss_provision",
                                                        "solvency_ratio")}})

    items = []
    for x in recent:
        parts = [f"{FLOW_KO[f]} {won(x[f])}" for f in FLOWS if x[f] is not None]
        yoy = [f"{FLOW_KO[f]} {pct(x[f + '_yoy_pct'])}" for f in FLOWS if x.get(f + "_yoy_pct") is not None]
        if x["op_margin_pct"] is not None:
            parts.append(f"영업이익률 {x['op_margin_pct']:.1f}%")
        op_y = x.get("operating_income_yoy_pct")
        hint = (f"{x['quarter']}분기 영업이익 " + ("꺾였던데" if op_y < 0 else "늘었던데")) if op_y is not None else \
            f"{x['quarter']}분기 실적 나온 거"
        items.append(item(f"{symbol}/fin/{x['year']}Q{x['quarter']}", "재무", "fin_quarter", x["ids"] + x.get("yoy_ids", []),
                          f"{x['label']} 단독({FS_KO.get(x['fs_div'], '연결')}) " + " · ".join(parts)
                          + (f" · 전년 동기 대비 {', '.join(yoy)}" if yoy else ""), hint,
                          [x[f] for f in FLOWS] + [x["op_margin_pct"]] + [x.get(f + "_yoy_pct") for f in FLOWS],
                          [x["period_end"]]))
    for a in annual:
        parts = [f"{FLOW_KO[f]} {won(a[f])}" for f in FLOWS if a[f] is not None]
        for k, ko in (("op_margin_pct", "영업이익률"), ("roe_pct", "ROE"), ("debt_ratio_pct", "부채비율")):
            if a[k] is not None:
                parts.append(f"{ko} {a[k]:.1f}%")
        yoy = [f"{FLOW_KO[f]} {pct(a[f + '_yoy_pct'])}" for f in FLOWS if a.get(f + "_yoy_pct") is not None]
        items.append(item(f"{symbol}/fin/{a['year']}", "재무", "fin_annual", a["ids"],
                          f"{a['label']}({FS_KO.get(a['fs_div'], '연결')}) " + " · ".join(parts) + (f" · 전년 대비 {', '.join(yoy)}" if yoy else ""),
                          "작년 연간 실적" if a is annual[-1] else f"{a['year']}년 실적",
                          [a[f] for f in FLOWS] + [a["op_margin_pct"], a["roe_pct"], a["debt_ratio_pct"]]
                          + [a.get(f + "_yoy_pct") for f in FLOWS], [a["period_end"]]))
    for x in fin_extra:
        label = {"q1": "1분기", "half": "상반기", "q3": "3분기", "annual": "연간"}[x["period_type"]]
        parts = [f"{ko} {won(x[k])}" for k, ko in (("net_interest_income", "순이자이익"), ("fee_income", "수수료이익"),
                                                    ("loan_loss_provision", "대손충당금")) if x[k] is not None]
        if x["solvency_ratio"] is not None:
            parts.append(f"자본비율(BIS 등) {x['solvency_ratio']:.2f}%")
        if parts:
            y = x["period_end"][:4]
            items.append(item(f"{symbol}/finfin/{x['period_end']}", "재무", "fin_financial_sector", [x["id"]],
                              f"{y}년 {label} 누적(금융 항목) " + " · ".join(parts), f"{y}년 {label} 순이자이익",
                              [x[k] for k in ("net_interest_income", "fee_income", "loan_loss_provision", "solvency_ratio")],
                              [x["period_end"]]))
    block = {"basis": "손익은 분기 단독값(누적값 차감), 재무상태는 기말값. ROE=순이익/기말자본, 부채비율=부채/자본",
             "quarters": recent or NONE, "annual": annual or NONE, "financial_sector": fin_extra or NONE}
    return block, items


def macro_block(latest: list[dict], base: list[dict], as_of: date):
    base_by = {r["indicator_code"]: r for r in base}
    out, items = {}, []
    for code, ko in MACRO_CODES.items():
        r = next((x for x in latest if x["indicator_code"] == code), None)
        if r is None:
            out[code] = NONE
            continue
        v, b = num(r["value"]), base_by.get(code)
        oid = f"economic_observations:{code}:{r['observation_date']}"
        rec = {"name": r["name"], "unit": r["unit"], "value": v, "date": str(r["observation_date"]), "id": oid}
        ids, nums, dates = [oid], [v], [r["observation_date"]]
        change_txt = "3개월 전 값 없음"
        if b is not None:
            bv = num(b["value"])
            bid = f"economic_observations:{code}:{b['observation_date']}"
            if code in RATE_CODES:
                ch = round(v - bv, 3)
                change_txt = f"3개월 전({b['observation_date']}) {bv:g}% → 변화 {ch:+.2f}%p"
            else:
                ch = round((v / bv - 1) * 100, 2) if bv else None
                change_txt = f"3개월 전({b['observation_date']}) {bv:,.2f} → 변화 {pct(ch)}" if ch is not None else change_txt
            rec.update({"base_value": bv, "base_date": str(b["observation_date"]), "base_id": bid, "change": ch,
                        "change_unit": "%p" if code in RATE_CODES else "%"})
            ids.append(bid)
            nums += [bv, ch]
            dates.append(b["observation_date"])
        out[code] = rec
        val_txt = f"{v:g}%" if code in RATE_CODES else (f"{v:,.2f}원" if code == "USD_KRW" else f"{v:,.2f}달러")
        if code == "KR_POLICY_RATE":
            hint = "기준금리 " + ("그대로" if rec.get("change") == 0 else "바뀐 거")
        elif code == "USD_KRW":
            hint = f"환율 {int(v // 100) * 100:,}원대"
        elif code == "WTI_SPOT":
            hint = "유가 " + ("오른 거" if (rec.get("change") or 0) > 0 else "내린 거")
        else:
            hint = f"{ko} 금리 " + ("오른 거" if (rec.get("change") or 0) > 0 else "내린 거")
        items.append(item(f"macro/{code}", "거시", "macro", ids,
                          f"{ko} {val_txt} ({r['observation_date']}) · {change_txt}", hint, nums, dates))
    return out, items


def numbers_in(text: str) -> list[float]:
    """근거 원문 속 숫자(단위 포함 해석). checks.parse_numbers와 같은 해석을 쓴다."""
    from .checks import parse_numbers

    return [n["value"] for n in parse_numbers(text)]


# ─────────────────────────────────────────────────────────────
# 실행
# ─────────────────────────────────────────────────────────────
def company_pack(name: str, symbol: str, as_of: date, rows: dict, cfg: dict) -> dict:
    """DB에서 읽은 행(rows) → 기업 근거 묶음. rows 키: prices, disclosures, chunks, news, financials, financials_fin."""
    ev = cfg["evidence"]
    price, p_items, p_warn = price_block(symbol, rows["prices"], as_of, cfg)
    discs, d_items = disclosure_block(symbol, rows["disclosures"], rows["chunks"], cfg)
    news, n_items = news_block(symbol, rows["news"], cfg)
    fin, f_items = financial_block(symbol, rows["financials"], rows["financials_fin"])
    items = p_items + d_items + n_items + f_items
    warn = list(p_warn)
    counts = {t: sum(1 for i in items if i["type"] == t) for t in EVIDENCE_TYPES if t != "거시"}
    for t, n in counts.items():
        if n < ev["min_items"][t]:
            warn.append(f"{name}: {t} 근거 {n}건 (최소 {ev['min_items'][t]}건) → 메모 생성 때 {t} 비중을 다른 유형으로 옮깁니다")
    return {"symbol": symbol, "name": name, "as_of_date": str(as_of), "price": price, "disclosures": discs,
            "financials": fin, "news": news, "items": items, "counts": counts, "warnings": warn}


def macro_pack(latest: list[dict], base: list[dict], as_of: date, base_day: date, cfg: dict) -> dict:
    macro, items = macro_block(latest, base, as_of)
    warn = [f"거시: {MACRO_CODES[c]}({c}) 관측치 없음" for c, v in macro.items() if v == NONE]
    if len(items) < cfg["evidence"]["min_items"]["거시"]:
        warn.append(f"거시 근거 {len(items)}건 (최소 {cfg['evidence']['min_items']['거시']}건) → 메모 생성 때 거시 비중을 다른 유형으로 옮깁니다")
    return {"as_of_date": str(as_of), "base_date": str(base_day), "indicators": macro, "items": items,
            "counts": {"거시": len(items)}, "warnings": warn}


def build_all(conn, cfg: dict) -> dict:
    ev = cfg["evidence"]
    fixed = date.fromisoformat(str(ev["as_of_date"])) if ev.get("as_of_date") else None
    try:
        alembic_version = [r["version_num"] for r in q(conn, SQL_ALEMBIC)]
    except Exception:  # noqa: BLE001 — 버전 표가 없어도 내보내기는 계속
        conn.rollback()
        alembic_version = None
    packs, warnings = {}, []
    for name, symbol in company_codes(cfg).items():
        as_of = q(conn, SQL_LAST_TRADE, symbol=symbol, as_of=fixed)[0]["last_trade"]
        if as_of is None:
            warnings.append(f"{name}({symbol}): prices_daily에 주가가 없어 기준일을 정할 수 없습니다")
            packs[symbol] = {"symbol": symbol, "name": name, "as_of_date": None, "items": [], "warnings": warnings[-1:]}
            continue
        drows = q(conn, SQL_DISCLOSURES, symbol=symbol, as_of=as_of, limit=ev["disclosures_max"])
        since = datetime.combine(sub_months(as_of, ev["news_months"]), datetime.min.time(), KST)
        until = datetime.combine(as_of + timedelta(days=1), datetime.min.time(), KST)
        rows = {
            "prices": q(conn, SQL_PRICES, symbol=symbol, start=as_of - timedelta(days=420), as_of=as_of),
            "disclosures": drows,
            "chunks": q(conn, SQL_CHUNKS, rcept_nos=[r["rcept_no"] for r in drows], k=ev["chunks_per_disclosure"]) if drows else [],
            "news": q(conn, SQL_NEWS, symbol=symbol, since=since, until=until),
            "financials": q(conn, SQL_FINANCIALS, symbol=symbol, as_of=as_of),
            "financials_fin": q(conn, SQL_FINANCIALS_FIN, symbol=symbol, as_of=as_of),
        }
        packs[symbol] = company_pack(name, symbol, as_of, rows, cfg)
        warnings += packs[symbol]["warnings"]
    as_ofs = [date.fromisoformat(p["as_of_date"]) for p in packs.values() if p["as_of_date"]]
    macro_as_of = fixed or (max(as_ofs) if as_ofs else date.today())
    base_day = sub_months(macro_as_of, ev["macro_change_months"])
    macro = macro_pack(q(conn, SQL_MACRO_LATEST, codes=list(MACRO_CODES), d=macro_as_of),
                       q(conn, SQL_MACRO_LATEST, codes=list(MACRO_CODES), d=base_day), macro_as_of, base_day, cfg)
    warnings += macro["warnings"]
    meta = {"generated_at": datetime.now(KST).isoformat(timespec="seconds"), "alembic_version": alembic_version,
            "read_only": True, "tool": "eval/memo_personas/export_evidence.py"}
    for p in list(packs.values()) + [macro]:
        p["meta"] = meta
    return {"packs": packs, "macro": macro, "warnings": warnings}


def render_coverage(result: dict, cfg: dict) -> str:
    L = ["# 근거 자료 현황 (coverage)", "",
         f"- 생성: {result['macro']['meta']['generated_at']} · Alembic 버전: {result['macro']['meta']['alembic_version']}",
         "- DB는 읽기 전용으로 조회했습니다. 수치는 DB 원본 또는 원본에서 계산한 값이며, 모든 항목에 DB 원본 ID가 있습니다.", "",
         "| 기업 | 기준일 | 종가 | 공시 | 뉴스 | 주가·거래 | 재무 | 급증일 |", "|---|---|---|---|---|---|---|---|"]
    for p in result["packs"].values():
        if not p["as_of_date"]:
            L.append(f"| {p['name']} ({p['symbol']}) | 없음 | - | - | - | - | - | - |")
            continue
        c = p["counts"]
        spikes = p["price"]["volume_spikes"]
        L.append(f"| {p['name']} ({p['symbol']}) | {p['as_of_date']} | {price_txt(p['price']['close'])} | {c['공시']} | "
                 f"{c['뉴스']} | {c['주가·거래']} | {c['재무']} | {len(spikes) if spikes != NONE else 0} |")
    m = result["macro"]
    L += ["", f"## 거시 (기준 {m['as_of_date']}, 비교 {m['base_date']})", ""]
    L += [f"- {i['text']}" for i in m["items"]] or ["- 없음"]
    L += ["", "## 경고", ""]
    L += [f"- {WARN} {w}" for w in result["warnings"]] or ["- 없음"]
    L += ["", "## 기업별 근거 항목", ""]
    for p in result["packs"].values():
        L += [f"### {p['name']} ({p['symbol']})", ""]
        L += [f"- `{i['type']}` {i['text'][:160]}  \n  ID: {', '.join(i['ids'][:4])}" for i in p["items"]] or ["- 없음"]
        L.append("")
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    setup_console()
    ap = argparse.ArgumentParser(description="팀 DB에서 근거 자료를 읽어 data/evidence_packs/에 저장합니다 (읽기 전용).")
    ap.parse_args(argv)
    load_env()
    cfg = load_config()
    url = env_value("DATABASE_URL")
    if not url:
        say(FAIL, ".env에 DATABASE_URL이 없습니다", fix="python -m eval.memo_personas.preflight 를 먼저 실행해 안내대로 고치세요.")
        return 1
    try:
        engine = make_engine(url)
        with engine.connect() as conn:
            missing = check_schema(conn)
            if missing:
                say(FAIL, "필요한 테이블·컬럼이 없습니다", ", ".join(f"{t}: {c}" for t, c in missing.items()),
                    fix="팀 DB에 최신 마이그레이션이 적용됐는지 확인하세요: alembic upgrade head (DB 담당자와 상의)")
                return 1
            result = build_all(conn, cfg)
            conn.rollback()
    except Exception as exc:  # noqa: BLE001 — 사람이 읽을 안내로 바꿔 보여 준다
        if type(exc).__name__ in ("OperationalError", "InterfaceError"):
            say(FAIL, "DB에 연결하지 못했습니다", type(exc).__name__,
                fix="docker compose ps 로 memos-db가 실행 중인지, .env의 DATABASE_URL 호스트·포트·비밀번호가 맞는지 확인하세요.")
            return 1
        raise
    out = rpath(cfg["paths"]["evidence_dir"])
    for symbol, pack in result["packs"].items():
        write_json(out / f"{symbol}.json", pack)
    write_json(out / "macro.json", result["macro"])
    write_text(out / "coverage.md", render_coverage(result, cfg))
    for p in result["packs"].values():
        say(OK if p["as_of_date"] else FAIL, f"{p['name']} ({p['symbol']})",
            f"기준일 {p['as_of_date']} · " + ", ".join(f"{k} {v}건" for k, v in p.get("counts", {}).items()))
    say(OK, "거시", f"{len(result['macro']['items'])}개 지표 (기준 {result['macro']['as_of_date']})")
    for w in result["warnings"]:
        say(WARN, w)
    print(f"\n저장 완료 → {out.relative_to(rpath('.')) if out.is_relative_to(rpath('.')) else out}/ (기업 4개 JSON, macro.json, coverage.md)")
    if any(not p["as_of_date"] for p in result["packs"].values()):
        say(FAIL, "주가가 없는 기업이 있어 메모를 만들 수 없습니다", fix="상규에게 coverage.md를 보내 주세요.")
        return 1
    print("다음 단계: python -m eval.memo_personas.generate_memos --pilot")
    return 0


if __name__ == "__main__":
    sys.exit(main())
