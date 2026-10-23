"""financials · financials_fin 적재 (스키마 변경 없음, WO-015).

함수는 Connection을 받아 쓰기만 하고 commit하지 않는다. 트랜잭션 경계는 호출자가 정한다
(실행 진입점은 기업·기간 하나당 `engine.begin()` 하나).
"""

from __future__ import annotations

from pathlib import Path

from datetime import date

from sqlalchemy import bindparam, text
from sqlalchemy.engine import Connection

from .financials import MappedPeriod


AMOUNT, PER_SHARE = "numeric(20,0)", "numeric(14,2)"
KEY_COLUMNS = {"symbol": "character(6)", "period_end": "date", "period_type": "report_period"}
FINANCIALS_VALUES = {
    "revenue": AMOUNT, "operating_income": AMOUNT, "net_income": AMOUNT, "total_assets": AMOUNT, "total_liabilities": AMOUNT,
    "total_equity": AMOUNT, "current_assets": AMOUNT, "current_liabilities": AMOUNT, "inventories": AMOUNT,
    "interest_expense": AMOUNT, "retained_earnings": AMOUNT, "eps": PER_SHARE, "bps": PER_SHARE,
    "capital_stock": AMOUNT, "capital_surplus": AMOUNT,
}
FIN_VALUES = {"net_interest_income": AMOUNT, "fee_income": AMOUNT, "loan_loss_provision": AMOUNT}
EXPECTED_COLUMNS = {
    "financials": {**KEY_COLUMNS, **FINANCIALS_VALUES, "fs_div": "text"},
    "financials_fin": {**KEY_COLUMNS, **FIN_VALUES, "solvency_ratio": "numeric(8,2)"},
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
    """alembic 0005, 두 테이블 컬럼·타입이 명세와 정확히 같은지, stocks에 대상 종목이 있는지. 하나라도 다르면 중단."""
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


def upsert_financials(conn: Connection, period: MappedPeriod) -> None:
    columns = list(FINANCIALS_VALUES) + ["fs_div"]
    names = ", ".join(columns)
    params = ", ".join(f":{c}" for c in columns)
    updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in columns)
    conn.execute(
        text(
            f"INSERT INTO financials (symbol, period_end, period_type, {names})"
            f" VALUES (:symbol, :period_end, CAST(:period_type AS report_period), {params})"
            f" ON CONFLICT (symbol, period_end, period_type) DO UPDATE SET {updates}"
        ),
        {**_key(period), **{c: period.values.get(c) for c in FINANCIALS_VALUES}, "fs_div": period.fs_div},
    )


def upsert_financials_fin(conn: Connection, period: MappedPeriod) -> None:
    """financials_fin의 재무 API 항목만 UPSERT한다. solvency_ratio는 bis 단계 소관이라 건드리지 않는다."""
    if period.fin_values is None:
        raise ValueError(f"{period.symbol}은 financials_fin 대상이 아닙니다.")
    columns = list(FIN_VALUES)
    names = ", ".join(columns)
    params = ", ".join(f":{c}" for c in columns)
    updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in columns)
    conn.execute(
        text(
            f"INSERT INTO financials_fin (symbol, period_end, period_type, {names})"
            f" VALUES (:symbol, :period_end, CAST(:period_type AS report_period), {params})"
            f" ON CONFLICT (symbol, period_end, period_type) DO UPDATE SET {updates}"
        ),
        {**_key(period), **{c: period.fin_values.get(c) for c in FIN_VALUES}},
    )
