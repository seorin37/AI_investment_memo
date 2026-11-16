"""우선주 → 보통주 매핑 (2026-11-10). 우선주 항목의 공시·뉴스는 보통주 종목코드로 조회하고, 가격 판정은 우선주 자체 종가로 한다.

매핑 근거 (DB 읽기 전용):
1) DB: stocks.dart_corp_code가 같은 종목 중 우선주가 아닌 종목 하나 (DART 고유번호는 회사 단위라 우선주와 보통주가 같다).
2) 규칙: 1)로 못 찾으면 종목코드 끝자리를 0으로 바꾼 코드(005935 → 005930, 00088K → 000880)가 stocks에 있으면 그것.
우선주 판단: 이름이 '우'·'1우'·'2우B'·'3우B'·'우(전환)'으로 끝난다.
    PYTHONPATH=backend python -m pipelines.updates.preferred       # 매핑 표와 규칙이 맞지 않는 경우
"""

from __future__ import annotations

import argparse
import re

PREF_NAME = re.compile(r"\d?우[A-Z]?(\(전환\))?$")
STOCKS_SQL = "SELECT btrim(symbol), name, dart_corp_code, market::text FROM stocks"


def is_preferred(name: str) -> bool:
    return bool(PREF_NAME.search(name or ""))


def rule_common(symbol: str) -> str:
    """종목코드 규칙: 끝자리를 0으로."""
    return symbol[:5] + "0"


def build_map(stocks: list[tuple]) -> tuple[dict[str, str], list[dict]]:
    """stocks: (symbol, name, dart_corp_code, market). 반환 ({우선주: 보통주}, 점검 행).
    점검 행 status: db(고유번호로 찾음, 규칙과 같음) | db_rule_differs(고유번호로 찾았는데 규칙과 다름) |
    rule_only(고유번호가 없거나 짝이 없어 규칙으로 찾음) | unmapped(둘 다 못 찾음) | db_ambiguous(같은 고유번호 보통주가 여럿)."""
    by_symbol = {s: (n, c) for s, n, c, _ in stocks}
    commons_by_corp: dict[str, list[str]] = {}
    for s, n, c, _ in stocks:
        if c and c.strip() and not is_preferred(n):
            commons_by_corp.setdefault(c.strip(), []).append(s)
    out, rows = {}, []
    for s, n, c, _ in stocks:
        if not is_preferred(n):
            continue
        rule = rule_common(s)
        rule_ok = rule in by_symbol and not is_preferred(by_symbol[rule][0])
        cands = commons_by_corp.get((c or "").strip(), []) if c and c.strip() else []
        if len(cands) == 1:
            common, status = cands[0], ("db" if cands[0] == rule else "db_rule_differs")
        elif len(cands) > 1:
            common, status = (rule if rule in cands else None), "db_ambiguous"
        elif rule_ok:
            common, status = rule, "rule_only"
        else:
            common, status = None, "unmapped"
        if common:
            out[s] = common
        rows.append({"symbol": s, "name": n, "dart_corp_code": (c or "").strip() or None, "common": common,
                     "common_name": by_symbol.get(common, ("",))[0] if common else None,
                     "rule": rule, "rule_name": by_symbol.get(rule, (None,))[0], "status": status})
    return out, rows


def load_map(conn) -> dict[str, str]:
    with conn.cursor() as cur:
        cur.execute(STOCKS_SQL)
        return build_map(cur.fetchall())[0]


def source_symbol(symbol: str, pref_map: dict[str, str] | None) -> str:
    """공시·뉴스를 조회할 종목코드 (우선주면 보통주)."""
    return (pref_map or {}).get(symbol, symbol)


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(description="우선주 → 보통주 매핑 점검 (DB 읽기 전용)").parse_args(argv)
    import psycopg
    from collections import Counter

    from ..common.db import get_read_dsn

    with psycopg.connect(get_read_dsn()) as conn:
        conn.read_only = True
        stocks = conn.execute(STOCKS_SQL).fetchall()
        conn.rollback()
    mapping, rows = build_map(stocks)
    print(f"stocks {len(stocks)}개 · 우선주(이름 규칙) {len(rows)}개 · 매핑 {len(mapping)}개 · 상태 {dict(Counter(r['status'] for r in rows))}")
    print(f"고유번호(dart_corp_code)가 있는 우선주 {sum(bool(r['dart_corp_code']) for r in rows)}개")
    odd = [r for r in rows if r["status"] in ("unmapped", "db_ambiguous", "db_rule_differs")
           or not name_matches(r["name"], r["common_name"])]
    print(f"규칙이 맞지 않거나 이름이 어긋나는 우선주: {len(odd)}개")
    for r in odd:
        print(f"- {r['status']}: {r['symbol']} {r['name']} → {r['common']} {r['common_name']} · 규칙 {r['rule']} {r['rule_name']}")
    others = [(s, n) for s, n, _, _ in stocks if not s.endswith("0") and not is_preferred(n)]
    print(f"종목코드 끝자리가 0이 아닌데 우선주 이름이 아닌 종목 (규칙 밖): {len(others)}개 {others}")
    return 0


def name_matches(pref_name: str, common_name: str | None) -> bool:
    """보통주 이름이 우선주 이름(끝의 '우…' 뗀 것)으로 시작하거나 그 반대 (남선알미우 ↔ 남선알미늄)."""
    if not common_name:
        return False
    base = PREF_NAME.sub("", pref_name).strip()
    return bool(base) and (common_name.startswith(base) or base.startswith(common_name))


if __name__ == "__main__":
    raise SystemExit(main())
