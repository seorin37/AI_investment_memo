"""사건 공시 표준 비율 (마이그레이션 0018, 2026-11-17).

수시공시 정리값(disclosure_events.fields)의 금액·주식 수를 회사 규모와 견준 비율을 계산해 disclosure_event_metrics에 저장한다.
LLM이 계산하지 않아도 "유상증자가 영업이익의 몇 배야?", "자사주를 시가총액의 몇 % 사?", "배당성향은?"에 답할 수 있게.

| 사건 | 지표 | 공식 |
|---|---|---|
| rights_offering | raise_krw | Σ(신주 수 × 발행가) (보통·기타). 발행가가 없으면 자금 용도 합계 |
|  | dilution_pct | 신주 수(보통+기타) / 증자 전 보통주 수 x100 |
|  | raise_to_prev_op_income_x | raise_krw / 직전 사업연도 영업이익 (배) |
|  | raise_to_equity_pct | raise_krw / 최근 자본총계 x100 |
|  | raise_to_market_cap_pct | raise_krw / 접수일 전 시가총액 x100 |
| treasury_buy | amount_krw | 취득 예정 금액(직접 취득) 또는 신탁 계약 금액 |
|  | amount_to_market_cap_pct | amount_krw / 시가총액 x100 |
|  | shares_pct | 취득 예정 주식 수 / 상장주식 수 x100 |
| treasury_sell | amount_krw · amount_to_market_cap_pct · shares_pct | 처분 금액·주식 수 (신탁 해지는 해지 주식 수) |
| share_cancel | cancel_pct | 소각 주식 수 / 발행주식 총수 x100 |
|  | amount_to_market_cap_pct | 소각 금액 / 시가총액 x100 |
| dividend | payout_ratio_pct | 배당금 총액 / 직전 사업연도 지배주주 순이익 x100 (결산 배당만) |

- 분모는 공시 접수일에 공개돼 있던 값만 쓴다: 재무는 그 기간 정기보고서가 접수일 전에 접수된 최신 행(financials, 보고서 기록이 없으면 법정 기한 경과), 시가총액은 접수일 전 최근 거래일(prices_daily).
- 자회사 공시(is_subsidiary)는 계산하지 않는다 (subsidiary_event). 분모가 0 이하이면 non_positive_base, 없으면 missing_*.
- 분기·중간 배당은 연간 순이익과 견주면 배당성향이 낮게 나와 계산하지 않는다 (interim_dividend).
"""

from __future__ import annotations

import json
import logging
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import text
from sqlalchemy.engine import Connection

log = logging.getLogger(__name__)
CALC_VERSION = "2026-11-17.2"   # .2: 분모를 접수일에 공개된 재무로 제한
EVENT_TYPES = ("rights_offering", "treasury_buy", "treasury_sell", "share_cancel", "dividend")
CENT = Decimal("0.01")


def _d(v) -> Decimal | None:
    if v is None or isinstance(v, bool):
        return None
    try:
        return Decimal(str(v))
    except Exception:
        return None


def _ratio(num, den, scale: int = 100) -> tuple[float | None, str | None]:
    """(값, 사유). 분모가 없으면 missing, 0 이하이면 non_positive_base."""
    n, d = _d(num), _d(den)
    if n is None:
        return None, "source_null"
    if d is None:
        return None, "missing_base"
    if d <= 0:
        return None, "non_positive_base"
    return float((n / d * scale).quantize(CENT, ROUND_HALF_UP)), None


def _put(metrics: dict, reasons: dict, key: str, value_reason: tuple) -> None:
    value, reason = value_reason
    if value is not None:
        metrics[key] = value
    else:
        reasons[key] = reason


def _market_cap(ctx: dict) -> tuple[Decimal | None, dict | None]:
    m = ctx.get("market")
    if not m:
        return None, None
    cap = _d(m.get("market_cap"))
    source = "prices_daily.market_cap"
    if cap is None and _d(m.get("close")) is not None and _d(m.get("listed_shares")) is not None:
        cap, source = _d(m["close"]) * _d(m["listed_shares"]), "close×listed_shares"
    return cap, {"value": None if cap is None else int(cap), "trade_date": str(m.get("trade_date")), "source": source}


def compute(event_type: str, fields: dict, is_subsidiary: bool, ctx: dict) -> tuple[dict, dict, dict]:
    """(metrics, inputs, null_reasons). ctx: {prev_annual: {period_end, operating_income, net_income},
    equity: {period_end, total_equity}, market: {trade_date, market_cap, close, listed_shares}} (없으면 None)."""
    f = fields or {}
    metrics: dict = {}
    inputs: dict = {}
    reasons: dict = {}
    if is_subsidiary:
        return {}, {}, {"all": "subsidiary_event"}
    cap, cap_input = _market_cap(ctx)
    pa, eq = ctx.get("prev_annual"), ctx.get("equity")

    def use_cap(key: str, amount) -> None:
        if cap_input:
            inputs["market_cap"] = cap_input
        _put(metrics, reasons, key, _ratio(amount, cap) if cap_input else (None, "missing_market_cap"))

    def use_shares(key: str, shares) -> None:
        listed = _d((ctx.get("market") or {}).get("listed_shares"))
        if listed is not None:
            inputs["listed_shares"] = {"value": int(listed), "trade_date": str(ctx["market"].get("trade_date")),
                                       "source": "prices_daily.listed_shares"}
        _put(metrics, reasons, key, _ratio(shares, listed) if listed is not None else (None, "missing_listed_shares"))

    if event_type == "rights_offering":
        parts = [(_d(f.get(f"new_shares_{k}")), _d(f.get(f"issue_price_{k}"))) for k in ("common", "other")]
        priced = [s * p for s, p in parts if s is not None and p is not None]
        uses = [_d(v) for k, v in f.items() if k.startswith("use_") and _d(v) is not None]
        if priced:
            raise_krw, inputs["raise_source"] = sum(priced), "new_shares×issue_price"
        elif uses:
            raise_krw, inputs["raise_source"] = sum(uses), "use_of_funds_sum"
        else:
            raise_krw = None
        if raise_krw is not None:
            metrics["raise_krw"] = int(raise_krw)
        else:
            reasons["raise_krw"] = "source_null"
        new_total = sum(s for s, _ in parts if s is not None) if any(s is not None for s, _ in parts) else None
        _put(metrics, reasons, "dilution_pct", _ratio(new_total, f.get("shares_before_common")))
        if pa:
            inputs["prev_op_income"] = {"value": None if pa.get("operating_income") is None else int(pa["operating_income"]),
                                        "period_end": str(pa["period_end"]), "source": "financials.annual"}
        _put(metrics, reasons, "raise_to_prev_op_income_x",
             _ratio(raise_krw, (pa or {}).get("operating_income"), 1) if pa else (None, "missing_prev_annual"))
        if eq:
            inputs["equity"] = {"value": None if eq.get("total_equity") is None else int(eq["total_equity"]),
                                "period_end": str(eq["period_end"]), "source": "financials.total_equity"}
        _put(metrics, reasons, "raise_to_equity_pct",
             _ratio(raise_krw, (eq or {}).get("total_equity")) if eq else (None, "missing_equity"))
        use_cap("raise_to_market_cap_pct", raise_krw)
    elif event_type in ("treasury_buy", "treasury_sell"):
        amount = _d(f.get("amount_common"))
        if amount is None:
            amount = _d(f.get("trust_amount")) if event_type == "treasury_buy" else None
        shares = _d(f.get("shares_common")) if f.get("shares_common") is not None else _d(f.get("cancel_shares_common"))
        if amount is not None:
            metrics["amount_krw"] = int(amount)
        else:
            reasons["amount_krw"] = "source_null"
        use_cap("amount_to_market_cap_pct", amount)
        use_shares("shares_pct", shares)
    elif event_type == "share_cancel":
        _put(metrics, reasons, "cancel_pct", _ratio(f.get("shares_common"), f.get("issued_common")))
        if _d(f.get("amount_krw")) is not None:
            metrics["amount_krw"] = int(_d(f["amount_krw"]))
        use_cap("amount_to_market_cap_pct", f.get("amount_krw"))
    elif event_type == "dividend":
        if _d(f.get("total_krw")) is not None:
            metrics["total_krw"] = int(_d(f["total_krw"]))
        if not pa:
            reasons["payout_ratio_pct"] = "missing_prev_annual"
        elif not _is_year_end(f, pa):
            reasons["payout_ratio_pct"] = "interim_dividend"
        else:
            inputs["prev_net_income"] = {"value": None if pa.get("net_income") is None else int(pa["net_income"]),
                                         "period_end": str(pa["period_end"]), "source": "financials.annual(지배주주)"}
            _put(metrics, reasons, "payout_ratio_pct", _ratio(f.get("total_krw"), pa.get("net_income")))
    return metrics, inputs, reasons


def _is_year_end(f: dict, pa: dict) -> bool:
    """결산 배당인가: 배당 종류에 '결산'이 있거나, 배당기준일 월·일이 직전 사업연도 끝과 같다."""
    kind = str(f.get("dividend_kind") or "")
    if "결산" in kind:
        return True
    if any(w in kind for w in ("분기", "중간")):
        return False
    rd = str(f.get("record_date") or "")
    end = pa.get("period_end")
    return bool(rd and end and rd[5:10] == str(end)[5:10])


# ── DB ─────────────────────────────────────────────
EVENTS_SQL = """SELECT e.rcept_no, btrim(d.symbol) AS symbol, d.rcept_dt, e.event_type, e.fields, e.is_subsidiary
FROM disclosure_events e JOIN disclosures d ON d.rcept_no = e.rcept_no
WHERE e.event_type = ANY(:types) AND d.symbol IS NOT NULL{where} ORDER BY d.rcept_dt"""
# 공시 접수일에 '이미 공개된' 재무만 쓴다 (2026-11-17 수정: 기간 끝만 보면 10-22 사건에 11-16 접수된 3분기 자본총계가 들어갔다).
# 그 기간 정기보고서가 접수일 전에 접수됐거나, 보고서 기록이 DB에 없으면 법정 제출 기한(분기·반기 45일, 사업보고서 90일)이 지났을 때.
_PUBLISHED = """(EXISTS (SELECT 1 FROM disclosures r WHERE btrim(r.symbol) = f.symbol AND r.period_end = f.period_end
      AND r.kind IN ('quarterly', 'half', 'annual') AND r.rcept_dt < :d)
  OR (NOT EXISTS (SELECT 1 FROM disclosures r WHERE btrim(r.symbol) = f.symbol AND r.period_end = f.period_end
      AND r.kind IN ('quarterly', 'half', 'annual'))
      AND f.period_end + (CASE WHEN f.period_type = 'annual' THEN 90 ELSE 45 END) < :d))"""
PREV_ANNUAL_SQL = f"""SELECT f.period_end, f.operating_income, f.net_income FROM financials f
WHERE f.symbol = :s AND f.period_type = 'annual' AND f.period_end < :d AND {_PUBLISHED}
ORDER BY f.period_end DESC LIMIT 1"""
EQUITY_SQL = f"""SELECT f.period_end, f.total_equity FROM financials f
WHERE f.symbol = :s AND f.total_equity IS NOT NULL AND f.period_end < :d AND {_PUBLISHED}
ORDER BY f.period_end DESC LIMIT 1"""
MARKET_SQL = """SELECT trade_date, market_cap, close, listed_shares FROM prices_daily
WHERE symbol = :s AND trade_date < :d ORDER BY trade_date DESC LIMIT 1"""


def context(conn: Connection, symbol: str, base: date) -> dict:
    p = {"s": symbol, "d": base}
    one = lambda sql: (lambda r: dict(r) if r else None)(conn.execute(text(sql), p).mappings().first())
    return {"prev_annual": one(PREV_ANNUAL_SQL), "equity": one(EQUITY_SQL), "market": one(MARKET_SQL)}


def events(conn: Connection, only: list[str] | None = None) -> list[dict]:
    where = " AND btrim(d.symbol) = ANY(:ss)" if only else ""
    params = {"types": list(EVENT_TYPES), **({"ss": only} if only else {})}
    return [dict(r) for r in conn.execute(text(EVENTS_SQL.format(where=where)), params).mappings().all()]


def compute_row(conn: Connection, ev: dict) -> dict:
    fields = ev["fields"] if isinstance(ev["fields"], dict) else json.loads(ev["fields"] or "{}")
    ctx = {} if ev["is_subsidiary"] else context(conn, ev["symbol"], ev["rcept_dt"])
    metrics, inputs, reasons = compute(ev["event_type"], fields, bool(ev["is_subsidiary"]), ctx)
    return {"rcept_no": ev["rcept_no"], "symbol": ev["symbol"], "event_type": ev["event_type"], "base_date": ev["rcept_dt"],
            "metrics": metrics, "inputs": inputs, "null_reasons": reasons}


UPSERT_SQL = """INSERT INTO disclosure_event_metrics (rcept_no, symbol, event_type, base_date, metrics, inputs, null_reasons, calc_version)
VALUES (:rcept_no, :symbol, :event_type, :base_date, CAST(:metrics AS jsonb), CAST(:inputs AS jsonb), CAST(:null_reasons AS jsonb), :v)
ON CONFLICT (rcept_no) DO UPDATE SET symbol = EXCLUDED.symbol, event_type = EXCLUDED.event_type, base_date = EXCLUDED.base_date,
  metrics = EXCLUDED.metrics, inputs = EXCLUDED.inputs, null_reasons = EXCLUDED.null_reasons,
  calc_version = EXCLUDED.calc_version, computed_at = now()"""


def save(conn: Connection, row: dict) -> None:
    conn.execute(text(UPSERT_SQL), {**row, "v": CALC_VERSION,
                                    **{k: json.dumps(row[k], ensure_ascii=False) for k in ("metrics", "inputs", "null_reasons")}})


# ── 적재 직후 자동 계산 (2026-11-17) ─────────────────
# events_loader.upsert_event: 사건 공시를 저장한 직후 그 공시 하나를 계산한다.
# financials_loader.upsert_financials: 재무가 바뀌면 분모(직전 연도 영업이익·자본총계)가 바뀔 수 있어 그 회사 사건을 다시 계산한다.
# 비율 계산이 실패해도 원본(사건·재무) 저장은 그대로 끝나야 하므로 SAVEPOINT 안에서 돌리고 실패는 경고만 남긴다.
SYMBOL_EVENTS_SQL = """SELECT e.rcept_no, btrim(d.symbol) AS symbol, d.rcept_dt, e.event_type, e.fields, e.is_subsidiary
FROM disclosure_events e JOIN disclosures d ON d.rcept_no = e.rcept_no
WHERE {cond} AND e.event_type = ANY(:types)"""


def _table_ready(conn: Connection) -> bool:
    return conn.execute(text("SELECT to_regclass('public.disclosure_event_metrics')")).scalar() is not None


def refresh(conn: Connection, *, rcept_no: str | None = None, symbol: str | None = None) -> int:
    """rcept_no 하나 또는 symbol의 사건 전부를 다시 계산해 저장한다. 계산한 건수 (표가 없거나 실패하면 0)."""
    if (rcept_no is None) == (symbol is None):
        raise ValueError("rcept_no와 symbol 중 하나만 주세요")
    try:
        with conn.begin_nested():
            if not _table_ready(conn):
                return 0
            cond, params = ("e.rcept_no = :k", {"k": rcept_no}) if rcept_no else ("btrim(d.symbol) = :k", {"k": symbol})
            evs = [dict(r) for r in conn.execute(text(SYMBOL_EVENTS_SQL.format(cond=cond)),
                                                 {**params, "types": list(EVENT_TYPES)}).mappings().all()]
            for ev in evs:
                save(conn, compute_row(conn, ev))
            return len(evs)
    except Exception as exc:  # 비율 실패가 원본 저장을 막지 않게
        log.warning("사건 비율 계산 실패 (%s): %s: %s", rcept_no or symbol, type(exc).__name__, str(exc)[:200])
        return 0
