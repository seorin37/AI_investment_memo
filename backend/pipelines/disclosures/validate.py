"""완료 조건 자동 검사.

- 기업별 disclosures 행 수(전체 실행: 기업당 대상 기간 수), (symbol, kind, period_end) 중복 0
- 청크 없는 공시 0, chunk_index 0부터 연속
- embedding NULL 0, 노름 0.99~1.01, NaN/Inf 0
- hybrid: sparse 파일의 (rcept_no, chunk_index) 집합 = DB 청크 집합
- 매니페스트 행 = DB 청크 (개수·(rcept_no, chunk_index)·chunk_hash 모두 일치)
- 문서별 doc_fingerprint (DB chunk_text 기준)
"""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import bindparam, text
from sqlalchemy.engine import Connection

from . import sparse_store
from .chunker import doc_fingerprint, sha256_text


NORM_LOW, NORM_HIGH = 0.99, 1.01
PERIODIC = "kind IN ('annual', 'half', 'quarterly') AND period_end IS NOT NULL"
EXPECTED_KIND_BY_MONTH = {"03": "quarterly", "06": "half", "09": "quarterly", "12": "annual"}


def _check(name: str, ok: bool, detail) -> dict:
    return {"name": name, "ok": bool(ok), "detail": detail}


def _in(sql: str):
    return text(sql).bindparams(bindparam("rs", expanding=True))


def validate_disclosures_per_symbol(
    conn: Connection, expected_per_symbol: dict[str, int], periods: list[str]
) -> dict:
    """기업별 기대 슬롯과 실제 정기보고서를 비교해 개수·누락·중복을 함께 설명한다."""
    symbols = sorted(expected_per_symbol)
    rows = conn.execute(
        text(
            f"SELECT symbol, kind::text, period_end::text, rcept_no FROM disclosures"
            f" WHERE symbol IN :ss AND {PERIODIC} AND period_end::text IN :ps"
            " ORDER BY symbol, period_end, kind, rcept_no"
        ).bindparams(bindparam("ss", expanding=True), bindparam("ps", expanding=True)),
        {"ss": symbols, "ps": list(periods)},
    ).all() if symbols and periods else []
    return disclosures_per_symbol_detail(rows, expected_per_symbol, periods)


def disclosures_per_symbol_detail(rows, expected_per_symbol: dict[str, int], periods: list[str]) -> dict:
    """조회 행을 기업별 10개 슬롯 상세로 바꾼다. DB 없는 단위 테스트에서도 사용한다."""
    symbols = sorted(expected_per_symbol)
    expected_slots = [(period, EXPECTED_KIND_BY_MONTH.get(period[5:7], "unknown")) for period in sorted(periods)]

    by_symbol: dict[str, list[tuple[str, str, str]]] = {symbol: [] for symbol in symbols}
    for symbol, kind, period_end, rcept_no in rows:
        by_symbol.setdefault(symbol.strip(), []).append((period_end, kind, rcept_no))

    companies: dict[str, dict] = {}
    ok = True
    expected_slot_set = set(expected_slots)
    for symbol in symbols:
        actual_rows = by_symbol.get(symbol, [])
        actual_slots: dict[tuple[str, str], list[str]] = {}
        for period_end, kind, rcept_no in actual_rows:
            actual_slots.setdefault((period_end, kind), []).append(rcept_no)
        missing = [
            {"period_end": period, "kind": kind}
            for period, kind in expected_slots
            if (period, kind) not in actual_slots
        ]
        duplicates = [
            {"period_end": period, "kind": kind, "count": len(rcept_nos), "rcept_nos": sorted(rcept_nos)}
            for (period, kind), rcept_nos in sorted(actual_slots.items())
            if len(rcept_nos) > 1
        ]
        unexpected = [
            {"period_end": period, "kind": kind, "rcept_nos": sorted(rcept_nos)}
            for (period, kind), rcept_nos in sorted(actual_slots.items())
            if (period, kind) not in expected_slot_set
        ]
        expected = expected_per_symbol[symbol]
        actual = len(actual_rows)
        company_ok = actual == expected and not missing and not duplicates and not unexpected
        ok = ok and company_ok
        companies[symbol] = {
            "expected": expected,
            "actual": actual,
            "missing": missing,
            "duplicates": duplicates,
            "unexpected": unexpected,
        }
    return _check("disclosures_per_symbol", ok, {"companies": companies})


def validate(
    conn: Connection,
    rcept_nos: list[str],
    *,
    manifest_path: Path,
    sparse_dir: Path | None,
    expected_per_symbol: dict[str, int] | None,
    periods: list[str] | None = None,
) -> dict:
    """expected_per_symbol이 있으면 기업별 정기보고서(대상 기간 periods 안) 행 수를 검사한다."""
    rcept_nos = sorted(set(rcept_nos))
    checks: list[dict] = []
    if not rcept_nos:
        return {"ok": False, "checks": [_check("scope", False, "검사할 문서가 없습니다.")], "fingerprints": {}}

    present = conn.execute(_in("SELECT rcept_no, symbol FROM disclosures WHERE rcept_no IN :rs"), {"rs": rcept_nos}).all()
    missing = sorted(set(rcept_nos) - {r[0] for r in present})
    checks.append(_check("disclosures_present", not missing, {"expected": len(rcept_nos), "missing": missing}))
    symbols = sorted({r[1].strip() for r in present} | set(expected_per_symbol or {}))

    if expected_per_symbol is not None:
        checks.append(validate_disclosures_per_symbol(conn, expected_per_symbol, list(periods or [])))

    duplicates = conn.execute(
        text(
            f"SELECT symbol, kind::text, period_end::text, count(*) FROM disclosures WHERE symbol IN :ss AND {PERIODIC}"
            " AND period_end::text IN :ps"
            " GROUP BY symbol, kind, period_end HAVING count(*) > 1"
        ).bindparams(bindparam("ss", expanding=True), bindparam("ps", expanding=True)),
        {"ss": symbols, "ps": list(periods or [])},
    ).all() if symbols and periods else []
    checks.append(_check("kind_period_unique", not duplicates, [list(map(str, d)) for d in duplicates]))

    stats = conn.execute(
        _in(
            "SELECT d.rcept_no, count(c.id), coalesce(min(c.chunk_index), -1), coalesce(max(c.chunk_index), -1),"
            " count(c.id) FILTER (WHERE c.embedding IS NULL)"
            " FROM disclosures d LEFT JOIN disclosure_chunks c ON c.rcept_no = d.rcept_no"
            " WHERE d.rcept_no IN :rs GROUP BY d.rcept_no"
        ),
        {"rs": rcept_nos},
    ).all()
    chunkless = [r[0] for r in stats if r[1] == 0]
    gaps = [r[0] for r in stats if r[1] and (r[2] != 0 or r[3] != r[1] - 1)]
    nulls = {r[0]: r[4] for r in stats if r[4]}
    total_chunks = sum(r[1] for r in stats)
    checks.append(_check("chunks_exist", not chunkless, {"chunkless": chunkless}))
    checks.append(_check("chunk_index_contiguous", not gaps, {"gaps": gaps}))
    checks.append(_check("embedding_not_null", not nulls, {"null_by_doc": nulls, "total_chunks": total_chunks}))

    norm = conn.execute(
        _in(
            "SELECT min(n), max(n), count(*) FILTER (WHERE n = 'NaN'::float8 OR n = 'Infinity'::float8 OR n < :lo OR n > :hi)"
            " FROM (SELECT vector_norm(embedding) AS n FROM disclosure_chunks WHERE rcept_no IN :rs AND embedding IS NOT NULL) t"
        ),
        {"rs": rcept_nos, "lo": NORM_LOW, "hi": NORM_HIGH},
    ).one()
    checks.append(
        _check(
            "embedding_norm",
            norm[2] == 0 and norm[0] is not None,
            {"min": norm[0], "max": norm[1], "out_of_range_or_nonfinite": norm[2]},
        )
    )

    db_rows = conn.execute(
        _in("SELECT rcept_no, chunk_index, chunk_text FROM disclosure_chunks WHERE rcept_no IN :rs ORDER BY rcept_no, chunk_index"),
        {"rs": rcept_nos},
    ).all()
    db_hashes = {(r[0], r[1]): sha256_text(r[2]) for r in db_rows}
    fingerprints: dict[str, str] = {}
    for rcept_no in rcept_nos:
        hashes = [db_hashes[k] for k in sorted(k for k in db_hashes if k[0] == rcept_no)]
        if hashes:
            fingerprints[rcept_no] = doc_fingerprint(hashes)

    if sparse_dir is not None:
        sparse_keys = sparse_store.keys(sparse_dir, rcept_nos)
        extra, lacking = sorted(sparse_keys - set(db_hashes)), sorted(set(db_hashes) - sparse_keys)
        checks.append(_check("sparse_matches_db", not extra and not lacking, {"sparse": len(sparse_keys), "db": len(db_hashes), "extra": extra[:10], "missing": lacking[:10]}))

    manifest: dict[tuple[str, int], str] = {}
    manifest_rows = 0
    if manifest_path.exists():
        with manifest_path.open(encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    row = json.loads(line)
                    if row["rcept_no"] in rcept_nos:
                        manifest_rows += 1
                        manifest[(row["rcept_no"], int(row["chunk_index"]))] = row["chunk_hash"]
    mismatched = sorted(k for k in set(manifest) | set(db_hashes) if manifest.get(k) != db_hashes.get(k))
    checks.append(
        _check(
            "manifest_matches_db",
            manifest_rows == len(db_hashes) and not mismatched,
            {"manifest_rows": manifest_rows, "db_chunks": len(db_hashes), "mismatched": [list(k) for k in mismatched[:10]]},
        )
    )
    return {"ok": all(c["ok"] for c in checks), "checks": checks, "fingerprints": fingerprints}
