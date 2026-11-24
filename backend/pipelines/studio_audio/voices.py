"""Fish Audio 목소리 찾기·미리 듣기 (2026-11-23). 키는 FISH_API_KEY에서만 읽는다.

    PYTHONPATH=backend python -m pipelines.studio_audio.voices --language ko                 # 공개 목소리 (인기순)
    PYTHONPATH=backend python -m pipelines.studio_audio.voices --language ko --title 뉴스      # 제목으로 좁히기
    PYTHONPATH=backend python -m pipelines.studio_audio.voices --self                         # 내가 만든(복제한) 목소리
    PYTHONPATH=backend python -m pipelines.studio_audio.voices --try <id> [--try <id2>]       # 같은 문장으로 들어 보기

고른 id를 .env에 FISH_VOICE_A=<메인 진행자 id>, FISH_VOICE_B=<해설 진행자 id> 로 넣는다.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

SAMPLE = "11월 셋째 주 내 종목 라디오예요. 에스케이하이닉스는 11월 18일 다트에 신규 시설투자 공시가 올라왔어요."


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Fish Audio 목소리 찾기")
    ap.add_argument("--language", default="ko")
    ap.add_argument("--title")
    ap.add_argument("--self", action="store_true", help="내 목소리만")
    ap.add_argument("--sort", default="task_count", help="task_count(많이 쓴 순) | score | created_at")
    ap.add_argument("--size", type=int, default=20)
    ap.add_argument("--try", dest="tries", action="append", help="이 목소리 id로 예시 문장을 합성해 본다 (여러 번 가능)")
    ap.add_argument("--text", default=SAMPLE)
    args = ap.parse_args(argv)

    import requests

    from app.studio_audio.prompt import config
    from app.studio_audio.tts import FishTTS

    from ..common.config import resolve_path
    from ..common.db import load_env
    load_env()
    key = os.getenv("FISH_API_KEY")
    if not key:
        raise SystemExit("FISH_API_KEY가 없어요 (.env)")
    headers = {"Authorization": f"Bearer {key}"}

    if args.tries:
        out = resolve_path("results/studio_audio/voice_try")
        out.mkdir(parents=True, exist_ok=True)
        cfg = dict(config()["tts"])
        for vid in args.tries:
            cfg["voices"] = {"A": {"id": vid}}
            tts = FishTTS(cfg, resolve_path("results/studio_audio/tts_cache"), api_key=key)
            path = Path(out) / f"{vid}.wav"
            path.write_bytes(tts(args.text, "A"))
            print(f"{vid} → {path}")
        return 0

    params = {"page_size": args.size, "page_number": 1, "sort_by": args.sort}
    if args.self:
        params["self"] = "true"
    else:
        params["language"] = args.language
    if args.title:
        params["title"] = args.title
    r = requests.get("https://api.fish.audio/model", headers=headers, params=params, timeout=30)
    if r.status_code != 200:
        raise SystemExit(f"목록을 받지 못했어요: HTTP {r.status_code} {r.text[:200]}")
    data = r.json()
    print(f"{data.get('total', '?')}개 중 {len(data.get('items') or [])}개")
    for m in data.get("items") or []:
        langs = ",".join(m.get("languages") or [])
        tags = ",".join((m.get("tags") or [])[:4])
        print(f"{m.get('_id')}  {m.get('title', '')[:30]:<30}  언어 {langs:<8} 사용 {m.get('task_count', '-'):>8}  {tags}")
    print("\n들어 보기: --try <id> --try <id2>   ·   고른 뒤 .env에 FISH_VOICE_A / FISH_VOICE_B")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
