"""기업정보 페이지 계산 지표 (마이그레이션 0017, docs/company-page-data-gaps-plan.md).

한 행 = financials 한 행 (symbol, period_end). 원본 표는 읽기만 한다.

| 지표 | 공식 | 기간 |
|---|---|---|
| operating_margin | 분기 단독 영업이익 / 분기 단독 매출 x100 | 분기 (financials_quarterly) |
| net_margin | 분기 단독 순이익 / 분기 단독 매출 x100 | 분기 |
| roe | TTM 순이익 / 기말 자본총계 x100 | 최근 4분기 |
| debt_ratio | 부채총계 / 자본총계 x100 | 기말 |
| current_ratio | 유동자산 / 유동부채 x100 | 기말 |
| quick_ratio | (유동자산 - 재고자산) / 유동부채 x100 | 기말 |
| interest_coverage | TTM 영업이익 / TTM 이자비용 | 최근 4분기 |
| reserve_ratio | (자본잉여금 + 이익잉여금) / 자본금 x100 | 기말 |
| fin_operating_revenue | 금융사 분기 단독 영업수익 대용값 | 분기 |

- 매출이 없는 금융사는 이익률 분모로 fin_operating_revenue를 쓴다(화면에는 금융사 이익률을 띄우지 않지만 값은 저장, 11-16 결정).
- TTM(누적값 기준) = 이번 누적 + 직전 회계연도 연간 - 직전 회계연도 같은 기간 누적. 사업보고서 기간이면 연간 값 그대로.
- 재고자산이 '없음(not_reported·not_applicable)'이면 당좌비율에서 0으로 본다.
- NULL 사유 코드: source_null(원본 값 없음) · missing_prev_period(TTM에 필요한 이전 기간 없음) · fs_div_mismatch ·
  basis_mismatch(이자비용 근거가 기간마다 다름) · non_positive_base(분모 0 이하) · no_interest(이자비용 0) ·
  not_applicable_fin(금융사에 해당 없는 항목) · not_applicable(금융사가 아님) · not_reported/needs_review(이자비용 원천).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import text
from sqlalchemy.engine import Connection

from .financials_quarterly import add_months, fiscal_year_end

HUNDRED = Decimal(100)
CENT = Decimal("0.01")
BALANCE_COLS = ("total_assets", "total_liabilities", "total_equity", "current_assets", "current_liabilities", "inventories",
                "retained_earnings", "capital_stock", "capital_surplus")
FLOW_COLS = ("revenue", "operating_income", "net_income")
METRICS = ("operating_margin", "net_margin", "roe", "debt_ratio", "current_ratio", "quick_ratio", "interest_coverage",
           "reserve_ratio", "fin_operating_revenue")
BASIS_RANK = {"income_statement": 0, "cf_adjustment": 1, "cf_paid": 2}
FIN_REVENUE = {  # fin_type → (근거, 분기 단독 원천 컬럼들)
    "securities": ("securities_operating_revenue", ("securities_operating_revenue",)),
    "insurance": ("insurance_revenue", ("insurance_revenue",)),
    "bank": ("nii_plus_fee", ("net_interest_income", "fee_income")),
    "holding": ("nii_plus_fee", ("net_interest_income", "fee_income")),
    "other": ("revenue", ()),
}


@dataclass
class Period:
    period_end: date
    period_type: str
    fs_div: str | None
    values: dict[str, Decimal | None]  # financials 원본(누적 손익 + 잔액)
    reasons: dict[str, str] = field(default_factory=dict)  # financials.null_reasons
    interest: Decimal | None = None
    interest_basis: str | None = None
    interest_reason: str | None = None


@dataclass
class MetricRow:
    period_end: date
    period_type: str
    fiscal_year_end: date
    fs_div: str | None
    values: dict[str, Decimal | None] = field(default_factory=dict)
    interest_coverage_basis: str | None = None
    fin_revenue_basis: str | None = None
    null_reasons: dict[str, str] = field(default_factory=dict)


def _ratio(num: Decimal | None, den: Decimal | None, scale: Decimal = HUNDRED) -> tuple[Decimal | None, str | None]:
    if num is None or den is None:
        return None, "source_null"
    if den <= 0:
        return None, "non_positive_base"
    return (num / den * scale).quantize(CENT, rounding=ROUND_HALF_UP), None


def _ttm(p: Period, by_key: dict, get) -> tuple[Decimal | None, str | None]:
    """누적값 기준 최근 4분기 합. get(period) → 값."""
    cur = get(p)
    if cur is None:
        return None, "source_null"
    if p.period_type == "annual":
        return cur, None
    fy_prev = add_months(fiscal_year_end(p.period_end, p.period_type), -12)
    prev_annual = by_key.get((fy_prev, "annual"))
    prev_same = by_key.get((add_months(p.period_end, -12), p.period_type))
    if prev_annual is None or prev_same is None:
        return None, "missing_prev_period"
    if len({p.fs_div, prev_annual.fs_div, prev_same.fs_div}) != 1:
        return None, "fs_div_mismatch"
    a, s = get(prev_annual), get(prev_same)
    if a is None or s is None:
        return None, "source_null"
    return cur + a - s, None


def compute(periods: list[Period], quarters: dict[date, dict], fin_quarters: dict[date, dict],
            sector: str | None, fin_type: str | None) -> list[MetricRow]:
    """한 회사의 지표 행. 순수 함수 (DB 없음)."""
    by_key = {(p.period_end, p.period_type): p for p in periods}
    # (회계연도 말, 'annual') 키도 찾을 수 있게: 사업보고서 기간의 period_end가 곧 회계연도 말
    out: list[MetricRow] = []
    financial = sector == "financial"
    for p in sorted(periods, key=lambda x: x.period_end):
        row = MetricRow(p.period_end, p.period_type, fiscal_year_end(p.period_end, p.period_type), p.fs_div)
        v, put = row.values, row.null_reasons

        def setv(col: str, value: Decimal | None, reason: str | None) -> None:
            v[col] = value
            if value is None and reason:
                put[col] = reason

        # 금융사 영업수익 대용값 (분기 단독)
        q = quarters.get(p.period_end, {})
        fq = fin_quarters.get(p.period_end, {})
        if financial:
            basis, cols = FIN_REVENUE.get(fin_type or "other", FIN_REVENUE["other"])
            row.fin_revenue_basis = basis
            if basis == "revenue":
                rev = q.get("revenue")
            else:
                parts = [fq.get(c) for c in cols]
                rev = None if not fq or any(x is None for x in parts) else sum(parts, Decimal(0))
            setv("fin_operating_revenue", rev, None if rev is not None else "source_null")
            if rev is None:
                row.fin_revenue_basis = None
        else:
            setv("fin_operating_revenue", None, "not_applicable")

        # 분기 이익률
        base = q.get("revenue") if q.get("revenue") is not None else (v.get("fin_operating_revenue") if financial else None)
        if not q:
            setv("operating_margin", None, "missing_prev_period")
            setv("net_margin", None, "missing_prev_period")
        else:
            setv("operating_margin", *_ratio(q.get("operating_income"), base))
            setv("net_margin", *_ratio(q.get("net_income"), base))

        # 잔액 비율
        b = p.values
        setv("debt_ratio", *_ratio(b.get("total_liabilities"), b.get("total_equity")))
        if financial and b.get("current_assets") is None:
            setv("current_ratio", None, "not_applicable_fin")
            setv("quick_ratio", None, "not_applicable_fin")
        else:
            setv("current_ratio", *_ratio(b.get("current_assets"), b.get("current_liabilities")))
            inv = b.get("inventories")
            if inv is None and p.reasons.get("inventories") in ("not_reported", "not_applicable"):
                inv = Decimal(0)
            quick_num = None if b.get("current_assets") is None or inv is None else b["current_assets"] - inv
            setv("quick_ratio", *_ratio(quick_num, b.get("current_liabilities")))
        cs, re_ = b.get("capital_surplus"), b.get("retained_earnings")
        setv("reserve_ratio", *_ratio(None if cs is None or re_ is None else cs + re_, b.get("capital_stock")))

        # TTM 지표
        ni, ni_reason = _ttm(p, by_key, lambda x: x.values.get("net_income"))
        if ni is None:
            setv("roe", None, ni_reason)
        else:
            setv("roe", *_ratio(ni, b.get("total_equity")))

        oi, oi_reason = _ttm(p, by_key, lambda x: x.values.get("operating_income"))
        it, it_reason = _ttm(p, by_key, lambda x: x.interest)
        if it is None and p.interest is None and p.interest_reason:
            it_reason = p.interest_reason
        if it is not None and p.period_type != "annual":
            fy_prev = add_months(fiscal_year_end(p.period_end, p.period_type), -12)
            bases = {p.interest_basis, by_key[(fy_prev, "annual")].interest_basis,
                     by_key[(add_months(p.period_end, -12), p.period_type)].interest_basis}
            if len(bases) != 1:
                it, it_reason = None, "basis_mismatch"
        if oi is None:
            setv("interest_coverage", None, oi_reason)
        elif it is None:
            setv("interest_coverage", None, it_reason)
        elif it == 0:
            setv("interest_coverage", None, "no_interest")
        else:
            setv("interest_coverage", (oi / it).quantize(CENT, rounding=ROUND_HALF_UP), None)
            row.interest_coverage_basis = p.interest_basis
        out.append(row)
    return out


# ─── DB ─────────────────────────────────────────────────────────────

def _load(conn: Connection, symbol: str) -> tuple[list[Period], dict, dict, str | None, str | None]:
    rows = conn.execute(text(
        f"SELECT f.period_end, f.period_type::text AS period_type, f.fs_div, f.null_reasons, {', '.join('f.' + c for c in FLOW_COLS + BALANCE_COLS)},"
        " m.interest_cost, m.interest_cost_basis, m.null_reasons AS m_reasons"
        " FROM financials f LEFT JOIN financial_metrics m ON m.symbol = f.symbol AND m.period_end = f.period_end"
        " WHERE f.symbol = :s"), {"s": symbol}).mappings().all()
    periods = [Period(r["period_end"], r["period_type"], r["fs_div"], {c: r[c] for c in FLOW_COLS + BALANCE_COLS},
                      dict(r["null_reasons"] or {}), r["interest_cost"], r["interest_cost_basis"],
                      (r["m_reasons"] or {}).get("interest_cost")) for r in rows]
    quarters = {r["period_end"]: dict(r) for r in conn.execute(text(
        "SELECT period_end, revenue, operating_income, net_income FROM financials_quarterly WHERE symbol = :s"), {"s": symbol}).mappings()}
    fin_quarters = {r["period_end"]: dict(r) for r in conn.execute(text(
        "SELECT period_end, net_interest_income, fee_income, insurance_revenue, securities_operating_revenue"
        " FROM financials_fin_quarterly WHERE symbol = :s"), {"s": symbol}).mappings()}
    stock = conn.execute(text("SELECT sector::text, fin_type FROM stocks WHERE symbol = :s"), {"s": symbol}).first()
    return periods, quarters, fin_quarters, (stock[0] if stock else None), (stock[1] if stock else None)


def set_interest(conn: Connection, symbol: str, period_end: date | str, period_type: str, fs_div: str | None,
                 interest: tuple[Decimal | None, str | None, str | None]) -> None:
    """재무 적재 때 고른 이자비용 누적값을 저장한다 (비율은 recompute_symbol이 채운다)."""
    if isinstance(period_end, str):
        period_end = date.fromisoformat(period_end)
    value, basis, reason = interest
    reasons = json.dumps({"interest_cost": reason} if value is None and reason else {}, ensure_ascii=False)
    conn.execute(text(
        "INSERT INTO financial_metrics (symbol, period_end, period_type, fiscal_year_end, fs_div, interest_cost, interest_cost_basis, null_reasons)"
        " VALUES (:s, :p, CAST(:t AS report_period), :fy, :fs, :v, :b, CAST(:r AS jsonb))"
        " ON CONFLICT (symbol, period_end) DO UPDATE SET interest_cost = EXCLUDED.interest_cost,"
        " interest_cost_basis = EXCLUDED.interest_cost_basis, fs_div = EXCLUDED.fs_div,"
        " null_reasons = (financial_metrics.null_reasons - 'interest_cost') || EXCLUDED.null_reasons, computed_at = now()"),
        {"s": symbol, "p": period_end, "t": period_type, "fy": fiscal_year_end(period_end, period_type), "fs": fs_div,
         "v": value, "b": basis, "r": reasons})


def recompute_symbol(conn: Connection, symbol: str) -> int:
    """한 회사의 지표를 모두 다시 계산한다. financials에 없는 기간의 행은 지운다. 쓴 행 수 반환. commit은 호출자 몫."""
    periods, quarters, fin_quarters, sector, fin_type = _load(conn, symbol)
    conn.execute(text("DELETE FROM financial_metrics m WHERE m.symbol = :s AND NOT EXISTS"
                      " (SELECT 1 FROM financials f WHERE f.symbol = m.symbol AND f.period_end = m.period_end)"), {"s": symbol})
    rows = compute(periods, quarters, fin_quarters, sector, fin_type)
    if not rows:
        return 0
    by_end = {p.period_end: p for p in periods}
    sets = ", ".join(f"{c} = EXCLUDED.{c}" for c in METRICS)
    conn.execute(text(
        f"INSERT INTO financial_metrics (symbol, period_end, period_type, fiscal_year_end, fs_div, {', '.join(METRICS)},"
        " interest_coverage_basis, fin_revenue_basis, null_reasons, computed_at)"
        f" VALUES (:symbol, :period_end, CAST(:period_type AS report_period), :fy, :fs_div, {', '.join(':' + c for c in METRICS)},"
        " :icb, :frb, CAST(:null_reasons AS jsonb), now())"
        f" ON CONFLICT (symbol, period_end) DO UPDATE SET {sets}, period_type = EXCLUDED.period_type,"
        " fiscal_year_end = EXCLUDED.fiscal_year_end, fs_div = EXCLUDED.fs_div,"
        " interest_coverage_basis = EXCLUDED.interest_coverage_basis, fin_revenue_basis = EXCLUDED.fin_revenue_basis,"
        " null_reasons = EXCLUDED.null_reasons, computed_at = now()"),
        [{"symbol": symbol, "period_end": r.period_end, "period_type": r.period_type, "fy": r.fiscal_year_end, "fs_div": r.fs_div,
          **r.values, "icb": r.interest_coverage_basis, "frb": r.fin_revenue_basis,
          "null_reasons": json.dumps({**r.null_reasons,
                                      **({"interest_cost": by_end[r.period_end].interest_reason}
                                         if by_end[r.period_end].interest is None and by_end[r.period_end].interest_reason else {})},
                                     ensure_ascii=False, sort_keys=True)}
         for r in rows])
    return len(rows)


def symbols(conn: Connection, only: list[str] | None = None) -> list[str]:
    where = " WHERE symbol = ANY(:ss)" if only else ""
    return sorted({s.strip() for (s,) in conn.execute(text(f"SELECT DISTINCT symbol FROM financials{where}"),
                                                       {"ss": only} if only else {})})
