"""같은 문장을 TTS 설정만 바꿔 합성해 나란히 듣기 (2026-11-23). 목소리 빠르기·숫자 읽기 띄어쓰기·temperature 고르기용.

    PYTHONPATH=backend python -m pipelines.studio_audio.tts_compare --speaker B \\
        --text "2월 6일 코스피는 2,588.2로 마감했어요. 기간 첫 거래일보다 0.55% 낮아요."

결과: results/studio_audio/compare_<시각>/index.html (변형마다 wav · 보낸 읽기 문장 · 설정)
변형: --variants 로 바꿀 수 있다. 각 변형 = 이름:speed:temperature:compact(0|1). compact=1이면 '영 점 오오'를 '영점오오'처럼 붙여 보낸다.
"""
from __future__ import annotations

import argparse
import html
import re
from datetime import datetime
from pathlib import Path

DEFAULT_VARIANTS = ["지금:1.0:0.7:0", "숫자붙임:1.0:0.7:1", "숫자붙임+빠르게:1.15:0.7:1", "숫자붙임+빠르게+안정:1.15:0.5:1"]


def compact_numbers(speech: str) -> str:
    """'이천오백팔십팔 점 이로' → '이천오백팔십팔점이로', '영 점 오오 퍼센트' → '영점오오 퍼센트'."""
    return re.sub(r"(\S+) 점 (\S+)", r"\1점\2", speech)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="TTS 설정 비교 듣기")
    ap.add_argument("--speaker", choices=["A", "B"], default="B")
    ap.add_argument("--text", action="append", required=True, help="화면 문장 (여러 번 가능)")
    ap.add_argument("--variants", nargs="+", default=DEFAULT_VARIANTS, help="이름:speed:temperature:compact")
    ap.add_argument("--raw", action="store_true", help="--text를 읽기 문장으로 바꾸지 않고 그대로 보낸다 (읽는 방식 비교용)")
    args = ap.parse_args(argv)

    from app.studio_audio.prompt import config
    from app.studio_audio.speech import to_speech
    from app.studio_audio.tts import FishTTS

    from ..common.config import REPO_ROOT, resolve_path
    from ..common.db import load_env

    load_env()
    base = config()["tts"]
    out = REPO_ROOT / "results/studio_audio" / f"compare_{datetime.now():%Y%m%d_%H%M%S}"
    out.mkdir(parents=True)
    rows = []
    for ti, text in enumerate(args.text, 1):
        plain = text if args.raw else to_speech(text, config().get("pronounce"))
        for vi, spec in enumerate(args.variants, 1):
            name, speed, temp, compact = spec.split(":")
            voices = {sp: dict(v) for sp, v in (base.get("voices") or {}).items()}
            voices[args.speaker].update(speed=float(speed), temperature=float(temp))
            tts = FishTTS({**base, "voices": voices}, resolve_path("results/studio_audio/tts_cache"))
            if tts.check_ready():
                raise SystemExit("Fish Audio 준비가 안 됐어요: " + " / ".join(tts.check_ready()))
            speech = compact_numbers(plain) if compact == "1" else plain
            fname = f"t{ti}_v{vi}.wav"
            (out / fname).write_bytes(tts(speech, args.speaker))
            rows.append((text, name, speed, temp, speech, fname))
            print(f"문장 {ti} · {name} (speed {speed}, temperature {temp}) → {fname}")
    body = "".join(
        f"<tr><td>{html.escape(n)}</td><td>speed {s} · temp {t}</td><td><audio controls src='{f}'></audio></td>"
        f"<td class='say'>{html.escape(sp)}</td></tr>" for _, n, s, t, sp, f in rows)
    texts = "".join(f"<li>{html.escape(t)}</li>" for t in args.text)
    (out / "index.html").write_text(
        "<!DOCTYPE html><html lang='ko'><head><meta charset='utf-8'><title>TTS 비교</title><style>"
        "body{font-family:'Malgun Gothic',sans-serif;max-width:980px;margin:24px auto;padding:0 16px}"
        "td{padding:6px 8px;border-bottom:1px solid #eee;font-size:13px;vertical-align:middle}.say{color:#666}</style></head>"
        f"<body><h2>진행자 {args.speaker} · TTS 설정 비교</h2><ol>{texts}</ol><table>{body}</table></body></html>",
        encoding="utf-8")
    print(f"비교 페이지: {out / 'index.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
