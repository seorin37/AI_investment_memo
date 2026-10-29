"""financials · financials_fin 완료 조건 자동 검사 (WO-015 ③단계, 읽기 전용).

| 검사 | 기준 | 실패 시 |
|---|---|---|
| row_counts | financials = 종목 × 기간, financials_fin = 금융 종목 × 기간 | error |
| accounting_identity | total_assets = total_liabilities + total_equity (오차 0) | error |
| cumulative_monotonic | 일반 기업, 같은 연도 revenue q1 ≤ half ≤ q3 ≤ annual | error |
| chunk_cross_check | 고정 대조값(삼성 2026 반기 누적 매출 = 청크 305,372,914백만원 × 1,000,000) | error |
| annual_statement_cross_check | 2025 사업보고서 연결 손익 청크의 매출·영업이익 = API 값 (청크 단위 반올림 이내) | 불일치 error, 청크 없음 warning |
| eps_consistency | net_income ÷ 유통주식수 vs 공시 EPS 차이 10% 이내 | warning |
| null_report / rcept_no_match / bis_ratio | NULL 목록·사유, API 접수번호와 disclosures 대조, BIS 값 | info |
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

from sqlalchemy import bindparam, text
from sqlalchemy.engine import Connection

from .financials import ShareCounts, period_type
from .financials_loader import FIN_VALUES, FINANCIALS_VALUES
from .financials_shares import parse_capital_issued


ORDER = {"q1": 0, "half": 1, "q3": 2, "annual": 3}
EPS_TOLERANCE = Decimal("0.10")
# 명세 §10: DB 청크에서 확인한 값과 API 값의 고정 대조
CHUNK_CROSS_CHECKS = [
    {"symbol": "005930", "period_end": "2026-06-30", "column": "revenue", "chunk_text": "305,372,914", "unit": 10**6},
]
STATEMENT_PERIOD = "2025-12-31"
STATEMENT_LABELS = {"revenue": {"매출액", "수익(매출액)", "영업수익", "매출"}, "operating_income": {"영업이익", "영업이익(손실)"}}
UNITS = {"원": 1, "천원": 10**3, "백만원": 10**6, "십억원": 10**9}


def _check(name: str, ok: bool, detail, severity: str = "error") -> dict:
    return {"name": name, "ok": bool(ok), "severity": severity, "detail": detail}


def _rows(conn: Connection, table: str, symbols: list[str], periods: list[str]) -> dict[tuple[str, str], dict]:
    if not symbols or not periods:
        return {}

    result = conn.execute(
        text(f"SELECT * FROM {table} WHERE symbol IN :ss AND period_end::text IN :ps").bindparams(
            bindparam("ss", expanding=True), bindparam("ps", expanding=True)
        ),
        {"ss": symbols, "ps": periods},
    ).mappings().all()
    return {(r["symbol"].strip(), str(r["period_end"])): dict(r) for r in result}


def check_row_counts(fin_rows: dict, fin_fin_rows: dict, symbols: list[str], fin_symbols: list[str], periods: list[str]) -> dict:
    expected = {(s, p) for s in symbols for p in periods}
    expected_fin = {(s, p) for s in fin_symbols for p in periods}
    missing = sorted(expected - set(fin_rows))
    extra = sorted(set(fin_rows) - expected)
    missing_fin = sorted(expected_fin - set(fin_fin_rows))
    extra_fin = sorted(set(fin_fin_rows) - expected_fin)
    ok = not missing and not extra and not missing_fin and not extra_fin
    return _check("row_counts", ok, {"financials": f"{len(fin_rows)}/{len(expected)}", "financials_fin": f"{len(fin_fin_rows)}/{len(expected_fin)}",
                                     "missing": missing, "extra": extra, "missing_fin": missing_fin, "extra_fin": extra_fin})


def check_accounting_identity(fin_rows: dict) -> dict:
    bad = []
    for key, r in sorted(fin_rows.items()):
        values = (r["total_assets"], r["total_liabilities"], r["total_equity"])
        if None in values:
            bad.append({"row": list(key), "reason": "자산·부채·자본 중 NULL"})
        elif values[0] != values[1] + values[2]:
            bad.append({"row": list(key), "diff": str(values[0] - values[1] - values[2])})
    return _check("accounting_identity", not bad, {"checked": len(fin_rows), "violations": bad})


def check_cumulative_monotonic(fin_rows: dict, general_symbols: list[str]) -> dict:
    by_year: dict[tuple[str, str], list[tuple[int, str, Decimal]]] = defaultdict(list)
    skipped = []
    for (symbol, period_end), r in fin_rows.items():
        if symbol not in general_symbols:
            continue
        if r["revenue"] is None:
            skipped.append([symbol, period_end])
            continue
        by_year[(symbol, period_end[:4])].append((ORDER[r["period_type"]], period_end, r["revenue"]))
    violations = []
    for (symbol, year), items in sorted(by_year.items()):
        items.sort()
        for (_, p1, v1), (_, p2, v2) in zip(items, items[1:]):
            if v1 > v2:
                violations.append({"symbol": symbol, "year": year, "earlier": [p1, str(v1)], "later": [p2, str(v2)]})
    return _check("cumulative_monotonic", not violations, {"series": len(by_year), "violations": violations, "revenue_null": sorted(skipped)})


def check_chunk_cross(conn: Connection, fin_rows: dict, rcept_of: dict[tuple[str, str], str]) -> dict:
    results = []
    ok = True
    for spec in CHUNK_CROSS_CHECKS:
        key = (spec["symbol"], spec["period_end"])
        if key not in rcept_of and key not in fin_rows:
            continue  # 이번 실행 범위(--symbols) 밖
        expected = Decimal(spec["chunk_text"].replace(",", "")) * spec["unit"]
        actual = fin_rows.get(key, {}).get(spec["column"])
        rcept_no = rcept_of.get(key)
        in_chunk = bool(rcept_no) and bool(
            conn.execute(
                text("SELECT 1 FROM disclosure_chunks WHERE rcept_no = :r AND position(:t in chunk_text) > 0 LIMIT 1"),
                {"r": rcept_no, "t": spec["chunk_text"]},
            ).first()
        )
        passed = actual == expected and in_chunk
        ok = ok and passed
        results.append({**spec, "expected": str(expected), "actual": None if actual is None else str(actual), "found_in_chunk": in_chunk, "rcept_no": rcept_no, "ok": passed})
    return _check("chunk_cross_check", ok, results)


def statement_values(chunk_text: str, period_end: str) -> dict[str, tuple[Decimal, int]]:
    """연결 손익 표 청크에서 대상 기간(당기) 열의 {정규화 계정명: (값, 단위)}. 표 머리에 기수·기간이 없으면 빈 dict."""
    year, month, day = period_end.split("-")
    period = re.search(rf"제\s*(\d+)\s*기\s+\d{{4}}\.\d{{2}}\.\d{{2}}\s*부터\s*{year}\.{month}\.{day}\s*까지", chunk_text)
    unit = re.search(r"\(\s*단위\s*:\s*(원|천원|백만원|십억원)\s*\)", chunk_text)
    if not period or not unit:
        return {}
    term = period.group(1)
    values: dict[str, tuple[Decimal, int]] = {}
    for match in re.finditer(rf"^([^|\n]+?)\s*\|\s*제\s*{term}\s*기\s*:\s*\(?(-?[\d,]+)\)?", chunk_text, re.M):
        label = re.sub(r"\s+", "", re.sub(r"\(주[\d,\s]*\)", "", match.group(1)))
        amount = Decimal(match.group(2).replace(",", ""))
        if "(" in match.group(0).split(":")[-1]:
            amount = -amount
        values.setdefault(label, (amount, UNITS[unit.group(1)]))
    return values


def check_annual_statements(conn: Connection, fin_rows: dict, rcept_of: dict[tuple[str, str], str], symbols: list[str]) -> list[dict]:
    """각 기업 2025 사업보고서 연결 손익 청크의 매출·영업이익을 API 값과 대조한다."""
    mismatches, unverifiable, matched = [], [], []
    for symbol in symbols:
        key = (symbol, STATEMENT_PERIOD)
        rcept_no = rcept_of.get(key)
        row = fin_rows.get(key)
        if not rcept_no or row is None:
            unverifiable.append({"symbol": symbol, "reason": "2025 사업보고서 공시 또는 재무 행 없음"})
            continue
        chunks = conn.execute(
            text("SELECT chunk_index, chunk_text FROM disclosure_chunks WHERE rcept_no = :r AND section ~ '연결' AND section !~ '주석' ORDER BY chunk_index"),
            {"r": rcept_no},
        ).all()
        found: dict[str, set[tuple[Decimal, int]]] = defaultdict(set)
        for _, chunk_text in chunks:
            for label, value in statement_values(chunk_text, STATEMENT_PERIOD).items():
                for column, labels in STATEMENT_LABELS.items():
                    if label in labels:
                        found[column].add(value)
        for column in STATEMENT_LABELS:
            api = row.get(column)
            if api is None:
                continue  # 매핑상 NULL (예: KB금융 revenue)
            candidates = found.get(column, set())
            entry = {"symbol": symbol, "column": column, "api": str(api), "rcept_no": rcept_no,
                     "chunk": sorted(f"{v}×{u}" for v, u in candidates)}
            if not candidates:
                unverifiable.append({**entry, "reason": f"연결 손익 청크에서 {column} 행을 찾지 못함 (청크 {len(chunks)}개)"})
            elif any(abs(api - v * u) < u for v, u in candidates):
                matched.append(entry)
            else:
                mismatches.append(entry)
    return [
        _check("annual_statement_cross_check", not mismatches, {"matched": matched, "mismatches": mismatches}),
        _check("annual_statement_unverifiable", not unverifiable, unverifiable, severity="warning"),
    ]


def check_eps(fin_rows: dict, shares: dict[tuple[str, str], ShareCounts | None]) -> dict:
    warnings, checked = [], 0
    for key, r in sorted(fin_rows.items()):
        counts = shares.get(key)
        if r["eps"] is None or r["net_income"] is None or counts is None or not counts.outstanding:
            continue
        checked += 1
        implied = r["net_income"] / Decimal(counts.outstanding)
        gap = abs(implied - r["eps"]) / abs(r["eps"]) if r["eps"] else None
        if gap is None or gap > EPS_TOLERANCE:
            warnings.append({"row": list(key), "eps": str(r["eps"]), "implied": str(implied.quantize(Decimal("0.01"))),
                             "gap_pct": None if gap is None else str((gap * 100).quantize(Decimal("0.1")))})
    return _check("eps_consistency", not warnings, {"checked": checked, "over_10pct": warnings}, severity="warning")


def check_share_issuance_notes(conn: Connection, shares: dict[tuple[str, str], ShareCounts | None], rcept_of: dict[tuple[str, str], str]) -> dict:
    """공시 fallback을 쓴 슬롯의 발행주식수(A)를 같은 공시 연결 자본금 주석과 대조한다."""
    matched, mismatches, unavailable = [], [], []
    for key, counts in sorted(shares.items()):
        if counts is None or counts.basis not in {"의결권 현황 표", "연결 자본금 주석"}:
            continue
        rcept_no = rcept_of.get(key)
        if not rcept_no:
            unavailable.append({"row": list(key), "reason": "같은 기간 공시 없음"})
            continue
        chunks = conn.execute(
            text("SELECT chunk_index, chunk_text FROM disclosure_chunks WHERE rcept_no = :r"
                 " AND position('발행주식수' in chunk_text) > 0"
                 " ORDER BY chunk_index"),
            {"r": rcept_no},
        ).all()
        candidates = []
        for chunk_index, chunk_text in chunks:
            issued = parse_capital_issued(chunk_text, key[1])
            if issued is not None:
                candidates.append((chunk_index, issued))
        issued_values = sorted({issued for _, issued in candidates})
        entry = {"row": list(key), "rcept_no": rcept_no, "bps_issued": counts.issued,
                 "note_issued": issued_values, "chunk_indexes": [index for index, _ in candidates]}
        if not candidates:
            unavailable.append({**entry, "reason": "연결 자본금/주식 발행 주석에서 대조 불가"})
        elif issued_values == [counts.issued]:
            matched.append(entry)
        else:
            mismatches.append(entry)
    return _check("share_issuance_note_cross_check", not mismatches,
                  {"matched": matched, "mismatches": mismatches, "unavailable": unavailable})


def null_report(fin_rows: dict, fin_fin_rows: dict, provenance_path: Path) -> dict:
    reasons: dict[tuple, str] = {}
    if provenance_path.exists():
        with provenance_path.open(encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    p = json.loads(line)
                    reasons[(p["symbol"], p["period_end"], p["table"], p["column"])] = p.get("reason", "")
    report: dict[str, list] = {}
    for table, rows, columns in (("financials", fin_rows, FINANCIALS_VALUES), ("financials_fin", fin_fin_rows, list(FIN_VALUES) + ["bis_ratio"])):
        for column in columns:
            nulls = [f"{s} {p}: {reasons.get((s, p, table, column), '사유 기록 없음')}" for (s, p), r in sorted(rows.items()) if r[column] is None]
            if nulls:
                report[f"{table}.{column}"] = nulls
    unexplained = [line for lines in report.values() for line in lines if line.endswith("사유 기록 없음")]
    return _check("null_report", not unexplained, {"null_columns": {k: len(v) for k, v in report.items()}, "details": report, "unexplained": unexplained}, severity="warning")


def rcept_no_match(provenance_path: Path, rcept_of: dict[tuple[str, str], str]) -> dict:
    api: dict[tuple[str, str], str] = {}
    if provenance_path.exists():
        with provenance_path.open(encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    p = json.loads(line)
                    if p.get("rcept_no") and p["table"] == "financials":
                        api[(p["symbol"], p["period_end"])] = p["rcept_no"]
    differ = [{"row": list(k), "api": v, "disclosures": rcept_of.get(k)} for k, v in sorted(api.items()) if rcept_of.get(k) != v]
    return _check("rcept_no_match", not differ, {"compared": len(api), "differ": differ}, severity="info")


def disclosure_rcept_nos(conn: Connection, symbols: list[str], periods: list[str]) -> dict[tuple[str, str], str]:
    rows = conn.execute(
        text(
            "SELECT symbol, period_end::text, rcept_no FROM disclosures WHERE symbol IN :ss AND period_end::text IN :ps"
            " AND kind IN ('annual', 'half', 'quarterly')"
        ).bindparams(bindparam("ss", expanding=True), bindparam("ps", expanding=True)),
        {"ss": symbols, "ps": periods},
    ).all()
    return {(s.strip(), p): r for s, p, r in rows}


def validate(
    conn: Connection,
    symbols: list[str],
    fin_symbols: list[str],
    periods: list[str],
    *,
    shares: dict[tuple[str, str], ShareCounts | None],
    provenance_path: Path,
) -> dict:
    fin_rows = _rows(conn, "financials", symbols, periods)
    fin_fin_rows = _rows(conn, "financials_fin", fin_symbols, periods)
    rcept_of = disclosure_rcept_nos(conn, symbols, periods)
    general = [s for s in symbols if s not in fin_symbols]
    for (symbol, period_end), r in fin_rows.items():
        if r["period_type"] != period_type(period_end):
            raise AssertionError(f"{symbol} {period_end}: period_type {r['period_type']}")
    checks = [
        check_row_counts(fin_rows, fin_fin_rows, symbols, fin_symbols, periods),
        check_accounting_identity(fin_rows),
        check_cumulative_monotonic(fin_rows, general),
        check_chunk_cross(conn, fin_rows, rcept_of),
        *check_annual_statements(conn, fin_rows, rcept_of, symbols),
        check_eps(fin_rows, shares),
        check_share_issuance_notes(conn, shares, rcept_of),
        null_report(fin_rows, fin_fin_rows, provenance_path),
        rcept_no_match(provenance_path, rcept_of),
        _check("bis_ratio", True, {f"{s} {p}": None if r["bis_ratio"] is None else str(r["bis_ratio"]) for (s, p), r in sorted(fin_fin_rows.items())}, severity="info"),
    ]
    return {"ok": all(c["ok"] for c in checks if c["severity"] == "error"), "checks": checks}
