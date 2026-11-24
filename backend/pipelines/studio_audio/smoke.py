"""AI 오디오 DB 없이 끝까지 확인 (2026-11-23). 가상의 브리프(prompt.FEWSHOT_BRIEF: 예시전자·예시금융) → 대본 → 검사 → 읽기 문장
→ TTS → player.html. DB에 연결하지도 쓰지도 않는다. 공용 DB에 시험 데이터를 만들기 전에 LLM·Fish·조립·플레이어를 먼저 본다.

    # 비용 없이: 규칙 대본 + 신호음
    PYTHONPATH=backend python -m pipelines.studio_audio.smoke --llm none --tts fake
    # LLM 대본만 (OpenAI 한 번)
    PYTHONPATH=backend python -m pipelines.studio_audio.smoke --llm openai --tts none
    # Fish 음성 (앞 N줄만 합성해 크레딧 아끼기, 0이면 전부)
    PYTHONPATH=backend python -m pipelines.studio_audio.smoke --llm openai --tts fish --lines 4

결과: results/studio_audio/smoke_<시각>/ (brief.txt · script.json · meta.json · script.md · episode.json · episode.wav · player.html)
주의: 예시 브리프는 프롬프트의 few-shot 예시와 같아서 LLM이 예시 답을 거의 그대로 쓸 수 있다. 대본 품질은 seed_week 데이터로 본다.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from .run import SEOUL, _dump, script_md


def sample_brief():
    """프롬프트 예시(FEWSHOT_BRIEF)와 다른 가상 브리프. 예시와 같은 재료면 LLM이 예시 답을 베껴서 말투·구성을 볼 수 없다.
    회사·매체·숫자는 모두 가상이다 (실제 회사 사실이 아니다)."""
    from app.studio_audio.collect import Brief, CardIn, MarketRow, MemoIn, PriceIn, StockIn

    def src(kind, title, source, day):
        return [{"kind": kind, "title": title, "source": source, "published_at": day, "url": ""}]
    bio = StockIn(
        "900001", "샘플바이오", "보유",
        memos=[MemoIn(11, "미국 공장 진행 상황", "미국 공장 착공 일정이랑 투자 금액 나오면 확인. 자금은 어떻게 마련하는지도 궁금함.",
                      "2026-02-02", ["미국 공장 착공", "자금 조달"])],
        cards=[CardIn("U1", [11], "900001", "공시", "2026-02-03", "유상증자로 1,500억 원 조달",
                      ["샘플바이오가 1,500억 원 규모의 유상증자를 결정했어요.", "새로 발행하는 주식은 1,200만 주예요.",
                       "조달한 돈은 미국 공장 시설 자금에 쓴다고 적혀 있어요."],
                      "메모의 '자금 조달' 항목에 해당하는 공시예요.", "자금 조달", [11], ["미국 공장 진행 상황"],
                      src("공시", "주요사항보고서(유상증자결정)", "DART", "2026-02-03")),
               CardIn("U2", [12], "900001", "뉴스", "2026-02-05", "미국 공장 3월 착공 보도",
                      ["예시일보는 샘플바이오가 미국 공장을 3월에 착공한다고 보도했어요."],
                      "메모의 '미국 공장 착공' 항목과 같은 주제의 기사예요.", "미국 공장 착공", [11], ["미국 공장 진행 상황"],
                      src("뉴스", "샘플바이오, 미국 공장 3월 첫 삽", "예시일보", "2026-02-05"))],
        price=PriceIn("2026-02-02", 84200, "2026-02-06", 81900, -2.73))
    food = StockIn(
        "900002", "샘플식품", "관심",
        memos=[MemoIn(12, "라면 수출 계속 보기", "해외 매출, 특히 라면 수출 숫자 나오면 보고 싶다.", "2026-02-03", ["라면 수출 실적"])],
        cards=[CardIn("U3", [13], "900002", "뉴스", "2026-02-06", "1월 라면 수출 18% 증가",
                      ["예시뉴스는 1월 라면 수출액이 1년 전보다 18% 늘었다고 보도했어요.",
                       "이 가운데 샘플식품 제품이 얼마인지는 기사에 나오지 않았어요."],
                      "메모의 '라면 수출 실적' 항목과 이어지는 기사예요.", "라면 수출 실적", [12], ["라면 수출 계속 보기"],
                      src("뉴스", "1월 라면 수출 18% 늘어", "예시뉴스", "2026-02-06"))],
        price=PriceIn("2026-02-02", 412000, "2026-02-06", 418500, 1.58))
    build = StockIn("900003", "샘플건설", "관심",
                    memos=[MemoIn(13, "해외 수주 공시 확인", "해외 수주 공시 나오면 금액이랑 발주처 확인.", "2026-02-04", ["해외 수주"])])
    return Brief(user_id=0, start="2026-02-02", end="2026-02-08", made_at="2026-02-09T09:00:00+09:00", stocks=[bio, food, build],
                 market=[MarketRow("코스피", "", "2026-02-06", 2588.2, 2571.9, "2026-02-02", 2602.5),
                         MarketRow("원/달러 환율", "원", "2026-02-06", 1412.3, 1418.0, "2026-02-02", 1405.1)])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="AI 오디오 DB 없이 확인 (가상 브리프)")
    ap.add_argument("--llm", choices=["openai", "none"], default="none")
    ap.add_argument("--tts", choices=["fish", "fake", "none"], default="fake")
    ap.add_argument("--lines", type=int, default=0, help="앞 N줄만 합성 (0 = 전부)")
    ap.add_argument("--script", help="이 script.json으로 음성만 만든다 (LLM을 부르지 않음, 같은 --brief로)")
    ap.add_argument("--brief", choices=["sample", "fewshot"], default="sample",
                    help="sample: 예시와 다른 가상 브리프(기본) / fewshot: 프롬프트 예시와 같은 브리프")
    ap.add_argument("--no-emotion", action="store_true", help="감정 태그 없이 보낸다 (같은 --script로 비교 듣기)")
    ap.add_argument("--out-dir", help="결과 폴더 (기본: results/studio_audio)")
    args = ap.parse_args(argv)

    from app.studio_audio.episode import estimate_starts, flatten, lines_dict, text_hash, to_content, write_script
    from app.studio_audio.llm import model_name, openai_call
    from app.studio_audio.prompt import FEWSHOT_BRIEF, build_user, config, target_chars

    from ..common.config import REPO_ROOT, resolve_path
    from ..common.db import load_env
    from .player import render

    load_env()
    cfg = config()
    synth = None
    if args.tts == "fish":
        from app.studio_audio.tts import FishTTS
        synth = FishTTS(cfg["tts"], resolve_path("results/studio_audio/tts_cache"))
        problems = synth.check_ready()
        if problems:
            raise SystemExit("Fish Audio 준비가 안 됐어요: " + " / ".join(problems))
    elif args.tts == "fake":
        from app.studio_audio.tts import FakeTTS
        synth = FakeTTS()

    now = datetime.now(SEOUL)
    out = (Path(args.out_dir) if args.out_dir else REPO_ROOT / "results/studio_audio") / f"smoke_{now:%Y%m%d_%H%M%S}"
    out.mkdir(parents=True)
    brief = sample_brief() if args.brief == "sample" else FEWSHOT_BRIEF
    if args.brief == "sample" and not args.script:              # 만든 시각 = 지금 → 오프닝 소재가 방송마다 바뀐다
        brief.made_at = now.isoformat(timespec="seconds")
    (out / "brief.txt").write_text(build_user(brief, cfg) + "\n", encoding="utf-8")

    if args.script:                                             # 이미 만든 대본으로 음성만 (LLM을 다시 부르면 대본이 바뀐다)
        from app.studio_audio.prompt import PROMPT_VERSION
        from app.studio_audio.schema import check
        script = json.loads(Path(args.script).read_text(encoding="utf-8"))
        meta = {"source": "file", "prompt": PROMPT_VERSION, "tries": 0, "errors": [], "usage": [], "model": None,
                "checks": check(script, brief, cfg)}
    else:
        llm = (lambda msgs: openai_call(msgs, cfg)) if args.llm == "openai" else None
        script, meta = write_script(brief, llm, cfg)
        meta["model"] = model_name(cfg) if llm else None
    _dump(out / "script.json", script)
    _dump(out / "meta.json", meta)
    lines = flatten(script, cfg, emotion=False if args.no_emotion else None)
    print(f"[1] 대본 {meta['source']} · 모델 {meta['model']} · 시도 {meta['tries']} · {len(lines)}줄 · "
          f"{sum(len(ln.text) for ln in lines)}자 (목표 약 {target_chars(brief, cfg)}자) · 토큰 {meta['usage']}")
    for e in meta["errors"]:
        print(f"    검사/호출 오류: {e[:300]}")

    audio_file, tts_info = None, {"provider": args.tts}
    if synth is not None:
        from app.studio_audio.tts import synthesize
        part = lines[:args.lines] if args.lines else lines
        res = synthesize(part, synth, cfg["tts"], out,
                         progress=lambda i, n: print(f"\r[2] 음성 합성 {i}/{n}", end="", flush=True))
        print()
        starts, duration = res["starts"], res["duration"]
        lines = part
        audio_file = Path(res["path"]).name
        voices = {sp: synth.voice(sp) for sp in ("A", "B")}
        tts_info = {"provider": synth.provider, "model": synth.model, "path": res["path"], "duration_sec": duration,
                    "calls": synth.calls, "text_hash": text_hash(lines, voices, synth.model),
                    "speech_chars": sum(len(ln.speech) for ln in lines), "emotion": any(ln.tag for ln in lines)}
        print(f"[2] {synth.provider} {synth.model} · 새 합성 {synth.calls['api']}줄 · 캐시 {synth.calls['cached']}줄 · "
              f"읽기 {tts_info['speech_chars']}자 · {duration:.1f}초 → {res['path']}")
    else:
        starts, duration = estimate_starts(lines, cfg)
        print(f"[2] 음성 없음 · 길이 어림 {duration:.0f}초")
    content = to_content(brief, script, lines, starts, duration, meta, cfg)
    content["audio"] = tts_info
    _dump(out / "episode.json", content)
    (out / "script.md").write_text(script_md(content, lines_dict(lines)), encoding="utf-8")
    (out / "player.html").write_text(render(content, lines_dict(lines), audio_file, brief.to_dict()), encoding="utf-8")
    print(f"[3] 미리듣기: {out / 'player.html'} · 대본: {out / 'script.md'}")
    print(json.dumps({"source": meta["source"], "lines": len(lines), "duration_sec": round(duration, 1)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
