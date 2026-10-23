"""disclosures · disclosure_chunks · stocks.dart_corp_code · ingest_runs 적재 (스키마 변경 없음).

함수는 Connection을 받아 쓰기만 하고 commit하지 않는다. 트랜잭션 경계는 호출자가 정한다
(실행 진입점은 문서 하나당 `engine.begin()` 하나).
"""

from __future__ import annotations

from pathlib import Path

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import bindparam, text
from sqlalchemy.engine import Connection, Engine

from ..common.logging import REDACTOR
from .chunker import Chunk, doc_fingerprint, sha256_text
from .dart import ReportRef


KST = timezone(timedelta(hours=9))

EXPECTED_EMBEDDING_TYPE = "vector(1024)"


class PreflightError(RuntimeError):
    """적재 전 DB 점검 실패."""


class ReferencedDisclosureError(RuntimeError):
    """교체 대상 공시가 tracking_matches·update_sources에서 참조되고 있어 교체를 중단한다."""


def preflight(conn: Connection, symbols: list[str]) -> None:
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
    if conn.execute(text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")).scalar() is None:
        problems.append("vector 확장이 설치되어 있지 않습니다.")
    found = set(
        conn.execute(text("SELECT symbol FROM stocks WHERE symbol IN :symbols").bindparams(bindparam("symbols", expanding=True)), {"symbols": list(symbols)})
        .scalars()
        .all()
    )
    missing = sorted(set(symbols) - {s.strip() for s in found})
    if missing:
        problems.append(f"stocks에 대상 종목이 없습니다: {', '.join(missing)}")
    column_type = conn.execute(
        text(
            "SELECT format_type(a.atttypid, a.atttypmod) FROM pg_attribute a "
            "WHERE a.attrelid = 'disclosure_chunks'::regclass AND a.attname = 'embedding' AND NOT a.attisdropped"
        )
    ).scalar()
    if column_type != EXPECTED_EMBEDDING_TYPE:
        problems.append(f"disclosure_chunks.embedding 타입이 {EXPECTED_EMBEDDING_TYPE}가 아닙니다: {column_type}")
    if problems:
        raise PreflightError("; ".join(problems))


def update_corp_codes(conn: Connection, corp_codes: dict[str, str]) -> int:
    """stocks.dart_corp_code를 UPDATE만 한다 (INSERT 없음). 바뀐 행 수 반환."""
    changed = 0
    for symbol, corp_code in sorted(corp_codes.items()):
        result = conn.execute(
            text("UPDATE stocks SET dart_corp_code = :corp WHERE symbol = :symbol AND dart_corp_code IS DISTINCT FROM :corp"),
            {"symbol": symbol, "corp": corp_code},
        )
        changed += result.rowcount or 0
    return changed


def _references(conn: Connection, rcept_no: str) -> int:
    return int(
        conn.execute(
            text(
                "SELECT (SELECT count(*) FROM tracking_matches WHERE disclosure_rcept_no = :r)"
                " + (SELECT count(*) FROM update_sources WHERE disclosure_rcept_no = :r)"
            ),
            {"r": rcept_no},
        ).scalar()
    )


def upsert_disclosure(conn: Connection, ref: ReportRef) -> list[str]:
    """공시 1건을 UPSERT한다. 같은 (symbol, kind, period_end)의 이전 정정본은 지우고 그 접수번호를 반환한다.

    이전 정정본이 참조되고 있으면 ReferencedDisclosureError (아무것도 바꾸지 않음).
    """
    params = {"symbol": ref.symbol, "kind": ref.kind, "period_end": date.fromisoformat(ref.period_end), "rcept_no": ref.rcept_no}
    stale = (
        conn.execute(
            text(
                "SELECT rcept_no FROM disclosures WHERE symbol = :symbol AND kind = CAST(:kind AS disclosure_kind)"
                " AND period_end = :period_end AND rcept_no <> :rcept_no ORDER BY rcept_no"
            ),
            params,
        )
        .scalars()
        .all()
    )
    referenced = [old for old in stale if _references(conn, old)]
    if referenced:
        raise ReferencedDisclosureError(
            f"{ref.symbol} {ref.period_end}: 기존 공시 {', '.join(referenced)}가 tracking_matches/update_sources에서 참조되어 "
            f"정정본 {ref.rcept_no}로 교체하지 않았습니다."
        )
    for old in stale:
        conn.execute(text("DELETE FROM disclosure_chunks WHERE rcept_no = :r"), {"r": old})
        conn.execute(text("DELETE FROM disclosures WHERE rcept_no = :r"), {"r": old})
    conn.execute(
        text(
            "INSERT INTO disclosures (rcept_no, symbol, title, kind, period_end, rcept_dt, source_url)"
            " VALUES (:rcept_no, :symbol, :title, CAST(:kind AS disclosure_kind), :period_end, :rcept_dt, :source_url)"
            " ON CONFLICT (rcept_no) DO UPDATE SET symbol = EXCLUDED.symbol, title = EXCLUDED.title, kind = EXCLUDED.kind,"
            " period_end = EXCLUDED.period_end, rcept_dt = EXCLUDED.rcept_dt, source_url = EXCLUDED.source_url"
        ),
        {**params, "title": ref.title, "rcept_dt": date.fromisoformat(ref.rcept_dt), "source_url": ref.source_url},
    )
    return list(stale)


def db_fingerprint(conn: Connection, rcept_no: str) -> str | None:
    """DB에 있는 청크 텍스트로 doc_fingerprint를 다시 계산한다. 청크가 없으면 None."""
    texts = conn.execute(
        text("SELECT chunk_text FROM disclosure_chunks WHERE rcept_no = :r ORDER BY chunk_index"), {"r": rcept_no}
    ).scalars().all()
    return doc_fingerprint([sha256_text(t) for t in texts]) if texts else None


def load_chunks(conn: Connection, rcept_no: str, chunks: list[Chunk]) -> bool:
    """청크를 교체 적재한다 (embedding = NULL). fingerprint가 DB와 같으면 건너뛰고 False."""
    if not chunks:
        raise ValueError(f"{rcept_no}: 적재할 청크가 없습니다.")
    if db_fingerprint(conn, rcept_no) == doc_fingerprint([c.chunk_hash for c in chunks]):
        return False
    conn.execute(text("DELETE FROM disclosure_chunks WHERE rcept_no = :r"), {"r": rcept_no})
    conn.execute(
        text(
            "INSERT INTO disclosure_chunks (rcept_no, chunk_index, section, chunk_text, embedding)"
            " VALUES (:rcept_no, :chunk_index, :section, :chunk_text, NULL)"
        ),
        [
            {"rcept_no": rcept_no, "chunk_index": c.chunk_index, "section": c.section, "chunk_text": c.chunk_text}
            for c in chunks
        ],
    )
    return True


# ── ingest_runs ──────────────────────────────────────
def start_run(engine: Engine) -> int:
    with engine.begin() as conn:
        return int(
            conn.execute(
                text("INSERT INTO ingest_runs (job, target_date, status) VALUES ('disclosures', :d, 'running') RETURNING id"),
                {"d": datetime.now(KST).date()},
            ).scalar()
        )


def finish_run(engine: Engine, run_id: int, status: str, fetched_count: int, error: str | None = None) -> None:
    if status not in {"success", "failed", "empty"}:
        raise ValueError(status)
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE ingest_runs SET status = CAST(:status AS ingest_status), finished_at = now(),"
                " fetched_count = :count, error = :error WHERE id = :id"
            ),
            {"status": status, "count": fetched_count, "error": REDACTOR.redact(error)[:4000] if error else None, "id": run_id},
        )
