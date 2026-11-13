"""실험 실행 폴더(들)의 llm_io.jsonl → LLM 입력·응답 원문을 나란히 보는 report (파일만 읽음) (2026-11-12).

    PYTHONPATH=backend python -m pipelines.updates.llm_io_report <실행 폴더 A> [<실행 폴더 B> ...] --out compare.html

experiment --save-llm-io로 만든 실행 폴더를 준다. 항목마다 실행별로: 카드 생성 프롬프트(펼쳐 보기) · LLM 응답 원문(JSON) ·
최종 결과(카드 제목·사실·연결, 또는 응답 유형과 이유) · 사실 문장 수와 글자 수. 관련성 판정·검수 호출은 단계 이름만 센다.
"""

from __future__ import annotations

import argparse
import json
from html import escape
from pathlib import Path

from .memo_followup_report import CSS


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()] if path.is_file() else []


def _pretty(raw: str | None) -> str:
    if raw is None:
        return "(응답 없음)"
    try:
        start, end = raw.index("{"), raw.rindex("}") + 1
        return json.dumps(json.loads(raw[start:end]), ensure_ascii=False, indent=2)
    except ValueError:
        return raw


def _stats(raw: str | None) -> str:
    try:
        data = json.loads(raw[raw.index("{"): raw.rindex("}") + 1])
    except (ValueError, AttributeError, TypeError):
        return ""
    facts = [f.get("text", "") for f in data.get("facts") or [] if isinstance(f, dict)]
    chars = sum(len(t) for t in facts) + len(data.get("headline") or "") + len(data.get("memo_link") or "")
    return f"status {data.get('status')} · 사실 문장 {len(facts)}개 · 제목+사실+연결 {chars}자"


def build(runs: list[Path]) -> str:
    data = []
    for run in runs:
        io = _jsonl(run / "llm_io.jsonl")
        resp = {r["item_id"]: r for r in _jsonl(run / "responses.jsonl")}
        out = {o["item_id"]: o for o in _jsonl(run / "outcomes.jsonl")}
        summary = json.loads((run / "summary.json").read_text(encoding="utf-8")) if (run / "summary.json").is_file() else {}
        data.append((run, io, resp, out, summary))
    items = []
    for _, io, resp, out, _ in data:
        for iid in list(out) + list(resp):
            if iid not in items:
                items.append(iid)
    head = "".join(f"<li><b>{escape(chr(65 + i))}</b> {escape(str(run))} · 모델 {escape(str(s.get('model')))}"
                   f" · LLM 호출 {s.get('llm_calls')}</li>" for i, (run, _, _, _, s) in enumerate(data))
    parts = [f"<h1>LLM 카드 응답 비교</h1><ul class='muted'>{head}</ul>"]
    for iid in items:
        desc = next((o[iid]["description"] for _, _, _, o, _ in data if iid in o), "")
        parts.append(f"<h2>항목 {escape(iid)} · {escape(desc)}</h2>")
        for i, (run, io, resp, out, _) in enumerate(data):
            calls = [c for c in io if c["item_id"] == iid]
            cards = [c for c in calls if c["stage"] not in ("relevance", "verify")]
            other = [c["stage"] for c in calls if c not in cards]
            r = resp.get(iid) or {}
            o = out.get(iid) or {}
            card = o.get("card") or {}
            final = (f"<div class='card'><div class='h'>{escape(card.get('title') or '')}</div>"
                     f"<div class='muted'>when {escape(str(card.get('when') or ''))}</div>"
                     + (f"<p>{escape(card['explanation'])}</p>" if card.get("explanation") else "")
                     + f"<div><b>사실</b> {escape(card.get('summary') or '')}</div>"
                     + (f"<div><b>메모와의 연결</b> {escape(card['memo_link'])}</div>" if card.get("memo_link") else "")
                     + f"<div class='muted'>글자 수: 설명 {len(card.get('explanation') or '')} · 사실 {len(card.get('summary') or '')}"
                       f" · 연결 {len(card.get('memo_link') or '')}</div></div>"
                     if card else f"<div class='muted'>카드 없음 · {escape(r.get('type') or '')} {escape(r.get('reason') or '')}"
                                  f" {escape(' '.join(o.get('fail_codes') or []))}</div>")
            body = [f"<h3>{chr(65 + i)} · 응답 {escape(r.get('type') or '-')}</h3>",
                    f"<div class='muted'>LLM 호출: 카드 {len(cards)}회" + (f" · 그 밖 {', '.join(other)}" if other else "") + "</div>"]
            for n, c in enumerate(cards, 1):
                body.append(f"<details><summary>카드 프롬프트 {n} ({len(c['prompt']):,}자)</summary><pre>{escape(c['prompt'])}</pre></details>"
                            f"<div><b>LLM 응답 원문 {n}</b> <span class='muted'>{escape(_stats(c['response']))}</span></div>"
                            f"<pre>{escape(_pretty(c['response']))}</pre>")
            body.append("<div><b>최종 결과 (코드 검사 뒤)</b></div>" + final)
            parts.append("".join(body))
    return ("<!doctype html><html lang='ko'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>LLM 카드 응답 비교</title><style>{CSS}</style></head><body><main>{''.join(parts)}</main></body></html>")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="llm_io.jsonl → 입력·응답 원문 비교 HTML")
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    out = Path(args.out)
    out.write_text(build([Path(r) for r in args.runs]), encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
