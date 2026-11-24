"""AI 오디오 실행 결과 비교: 비용(LLM 토큰·Fish 글자) + 대본 차이 + 듣기 (2026-11-24). LLM·Fish를 부르지 않는다.

    PYTHONPATH=backend python -m pipelines.studio_audio.cost_compare \\
        "gpt-4.1-mini=results/studio_audio/smoke_20261124_140010:results/studio_audio/smoke_20261124_140138" \\
        "gpt-5.6-sol=results/studio_audio/smoke_<시각>"

인자 하나 = 이름=대본 폴더[:음성 폴더]. 대본 폴더의 meta.json(토큰)·script.json, 음성 폴더의 episode.json(길이·Fish 글자)·episode.wav를 읽는다.
--script로 음성만 다시 만든 폴더는 meta에 토큰이 없어서, 대본을 만든 폴더를 앞에 쓴다.
가격: configs/studio_audio.yaml costs (LLM 1M 토큰당 입력·출력 USD, Fish 1M UTF-8 바이트당 USD). 모르는 값은 비워 두면 비용 칸이 '-'.
결과: results/studio_audio/cost_compare_<시각>/index.html
"""
from __future__ import annotations

import argparse
import html
import json
import os
from datetime import datetime
from pathlib import Path


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _cost(n: float | None, price: float | None) -> float | None:
    return None if n is None or price is None else n / 1_000_000 * price


def _usd(v: float | None) -> str:
    return "-" if v is None else f"${v:.4f}"


def summarize(name: str, script_dir: Path, audio_dir: Path, cfg: dict) -> dict:
    from app.studio_audio.episode import flatten

    meta, script = _load(script_dir / "meta.json"), _load(script_dir / "script.json")
    ep = _load(audio_dir / "episode.json")
    audio = ep.get("audio") or {}
    costs = cfg.get("costs") or {}
    usage = [u for u in meta.get("usage") or [] if u]
    model = meta.get("model") or (usage[0].get("model") if usage else None)
    tin = sum(int(u.get("input") or 0) for u in usage) if usage else None
    tout = sum(int(u.get("output") or 0) for u in usage) if usage else None
    pin, pout = ((costs.get("llm_per_1m") or {}).get(model) or [None, None])
    lines = flatten(script, cfg) if script else []
    total = sum(len(ln.text) for ln in lines) or 1
    fish_bytes = audio.get("speech_bytes") or (sum(len(ln.tts_text.encode("utf-8")) for ln in lines) if lines else None)
    llm_cost = None if pin is None else (_cost(tin, pin) or 0) + (_cost(tout, pout) or 0)
    fish_cost = _cost(fish_bytes, costs.get("fish_per_1m_bytes"))
    wav = audio_dir / "episode.wav"
    return {
        "name": name, "script_dir": script_dir, "audio_dir": audio_dir, "model": model, "source": meta.get("source"),
        "tries": meta.get("tries"), "errors": meta.get("errors") or [], "tokens_in": tin, "tokens_out": tout,
        "llm_cost": llm_cost, "fish_bytes": fish_bytes, "fish_cost": fish_cost,
        "total_cost": None if llm_cost is None or fish_cost is None else llm_cost + fish_cost,
        "lines": len(lines), "chars": sum(len(ln.text) for ln in lines),
        "a_share": sum(len(ln.text) for ln in lines if ln.speaker == "A") / total,
        "short": sum(len(ln.text) <= 10 for ln in lines),
        "duration": audio.get("duration_sec") or ep.get("dur"), "speed": audio.get("speed"),
        "wav": wav if wav.exists() else None, "script": script, "flat": lines}


ROWS = [("모델", lambda r: r["model"] or "-"), ("대본", lambda r: f"{r['source']} · 시도 {r['tries']}"),
        ("토큰 입력 / 출력", lambda r: f"{r['tokens_in'] or '-'} / {r['tokens_out'] or '-'}"),
        ("LLM 비용", lambda r: _usd(r["llm_cost"])),
        ("Fish 보낸 바이트", lambda r: f"{r['fish_bytes']:,}" if r["fish_bytes"] else "-"),
        ("Fish 비용", lambda r: _usd(r["fish_cost"])), ("합계", lambda r: _usd(r["total_cost"])),
        ("줄 수 · 글자", lambda r: f"{r['lines']}줄 · {r['chars']}자"),
        ("A 비중 · 짧은 반응", lambda r: f"{r['a_share']:.0%} · {r['short']}줄"),
        ("길이", lambda r: f"{r['duration']:.0f}초" if r["duration"] else "-"),
        ("말 빠르기 A / B", lambda r: f"{r['speed']['A']} / {r['speed']['B']}" if r["speed"] else "기록 없음"),
        ("검사 오류(재시도 원인)", lambda r: "<br>".join(html.escape(e[:160]) for e in r["errors"]) or "없음")]


def _script_html(r: dict) -> str:
    out, seg = [], None
    for ln in r["flat"]:
        if ln.seg != seg:
            seg = ln.seg
            out.append(f"<div class='seg'>{html.escape(ln.kind)} {html.escape(ln.stock_code)}</div>")
        cue = f" · {ln.cue}" if ln.cue else ""
        refs = f" <span class='refs'>{', '.join(ln.refs)}</span>" if ln.refs else ""
        out.append(f"<div class='ln {ln.speaker}'><b>{ln.speaker}</b> <span class='tone'>{ln.tone}{cue}</span> "
                   f"{html.escape(ln.text)}{refs}</div>")
    return "".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="AI 오디오 실행 비교 (비용·대본)")
    ap.add_argument("runs", nargs="+", help="이름=대본 폴더[:음성 폴더]")
    args = ap.parse_args(argv)

    from app.studio_audio.prompt import config

    from ..common.config import REPO_ROOT

    cfg = config()
    rows = []
    for spec in args.runs:
        name, _, dirs = spec.partition("=")
        sdir, _, adir = dirs.partition(":")
        sdir_p = (REPO_ROOT / sdir) if not os.path.isabs(sdir) else Path(sdir)
        adir_p = ((REPO_ROOT / adir) if not os.path.isabs(adir) else Path(adir)) if adir else sdir_p
        rows.append(summarize(name, sdir_p, adir_p, cfg))

    width = max(len(label) for label, _ in ROWS) + 2
    for label, fn in ROWS[:-1]:
        print(f"{label:<{width}}" + " | ".join(f"{fn(r):<28}" for r in rows))
    out = REPO_ROOT / "results/studio_audio" / f"cost_compare_{datetime.now():%Y%m%d_%H%M%S}"
    out.mkdir(parents=True)
    head = "".join(f"<th>{html.escape(r['name'])}</th>" for r in rows)
    body = "".join(f"<tr><th>{label}</th>" + "".join(f"<td>{fn(r)}</td>" for r in rows) + "</tr>" for label, fn in ROWS)
    players = "".join(f"<td><audio controls src='{os.path.relpath(r['wav'], out)}'></audio></td>" if r["wav"] else "<td>-</td>"
                      for r in rows)
    scripts = "".join(f"<div class='col'><h3>{html.escape(r['name'])}</h3>{_script_html(r)}</div>" for r in rows)
    (out / "index.html").write_text(
        "<!DOCTYPE html><html lang='ko'><head><meta charset='utf-8'><title>오디오 비교</title><style>"
        "body{font-family:'Malgun Gothic',sans-serif;max-width:1200px;margin:24px auto;padding:0 16px;font-size:14px}"
        "table{border-collapse:collapse;width:100%}th,td{border:1px solid #ddd;padding:6px 8px;text-align:left;vertical-align:top}"
        ".cols{display:flex;gap:16px}.col{flex:1;min-width:0}.seg{margin-top:12px;font-weight:bold;color:#555}"
        ".ln{padding:2px 0}.ln.A b{color:#c0392b}.ln.B b{color:#2c5aa0}.tone{color:#999;font-size:12px}.refs{color:#888;font-size:12px}"
        "</style></head><body><h2>AI 오디오 실행 비교</h2>"
        f"<table><tr><th></th>{head}</tr>{body}<tr><th>듣기</th>{players}</tr></table>"
        f"<h2>대본</h2><div class='cols'>{scripts}</div></body></html>", encoding="utf-8")
    print(f"비교 페이지: {out / 'index.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
