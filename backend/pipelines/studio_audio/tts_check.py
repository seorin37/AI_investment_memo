"""Fish Audio 두 진행자 합성 점검 (2026-11-24, 무료 모델 s2.1-pro-free 확인용). LLM·DB를 부르지 않는다.

    PYTHONPATH=backend python -m pipelines.studio_audio.tts_check

고정 대본(A 한 줄 · B 한 줄 · A 한 줄 · B 한 줄)을 실제 서비스와 같은 FishTTS·synthesize로 합성한다.
캐시를 새 폴더로 둬서 반드시 Fish를 부른다. 키·목소리 id 값은 출력하지 않는다 (설정됐는지·서로 다른지만).
결과: results/studio_audio/tts_check_<시각>/ (episode.wav · episode.mp3 · check.json)
"""
from __future__ import annotations

import array
import json
import math
import sys
from datetime import datetime

SCRIPT = {"title": "목소리 점검", "segments": [{"kind": "opening", "stock_code": "", "lines": [
    {"speaker": "A", "text": "안녕하세요, 메모스 라디오예요. 오늘은 목소리 점검부터 할게요.", "refs": [], "tone": "bright", "cue": ""},
    {"speaker": "B", "text": "네, 저는 해설을 맡은 진행자예요. 두 목소리가 다르게 들리는지 봐 주세요.", "refs": [], "tone": "warm", "cue": ""},
    {"speaker": "A", "text": "코스피는 11월 21일 2,588.20으로 마감했어요.", "refs": [], "tone": "calm", "cue": ""},
    {"speaker": "B", "text": "판단은 메모와 원문을 직접 보고 해 주세요.", "refs": [], "tone": "gentle", "cue": ""}]}]}


def rms(frames: bytes, width: int) -> float:
    if width != 2 or not frames:
        return 0.0
    a = array.array("h", frames)
    return math.sqrt(sum(x * x for x in a[:: max(1, len(a) // 20000)]) / max(1, len(a[:: max(1, len(a) // 20000)])))


def main() -> int:
    from app.studio_audio.episode import flatten
    from app.studio_audio.prompt import config
    from app.studio_audio.tts import FishTTS, TTSError, read_wav, synthesize

    from ..common.config import REPO_ROOT
    from ..common.db import load_env

    load_env()
    cfg = config()
    out = REPO_ROOT / "results/studio_audio" / f"tts_check_{datetime.now():%Y%m%d_%H%M%S}"
    synth = FishTTS(cfg["tts"], out / "cache")                      # 새 캐시 → 줄마다 실제 호출
    info = {"model": synth.model, "url": cfg["tts"].get("url"), "key_set": bool(synth.key),
            "voice_a_set": bool(synth.voice("A")), "voice_b_set": bool(synth.voice("B")),
            "voices_differ": synth.voice("A") != synth.voice("B")}
    print(json.dumps(info, ensure_ascii=False))
    problems = synth.check_ready()
    if problems:
        print("준비 안 됨: " + " / ".join(problems))
        return 2
    lines = flatten(SCRIPT, cfg)
    try:
        res = synthesize(lines, synth, cfg["tts"], out)
    except TTSError as exc:                                         # 메시지에 HTTP 상태와 응답 앞부분이 들어 있다 (키는 없음)
        print(f"실패: {exc}")
        (out / "check.json").write_text(json.dumps({**info, "error": str(exc)}, ensure_ascii=False, indent=1), encoding="utf-8")
        return 1
    per = []
    for ln in lines:
        pcm = read_wav((out / "cache" / f"{synth.key_of(ln.tts_text, ln.speaker)}.wav").read_bytes())
        per.append({"speaker": ln.speaker, "chars": len(ln.speech), "sec": round(pcm.seconds, 2),
                    "rms": round(rms(pcm.frames, pcm.width)), "rate": pcm.rate})
    result = {**info, "http": "200 (줄마다)", "api_calls": synth.calls["api"], "lines": per,
              "duration_sec": res["duration"], "file": res["path"], "mime": res["mime"], "bytes": res["bytes"]}
    (out / "check.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
