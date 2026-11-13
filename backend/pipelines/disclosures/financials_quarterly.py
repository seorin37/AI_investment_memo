"""분기 단독 손익 계산·저장 (마이그레이션 0016).

financials·financials_fin의 손익은 회계연도 누적값이다. 같은 회계연도 안에서
Q1 = q1, Q2 = half − q1, Q3 = q3 − half, Q4 = annual − q3 으로 분기 단독값을 만든다.
누적 원본은 건드리지 않는다.

- 회계연도 말 = period_end + {q1: 9, half: 6, q3: 3, annual: 0}개월 (월말). 결산월이 12월이 아니어도 같은 규칙.
- 원천 행이 있는 분기만 행을 만든다. 값을 못 구하면 NULL과 사유를 남긴다:
  missing_prev_period(앞 기간 행 없음) · source_null(원천 값 NULL) · fs_div_mismatch(연결·별도 섞임) ·
  needs_review(매출성 항목의 단독값이 음수 = 누적 역전).
- recompute()는 한 회사·한 회계연도를 지우고 다시 쓴다(정정으로 q1이 바뀌면 Q2도 바뀌므로). commit은 호출자 몫.
"""

from __future__ import annotations

import calendar
import json
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.engine import Connection

OFFSET_MONTHS = {"q1": 9, "half": 6, "q3": 3, "annual": 0}
QUARTER = {"q1": 1, "half": 2, "q3": 3, "annual": 4}
PREV = {"half": "q1", "q3": "half", "annual": "q3"}

GENERAL_FLOWS = ("revenue", "operating_income", "net_income")
FIN_FLOWS = ("net_interest_income", "fee_income", "loan_loss_provision", "insurance_revenue", "securities_operating_revenue")
# 단독값이 음수면 누적 역전으로 보고 저장하지 않는 항목 (이익·충당금은 음수가 정상일 수 있어 제외)
NON_NEGATIVE = {"revenue", "insurance_revenue", "securities_operating_revenue"}

TABLES = {
    "general": {"source": "financials", "target": "financials_quarterly", "flows": GENERAL_FLOWS},
    "fin": {"source": "financials_fin", "target": "financials_fin_quarterly", "flows": FIN_FLOWS},
}


def month_end(year: int, month: int) -> date:
    return date(year, month, calendar.monthrange(year, month)[1])


def add_months(d: date, months: int) -> date:
    """월말 기준으로 months개월 뒤의 월말."""
    index = d.year * 12 + (d.month - 1) + months
    return month_end(index // 12, index % 12 + 1)


def fiscal_year_end(period_end: date, period_type: str) -> date:
    return add_months(period_end, OFFSET_MONTHS[period_type])


@dataclass
class SourceRow:
    period_end: date
    period_type: str
    fs_div: str | None
    values: dict[str, Decimal | None]


@dataclass
class QuarterRow:
    period_end: date
    fiscal_year_end: date
    quarter: int
    fs_div: str | None
    method: str
    values: dict[str, Decimal | None] = field(default_factory=dict)
    null_reasons: dict[str, str] = field(default_factory=dict)


def derive(rows: list[SourceRow], flows: tuple[str, ...]) -> list[QuarterRow]:
    """한 회사·한 회계연도의 누적 원천 행 → 분기 단독 행. 순수 함수 (DB 없음)."""
    by_type = {r.period_type: r for r in rows}
    if not by_type:
        return []
    fy_end = fiscal_year_end(rows[0].period_end, rows[0].period_type)
    out: list[QuarterRow] = []
    for ptype in ("q1", "half", "q3", "annual"):
        cur = by_type.get(ptype)
        if cur is None:
            continue
        prev = by_type.get(PREV[ptype]) if ptype != "q1" else None
        q = QuarterRow(period_end=cur.period_end, fiscal_year_end=fy_end, quarter=QUARTER[ptype], fs_div=cur.fs_div,
                       method="reported" if ptype == "q1" else "derived")
        for col in flows:
            value, reason = _one(col, cur, prev, ptype)
            q.values[col] = value
            if reason:
                q.null_reasons[col] = reason
        out.append(q)
    return out


def _one(col: str, cur: SourceRow, prev: SourceRow | None, ptype: str) -> tuple[Decimal | None, str | None]:
    if cur.values.get(col) is None:
        return None, "source_null"
    if ptype == "q1":
        return cur.values[col], None
    if prev is None:
        return None, "missing_prev_period"
    if prev.values.get(col) is None:
        return None, "source_null"
    if cur.fs_div != prev.fs_div:
        return None, "fs_div_mismatch"
    value = cur.values[col] - prev.values[col]
    if col in NON_NEGATIVE and value < 0:
        return None, "needs_review"
    return value, None


# ─── DB ─────────────────────────────────────────────────────────────

def _fetch(conn: Connection, kind: str, symbol: str, fy_end: date) -> list[SourceRow]:
    """회계연도 말 fy_end에 속하는 원천 행 (q1은 fy_end − 9개월 …). 금융 표는 fs_div를 financials에서 가져온다."""
    spec = TABLES[kind]
    cols = ", ".join(f"s.{c}" for c in spec["flows"])
    fs = "s.fs_div" if kind == "general" else "f.fs_div"
    join = "" if kind == "general" else (
        " LEFT JOIN financials f ON f.symbol = s.symbol AND f.period_end = s.period_end AND f.period_type = s.period_type")
    rows = conn.execute(
        text(f"SELECT s.period_end, s.period_type::text AS period_type, {fs} AS fs_div, {cols}"
             f" FROM {spec['source']} s{join}"
             " WHERE s.symbol = :s AND s.period_end > :lo AND s.period_end <= :hi"),
        {"s": symbol, "lo": add_months(fy_end, -12), "hi": fy_end},
    ).mappings().all()
    out = []
    for r in rows:
        if fiscal_year_end(r["period_end"], r["period_type"]) != fy_end:
            continue  # 결산월이 바뀐 해 등 다른 회계연도 행
        out.append(SourceRow(r["period_end"], r["period_type"], r["fs_div"], {c: r[c] for c in spec["flows"]}))
    return out


def recompute(conn: Connection, kind: str, symbol: str, fy_end: date) -> int:
    """한 회사·한 회계연도의 분기 행을 지우고 다시 쓴다. 쓴 행 수 반환."""
    spec = TABLES[kind]
    quarters = derive(_fetch(conn, kind, symbol, fy_end), spec["flows"])
    conn.execute(text(f"DELETE FROM {spec['target']} WHERE symbol = :s AND fiscal_year_end = :fy"),
                 {"s": symbol, "fy": fy_end})
    if not quarters:
        return 0
    cols = ", ".join(spec["flows"])
    params = ", ".join(f":{c}" for c in spec["flows"])
    conn.execute(
        text(f"INSERT INTO {spec['target']} (symbol, period_end, fiscal_year_end, quarter, fs_div, {cols}, method, null_reasons)"
             f" VALUES (:symbol, :period_end, :fy, :quarter, :fs_div, {params}, :method, CAST(:null_reasons AS jsonb))"),
        [{"symbol": symbol, "period_end": q.period_end, "fy": q.fiscal_year_end, "quarter": q.quarter, "fs_div": q.fs_div,
          **q.values, "method": q.method, "null_reasons": json.dumps(q.null_reasons, ensure_ascii=False, sort_keys=True)}
         for q in quarters],
    )
    return len(quarters)


def recompute_for_period(conn: Connection, kind: str, symbol: str, period_end: date | str, period_type: str) -> int:
    """원천 한 기간을 쓴 직후 호출: 그 기간이 속한 회계연도를 다시 계산."""
    if isinstance(period_end, str):
        period_end = date.fromisoformat(period_end)
    return recompute(conn, kind, symbol, fiscal_year_end(period_end, period_type))


def fiscal_years(conn: Connection, kind: str, symbols: list[str] | None = None) -> list[tuple[str, date]]:
    """원천 표에 있는 (symbol, 회계연도 말) 전체."""
    spec = TABLES[kind]
    where = " WHERE symbol = ANY(:ss)" if symbols else ""
    rows = conn.execute(text(f"SELECT DISTINCT symbol, period_end, period_type::text FROM {spec['source']}{where}"),
                        {"ss": symbols} if symbols else {}).all()
    return sorted({(s.strip(), fiscal_year_end(p, t)) for s, p, t in rows})
