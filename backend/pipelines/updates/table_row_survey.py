"""공시 청크의 표가 "한 줄 = 표 한 행"인지 세기 (읽기 전용, 2026-11-18).

    PYTHONPATH=backend python -m pipelines.updates.table_row_survey [--limit N]

숫자 검사(checks.evidence_number_sets)는 표 행 이름표의 단위("주당배당금(단위: 원) | …")를 그 줄에만 적용한다.
그래서 청크 글에서 표 한 행이 한 줄에 다 들어 있는지 확인한다. 청커(disclosures/chunker._table_bodies)는 행을 "\\n"으로 잇고,
행 하나가 토큰 한도를 넘을 때만 _hard_split으로 잘라 여러 줄로 만든다. 잘린 뒤 조각은 이름표 없이 시작한다.
- 행 줄: 표 안([표] 줄부터 빈 줄까지)에서 머리말([표]·단위·열:)이 아닌 줄
- 잘림 의심: 앞 줄이 400자 이상이고 이번 줄이 이름표("이름 | " 또는 "이름: ")로 시작하지 않는 줄
- 이름표 단위: 첫 " | " 앞 이름표의 괄호 단위 ("(단위: 원)"·"(원)"·"(%)"…). 앞 글자에 붙었는지 띄어 썼는지도 센다
- 표 머리 여러 개: 한 청크에 서로 다른 "(단위 : …)" 머리(이름표 밖)가 둘 이상
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter

import psycopg

from pipelines.common.db import get_read_dsn

SQL = """SELECT c.rcept_no, c.chunk_index, c.chunk_text FROM disclosure_chunks c
WHERE c.chunk_text LIKE '%%[표]%%' ORDER BY c.rcept_no, c.chunk_index {limit}"""
_PREFIX = re.compile(r"^(\[표\]|\(?\s*단위|열: )")
_LABEL_START = re.compile(r"^[^|:]{1,80}(\s\|\s|:\s)")
_HEAD = re.compile(r"단위\s*[:：]?\s*(조원|억원|백만원|천원|원|천주|주|%)")
_LABEL_UNIT = re.compile(r"(\s?)\(\s*(단위\s*[:：]?\s*)?([^()]{1,12}?)\s*[,)]")
_BARE_OK = {"원", "천원", "백만원", "억원", "조원", "%"}   # "(주)"는 주식회사라 "단위" 없이는 단위로 보지 않는다
# 행이 토큰 한도로 잘린 뒤 조각: 칸 경계(": 값", " | ", 숫자 중간)에서 시작한다
_CONT = re.compile(r"^(?:[:|,]|\d{1,3}(?:,\d{3})+(?:\s|$)|\d*,\d{3})")
_UNITS = {"원", "천원", "백만원", "억원", "조원", "%", "주", "천주", "배", "명", "개", "건", "회"}


def _in_label(text: str, pos: int) -> bool:
    """pos가 표 행 이름표(그 줄의 첫 " | " 앞) 안인가."""
    start = text.rfind("\n", 0, pos) + 1
    end = text.find("\n", pos)
    line = text[start:end if end >= 0 else len(text)]
    return " | " in line and pos - start < line.index(" | ")


def survey(rows) -> dict:
    stats = Counter()
    row_units = Counter()
    samples = {"split": [], "multi_header": [], "spaced": [], "split_unit": []}
    for rcept, idx, text in rows:
        stats["chunks"] += 1
        heads = {m.group(1) for m in _HEAD.finditer(text) if not _in_label(text, m.start())}
        if len(heads) > 1:
            stats["multi_header_chunks"] += 1
            if len(samples["multi_header"]) < 3:
                samples["multi_header"].append(f"{rcept}#{idx}: {sorted(heads)}")
        in_table, prev, prev_in_table, prev_unit = False, "", False, False
        for line in text.split("\n"):
            if line.startswith("[표]"):
                in_table = True
            elif not line.strip():
                in_table = False
            if not in_table or _PREFIX.match(line):
                prev, prev_in_table, prev_unit = line, False, False
                continue
            stats["row_lines"] += 1
            if " | " not in line:
                stats["row_lines_no_pipe"] += 1
            label = line.split(" | ", 1)[0] if " | " in line else ""
            found = [(sp, u) for sp, kw, u in _LABEL_UNIT.findall(label) if u in _UNITS and (kw or u in _BARE_OK)]
            if _CONT.match(line) and prev_in_table:
                stats["split_strong"] += 1
                if prev_unit:
                    stats["split_strong_after_row_unit"] += 1
                    if len(samples["split_unit"]) < 5:
                        samples["split_unit"].append(f"{rcept}#{idx}: …{prev[-60:]!r} ⏎ {line[:80]!r}")
            if len(line) >= 900:
                stats["row_lines_900chars"] += 1
            prev_in_table = True
            if " | " in line:
                prev_unit = bool(found)
            if found:
                sp, u = found[-1]
                stats["row_unit_lines"] += 1
                stats["row_unit_spaced" if sp else "row_unit_attached"] += 1
                row_units[u] += 1
                if sp and len(samples["spaced"]) < 3:
                    samples["spaced"].append(f"{rcept}#{idx}: {label[:80]!r}")
            if len(prev) >= 400 and not _LABEL_START.match(line):
                stats["split_suspect"] += 1
                if len(samples["split"]) < 5:
                    samples["split"].append(f"{rcept}#{idx}: …{prev[-60:]!r} ⏎ {line[:80]!r}")
            prev = line
    return {"stats": dict(stats), "row_units": dict(row_units.most_common(20)), "samples": samples}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="공시 표 청크의 줄 구조 세기 (읽기 전용)")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args(argv)
    with psycopg.connect(get_read_dsn()) as conn:
        conn.read_only = True
        rows = conn.execute(SQL.format(limit=f"LIMIT {args.limit}" if args.limit else "")).fetchall()
        conn.rollback()
    out = survey(rows)
    print(json.dumps(out["stats"], ensure_ascii=False))
    print(json.dumps(out["row_units"], ensure_ascii=False))
    for k, v in out["samples"].items():
        print(k, json.dumps(v, ensure_ascii=False, indent=0))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
