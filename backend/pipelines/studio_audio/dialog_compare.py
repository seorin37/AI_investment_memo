"""AI 오디오 대본 흐름 비교 (2026-11-24, audio-v6 → v7 프롬프트). LLM·Fish를 부르지 않고 이미 만든 smoke 결과를 읽는다.

    PYTHONPATH=backend python -m pipelines.studio_audio.dialog_compare \\
        "v6=results/studio_audio/smoke_20261124_145729" "v7=results/studio_audio/smoke_<시각>"

인자 하나 = 이름=smoke 폴더(script.json·meta.json). 브리프는 smoke 기본 가상 브리프(sample_brief)로 본다.
보는 것 (종목 하나, 기본 900001 샘플바이오):
- 숫자 되묻기: A의 질문 줄이 바로 앞 줄의 숫자를 다시 말하거나, "금액은요?"처럼 숫자 하나만 끌어내는 짧은 질문
- 되풀이 맞장구: 12자 이하 줄이 새 사실 없이 확인만 ("네, 맞아요", "빙고", "딱 맞는 공시네요")
- 앞 줄 겹침: 앞 줄과 글자 두 개 묶음이 절반 넘게 겹치는 줄
- 지금 검사(schema.check) 결과: 그 대본을 지금 규칙으로 다시 검사
결과: 화면 출력 + results/studio_audio/dialog_compare_<시각>.md
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path

NUM = re.compile(r"\d[\d,.]*\d|\d")
PULL = re.compile(r"^(금액|규모|얼마|몇|기간|날짜|언제|종가|숫자)[^ ]{0,4}\?$")
ECHO = re.compile(r"^(네|맞아요|빙고|그렇죠|정확히|딱 맞|아,? 그래요)")


def _bigrams(t: str) -> set[str]:
    t = re.sub(r"[\s.,?!]", "", t)
    return {t[i:i + 2] for i in range(len(t) - 1)}


def flags(prev: dict | None, ln: dict) -> list[str]:
    t = ln["text"].strip()
    out = []
    if prev is not None and ln["speaker"] == "A" and t.endswith("?"):
        same = set(NUM.findall(t)) & set(NUM.findall(prev["text"]))
        if same:
            out.append(f"숫자 되묻기 {sorted(same)}")
    if ln["speaker"] == "A" and PULL.match(t.replace(" ", "")):
        out.append("숫자 끌어내기")
    if len(t) <= 12 and ECHO.match(t):
        out.append("되풀이 맞장구")
    if prev is not None:
        a, b = _bigrams(t), _bigrams(prev["text"])
        if a and len(a & b) / len(a) > 0.5:
            out.append("앞 줄 겹침")
    return out


def analyze(name: str, folder: Path, code: str) -> dict:
    from app.studio_audio.schema import check

    from .smoke import sample_brief
    script = json.loads((folder / "script.json").read_text(encoding="utf-8"))
    meta = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
    seg = next((g for g in script["segments"] if g["kind"] == "stock" and g["stock_code"] == code), {"lines": []})
    rows, prev = [], None
    for ln in seg["lines"]:
        rows.append((ln, flags(prev, ln)))
        prev = ln
    allf = [f for _, fs in rows for f in fs]
    count = lambda key: sum(f.startswith(key) for f in allf)
    return {"name": name, "folder": folder, "source": meta.get("source"), "tries": meta.get("tries"),
            "prompt": meta.get("prompt"), "model": meta.get("model"), "errors": meta.get("errors") or [],
            "recheck": check(script, sample_brief()), "rows": rows, "lines": len(rows),
            "chars": sum(len(ln["text"]) for ln, _ in rows),
            "echo_num": count("숫자 되묻기") + count("숫자 끌어내기"), "echo_ack": count("되풀이 맞장구"),
            "overlap": count("앞 줄 겹침"), "kinds": [g["kind"] for g in script["segments"]]}


def to_md(results: list[dict], code: str) -> str:
    out = [f"# 대본 흐름 비교 ({code} 구간)", "",
           "| | " + " | ".join(r["name"] for r in results) + " |", "|---|" + "---|" * len(results)]
    for label, fn in [("프롬프트", lambda r: r["prompt"]), ("모델", lambda r: r["model"]),
                      ("대본", lambda r: f"{r['source']} · 시도 {r['tries']}"),
                      ("구간", lambda r: " → ".join(r["kinds"])),
                      ("이 종목 줄 · 글자", lambda r: f"{r['lines']}줄 · {r['chars']}자"),
                      ("숫자 되묻기·끌어내기", lambda r: r["echo_num"]), ("되풀이 맞장구", lambda r: r["echo_ack"]),
                      ("앞 줄 겹침", lambda r: r["overlap"]),
                      ("지금 검사", lambda r: "통과" if not r["recheck"] else "<br>".join(r["recheck"])),
                      ("생성 때 재시도 원인", lambda r: "<br>".join(e[:200] for e in r["errors"]) or "없음")]:
        out.append(f"| {label} | " + " | ".join(str(fn(r)).replace("|", "/") for r in results) + " |")
    for r in results:
        out += ["", f"## {r['name']} ({r['folder'].name})", ""]
        for ln, fs in r["rows"]:
            mark = f"  ← **{', '.join(fs)}**" if fs else ""
            refs = f" `{','.join(ln['refs'])}`" if ln["refs"] else ""
            out.append(f"- **{ln['speaker']}** {ln['text']}{refs}{mark}")
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="AI 오디오 대본 흐름 비교")
    ap.add_argument("runs", nargs="+", help="이름=smoke 폴더")
    ap.add_argument("--code", default="900001", help="볼 종목 코드 (기본 샘플바이오)")
    args = ap.parse_args(argv)

    from ..common.config import REPO_ROOT
    results = []
    for spec in args.runs:
        name, _, d = spec.partition("=")
        p = Path(d)
        results.append(analyze(name, p if p.is_absolute() else REPO_ROOT / p, args.code))
    md = to_md(results, args.code)
    out = REPO_ROOT / "results/studio_audio" / f"dialog_compare_{datetime.now():%Y%m%d_%H%M%S}.md"
    out.write_text(md, encoding="utf-8")
    print(md)
    print(f"저장: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
