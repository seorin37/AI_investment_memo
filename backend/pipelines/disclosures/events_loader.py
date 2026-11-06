"""수시공시 DB 저장: disclosures + disclosure_events + disclosure_chunks (run_events 3단계).

정기보고서용 loader.upsert_disclosure와 다르게, 같은 종목의 다른 공시를 지우지 않는다
(수시공시는 같은 종류가 여러 건 나오는 게 정상이다). 정정공시는 원본을 남기고 corrects로 연결한다.

함수는 Connection을 받아 쓰기만 하고 commit하지 않는다. 트랜잭션 경계는 호출자가 정한다.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from sqlalchemy import bindparam, text
from sqlalchemy.engine import Connection

from .chunker import Chunk, sha256_text
from .events_fields import ExtractResult
from .events_list import EventRef
from .events_parse import PARSER_VERSION, ParsedEvent
from .loader import load_chunks


CHUNK_MAX_CHARS = 1500  # BGE-M3 max_length 1024 토큰 안쪽 (한국어 1글자 ≈ 1토큰 이하)
EMPTY_VALUES = {"", "-"}


def preflight_events(conn: Connection) -> None:
    """저장 전 DB 점검: alembic 버전이 코드 head와 같고 disclosure_events가 있어야 한다."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    from .loader import PreflightError

    root = Path(__file__).resolve().parents[3]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "alembic"))
    expected = set(ScriptDirectory.from_config(cfg).get_heads())
    actual = set(conn.execute(text("SELECT version_num FROM alembic_version")).scalars().all())
    problems = []
    if actual != expected:
        problems.append(f"alembic 버전 불일치: DB={sorted(actual)}, 코드={sorted(expected)}")
    if conn.execute(text("SELECT to_regclass('public.disclosure_events')")).scalar() is None:
        problems.append("disclosure_events 테이블이 없습니다 (0014 미적용).")
    if problems:
        raise PreflightError("; ".join(problems))


def known_symbols(conn: Connection, symbols: list[str]) -> set[str]:
    if not symbols:
        return set()
    rows = conn.execute(
        text("SELECT symbol FROM stocks WHERE symbol IN :symbols").bindparams(bindparam("symbols", expanding=True)),
        {"symbols": sorted(set(symbols))},
    ).scalars().all()
    return {row.strip() for row in rows}


def done_rcept_nos(conn: Connection, rcept_nos: list[str], parser_version: str = PARSER_VERSION) -> set[str]:
    """이미 같은 파서 버전으로 처리한(실패 제외) 접수번호. 다시 실행할 때 건너뛴다."""
    if not rcept_nos:
        return set()
    rows = conn.execute(
        text(
            "SELECT rcept_no FROM disclosure_events WHERE rcept_no IN :rs"
            " AND parser_version = :version AND parse_status <> 'failed'"
        ).bindparams(bindparam("rs", expanding=True)),
        {"rs": sorted(set(rcept_nos)), "version": parser_version},
    ).scalars().all()
    return set(rows)


def find_original(conn: Connection, ref: EventRef, original_date: str | None) -> str | None:
    """정정공시가 고치는 직전 공시: 같은 종목·같은 보고서명(정규화)·더 앞선 접수번호 중 가장 최근.

    원래 공시 제출일(정정 표의 '정정관련 공시서류제출일')을 알면 그 날짜에 접수된 것만 본다.
    날짜를 알았는데 그날 공시가 DB에 없으면 추측하지 않고 None.
    """
    sql = (
        "SELECT d.rcept_no FROM disclosures d JOIN disclosure_events e ON e.rcept_no = d.rcept_no"
        " WHERE d.symbol = :symbol AND e.base_title = :base AND d.rcept_no < :rcept_no"
    )
    params: dict = {"symbol": ref.symbol, "base": ref.base_title, "rcept_no": ref.rcept_no}
    if original_date:
        try:
            params["original_date"] = date.fromisoformat(original_date)
        except ValueError:
            return None  # 날짜가 아닌 값이면 추측하지 않는다
        sql += " AND d.rcept_dt = :original_date"
    sql += " ORDER BY d.rcept_no DESC LIMIT 1"
    return conn.execute(text(sql), params).scalar()


def event_chunks(ref: EventRef, parsed: ParsedEvent) -> list[Chunk]:
    """'항목 경로: 값' 줄을 이어 청크를 만든다. 값이 '-'인 줄은 뺀다. 머리말에 회사·날짜·보고서명."""
    header = f"[{ref.corp_name} {ref.rcept_dt} 수시공시 | {ref.title}]\n"
    budget = CHUNK_MAX_CHARS - len(header)
    lines: list[str] = []
    for pair in parsed.pairs:
        value = pair.value.strip()
        if value in EMPTY_VALUES:
            continue
        line = f"{pair.path}: {value}" if pair.path else value
        while len(line) > budget:  # 아주 긴 설명 칸은 잘라서 여러 줄로
            lines.append(line[:budget])
            line = line[budget:]
        lines.append(line)
    bodies: list[str] = []
    current = ""
    for line in lines:
        candidate = f"{current}\n{line}" if current else line
        if len(candidate) > budget and current:
            bodies.append(current)
            current = line
        else:
            current = candidate
    if current:
        bodies.append(current)
    chunks = []
    for index, body in enumerate(bodies):
        chunk_text = header + body
        chunks.append(Chunk(
            rcept_no=ref.rcept_no,
            chunk_index=index,
            section=None,  # 스키마 주석: 수시공시는 NULL
            block_type="event",
            chunk_text=chunk_text,
            token_count=len(chunk_text),  # 근사값 (DB에 저장하지 않음)
            chunk_hash=sha256_text(chunk_text),
        ))
    return chunks


def upsert_event(
    conn: Connection,
    ref: EventRef,
    parsed: ParsedEvent | None,
    result: ExtractResult | None,
    *,
    parse_error: str | None = None,
    parser_version: str = PARSER_VERSION,
) -> dict:
    """공시 1건 저장. parsed가 None이면(원문 파싱 실패) parse_status=failed로 목록 정보만 남긴다.

    반환: {"corrects": 원본 접수번호 또는 None, "chunks_loaded": 청크를 새로 썼는지}
    """
    conn.execute(
        text(
            "INSERT INTO disclosures (rcept_no, symbol, title, kind, period_end, rcept_dt, source_url)"
            " VALUES (:rcept_no, :symbol, :title, CAST(:kind AS disclosure_kind), NULL, :rcept_dt, :source_url)"
            " ON CONFLICT (rcept_no) DO UPDATE SET symbol = EXCLUDED.symbol, title = EXCLUDED.title,"
            " kind = EXCLUDED.kind, rcept_dt = EXCLUDED.rcept_dt, source_url = EXCLUDED.source_url"
        ),
        {
            "rcept_no": ref.rcept_no,
            "symbol": ref.symbol,
            "title": ref.title,
            "kind": ref.kind,
            "rcept_dt": date.fromisoformat(ref.rcept_dt),
            "source_url": ref.source_url,
        },
    )
    correction = (result.correction if result else {}) or {}
    corrects = find_original(conn, ref, correction.get("original_date")) if ref.is_correction else None
    if parsed is None or result is None:
        status, fields, pairs, issues, doc_format = "failed", {}, [], [parse_error or "원문 파싱 실패"], None
    else:
        status, fields, doc_format = result.parse_status, result.fields, parsed.doc_format
        pairs = [pair.to_dict() for pair in parsed.pairs]
        issues = [f"missing: {name}" for name in result.missing] + list(result.errors) + list(parsed.warnings)
        if result.note:
            issues.append(f"{result.note}: 빈 값은 원문에 없음 (검토 불필요)")
    conn.execute(
        text(
            "INSERT INTO disclosure_events (rcept_no, event_type, topic, base_title, is_correction, is_subsidiary,"
            " corrects, fields, pairs, correction, parse_status, parse_issues, doc_format, parser_version)"
            " VALUES (:rcept_no, :event_type, :topic, :base_title, :is_correction, :is_subsidiary, :corrects,"
            " CAST(:fields AS jsonb), CAST(:pairs AS jsonb), CAST(:correction AS jsonb), :status,"
            " CAST(:issues AS jsonb), :doc_format, :parser_version)"
            " ON CONFLICT (rcept_no) DO UPDATE SET event_type = EXCLUDED.event_type, topic = EXCLUDED.topic,"
            " base_title = EXCLUDED.base_title, is_correction = EXCLUDED.is_correction,"
            " is_subsidiary = EXCLUDED.is_subsidiary, corrects = EXCLUDED.corrects, fields = EXCLUDED.fields,"
            " pairs = EXCLUDED.pairs, correction = EXCLUDED.correction, parse_status = EXCLUDED.parse_status,"
            " parse_issues = EXCLUDED.parse_issues, doc_format = EXCLUDED.doc_format,"
            " parser_version = EXCLUDED.parser_version, updated_at = now()"
        ),
        {
            "rcept_no": ref.rcept_no,
            "event_type": ref.event_type,
            "topic": ref.topic,
            "base_title": ref.base_title,
            "is_correction": ref.is_correction,
            "is_subsidiary": ref.is_subsidiary,
            "corrects": corrects,
            "fields": json.dumps(fields, ensure_ascii=False),
            "pairs": json.dumps(pairs, ensure_ascii=False),
            "correction": json.dumps(correction, ensure_ascii=False) if correction else None,
            "status": status,
            "issues": json.dumps(issues, ensure_ascii=False),
            "doc_format": doc_format,
            "parser_version": parser_version,
        },
    )
    chunks_loaded = False
    if parsed is not None:
        chunks = event_chunks(ref, parsed)
        if chunks:
            chunks_loaded = load_chunks(conn, ref.rcept_no, chunks)
    return {"corrects": corrects, "chunks_loaded": chunks_loaded}
