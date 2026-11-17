"""숫자 검사(checks.py) 고치기 전·후를 지난 실행 결과로 비교 (결과 파일만 읽음, DB·LLM 없음) (2026-11-17).

    PYTHONPATH=backend python -m pipelines.updates.number_check_compare <실행 폴더 또는 그 위 폴더> ... [--old-rev HEAD] [--out x.md]

llm_io.jsonl(experiment --save-llm-io)이 있는 실행만 쓸 수 있다: 카드 프롬프트의 "# 새 근거"에 LLM이 본 근거 원문이 있고,
응답 원문에 검사에서 떨어진 카드까지 남아 있기 때문이다. 근거 블록을 Evidence로 되살려 check_card_v2를 고치기 전 코드
(git --old-rev의 checks.py)와 지금 코드로 각각 돌리고 NUMBER가 바뀐 카드를 보여 준다.
"근거엔 단위가 붙은 숫자를 카드가 맨숫자로 쓴" 경우는 바뀌었는지와 상관없이 따로 모은다.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

from . import checks as new
from .judge import parse_card_v2
from .models import Candidate, Evidence

_SECTION = re.compile(r"# 새 근거\n(.*?)(?=\n# |\Z)", re.S)
_HEAD = re.compile(r"(E\d+) \[([^\]]+)\]\n")
_FIELD = {"제목": "title", "보고서명": "title", "게시 일자": "date", "접수일": "date", "언론사": "source"}


def load_old(rev: str):
    """git rev의 checks.py를 pipelines.updates._checks_old 모듈로 읽는다 (상대 import .models가 되게 패키지 이름을 준다)."""
    root = Path(__file__).resolve().parents[3]
    src = subprocess.run(["git", "-C", str(root), "show", f"{rev}:backend/pipelines/updates/checks.py"],
                         check=True, capture_output=True, text=True).stdout
    spec = importlib.util.spec_from_loader("pipelines.updates._checks_old", loader=None)
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = "pipelines.updates"
    exec(compile(src, f"{rev}:checks.py", "exec"), mod.__dict__)
    sys.modules[spec.name] = mod
    return mod


def parse_evidence(prompt: str) -> list[Evidence]:
    """카드 프롬프트의 "# 새 근거" 블록 → Evidence (judge.evidence_block의 거꾸로)."""
    m = _SECTION.search(prompt)
    if not m:
        return []
    body = m.group(1).strip()
    heads = list(_HEAD.finditer(body))
    out = []
    for i, h in enumerate(heads):
        block = body[h.end(): heads[i + 1].start() if i + 1 < len(heads) else len(body)].rstrip()
        eid, label = h.groups()
        f = {"title": "", "date": "", "source": ""}
        shown = block
        if label != "직전 같은 기간 비교":
            for key in ("제공 요약", "원문 발췌"):
                pre, sep, rest = block.partition(f"- {key}: ")
                if sep:
                    shown = rest
                    for line in pre.splitlines():
                        k, _, v = line.removeprefix("- ").partition(": ")
                        if k in _FIELD:
                            f[_FIELD[k]] = v.strip()
                    break
        kind = "disclosure" if label == "공시" else "news"
        doc = "compare" if label == "직전 같은 기간 비교" else ""
        out.append(Evidence(eid, Candidate(f"{eid}", kind, "", f["date"], f["title"], shown, None, f["source"], 0.0, doc),
                            shown))
    return out


def _texts(card) -> list[tuple[str, str]]:
    """(자리, 문장). 사실 문장은 쓴 근거 번호를 붙인다."""
    out = [("제목", card.headline)]
    out += [(f"사실 {eid or '-'}", t) for t, eid in card.facts]
    out.append(("메모 연결", card.memo_link))
    if getattr(card, "explanation", ""):
        out.append(("설명", card.explanation))
    return out


def _around(text: str, digits: str, width: int = 40) -> str:
    i = text.find(digits)
    if i < 0:
        return ""
    return "…" + text[max(0, i - width): i + len(digits) + width].replace("\n", " ") + "…"


def _raw_numbers(text: str) -> list[tuple[str, str]]:
    """(숫자 글자, 붙은 단위·원). 단위가 없으면 ""."""
    out = []
    for m in new._NUM.finditer(text or ""):
        raw, unit, pct, won = m.groups()
        tail = (unit or "") + ("원" if won else "") + (pct or "")
        out.append((raw, tail))
    return out


def bare_vs_unit(card, evidence: list[Evidence]) -> list[tuple[str, str, str]]:
    """근거에 단위(조·억·백만…)나 원이 붙은 숫자를 카드가 맨숫자로 쓴 곳: (자리, 카드 숫자, 근거 표기)."""
    ev_tail = {}
    for e in evidence:
        for raw, tail in _raw_numbers(f"{e.candidate.title} {e.shown_text}"):
            if tail and not tail.endswith(("%", "퍼센트")) and len(raw.replace(",", "")) >= 2:
                ev_tail.setdefault(raw.replace(",", ""), raw + tail)
    out = []
    for where, t in _texts(card):
        for raw, tail in _raw_numbers(t):
            if not tail and raw.replace(",", "") in ev_tail:
                out.append((where, raw, ev_tail[raw.replace(",", "")]))
    return out


def _runs(paths: list[str]) -> list[Path]:
    out = []
    for p in map(Path, paths):
        out += [p] if (p / "llm_io.jsonl").is_file() else sorted(x.parent for x in p.rglob("llm_io.jsonl"))
    return out


def compare(runs: list[Path], old) -> dict:
    rows, bare, seen = [], [], set()
    stats = {"runs": len(runs), "card_calls": 0, "update_cards": 0, "unique_cards": 0, "fail_to_pass": 0, "pass_to_fail": 0,
             "same_fail": 0, "same_pass": 0, "no_evidence": 0}
    for run in runs:
        for line in (run / "llm_io.jsonl").read_text(encoding="utf-8").splitlines():
            c = json.loads(line)
            if c["stage"] not in ("card", "format_retry"):
                continue
            stats["card_calls"] += 1
            card = parse_card_v2(c.get("response") or "")
            if card is None or card.status != "update":
                continue
            evidence = parse_evidence(c["prompt"])
            if not evidence:
                stats["no_evidence"] += 1
                continue
            stats["update_cards"] += 1
            key = (c["item_id"], c.get("response"))
            if key in seen:
                continue
            seen.add(key)
            stats["unique_cards"] += 1
            cfg = {"explanation": {"enabled": bool(card.explanation)}}
            before = "NUMBER" in old.check_card_v2(card, evidence, [], cfg)
            after = "NUMBER" in new.check_card_v2(card, evidence, [], cfg)
            stats[{(True, False): "fail_to_pass", (False, True): "pass_to_fail",
                   (True, True): "same_fail", (False, False): "same_pass"}[(before, after)]] += 1
            where = f"{run.parent.name}/{run.name} · 항목 {c['item_id']} · {c['stage']}"
            if before != after:
                rows.append({"where": where, "change": "실패→통과" if before else "통과→실패",
                             "lines": _changed_lines(card, evidence, old)})
            for b in bare_vs_unit(card, evidence):
                bare.append({"where": where, "place": b[0], "card": b[1], "evidence": b[2],
                             "before": "NUMBER" if before else "통과", "after": "NUMBER" if after else "통과"})
    return {"stats": stats, "changed": rows, "bare": bare}


def _changed_lines(card, evidence, old) -> list[dict]:
    """판정이 바뀐 문장: 카드 문장 · 그 문장의 숫자 · 근거에서 같은 숫자가 나온 곳."""
    ids = {e.eid: e for e in evidence}
    out = []
    for where, t in _texts(card):
        eid = where.split()[-1] if where.startswith("사실") else ""
        pool = [ids[eid]] if eid in ids else evidence
        ev_old = set().union(*(old.evidence_numbers(f"{e.candidate.title} {e.shown_text} {e.candidate.date}") for e in pool))
        ok_old = old.numbers(t) <= ev_old
        ev_new = new.EvidenceNumbers()
        for e in pool:
            ev_new |= new.evidence_number_sets(f"{e.candidate.title} {e.shown_text} {e.candidate.date}")
        ok_new = ev_new.supports(t)
        if ok_old == ok_new:
            continue
        nums = _raw_numbers(t)
        hits = []
        for raw, _ in nums:
            for e in pool:
                s = _around(f"{e.candidate.title} {e.shown_text}", raw)
                if s:
                    hits.append(f"{e.eid}: {s}")
                    break
            else:
                hits.append(f"{raw}: 근거에서 같은 글자 못 찾음")
        out.append({"place": where, "text": t, "numbers": [r + u for r, u in nums], "evidence": hits,
                    "before": "통과" if ok_old else "NUMBER", "after": "통과" if ok_new else "NUMBER"})
    return out


def to_markdown(res: dict, runs: list[Path], rev: str) -> str:
    s = res["stats"]
    lines = [f"# 숫자 검사 고치기 전({rev}) · 후 비교", "",
             f"- 실행 {s['runs']}개, 카드 호출 {s['card_calls']}회, update 카드 {s['update_cards']}장(같은 응답 중복 제외 {s['unique_cards']}장)",
             f"- 실패→통과 {s['fail_to_pass']} · 통과→실패 {s['pass_to_fail']} · 그대로 실패 {s['same_fail']} · 그대로 통과 {s['same_pass']}",
             f"- 근거 블록을 못 찾은 카드 {s['no_evidence']}", "", "## 판정이 바뀐 카드", ""]
    if not res["changed"]:
        lines.append("(없음)")
    for r in res["changed"]:
        lines += [f"### {r['change']} · {r['where']}", ""]
        for x in r["lines"]:
            lines += [f"- **{x['place']}** ({x['before']} → {x['after']}): {x['text']}",
                      f"  - 카드 숫자: {', '.join(x['numbers'])}"]
            lines += [f"  - 근거 {h}" for h in x["evidence"]]
        lines.append("")
    lines += ["## 근거엔 단위가 붙어 있는데 카드엔 맨숫자만 쓴 곳", ""]
    if not res["bare"]:
        lines.append("(없음)")
    for b in res["bare"]:
        lines.append(f"- {b['where']} · {b['place']}: 카드 `{b['card']}` ↔ 근거 `{b['evidence']}` (전 {b['before']} → 후 {b['after']})")
    lines += ["", "실행 폴더:", *[f"- {r}" for r in runs]]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="숫자 검사 고치기 전·후를 지난 실행(llm_io.jsonl)으로 비교")
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--old-rev", default="HEAD")
    ap.add_argument("--out")
    args = ap.parse_args(argv)
    runs = _runs(args.paths)
    res = compare(runs, load_old(args.old_rev))
    md = to_markdown(res, runs, args.old_rev)
    if args.out:
        Path(args.out).write_text(md, encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
