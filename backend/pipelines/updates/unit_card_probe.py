"""숫자 검사를 실제 공시 표로 확인 (읽기 전용, LLM 없음, 2026-11-18).

    PYTHONPATH=backend python -m pipelines.updates.unit_card_probe [--per 3]

운영 DB에서 "(단위 : 천명)"·"(단위 : 천주)" 표 청크와 "백만원 표 뒤 USD 표" 청크를 찾아, 그 표의 맨숫자 하나로
맞는 카드 문장(개수·맨숫자)과 틀린 카드 문장(원화)을 만들어 지금 checks와 옛 커밋(36dd9dc~1, fd9ac2e)의 checks로 검사한다.
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import subprocess
import tempfile
from pathlib import Path

import psycopg

from pipelines.common.db import get_read_dsn

from . import checks as new

PATTERNS = {"천명": r"단위\s*[:：]\s*천\s*명", "천주": r"단위\s*[:：]\s*천\s*주",
            "USD": r"단위\s*[:：]\s*백만원.*단위\s*[:：]\s*(USD|US\$|천USD)"}
SQL = """SELECT rcept_no, chunk_index, chunk_text FROM disclosure_chunks
         WHERE chunk_text ~ %(pat)s AND chunk_text LIKE '%%[표]%%' ORDER BY rcept_no DESC LIMIT %(n)s"""


def load_rev(rev: str):
    src = subprocess.run(["git", "show", f"{rev}:backend/pipelines/updates/checks.py"], capture_output=True, text=True,
                         check=True).stdout
    path = Path(tempfile.mkdtemp()) / "checks_old.py"
    path.write_text(src.replace("from .models import", "from pipelines.updates.models import"), encoding="utf-8")
    spec = importlib.util.spec_from_file_location(f"checks_{rev.replace('~', '_')}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def first_number_after(text: str, head_pat: str) -> tuple[str, str] | None:
    """머리 뒤 표 행에서 첫 맨숫자(쉼표 3자리 이상)와 그 행."""
    m = re.search(head_pat, text, re.S)
    if not m:
        return None
    for line in text[m.end():].split("\n")[1:]:
        if " | " in line and not re.search(r"\(\s*(단위|원|%)", line.split(" | ", 1)[0]) and not re.search("원화|KRW|환산", line):
            n = re.search(r"(?<![\d.])(\d{1,3}(?:,\d{3})+)(?![\d.])", line.split(" | ", 1)[1])
            if n:
                return n.group(1), line[:120]
        if "단위" in line:
            break
    return None


def supported(mod, ev: str, said: str) -> bool:
    if hasattr(mod, "evidence_number_sets"):
        return mod.evidence_number_sets(ev).supports(said)
    return mod.numbers(said) <= mod.evidence_numbers(ev)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per", type=int, default=3)
    args = ap.parse_args(argv)
    mods = {"36dd9dc~1": load_rev("36dd9dc~1"), "fd9ac2e": load_rev("fd9ac2e"), "now": new}
    with psycopg.connect(get_read_dsn()) as conn:
        conn.read_only = True
        for kind, pat in PATTERNS.items():
            rows = conn.execute(SQL, {"pat": pat, "n": args.per * 4}).fetchall()
            done = 0
            for rcept, idx, text in rows:
                if done >= args.per:
                    break
                head = r"단위\s*[:：]\s*(USD|US\$|천USD)" if kind == "USD" else pat
                got = first_number_after(text, head)
                if not got:
                    continue
                num, row = got
                v = int(num.replace(",", ""))
                if kind == "천명":
                    cases = [(f"{v:,}천 명", True), (f"{v * 1000:,}명", True), (f"{v:,}명", False), (f"{v * 1000:,}원", False)]
                elif kind == "천주":
                    cases = [(f"{v:,}천주", True), (f"{v * 1000:,}주", True), (f"{v:,}주", False), (f"{v * 1000:,}원", False)]
                else:
                    cases = [(num, True), (f"{v * 1_000_000:,}원", False), (f"{v:,}백만원", False), (f"{v:,}원", False)]
                done += 1
                print(f"\n[{kind}] {rcept}#{idx} · {row}")
                for said, want in cases:
                    res = {k: supported(m, text, f"값은 {said}이에요.") for k, m in mods.items()}
                    ok = "OK" if res["now"] == want else "XX"
                    print(f"  {ok} {said:>22} 기대 {'통과' if want else '실패'} | "
                          + " · ".join(f"{k} {'통과' if r else '실패'}" for k, r in res.items()))
        conn.rollback()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
