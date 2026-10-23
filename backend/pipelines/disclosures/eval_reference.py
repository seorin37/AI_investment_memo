"""팀 평가기준표(사실 그룹 AND/OR 형식)를 현재 DB 청크에 내용 기준으로 정렬한다 (WO-018).

기준표의 근거 청크 번호(`rcept_no:chunk_index`)는 기준표를 만든 쪽의 청크 기준이라 현재 DB 청크와 번호가 다르다.
근거 발췌(excerpt)를 내용으로 찾아 현재 DB의 청크 번호로 바꾼다.

정렬 규칙 (근거 1개 = valid_evidence_or 항목 1개)
1. content   : 같은 보고서에서 발췌 가운데 두 구간(헤더 제외, 공백·구두점 제거, 40자)이 모두 들어 있고, 그룹의 사실 표현
               (alternatives_or 중 하나)도 들어 있는 청크. 사실 표현은 기준표 규칙대로 헤더(섹션 제목) 포함 전체에서 찾는다
2. numbers   : 1이 없을 때(표는 펼치는 방식이 달라 1이 자주 실패). 사실 표현이 있는 청크를 점수(겹친 숫자 × 2 + 겹친
               한글 낱말 수) 순으로 보며, 이미 고른 청크가 덮지 못한 발췌 숫자를 충분히(2개 이상·발췌 숫자의 1/5 이상)
               새로 덮는 청크만 고른다. 고른 청크들이 발췌 숫자의 1/3 이상을 덮어야 인정. 사람 검토 대상
               (긴 발췌가 DB 청크 여러 개에 걸친 경우는 모두 잡고, 같은 숫자 일부만 가진 다른 표는 빠진다)
- 보고서 교체(rcept_map): 기준표가 쓴 보고서가 DB에 없고 같은 기간의 다른 정정본이 있으면 그 보고서에서 찾는다.
- 그룹 상태: aligned(1로 찾음) / fallback(2로만 찾음) / unresolved(못 찾음) / no_evidence(원래 근거 없음)
- 질문 eval_status: scored, 또는 excluded(not_disclosed_in_scope / no_team_evidence / unresolved_after_alignment)
- needs_human_check: numbers로 찾은 근거, 옮기지 못한 원본 근거, 보고서 교체 중 하나라도 있으면

    PYTHONPATH=backend python -m pipelines.disclosures.eval_reference \\
        --source eval/reference_rag_repair_20261022_v1 --out eval/reference_rag_repair_20261022_v1_db
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from sqlalchemy import text

from ..common.config import resolve_path
from .chunker import CHUNKER_VERSION
from .loader import KST
from .parser import PARSER_VERSION


SOURCE_FILE = "reference_annotations.jsonl"
PROBE_CHARS = 40
_HEADER_RE = re.compile(r"^\s*\[[^\]]*\]")
_KEEP_RE = re.compile(r"[^0-9A-Za-z가-힣]")
_NUMBER_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")
_DATE_LIKE_RE = re.compile(r"(19|20)\d\d((0[1-9]|1[0-2])(\d\d)?)?")
MIN_PROBE_CHARS = 15
_WORD_RE = re.compile(r"[가-힣]{2,}")


def content_key(value: str) -> str:
    """청크 헤더(`[기업 연도 보고서 | 섹션]`)를 빼고 숫자·영문·한글만 남긴다 (서식 차이 무시)."""
    return _KEEP_RE.sub("", _HEADER_RE.sub("", value))


def probes(excerpt: str) -> list[str]:
    """발췌 탐침. 너무 짧은 발췌(`해당사항 없음` 등)는 여러 청크에 흔해 내용 매핑에 쓰지 않는다."""
    key = content_key(excerpt)
    if len(key) < MIN_PROBE_CHARS:
        return []
    if len(key) <= 2 * PROBE_CHARS + 20:
        return [key]
    quarter, half = len(key) // 4, len(key) // 2
    return [key[quarter : quarter + PROBE_CHARS], key[half : half + PROBE_CHARS]]


def number_tokens(value: str) -> set[str]:
    """3자리 이상 숫자(쉼표·소수점 제거)만. 연도·연월·날짜(2025, 2025.12, 2025.12.31)는 뺀다."""
    tokens = {re.sub(r"[,.]", "", m) for m in _NUMBER_RE.findall(_HEADER_RE.sub("", value))}
    return {t for t in tokens if len(t) >= 3 and not _DATE_LIKE_RE.fullmatch(t)}


@dataclass
class DocChunks:
    """한 보고서의 청크: {chunk_index: (본문 key, 섹션+본문 key, section, 본문 숫자 집합)}

    사실 표현은 섹션 제목까지 포함해 찾는다(원본 규칙). 헤더의 기업명·연도·보고서 종류는 넣지 않는다.
    """

    rcept_no: str
    chunks: dict[int, tuple[str, str, str, frozenset]]


def make_doc(rcept_no: str, rows) -> DocChunks:
    """rows: (chunk_index, chunk_text, section)"""
    chunks = {}
    for i, chunk_text, section in rows:
        body = content_key(chunk_text)
        chunks[i] = (body, _KEEP_RE.sub("", section or "") + body, section or "", frozenset(number_tokens(chunk_text)))
    return DocChunks(rcept_no, chunks)


def _has_fact(full_key: str, alternatives: list[str]) -> bool:
    return any(_KEEP_RE.sub("", alt) and _KEEP_RE.sub("", alt) in full_key for alt in alternatives)


def locate_content(excerpt: str, alternatives: list[str], doc: DocChunks) -> list[int]:
    keys = probes(excerpt)
    if not keys:
        return []
    return sorted(i for i, (body, full, _, _) in doc.chunks.items() if all(p in body for p in keys) and _has_fact(full, alternatives))


def locate_numbers(excerpt: str, alternatives: list[str], doc: DocChunks) -> list[int]:
    numbers = number_tokens(excerpt)
    if len(numbers) < 2:
        return []
    words = set(_WORD_RE.findall(_HEADER_RE.sub("", excerpt)))
    candidates = []
    for i, (body, full, _, chunk_numbers) in doc.chunks.items():
        if not _has_fact(full, alternatives):
            continue
        matched = numbers & chunk_numbers  # 숫자 단위로 비교 (붙은 숫자 사이 부분 일치 방지)
        if len(matched) >= 2:
            candidates.append((len(matched) * 2 + sum(1 for w in words if w in body), i, matched))
    min_new = max(2, -(-len(numbers) // 5))
    covered: set[str] = set()
    picked: list[int] = []
    for _, i, matched in sorted(candidates, key=lambda c: (-c[0], c[1])):
        if len(matched - covered) >= min_new:
            picked.append(i)
            covered |= matched
    return sorted(picked) if len(covered) * 3 >= len(numbers) else []


def align_row(row: dict, load_doc: Callable[[str], DocChunks | None], rcept_map: dict[str, str]) -> tuple[dict, list[dict]]:
    """질문 1개를 정렬한다. (정렬된 질문, 근거별 보고 행) 반환. 입력 row는 바꾸지 않는다."""
    row = json.loads(json.dumps(row, ensure_ascii=False))
    report: list[dict] = []
    replaced: dict[str, str] = {}
    group_states = []
    for group in row.get("required_fact_groups", []):
        alternatives = group["required_fact"]["alternatives_or"]
        team_evidence = group.get("valid_evidence_or", [])
        new_evidence: dict[tuple[str, int], dict] = {}
        unaligned = []
        for evidence in team_evidence:
            source_rcept = evidence["rcept_no"]
            doc = load_doc(source_rcept)
            target_rcept = source_rcept
            if doc is None and source_rcept in rcept_map:
                target_rcept = rcept_map[source_rcept]
                doc = load_doc(target_rcept)
                if doc is not None:
                    replaced[source_rcept] = target_rcept
            hits, method = ([], "document_missing")
            if doc is not None:
                hits, method = locate_content(evidence["excerpt"], alternatives, doc), "content"
                if not hits:
                    hits, method = locate_numbers(evidence["excerpt"], alternatives, doc), "numbers"
                if not hits:
                    method = "not_found"
            report.append(
                {
                    "id": row["id"],
                    "group_id": group["group_id"],
                    "team_evidence": f"{source_rcept}:{evidence['chunk_index']}",
                    "db_evidence": " ".join(f"{target_rcept}:{i}" for i in hits),
                    "method": method,
                    "same_index": bool(hits) and target_rcept == source_rcept and evidence["chunk_index"] in hits,
                }
            )
            if not hits:
                unaligned.append({**evidence, "reason": method})
                continue
            for index in hits:
                key = (target_rcept, index)
                previous = new_evidence.get(key)
                if previous is not None and previous["alignment"] == "content":
                    continue
                new_evidence[key] = {
                    "rcept_no": target_rcept,
                    "chunk_index": index,
                    "section": doc.chunks[index][2],
                    "alignment": method,
                    "team_rcept_no": source_rcept,
                    "team_chunk_index": evidence["chunk_index"],
                    "matched_alternatives": [a for a in alternatives if _has_fact(doc.chunks[index][1], [a])],
                    "team_excerpt": evidence.get("excerpt", ""),
                }
        if not team_evidence:
            state = "no_evidence"
        elif not new_evidence:
            state = "unresolved"
        elif any(e["alignment"] == "content" for e in new_evidence.values()):
            state = "aligned"
        else:
            state = "fallback"
        group["team_valid_evidence_or"] = team_evidence
        group["valid_evidence_or"] = [new_evidence[k] for k in sorted(new_evidence)]
        group["unaligned_team_evidence"] = unaligned
        group["alignment_status"] = state
        group["has_numbers_evidence"] = any(e["alignment"] == "numbers" for e in new_evidence.values())
        group_states.append(state)

    # 보고서 교체는 모든 그룹을 본 뒤 한꺼번에 반영한다 (앞 그룹의 report_requirement도 맞춘다)
    for group in row.get("required_fact_groups", []):
        req = group.get("report_requirement", {})
        if req.get("rcept_no") in replaced:
            req["team_rcept_no"] = req["rcept_no"]
            req["rcept_no"] = replaced[req["rcept_no"]]

    for target in row.get("target_reports", []):
        if target.get("rcept_no") in replaced:
            target["team_rcept_no"] = target["rcept_no"]
            target["rcept_no"] = replaced[target["rcept_no"]]
    row["team_repaired_chunk_ids"] = row.get("current_repaired_chunk_ids", [])
    row["current_repaired_chunk_ids"] = sorted(
        {f"{e['rcept_no']}:{e['chunk_index']}" for g in row.get("required_fact_groups", []) for e in g["valid_evidence_or"]}
    )
    groups = row.get("required_fact_groups", [])
    if row.get("verification_status") == "not_disclosed_in_scope":
        status, reason = "excluded", "not_disclosed_in_scope"
    elif not group_states or "no_evidence" in group_states:
        status, reason = "excluded", "no_team_evidence"
    elif "unresolved" in group_states:
        status, reason = "excluded", "unresolved_after_alignment"
    else:
        status, reason = "scored", ""
    row["eval_status"] = status
    row["exclude_reason"] = reason
    # 검토 필요: 숫자로 찾은 근거, 옮기지 못한 원본 근거, 보고서 교체
    row["needs_human_check"] = (
        any(g.get("has_numbers_evidence") or g.get("unaligned_team_evidence") for g in groups) or bool(replaced)
    )
    row["report_replacements"] = replaced
    return row, report


def db_loader(conn) -> Callable[[str], DocChunks | None]:
    cache: dict[str, DocChunks | None] = {}

    def load(rcept_no: str) -> DocChunks | None:
        if rcept_no not in cache:
            rows = conn.execute(
                text("SELECT chunk_index, chunk_text, section FROM disclosure_chunks WHERE rcept_no = :r"), {"r": rcept_no}
            ).all()
            cache[rcept_no] = make_doc(rcept_no, rows) if rows else None
        return cache[rcept_no]

    return load


def same_period_replacements(conn, rcept_nos: set[str], annotations: list[dict]) -> dict[str, str]:
    """기준표 보고서의 청크가 DB에 없으면 같은 (symbol, period_end)의 청크 있는 DB 공시로 바꾼다 (정정본 차이)."""
    present = set(conn.execute(text("SELECT DISTINCT rcept_no FROM disclosure_chunks")).scalars())
    wanted: dict[str, tuple[str, str]] = {}
    for row in annotations:
        for target in row.get("target_reports", []):
            if target.get("rcept_no") in rcept_nos - present:
                wanted[target["rcept_no"]] = (row["symbol"], target["period_end"])
    mapping = {}
    for team_rcept, (symbol, period_end) in wanted.items():
        found = conn.execute(
            text(
                "SELECT d.rcept_no FROM disclosures d WHERE d.symbol = :s AND d.period_end = CAST(:p AS date)"
                " AND d.kind IN ('annual','half','quarterly') AND EXISTS (SELECT 1 FROM disclosure_chunks c WHERE c.rcept_no = d.rcept_no)"
            ),
            {"s": symbol, "p": period_end},
        ).scalars().all()
        if len(found) == 1:
            mapping[team_rcept] = found[0]
    return mapping


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="팀 평가기준표를 현재 DB 청크 번호로 정렬")
    ap.add_argument("--source", required=True, help="기준표 폴더 (reference_annotations.jsonl 포함)")
    ap.add_argument("--out", required=True, help="정렬 결과 폴더")
    args = ap.parse_args(argv)
    source, out = resolve_path(args.source), resolve_path(args.out)
    source_file = source / SOURCE_FILE
    with source_file.open(encoding="utf-8-sig") as handle:
        annotations = [json.loads(line) for line in handle if line.strip()]

    from ..common.db import get_engine

    with get_engine().connect() as conn:
        team_rcepts = {e["rcept_no"] for r in annotations for g in r.get("required_fact_groups", []) for e in g.get("valid_evidence_or", [])}
        rcept_map = same_period_replacements(conn, team_rcepts, annotations)
        load = db_loader(conn)
        aligned, report = [], []
        for row in annotations:
            new_row, rows = align_row(row, load, rcept_map)
            aligned.append(new_row)
            report.extend(rows)
        total_chunks = conn.execute(text("SELECT count(*) FROM disclosure_chunks")).scalar()

    out.mkdir(parents=True, exist_ok=True)
    with (out / SOURCE_FILE).open("w", encoding="utf-8", newline="\n") as handle:
        for row in aligned:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    with (out / "alignment_report.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(report[0].keys()) if report else ["id"])
        writer.writeheader()
        writer.writerows(report)
    with (out / "eval_scope.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["id", "company", "eval_status", "exclude_reason", "needs_human_check", "group_states", "db_chunk_ids", "report_replacements"])
        for row in aligned:
            writer.writerow(
                [
                    row["id"],
                    row.get("company", ""),
                    row["eval_status"],
                    row["exclude_reason"],
                    row["needs_human_check"],
                    " ".join(g["alignment_status"] for g in row.get("required_fact_groups", [])),
                    " ".join(row["current_repaired_chunk_ids"]),
                    " ".join(f"{k}->{v}" for k, v in row["report_replacements"].items()),
                ]
            )

    def count(values):
        result: dict[str, int] = {}
        for value in values:
            result[value] = result.get(value, 0) + 1
        return dict(sorted(result.items()))

    summary = {
        "created_at": datetime.now(KST).isoformat(timespec="seconds"),
        "source": str(source_file),
        "source_sha256": _sha256(source_file),
        "corpus": {"parser_version": PARSER_VERSION, "chunker_version": CHUNKER_VERSION, "db_chunks": total_chunks},
        "report_replacements": rcept_map,
        "questions": count(r["eval_status"] for r in aligned),
        "exclude_reasons": count(r["exclude_reason"] for r in aligned if r["exclude_reason"]),
        "needs_human_check": sum(1 for r in aligned if r["needs_human_check"]),
        "groups": count(g["alignment_status"] for r in aligned for g in r.get("required_fact_groups", [])),
        "team_evidence": count(r["method"] for r in report),
        "team_evidence_same_index": sum(1 for r in report if r["same_index"]),
    }
    (out / "alignment_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
