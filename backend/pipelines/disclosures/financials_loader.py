"""financials · financials_fin 적재 (WO-015, 금융 업종 컬럼·NULL 사유는 마이그레이션 0012).

함수는 Connection을 받아 쓰기만 하고 commit하지 않는다. 트랜잭션 경계는 호출자가 정한다
(실행 진입점은 기업·기간 하나당 `engine.begin()` 하나).
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from sqlalchemy import bindparam, text
from sqlalchemy.engine import Connection

from . import event_metrics, financial_metrics, financials_quarterly
from .financials import MappedPeriod


AMOUNT, PER_SHARE = "numeric(20,0)", "numeric(14,2)"
KEY_COLUMNS = {"symbol": "character(6)", "period_end": "date", "period_type": "report_period"}
FINANCIALS_VALUES = {
    "revenue": AMOUNT, "operating_income": AMOUNT, "net_income": AMOUNT, "total_assets": AMOUNT, "total_liabilities": AMOUNT,
    "total_equity": AMOUNT, "current_assets": AMOUNT, "current_liabilities": AMOUNT, "inventories": AMOUNT,
    "interest_expense": AMOUNT, "retained_earnings": AMOUNT, "eps": PER_SHARE, "bps": PER_SHARE,
    "capital_stock": AMOUNT, "capital_surplus": AMOUNT,
}
FIN_VALUES = {
    "net_interest_income": AMOUNT, "fee_income": AMOUNT, "loan_loss_provision": AMOUNT, "loans": AMOUNT, "deposits": AMOUNT,
    "insurance_revenue": AMOUNT, "securities_operating_revenue": AMOUNT,
}
RATIO = "numeric(8,2)"
FIN_RATIOS = {"bis_ratio": RATIO, "kics_ratio": RATIO, "ncr_ratio": RATIO}  # 공시 본문 추출 단계 소관
EXPECTED_COLUMNS = {
    "financials": {**KEY_COLUMNS, **FINANCIALS_VALUES, "fs_div": "text", "null_reasons": "jsonb"},
    "financials_fin": {**KEY_COLUMNS, **FIN_VALUES, **FIN_RATIOS, "null_reasons": "jsonb"},
}


class FinancialsPreflightError(RuntimeError):
    """적재 전 DB 점검 실패."""


def table_columns(conn: Connection, table: str) -> dict[str, str]:
    rows = conn.execute(
        text(
            "SELECT a.attname, format_type(a.atttypid, a.atttypmod) FROM pg_attribute a"
            " WHERE a.attrelid = CAST(:t AS regclass) AND a.attnum > 0 AND NOT a.attisdropped"
        ),
        {"t": table},
    ).all()
    return {name: type_ for name, type_ in rows}


def preflight(conn: Connection, symbols: list[str]) -> None:
    """alembic head, 두 테이블 컬럼·타입이 명세와 정확히 같은지, stocks에 대상 종목이 있는지. 하나라도 다르면 중단."""
    problems: list[str] = []
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    repo_root = Path(__file__).resolve().parents[3]
    alembic_cfg = Config(str(repo_root / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(repo_root / "alembic"))

    expected_heads = set(ScriptDirectory.from_config(alembic_cfg).get_heads())
    actual_heads = set(
        conn.execute(text("SELECT version_num FROM alembic_version")).scalars()
    )

    if actual_heads != expected_heads:
        problems.append(
            f"alembic 버전 불일치: DB={sorted(actual_heads)}, "
            f"코드={sorted(expected_heads)}"
        )
    for table, expected in EXPECTED_COLUMNS.items():
        actual = table_columns(conn, table)
        if actual != expected:
            missing = sorted(set(expected) - set(actual))
            extra = sorted(set(actual) - set(expected))
            changed = sorted(c for c in set(expected) & set(actual) if expected[c] != actual[c])
            problems.append(f"{table} 컬럼이 명세와 다릅니다: 없음 {missing}, 추가 {extra}, 타입 다름 {changed}")
    found = {
        s.strip()
        for s in conn.execute(
            text("SELECT symbol FROM stocks WHERE symbol IN :ss").bindparams(bindparam("ss", expanding=True)), {"ss": list(symbols)}
        ).scalars()
    }
    missing_symbols = sorted(set(symbols) - found)
    if missing_symbols:
        problems.append(f"stocks에 대상 종목이 없습니다: {', '.join(missing_symbols)}")
    if problems:
        raise FinancialsPreflightError("; ".join(problems))


def _key(period: MappedPeriod) -> dict:
    return {"symbol": period.symbol, "period_end": date.fromisoformat(period.period_end), "period_type": period.period_type}


def _reasons(reasons: dict[str, str], values: dict) -> str:
    """값이 있는 컬럼의 사유는 넣지 않는다 (NULL 컬럼만)."""
    return json.dumps({c: r for c, r in sorted(reasons.items()) if values.get(c) is None}, ensure_ascii=False)


def upsert_financials(conn: Connection, period: MappedPeriod, *, keep_direct: bool = False) -> bool:
    """keep_direct=True(전기 값)면 이미 있는 행은 건드리지 않는다 — 그 기간 보고서에서 직접 받은 값이 우선.
    쓴 경우 True."""
    columns = list(FINANCIALS_VALUES) + ["fs_div"]
    names = ", ".join(columns)
    params = ", ".join(f":{c}" for c in columns)
    updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in columns + ["null_reasons"])
    conflict = "DO NOTHING" if keep_direct else f"DO UPDATE SET {updates}"
    result = conn.execute(
        text(
            f"INSERT INTO financials (symbol, period_end, period_type, {names}, null_reasons)"
            f" VALUES (:symbol, :period_end, CAST(:period_type AS report_period), {params}, CAST(:null_reasons AS jsonb))"
            f" ON CONFLICT (symbol, period_end, period_type) {conflict}"
        ),
        {**_key(period), **{c: period.values.get(c) for c in FINANCIALS_VALUES}, "fs_div": period.fs_div,
         "null_reasons": _reasons(period.null_reasons, period.values)},
    )
    wrote = result.rowcount == 1
    if wrote:  # 누적 원본이 바뀌었으니 그 회계연도의 분기 단독값을 다시 계산 (0016)
        financials_quarterly.recompute_for_period(conn, "general", period.symbol, period.period_end, period.period_type)
        # 금융 표의 연결·별도 판정도 financials.fs_div를 쓰므로 함께 (금융사가 아니면 대상 행이 없어 바로 끝남)
        financials_quarterly.recompute_for_period(conn, "fin", period.symbol, period.period_end, period.period_type)
        # 계산 지표 (0017): 이 기간의 이자비용 원천값을 남기고 회사 전체 지표를 다시 계산
        financial_metrics.set_interest(conn, period.symbol, period.period_end, period.period_type, period.fs_div, period.interest_cost)
        financial_metrics.recompute_symbol(conn, period.symbol)
        # 사건 표준 비율 (0018): 분모(직전 연도 영업이익·자본총계)가 바뀌었을 수 있어 그 회사 사건을 다시 계산
        event_metrics.refresh(conn, symbol=period.symbol)
    return wrote


def upsert_financials_fin(conn: Connection, period: MappedPeriod, *, keep_direct: bool = False) -> bool:
    """financials_fin의 재무 API 항목만 UPSERT한다. 비율(bis·kics·ncr)과 그 NULL 사유는 비율 단계 소관이라 건드리지 않는다."""
    if period.fin_values is None:
        raise ValueError(f"{period.symbol}은 financials_fin 대상이 아닙니다.")
    columns = list(FIN_VALUES)
    names = ", ".join(columns)
    params = ", ".join(f":{c}" for c in columns)
    updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in columns)
    # 기존 사유에서 재무 API 항목 키만 지우고 새 사유를 합친다 (비율 키는 유지)
    api_keys = ", ".join(f"'{c}'" for c in columns)
    reasons = f"null_reasons = (financials_fin.null_reasons - ARRAY[{api_keys}]) || EXCLUDED.null_reasons"
    conflict = "DO NOTHING" if keep_direct else f"DO UPDATE SET {updates}, {reasons}"
    result = conn.execute(
        text(
            f"INSERT INTO financials_fin (symbol, period_end, period_type, {names}, null_reasons)"
            f" VALUES (:symbol, :period_end, CAST(:period_type AS report_period), {params}, CAST(:null_reasons AS jsonb))"
            f" ON CONFLICT (symbol, period_end, period_type) {conflict}"
        ),
        {**_key(period), **{c: period.fin_values.get(c) for c in FIN_VALUES},
         "null_reasons": _reasons(period.fin_null_reasons, period.fin_values)},
    )
    wrote = result.rowcount == 1
    if wrote:
        financials_quarterly.recompute_for_period(conn, "fin", period.symbol, period.period_end, period.period_type)
        financial_metrics.recompute_symbol(conn, period.symbol)  # 금융사 영업수익 대용값·이익률 (0017)
    return wrote


def set_ratio(conn: Connection, symbol: str, period_end: str, ptype: str, column: str, value, null_code: str | None) -> int:
    """비율 컬럼 하나와 그 NULL 사유를 함께 쓴다. 바뀐 행 수 반환 (행이 없으면 0)."""
    if column not in FIN_RATIOS:
        raise ValueError(f"비율 컬럼이 아닙니다: {column}")
    reasons = ("null_reasons - CAST(:c AS text)" if value is not None or null_code is None
               else "null_reasons || jsonb_build_object(CAST(:c AS text), CAST(:code AS text))")
    return conn.execute(
        text(f"UPDATE financials_fin SET {column} = :v, null_reasons = {reasons}"
             " WHERE symbol = :s AND period_end = CAST(:p AS date) AND period_type = CAST(:t AS report_period)"),
        {"v": value, "c": column, "code": null_code, "s": symbol, "p": period_end, "t": ptype},
    ).rowcount


def update_stock_sector(conn: Connection, symbol: str, fin_type: str | None) -> None:
    """금융 판별 결과를 stocks.sector·fin_type에 반영한다.

    일반 기업으로 판별되면 financials_fin 행을 지운다. 예전에 금융(other 등)으로 잘못 판별돼 생긴 행이 남지 않게.
    """
    conn.execute(
        text("UPDATE stocks SET sector = CAST(:sector AS sector_type), fin_type = :ft WHERE symbol = :s"),
        {"sector": "financial" if fin_type else "general", "ft": fin_type, "s": symbol},
    )
    if fin_type is None:
        conn.execute(text("DELETE FROM financials_fin WHERE symbol = :s"), {"s": symbol})
        conn.execute(text("DELETE FROM financials_fin_quarterly WHERE symbol = :s"), {"s": symbol})  # 0016 분기값도 함께
    if conn.execute(text("SELECT 1 FROM financial_metrics WHERE symbol = :s LIMIT 1"), {"s": symbol}).first():
        financial_metrics.recompute_symbol(conn, symbol)  # 업종이 바뀌면 금융사 전용 값·사유가 달라진다 (0017)
