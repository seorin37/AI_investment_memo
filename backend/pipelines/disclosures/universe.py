"""코스피 전체 수집 대상(universe) 확정: KRX 코스피 목록 × DART corpCode.

- KRX 일별 시세(stk_bydd_trd)에서 MKT_NM=KOSPI 종목을 가져온다 (최근 거래일까지 하루씩 거슬러 올라감).
- corpCode.xml의 stock_code(보통주 코드)와 맞는 종목만 남긴다. 우선주는 corpCode에 없으므로 자연히 보통주에 합쳐진다.
- 리츠·인프라펀드·외국기업도 corpCode에 있으면 포함한다. 정기보고서가 없으면 collect에서 0건으로 끝난다.
- stocks에는 INSERT만 하고 기존 행의 이름·섹터는 바꾸지 않는다 (dart_corp_code·market이 비어 있을 때만 채운다).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Callable

from sqlalchemy import text
from sqlalchemy.engine import Connection

from ..common.logging import get_logger


log = get_logger("disclosures.universe")


@dataclass(frozen=True)
class Company:
    symbol: str
    name: str
    corp_code: str
    market_cap: int  # 원. 처리 순서(시가총액 큰 순)에만 쓴다.


def _market_cap(value) -> int:
    try:
        return int(str(value or "0").replace(",", "").strip() or 0)
    except ValueError:
        return 0


def fetch_kospi_rows(as_of: date, fetcher: Callable[[date], list[dict]] | None = None, max_back_days: int = 10) -> tuple[date, list[dict]]:
    """as_of부터 하루씩 거슬러 올라가며 KOSPI 행이 있는 첫 거래일의 목록을 반환한다."""
    if fetcher is None:
        from ..market.krx import fetch_kospi_daily as fetcher
    for back in range(max_back_days + 1):
        day = as_of - timedelta(days=back)
        rows = [row for row in fetcher(day) if row.get("MKT_NM") == "KOSPI"]
        if rows:
            return day, rows
    raise RuntimeError(f"{as_of}부터 {max_back_days}일 안에 KRX 코스피 데이터가 없습니다.")


def build_universe(kospi_rows: list[dict], corp_codes: dict[str, str]) -> tuple[list[Company], list[dict]]:
    """(대상 기업 시가총액 큰 순, corpCode에 없는 종목). 후자는 대부분 우선주다."""
    companies: dict[str, Company] = {}
    unmatched: list[dict] = []
    for row in kospi_rows:
        symbol = str(row.get("ISU_CD", "")).strip()
        name = str(row.get("ISU_NM") or "").strip()
        if len(symbol) != 6 or not symbol.isalnum() or not name:
            unmatched.append({"symbol": symbol, "name": name, "reason": "종목코드·이름 형식 오류"})
            continue
        corp_code = corp_codes.get(symbol)
        if not corp_code:
            unmatched.append({"symbol": symbol, "name": name, "reason": "corpCode에 없음 (우선주 등)"})
            continue
        companies[symbol] = Company(symbol, name, corp_code, _market_cap(row.get("MKTCAP")))
    ordered = sorted(companies.values(), key=lambda c: (-c.market_cap, c.symbol))
    return ordered, unmatched


def save_universe(path: Path, trade_date: date, companies: list[Company], unmatched: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "trade_date": trade_date.isoformat(),
        "companies": [asdict(c) for c in companies],
        "unmatched": unmatched,
    }
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    temp.replace(path)


def load_universe(path: Path) -> tuple[str, list[Company]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["trade_date"], [Company(**row) for row in data["companies"]]


def upsert_stocks(conn: Connection, companies: list[Company]) -> int:
    """없는 종목은 INSERT, 있는 종목은 비어 있는 dart_corp_code·market만 채운다. 새로 넣은 행 수 반환."""
    inserted = 0
    for company in companies:
        result = conn.execute(
            text(
                "INSERT INTO stocks (symbol, name, market, sector, dart_corp_code)"
                " VALUES (:symbol, :name, 'KOSPI', 'general', :corp)"
                " ON CONFLICT (symbol) DO UPDATE SET"
                " dart_corp_code = COALESCE(stocks.dart_corp_code, EXCLUDED.dart_corp_code),"
                " market = COALESCE(stocks.market, EXCLUDED.market)"
                " RETURNING (xmax = 0)"
            ),
            {"symbol": company.symbol, "name": company.name, "corp": company.corp_code},
        ).scalar()
        inserted += int(bool(result))
    return inserted


def stock_names(conn: Connection, symbols: list[str]) -> dict[str, str]:
    """청크 헤더용 기업명. 이미 적재된 문서와 헤더가 같도록 stocks.name을 그대로 쓴다."""
    rows = conn.execute(text("SELECT symbol, name FROM stocks WHERE symbol = ANY(:ss)"), {"ss": list(symbols)}).all()
    return {str(symbol).strip(): name for symbol, name in rows}
