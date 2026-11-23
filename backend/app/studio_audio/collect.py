"""DB → 오디오 브리프 (LLM에 줄 재료). 읽기만 한다.

기간 규칙 (2026-11-23):
- 사용자가 고른 기간 start~end는 '자료 날짜' 기준이다. 카드는 자료가 나온 다음 날 아침(매일 실행 06:30)에 만들어지므로
  카드 생성 시각이 [start+1일 0시, end+2일 0시) (한국 시간)인 카드를 넣는다. 예: 11.16~11.22 → 11.17~11.23 아침에 만든 카드.
- 카드 날짜(말할 때 쓰는 날짜)는 대표 근거의 발행일·접수일, 근거가 없으면 생성일 하루 전.
- 같은 종목에서 근거가 같은 카드(메모 여러 개에 붙은 같은 기사·공시)는 하나로 합치고 메모 이름을 모두 남긴다.
- 시세(prices_daily)·지수(market_indices)·환율(economic_observations)은 기간 안 첫 거래일과 마지막 거래일 종가만 쓴다.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.updates.repository import UpdatesRepository
from app.updates.service import UpdatesService

SEOUL = ZoneInfo("Asia/Seoul")
KIND_LABEL = {"disclosure": "공시", "news": "뉴스", "price_condition": "가격 조건", "answer": "질문 답"}
WEEKDAY = "월화수목금토일"
MEMO_BODY_CHARS = 220


@dataclass
class CardIn:
    uid: str                    # 브리프 안 번호 U1, U2 … (LLM이 refs로 쓴다)
    card_ids: list[int]
    stock_code: str
    kind: str                   # 공시 | 뉴스 | 가격 조건 | 질문 답
    data_date: str              # YYYY-MM-DD (근거 발행일)
    headline: str
    facts: list[str]
    memo_link: str
    item: str                   # 추적 항목 설명
    memo_ids: list[int]
    memo_titles: list[str]
    sources: list[dict[str, Any]]   # {kind, title, source, published_at, url}


@dataclass
class MemoIn:
    memo_id: int
    title: str
    body: str
    created: str                # YYYY-MM-DD
    items: list[str]


@dataclass
class PriceIn:
    first_date: str
    first_close: float
    last_date: str
    last_close: float
    change_pct: float | None


@dataclass
class StockIn:
    code: str
    name: str
    hold: str                   # 보유 | 관심
    memos: list[MemoIn] = field(default_factory=list)
    cards: list[CardIn] = field(default_factory=list)
    price: PriceIn | None = None
    more_cards: int = 0         # 카드가 상한을 넘어 브리프에서 뺀 수


@dataclass
class MarketRow:
    label: str
    unit: str
    last_date: str
    last: float
    prev: float | None
    first_date: str
    first: float


@dataclass
class Brief:
    user_id: int
    start: str
    end: str
    made_at: str
    stocks: list[StockIn]
    market: list[MarketRow]

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def news_stocks(self) -> list[StockIn]:
        return [s for s in self.stocks if s.cards]

    @property
    def quiet_stocks(self) -> list[StockIn]:
        return [s for s in self.stocks if not s.cards]

    def card(self, uid: str) -> CardIn | None:
        return next((c for s in self.stocks for c in s.cards if c.uid == uid), None)

    def stock(self, code: str) -> StockIn | None:
        return next((s for s in self.stocks if s.code == code), None)


def card_window(start: date, end: date) -> tuple[datetime, datetime]:
    return (datetime.combine(start + timedelta(days=1), time.min, SEOUL),
            datetime.combine(end + timedelta(days=2), time.min, SEOUL))


def day_label(iso: str) -> str:
    """'2026-11-18' → '11월 18일(수)'."""
    d = date.fromisoformat(iso[:10])
    return f"{d.month}월 {d.day}일({WEEKDAY[d.weekday()]})"


def _iso(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.astimezone(SEOUL).date().isoformat()
    return value.isoformat()[:10] if hasattr(value, "isoformat") else str(value)[:10]


def _facts(card: dict[str, Any], fallback: str) -> list[str]:
    out = []
    for f in card.get("facts") or []:
        t = f.get("text") if isinstance(f, dict) else f
        if isinstance(t, str) and t.strip():
            out.append(t.strip())
    return out or ([fallback.strip()] if fallback and fallback.strip() else [])


STOCKS_SQL = """
SELECT btrim(us.symbol) AS code, s.name, us.status::text AS status
FROM user_stocks us JOIN stocks s ON s.symbol = us.symbol
WHERE us.user_id = :uid AND us.deleted_at IS NULL
ORDER BY us.position NULLS LAST, us.created_at, us.symbol"""

MEMOS_SQL = """
SELECT m.id, btrim(m.symbol) AS code, m.title, m.content, m.created_at,
       coalesce(array_agg(ti.description ORDER BY ti.id) FILTER (WHERE ti.id IS NOT NULL), '{}') AS items
FROM memos m
LEFT JOIN tracking_items ti ON ti.memo_id = m.id AND ti.status::text = 'active'
WHERE m.user_id = :uid AND m.deleted_at IS NULL AND m.kind::text = 'note' AND m.ai_linked
  AND m.created_at < :until
GROUP BY m.id ORDER BY m.created_at DESC, m.id DESC"""

PRICE_SQL = """
SELECT trade_date, close FROM prices_daily
WHERE symbol = :code AND trade_date BETWEEN :start AND :end AND close IS NOT NULL ORDER BY trade_date"""

INDEX_SQL = """
SELECT trade_date AS day, close AS value FROM market_indices
WHERE code = :code AND trade_date <= :end AND trade_date >= :from_ AND close IS NOT NULL ORDER BY trade_date"""

OBS_SQL = """
SELECT observation_date AS day, value FROM economic_observations
WHERE indicator_code = :code AND observation_date <= :end AND observation_date >= :from_ AND value IS NOT NULL
ORDER BY observation_date"""

MARKET = [("코스피", "", INDEX_SQL, "KOSPI"), ("코스닥", "", INDEX_SQL, "KOSDAQ"), ("원/달러 환율", "원", OBS_SQL, "USD_KRW")]


def _market(db: Session, start: date, end: date) -> list[MarketRow]:
    out = []
    for label, unit, sql, code in MARKET:
        try:
            rows = db.execute(text(sql), {"code": code, "end": end, "from_": start - timedelta(days=10)}).all()
        except Exception:                                   # 지표 테이블이 없어도 오디오는 만든다
            db.rollback()
            continue
        if not rows:
            continue
        inside = [r for r in rows if r[0] >= start] or rows[-1:]
        last = rows[-1]
        prev = rows[-2] if len(rows) >= 2 else None
        out.append(MarketRow(label, unit, _iso(last[0]), float(last[1]), float(prev[1]) if prev else None,
                             _iso(inside[0][0]), float(inside[0][1])))
    return out


def _price(db: Session, code: str, start: date, end: date) -> PriceIn | None:
    rows = db.execute(text(PRICE_SQL), {"code": code, "start": start, "end": end}).all()
    if not rows:
        return None
    first, last = rows[0], rows[-1]
    pct = round((float(last[1]) - float(first[1])) / float(first[1]) * 100, 2) if float(first[1]) else None
    return PriceIn(_iso(first[0]), float(first[1]), _iso(last[0]), float(last[1]), pct if len(rows) > 1 else None)


def collect_brief(db: Session, user_id: int, start: date, end: date, symbols: list[str] | None = None,
                  max_cards_per_stock: int = 4, max_memos_per_stock: int = 3, now: datetime | None = None) -> Brief:
    now = now or datetime.now(SEOUL)
    lo, hi = card_window(start, end)
    hi = min(hi, now)
    stocks = []
    for r in db.execute(text(STOCKS_SQL), {"uid": user_id}).mappings():
        if symbols and r["code"] not in symbols:
            continue
        stocks.append(StockIn(r["code"], r["name"], "보유" if r["status"] == "holding" else "관심"))
    by_code = {s.code: s for s in stocks}

    # 카드 (업데이트 화면과 같은 모양을 쓰려고 UpdatesService의 변환을 그대로 쓴다)
    repo = UpdatesRepository(db)
    rows = [r for r in repo.cards(user_id, ai_linked_only=False, active_stocks_only=True, limit=500)
            if r["symbol"] in by_code and lo <= r["created_at"] < hi
            and (r["details"] or {}).get("answer_status") != "no_answer"]      # 답을 못 찾은 질문 카드는 방송하지 않는다
    rows.sort(key=lambda r: (r["created_at"], r["id"]))     # 오래된 것부터 (방송은 날짜 순서로 말한다)
    updates = UpdatesService(repo)._ai_updates(rows)
    merged: dict[tuple, CardIn] = {}
    n = 0
    for r, u in zip(rows, updates):
        details = r["details"] or {}
        srcs = [{"kind": "공시" if s["kind"] == "disclosure" else "뉴스", "title": s["title"] or "", "source": s["source"] or "",
                 "published_at": _iso(s["published_at"]), "url": s["url"]} for s in u["sources"]]
        key = (r["symbol"], u["type"], u["url"] or "", u["title"]) if srcs else (r["symbol"], "card", r["id"])
        if key in merged:
            c = merged[key]
            c.card_ids.append(int(r["id"]))
            if int(r["memo_id"]) not in c.memo_ids:
                c.memo_ids.append(int(r["memo_id"]))
                c.memo_titles.append(r["memo_title"] or "")
            continue
        dates = [s["published_at"] for s in srcs if s["published_at"]]
        data_date = max(dates) if dates else _iso(r["created_at"] - timedelta(days=1))
        if r["type"] == "price_condition" and r["observed_trade_date"] is not None:
            data_date = _iso(r["observed_trade_date"])
        headline = details.get("headline") or r["title"] or ""
        n += 1
        merged[key] = CardIn(
            uid=f"U{n}", card_ids=[int(r["id"])], stock_code=r["symbol"], kind=KIND_LABEL.get(r["type"], "뉴스"),
            data_date=data_date, headline=headline.strip(), facts=_facts(details, r["summary"] or ""),
            memo_link=(details.get("memo_link") or r["reason"] or "").strip(), item=r["item_description"] or "",
            memo_ids=[int(r["memo_id"])], memo_titles=[r["memo_title"] or ""], sources=srcs)
    for c in merged.values():
        st = by_code[c.stock_code]
        if len(st.cards) < max_cards_per_stock:
            st.cards.append(c)
        else:
            st.more_cards += 1

    # 메모 (카드가 붙은 메모 먼저, 그다음 최근 메모)
    linked = {mid for st in stocks for c in st.cards for mid in c.memo_ids}
    memos = [dict(m) for m in db.execute(text(MEMOS_SQL), {"uid": user_id, "until": hi}).mappings()]
    memos.sort(key=lambda m: (m["id"] not in linked, -m["created_at"].timestamp()))
    for m in memos:
        st = by_code.get(m["code"])
        if st is None or len(st.memos) >= max_memos_per_stock:
            continue
        body = " ".join((m["content"] or "").split())
        st.memos.append(MemoIn(int(m["id"]), (m["title"] or "").strip(),
                               body[:MEMO_BODY_CHARS] + ("…" if len(body) > MEMO_BODY_CHARS else ""),
                               _iso(m["created_at"]), list(m["items"] or [])))

    for st in stocks:
        st.price = _price(db, st.code, start, end)
    # 방송 순서: 새 소식이 있는 종목(보유 먼저, 카드 많은 순) → 없는 종목
    stocks.sort(key=lambda s: (not s.cards, s.hold != "보유", -len(s.cards)))
    k = 0                                                    # 번호는 방송 순서로 다시 (상한으로 빠진 카드 자리도 메운다)
    for st in stocks:
        for c in st.cards:
            k += 1
            c.uid = f"U{k}"
    return Brief(user_id, start.isoformat(), end.isoformat(), now.isoformat(timespec="seconds"), stocks,
                 _market(db, start, end))
