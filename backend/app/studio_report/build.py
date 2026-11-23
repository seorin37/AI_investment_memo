"""주간보고서 종목 섹션 만들기 — 1단계: 코드만 (LLM 없음) (2026-11-23, docs/weekly-report-plan.md).

보고서 = 종목 섹션 여러 개. 섹션 모양은 프론트 `ReportStock`(ui/screens/studio/Studio.mock.ts)과 같다.
로고 색(logo·logo_bg·sc·st)은 프론트가 채운다. 맨 위 종합(종목 칸·합계·이번 주 한눈에)은 프론트가 섹션을 모아 계산한다.

- 주가: prices_daily 그 주 월~금 + 지난주 마지막 거래일 종가. 등락률·고가·저가·거래량 변화는 코드가 계산한다.
- 소식: 공시(그 주 접수, 자회사 공시 빼고 정정은 원본과 합침) + 뉴스(제목에 회사 이름, 시황 묶음 빼고, 같은 사건 하나, 최대 3건).
- 내 메모: AI 연결 메모의 추적 항목에 그 주 근거로 붙은 카드 → 연결 소식 수(linked_count).
- 지켜볼 것: 가격 조건까지 거리, 소식이 없으면 다음 주 소식.
- 흐름 문장(story): 지금은 코드 문장. 2단계에서 LLM 문장으로 바꾸고 이 문장은 대체 문장으로 남긴다.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import text

SEOUL = ZoneInfo("Asia/Seoul")
WEEKDAYS = "월화수목금토일"
NEWS_PER_STOCK = 3
# 여러 종목을 한꺼번에 다루는 시황·매매 동향 기사 (종목 소식이 아니다)
ROUNDUP = re.compile(r"시황|초고수|마감\s*[\]】]|\[이런국장|증시\s*(브리핑|요약)|오늘의\s*(증시|종목)|코스피.{0,6}(상승|하락|마감|출발)")
# 제목 앞 [기재정정]·[첨부정정] 같은 표시
TAG = re.compile(r"^\s*\[[^\]]*\]\s*")
# 공시 제목을 읽기 쉽게 (DART 붙여 쓴 이름 → 띄어 쓴 이름). 없으면 원래 제목
DISCLOSURE_NAMES = [
    (re.compile(r"타법인주식및출자증권취득결정"), "타법인 주식 취득 결정"),
    (re.compile(r"타법인주식및출자증권처분결정"), "타법인 주식 처분 결정"),
    (re.compile(r"신규시설투자등"), "신규 시설투자 결정"),
    (re.compile(r"자기주식취득결정"), "자기주식 취득 결정"),
    (re.compile(r"자기주식처분결정"), "자기주식 처분 결정"),
    (re.compile(r"주식소각결정"), "주식 소각 결정"),
    (re.compile(r"현금ㆍ현물배당결정"), "현금 배당 결정"),
    (re.compile(r"연결재무제표기준영업\(잠정\)실적\(공정공시\)"), "연결 영업(잠정)실적"),
    (re.compile(r"영업\(잠정\)실적\(공정공시\)"), "영업(잠정)실적"),
    (re.compile(r"기업설명회\(IR\)개최\(안내공시\)"), "기업설명회(IR) 개최"),
]


# ─── 주 ───────────────────────────────────────────────

def last_week(today: date) -> tuple[date, date]:
    """가장 최근에 끝난 월~금. 토·일이면 이번 주, 월~금이면 지난주."""
    monday = today - timedelta(days=today.weekday())
    if today.weekday() < 5:
        monday -= timedelta(days=7)
    return monday, monday + timedelta(days=4)


def week_label(monday: date) -> tuple[str, str]:
    """('2026년 11월 3주', '11월 3주 주간 보고서'). 그 달의 몇째 월요일 주인지."""
    n = (monday.day - 1) // 7 + 1
    return f"{monday.year}년 {monday.month}월 {n}주", f"{monday.month}월 {n}주 주간 보고서"


def md(d: date) -> str:
    return f"{d.month:02d}.{d.day:02d}"


def won(n: float) -> str:
    return f"{round(n):,}"


def won_short(n: float) -> str:
    """가격 조건 표기: 1,100,000 → '110만 원', 152,900 → '152,900원'."""
    n = round(n)
    return f"{n // 10000:,}만 원" if n % 10000 == 0 else f"{n:,}원"


# ─── 주가 ─────────────────────────────────────────────

def price_block(rows: list[dict], monday: date, friday: date) -> dict[str, Any] | None:
    """rows: 날짜 오름차순 {trade_date, high, low, close, volume} (지난주 포함). 그 주 거래일이 없으면 None."""
    week = [r for r in rows if monday <= r["trade_date"] <= friday]
    before = [r for r in rows if r["trade_date"] < monday]
    if not week or not before:
        return None
    prev = float(before[-1]["close"])
    closes = [float(r["close"]) for r in week]
    close = closes[-1]
    prev_week = [r for r in before if r["trade_date"] >= monday - timedelta(days=7)]
    # 거래량은 하루 평균으로 비교한다 (휴장·시세 누락으로 거래일 수가 다를 수 있다)
    vol_now = sum(int(r["volume"] or 0) for r in week) / len(week)
    vol_before = (sum(int(r["volume"] or 0) for r in prev_week) / len(prev_week)) if prev_week else 0
    lo_all, hi_all = min(closes + [prev]), max(closes + [prev])
    pad = max((hi_all - lo_all) * 0.15, hi_all * 0.005)
    return {
        "trade_dates": [r["trade_date"] for r in week],
        "close": close, "prev": prev, "closes": closes,
        "pct": round((close - prev) / prev * 100, 1),
        "hi": won(max(float(r["high"] or r["close"]) for r in week)),
        "lo": won(min(float(r["low"] or r["close"]) for r in week)),
        "vol": (f"{(vol_now - vol_before) / vol_before * 100:+.0f}%" if vol_before else ""),
        "yr": [math.floor(lo_all - pad), math.ceil(hi_all + pad)],
    }


# ─── 소식 ─────────────────────────────────────────────

@dataclass
class Item:
    kind: str                 # '공시' | '뉴스'
    day: date
    title: str
    src: str
    ref: str                  # disc:<rcept_no> | news:<id>
    url: str | None = None
    score: float = 0.0
    no: int = 0
    linked: bool = False      # 내 메모 추적 항목에 붙은 카드의 근거
    snippet: str = ""         # LLM 입력용 본문 앞부분 (뉴스 요약·리드·첫 청크 / 공시 첫 청크) — 화면에는 안 보인다
    show: bool = True         # '이번 주 소식' 목록에 보인다 (False면 이슈 정리 근거로만 쓰고 출처 목록에만)


def clean_disclosure_title(title: str) -> str:
    t = TAG.sub("", title or "").strip()
    for pat, name in DISCLOSURE_NAMES:
        if pat.search(t):
            return name
    return t


def pick_disclosures(rows: list[dict]) -> list[Item]:
    """rows: {rcept_no, title, rcept_dt, source_url}. 자회사 공시는 빼고, 같은 제목(정정 표시 뗀)은 늦게 접수한 것 하나."""
    by_title: dict[str, dict] = {}
    for r in sorted(rows, key=lambda r: (r["rcept_dt"], r["rcept_no"])):
        if "자회사" in (r["title"] or ""):
            continue
        by_title[clean_disclosure_title(r["title"])] = r
    return [Item("공시", r["rcept_dt"], name, "DART", f"disc:{r['rcept_no']}", r.get("source_url"))
            for name, r in by_title.items()]


HANGUL_OR_WORD = re.compile(r"[0-9A-Za-z가-힣]")
# 이름 바로 뒤에 와도 되는 조사 (한 글자, 그 뒤는 한글이 아니어야 한다): "네이버가 …" 는 되고 "네이버스", "삼성디스플레이", "KB증권"은 안 된다
PARTICLES = "가이는은의도와과에를을로서만"


def mentions(title: str, name: str) -> bool:
    """제목에 회사 이름이 낱말로 있는가. 앞은 글자가 아니어야 하고, 뒤는 끝·기호·공백이거나 조사 한 글자(+글자 아님)."""
    t, n = title.lower(), name.lower()
    start = 0
    while (i := t.find(n, start)) >= 0:
        start = i + 1
        if i > 0 and HANGUL_OR_WORD.match(t[i - 1]):
            continue
        rest = t[i + len(n):]
        if not rest or not HANGUL_OR_WORD.match(rest[0]):
            return True
        if rest[0] in PARTICLES and (len(rest) == 1 or not HANGUL_OR_WORD.match(rest[1])):
            return True
    return False


def pick_news(rows: list[dict], names: list[str], limit: int = NEWS_PER_STOCK) -> list[Item]:
    """rows: {id, title, published_at, url, score, source, cluster_id}. 제목에 회사 이름이 있는 기사만, 시황 묶음 빼고,
    같은 사건(cluster)·같은 제목은 하나, score 높은 순 limit건 → 날짜순."""
    keys = [n for n in names if n]
    seen_cluster: set = set()
    seen_title: set = set()
    out: list[Item] = []
    for r in sorted(rows, key=lambda r: (-(r["score"] or 0), r["published_at"])):
        title = (r["title"] or "").strip()
        if not any(mentions(title, k) for k in keys) or ROUNDUP.search(title):
            continue
        key = re.sub(r"\W", "", title.lower())[:20]      # 끝이 잘린 같은 제목("…매수자...")도 같은 기사로
        if (r.get("cluster_id") is not None and r["cluster_id"] in seen_cluster) or key in seen_title:
            continue
        seen_title.add(key)
        if r.get("cluster_id") is not None:
            seen_cluster.add(r["cluster_id"])
        out.append(Item("뉴스", r["published_at"].astimezone(SEOUL).date(), title, r.get("source") or "", f"news:{r['id']}",
                        r.get("url"), float(r["score"] or 0)))
        if len(out) >= limit:
            break
    return sorted(out, key=lambda i: i.day)


# ─── 내 메모 ──────────────────────────────────────────

@dataclass
class MemoLink:
    memo_id: int
    title: str
    created_at: datetime
    topics: list[tuple[int, str]] = field(default_factory=list)      # (item_id, 설명) 주제 항목
    prices: list[tuple[str, float]] = field(default_factory=list)    # (price_below|price_above, 가격)
    linked: dict[str, Item] = field(default_factory=dict)            # 그 주 근거 ref → 소식
    linked_topics: list[str] = field(default_factory=list)


def memo_section(links: list[MemoLink]) -> dict | None:
    """화면 칸이 하나라 카드가 붙은 메모 → 가장 최근 메모 순으로 하나만."""
    if not links:
        return None
    m = sorted(links, key=lambda x: (len(x.linked) > 0, x.created_at), reverse=True)[0]
    meta = f"{m.created_at.astimezone(SEOUL).month}.{m.created_at.astimezone(SEOUL).day} 작성 · AI 연결 중"
    if m.linked:
        nos = ", ".join(f"[{i.no}]" for i in sorted(m.linked.values(), key=lambda i: i.no))
        topic = m.linked_topics[0] if m.linked_topics else (m.topics[0][1] if m.topics else "")
        body = f"메모의 추적 항목 '{topic}'과 관련된 소식 {len(m.linked)}건({nos})이 이번 주에 붙었어요."
    else:
        body = "이번 주 이 메모와 관련된 새 소식은 없었어요."
    return {"memo_id": str(m.memo_id), "title": m.title, "meta": meta, "body": body, "linked_count": len(m.linked)}


def watch_lines(links: list[MemoLink], close: float, as_of: date, has_items: bool) -> list[dict]:
    out = []
    for m in links:
        for kind, th in m.prices:
            diff = (close - th) / th * 100
            out.append({"text": f"메모의 가격 조건 {won_short(th)}과 {md(as_of)} 종가의 차이 ({abs(diff):.1f}% {'위' if diff >= 0 else '아래'})",
                        "why": "내 메모 가격 조건"})
    if not has_items:
        out.append({"text": "다음 주 새 공시·뉴스가 나오는지", "why": "이번 주 소식 0건"})
    return out


# ─── 흐름 문장 (코드) ─────────────────────────────────

def code_story(p: dict, items: list[Item]) -> str:
    last = p["trade_dates"][-1]
    if not items:
        i = max(range(len(p["closes"])), key=lambda k: p["closes"][k])
        d = p["trade_dates"][i]
        return (f"이번 주 새 공시·뉴스는 없었어요. {WEEKDAYS[d.weekday()]}요일({md(d)}) 종가 {won(p['closes'][i])}원이 "
                f"이번 주 가장 높았고, {md(last)} 종가 기준 {won(p['close'])}원이에요.")
    nd = sum(1 for i in items if i.kind == "공시")
    nn = len(items) - nd
    bits = "·".join(b for b in (f"공시 {nd}건" if nd else "", f"뉴스 {nn}건" if nn else "") if b)
    move = "높은" if p["pct"] > 0 else "낮은" if p["pct"] < 0 else "같은"
    pct = f"{abs(p['pct']):.1f}% " if p["pct"] else ""
    return f"이번 주 {bits}이 있었어요. {md(last)} 종가는 지난주보다 {pct}{move} {won(p['close'])}원이에요."


# ─── DB ───────────────────────────────────────────────

PRICES_SQL = """SELECT trade_date, high, low, close, volume FROM prices_daily
WHERE symbol = :s AND trade_date BETWEEN :since AND :until ORDER BY trade_date"""
STOCK_SQL = """SELECT btrim(us.symbol) AS code, s.name, us.status::text AS status FROM user_stocks us
JOIN stocks s ON s.symbol = us.symbol WHERE us.user_id = :u AND us.deleted_at IS NULL ORDER BY us.created_at, us.symbol"""
DISC_SQL = """SELECT rcept_no, title, rcept_dt, source_url FROM disclosures
WHERE symbol = :s AND rcept_dt BETWEEN :mon AND :fri"""
NEWS_SQL = """SELECT a.id, a.title, a.published_at, a.url, ns.score, src.name AS source, cm.cluster_id
FROM news_stocks ns JOIN news_articles a ON a.id = ns.news_id
LEFT JOIN news_sources src ON src.id = a.source_id
LEFT JOIN news_cluster_members cm ON cm.news_id = a.id
WHERE ns.symbol = :s AND a.published_at >= :start AND a.published_at < :end"""
MEMO_SQL = """SELECT m.id AS memo_id, m.title, m.content, m.created_at, ti.id AS item_id, ti.type::text AS type,
       ti.description, ti.price_threshold
FROM memos m JOIN tracking_items ti ON ti.memo_id = m.id
WHERE m.user_id = :u AND m.symbol = :s AND m.deleted_at IS NULL AND m.ai_linked AND ti.status = 'active'
  AND ti.type::text <> 'ask'
ORDER BY m.id, ti.id"""
LINKED_SQL = """SELECT tu.tracking_item_id AS item_id, us.news_id, us.disclosure_rcept_no AS rcept_no,
       a.title AS news_title, a.published_at, a.url AS news_url, src.name AS source,
       d.title AS disc_title, d.rcept_dt, d.source_url
FROM tracking_updates tu JOIN update_sources us ON us.update_id = tu.id
LEFT JOIN news_articles a ON a.id = us.news_id LEFT JOIN news_sources src ON src.id = a.source_id
LEFT JOIN disclosures d ON d.rcept_no = us.disclosure_rcept_no
WHERE tu.tracking_item_id = ANY(:ids)
  AND ((a.published_at >= :start AND a.published_at < :end) OR d.rcept_dt BETWEEN :mon AND :fri)"""
NEWS_SNIP_SQL = """SELECT a.id, a.summary,
       (SELECT l.lead_text FROM news_article_leads l WHERE l.news_id = a.id) AS lead,
       (SELECT nc.chunk_text FROM news_chunks nc WHERE nc.news_id = a.id ORDER BY nc.chunk_index LIMIT 1) AS chunk
FROM news_articles a WHERE a.id = ANY(:ids)"""
DISC_SNIP_SQL = """SELECT rcept_no, string_agg(chunk_text, ' ' ORDER BY chunk_index) AS text FROM (
  SELECT rcept_no, chunk_index, chunk_text FROM disclosure_chunks WHERE rcept_no = ANY(:ids) AND chunk_index < 2) c
GROUP BY rcept_no"""
FUND_SQL = """SELECT basis_trade_date, per, pbr, eps, bps, w52_high, w52_low, market_cap FROM stock_fundamentals_snapshot
WHERE symbol = :s AND basis_trade_date <= :d ORDER BY basis_trade_date DESC LIMIT 1"""
QUARTER_SQL = """SELECT period_end, quarter, fs_div, revenue, operating_income, net_income FROM financials_quarterly
WHERE symbol = :s AND period_end <= :d ORDER BY period_end DESC, (fs_div = 'consolidated') DESC LIMIT 12"""
INDEX_SQL = """SELECT trade_date AS day, close AS value FROM market_indices
WHERE code = :c AND trade_date BETWEEN :since AND :fri ORDER BY trade_date"""
OBS_SQL = """SELECT observation_date AS day, value FROM economic_observations
WHERE indicator_code = :c AND value IS NOT NULL AND observation_date BETWEEN :since AND :fri ORDER BY observation_date"""


def _rows(db, sql: str, **params) -> list[dict]:
    return [dict(r) for r in db.execute(text(sql), params).mappings().all()]


def _memo_links(db, user_id: int, symbol: str, window: dict) -> list[MemoLink]:
    links: dict[int, MemoLink] = {}
    items: dict[int, MemoLink] = {}
    for r in _rows(db, MEMO_SQL, u=user_id, s=symbol):
        m = links.get(r["memo_id"])
        if m is None:
            title = (r["title"] or "").strip() or next((ln.strip() for ln in (r["content"] or "").splitlines() if ln.strip()), "")[:40]
            m = links[r["memo_id"]] = MemoLink(r["memo_id"], title or "제목 없는 메모", r["created_at"])
        if r["type"] in ("price_below", "price_above") and r["price_threshold"] is not None:
            m.prices.append((r["type"], float(r["price_threshold"])))
        else:
            m.topics.append((r["item_id"], r["description"]))
        items[r["item_id"]] = m
    if items:
        desc = {iid: d for m in links.values() for iid, d in m.topics}
        for r in _rows(db, LINKED_SQL, ids=list(items), **window):
            m = items[r["item_id"]]
            if r["news_id"] is not None:
                it = Item("뉴스", r["published_at"].astimezone(SEOUL).date(), r["news_title"] or "", r["source"] or "",
                          f"news:{r['news_id']}", r["news_url"])
            else:
                it = Item("공시", r["rcept_dt"], clean_disclosure_title(r["disc_title"]), "DART", f"disc:{r['rcept_no']}", r["source_url"])
            it.linked = True
            m.linked.setdefault(it.ref, it)
            if r["item_id"] in desc and desc[r["item_id"]] not in m.linked_topics:
                m.linked_topics.append(desc[r["item_id"]])
    return list(links.values())


def _change(rows: list[dict], monday: date) -> float | None:
    week = [r for r in rows if r["day"] >= monday]
    before = [r for r in rows if r["day"] < monday]
    if not week or not before:
        return None
    return round((float(week[-1]["value"]) - float(before[-1]["value"])) / float(before[-1]["value"]) * 100, 1)


def market_block(db, monday: date, friday: date) -> list[dict]:
    since = monday - timedelta(days=10)
    out = []
    for name, sql, code in (("코스피", INDEX_SQL, "KOSPI"), ("코스닥", INDEX_SQL, "KOSDAQ"), ("원/달러", OBS_SQL, "USD_KRW")):
        rows = _rows(db, sql, c=code, since=since, fri=friday)
        pct = _change(rows, monday)
        if pct is not None:
            week = [r for r in rows if r["day"] >= monday]
            out.append({"name": name, "value": f"{float(week[-1]['value']):,.2f}", "pct": pct, "as_of": week[-1]["day"].isoformat()})
    return out


def money(v) -> str:
    """원 단위 금액 → '195.3조원' / '8,345억원' (화면 표기, 코드 계산)."""
    if v is None:
        return ""
    v = float(v)
    return f"{v / 1e12:,.1f}조원" if abs(v) >= 1e12 else f"{v / 1e8:,.0f}억원"


def valuation(db, symbol: str, as_of: date, close: float) -> dict | None:
    """PER·PBR·EPS·시가총액·52주 위치 (stock_fundamentals_snapshot, 그 날 이전 마지막 값)."""
    r = next(iter(_rows(db, FUND_SQL, s=symbol, d=as_of)), None)
    if r is None:
        return None
    hi, lo = r["w52_high"], r["w52_low"]
    pos = round((close - float(lo)) / (float(hi) - float(lo)) * 100) if hi and lo and float(hi) > float(lo) else None
    f = lambda v, d=2: None if v is None else round(float(v), d)
    return {"basis": r["basis_trade_date"].isoformat(), "per": f(r["per"]), "pbr": f(r["pbr"]), "eps": f(r["eps"], 0),
            "market_cap": money(r["market_cap"]), "w52_high": f(hi, 0), "w52_low": f(lo, 0), "w52_pos": pos}


def quarter_block(db, symbol: str, as_of: date) -> dict | None:
    """최근 분기 매출·영업이익·순이익과 전년 같은 분기 대비 (연결 우선)."""
    rows = _rows(db, QUARTER_SQL, s=symbol, d=as_of)
    if not rows:
        return None
    fs = "consolidated" if any(r["fs_div"] == "consolidated" for r in rows) else rows[0]["fs_div"]
    rows = [r for r in rows if r["fs_div"] == fs]
    cur = rows[0]
    pe = cur["period_end"]
    prev = next((r for r in rows if r["period_end"].year == pe.year - 1 and r["period_end"].month == pe.month), None)
    yoy = lambda k: (round((float(cur[k]) - float(prev[k])) / abs(float(prev[k])) * 100, 1)
                     if prev and cur[k] is not None and prev[k] not in (None, 0) else None)
    return {"label": f"{pe.year}년 {cur['quarter']}분기" if cur.get("quarter") else f"{pe:%Y.%m}", "basis": "연결" if fs == "consolidated" else "별도",
            "revenue": money(cur["revenue"]), "operating_income": money(cur["operating_income"]), "net_income": money(cur["net_income"]),
            "revenue_yoy": yoy("revenue"), "op_yoy": yoy("operating_income")}


def add_snippets(db, items: list[Item]) -> None:
    news = [int(i.ref.split(":")[1]) for i in items if i.ref.startswith("news:")]
    discs = [i.ref.split(":")[1] for i in items if i.ref.startswith("disc:")]
    snip: dict[str, str] = {}
    if news:
        for r in _rows(db, NEWS_SNIP_SQL, ids=news):
            t = (r["summary"] or "").strip()
            snip[f"news:{r['id']}"] = t if len(t) >= 40 else (r["lead"] or r["chunk"] or t or "")
    if discs:
        for r in _rows(db, DISC_SNIP_SQL, ids=discs):
            snip[f"disc:{r['rcept_no']}"] = r["text"] or ""
    for i in items:
        # 정기보고서 첫 청크는 작성 기준 같은 상투 문구라 넣지 않는다 (제목만으로 충분)
        if i.kind == "공시" and re.search(r"(분기|반기|사업)보고서", i.title):
            i.snippet = ""
            continue
        i.snippet = re.sub(r"\s+", " ", snip.get(i.ref, "")).strip()[:300]


def company_names(name: str, symbol: str) -> list[str]:
    """뉴스 제목 필터용 이름: 종목 이름 + configs/stock_aliases.yaml + 판정 사전 별칭."""
    from pipelines.tracking.lexicon import load_lexicon
    from pipelines.updates.candidates import company_terms, load_symbol_aliases
    names = company_terms(name, symbol, None, load_symbol_aliases())
    try:
        names += [a for a, s in load_lexicon().aliases if s == symbol and len(a) >= 2]
    except Exception:
        pass
    return list(dict.fromkeys(names))


def build_report(db, user_id: int, codes: list[str] | None = None, today: date | None = None,
                 market: bool = True, now: datetime | None = None,
                 llm=None) -> dict[str, Any]:
    """보고서 content. codes가 없으면 내 종목 전부. llm(메시지→dict)을 주면 흐름 문장을 LLM으로 쓴다(2단계), 없으면 코드 문장."""
    today = today or datetime.now(SEOUL).date()
    monday, friday = last_week(today)
    start = datetime.combine(monday, time.min, SEOUL)
    end = datetime.combine(friday + timedelta(days=1), time.min, SEOUL)
    window = {"start": start, "end": end, "mon": monday, "fri": friday}
    mine = _rows(db, STOCK_SQL, u=user_id)
    stocks = [s for s in mine if not codes or s["code"] in codes]
    warnings: list[str] = []
    sections, all_items = [], []
    for s in stocks:
        p = price_block(_rows(db, PRICES_SQL, s=s["code"], since=monday - timedelta(days=10), until=friday), monday, friday)
        if p is None:
            warnings.append(f"{s['name']}: 그 주 시세가 없어 뺐어요")
            continue
        # 금요일 시세가 아직 없는 건 정상이다 (2026-11-23 확인). 머리·지수는 종목의 실제 마지막 거래일에 맞춘다
        items = pick_disclosures(_rows(db, DISC_SQL, s=s["code"], mon=monday, fri=friday))
        ctx_news = pick_news(_rows(db, NEWS_SQL, s=s["code"], start=start, end=end), company_names(s["name"], s["code"]), limit=10)
        shown = {i.ref for i in sorted(ctx_news, key=lambda i: -i.score)[:NEWS_PER_STOCK]}
        for i in ctx_news:
            i.show = i.ref in shown                       # 화면 목록은 3건, 나머지는 이슈 정리 근거
        items += ctx_news
        links = _memo_links(db, user_id, s["code"], window)
        refs = {i.ref for i in items}
        for m in links:                                   # 메모 카드 근거가 목록에 없으면 더한다
            for it in m.linked.values():
                if it.ref not in refs:
                    items.append(it)
                    refs.add(it.ref)
                else:
                    same = next(i for i in items if i.ref == it.ref)
                    same.linked = same.show = True
        items.sort(key=lambda i: (i.day, i.kind != "공시"))
        if llm is not None:
            add_snippets(db, items)
        all_items += items
        sections.append({"s": s, "p": p, "items": items, "links": links})
    # 출처 번호: 보고서 전체에서 날짜순 (공시 먼저)
    order = {id(sec): k for k, sec in enumerate(sections)}
    numbered = sorted(((it, sec) for sec in sections for it in sec["items"]),
                      key=lambda x: (not x[0].show, x[0].day, x[0].kind != "공시", order[id(x[1])]))   # 화면 목록 먼저, 이슈 근거는 뒤 번호
    sources = []
    for n, (it, sec) in enumerate(numbered, 1):
        it.no = n
        sources.append({"no": n, "text": f"[{n}] {it.src or '뉴스'} · {sec['s']['name']} {it.title} · {it.day:%Y.%m.%d}",
                        "code": sec["s"]["code"], "ref": it.ref, "url": it.url})
    out_stocks = []
    story_meta = {"llm_calls": 0, "usage": {"input": 0, "output": 0}, "fallbacks": []}
    for sec in sections:
        s, p, items, links = sec["s"], sec["p"], sec["items"], sec["links"]
        shown_items = [i for i in items if i.show]
        story, issues, source = code_story(p, shown_items), "", "code"
        if llm is not None:
            from .story import llm_stock
            story, issues, meta = llm_stock(s["name"], p, items, llm, story)
            source = meta["source"]
            story_meta["llm_calls"] += meta["tries"]
            for k in story_meta["usage"]:
                story_meta["usage"][k] += meta["usage"][k]
            if meta["problems"]:
                story_meta["fallbacks"].append({"name": s["name"], "problems": meta["problems"]})
            if meta.get("removed"):
                story_meta.setdefault("removed", []).append({"name": s["name"], "sentences": meta["removed"]})
        for m in links:                                    # 번호가 붙은 뒤 같은 객체로 맞춘다
            m.linked = {ref: next(i for i in items if i.ref == ref) for ref in m.linked}
        dates = p["trade_dates"]
        out_stocks.append({
            "stock_code": s["code"], "name": s["name"], "own": "보유" if s["status"] == "holding" else "관심",
            "pct": p["pct"], "close": p["close"], "prev": p["prev"], "closes": p["closes"], "yr": p["yr"],
            "hi": p["hi"], "lo": p["lo"], "vol": p["vol"], "trade_dates": [d.isoformat() for d in dates],
            "events": [[it.day.weekday(), it.no, "g" if it.kind == "공시" else "n"] for it in shown_items if monday <= it.day <= friday],
            "counts": {"공시": sum(1 for i in shown_items if i.kind == "공시"), "뉴스": sum(1 for i in shown_items if i.kind == "뉴스")},
            "story": story, "story_source": source, "issues": issues,
            "items": [{"no": i.no, "kind": i.kind, "date": md(i.day), "title": i.title, "src": i.src, "ref": i.ref,
                       "url": i.url, "linked": i.linked} for i in shown_items],
            "issue_refs": [i.no for i in items if not i.show],
            "valuation": valuation(db, s["code"], dates[-1], p["close"]),
            "quarter": quarter_block(db, s["code"], dates[-1]),
            "memo": memo_section(links),
            "watch": watch_lines(links, p["close"], dates[-1], bool(shown_items)),
        })
    week, title = week_label(monday)
    last_day = max((date.fromisoformat(x["trade_dates"][-1]) for x in out_stocks), default=friday)
    n_days = max((len(x["trade_dates"]) for x in out_stocks), default=0)
    days = [monday + timedelta(days=k) for k in range(5)]
    mk = None
    if market:
        from .market import market_section
        mk = market_section(db, monday, last_day, start, end, llm, first_no=len(sources) + 1)
        for i in mk["items"]:
            sources.append({"no": i["no"], "text": f"[{i['no']}] {i['src'] or '뉴스'} · {i['title']} · {i['day']:%Y.%m.%d}",
                            "code": "", "ref": i["ref"], "url": i["url"]})
        story_meta["llm_calls"] += mk["meta"]["tries"]
        for k in story_meta["usage"]:
            story_meta["usage"][k] += mk["meta"]["usage"][k]
        if mk["meta"]["problems"]:
            story_meta["fallbacks"].append({"name": "국내 증시", "problems": mk["meta"]["problems"]})
        if mk["meta"].get("removed"):
            story_meta.setdefault("removed", []).append({"name": "국내 증시", "sentences": mk["meta"]["removed"]})
    return {
        "period_start": monday.isoformat(), "period_end": friday.isoformat(),
        "week": week, "title": title,
        "range": f"{md(monday)}({WEEKDAYS[0]}) ~ {md(last_day)}({WEEKDAYS[last_day.weekday()]})",
        "trade_days": n_days, "as_of": last_day.isoformat(),
        "days": [f"{md(d)} {WEEKDAYS[d.weekday()]}" for d in days], "days_short": list(WEEKDAYS[:5]),
        "made_at": (now or datetime.now(SEOUL)).astimezone(SEOUL).strftime("%m.%d %H:%M"),
        "market": mk["cells"] if mk else [],                              # 종목과 같은 날 기준
        "market_summary": mk["summary"] if mk else "", "flow": mk["flow"] if mk else [],
        "stocks": out_stocks, "sources": sources,
        "source_note": "시세는 KIS, 공시는 DART 원문을 바탕으로 정리했어요. 뉴스는 제목·언론사·날짜만 쓰고 원문 링크로 연결해요.",
        "warnings": warnings, "story_meta": story_meta,
    }
