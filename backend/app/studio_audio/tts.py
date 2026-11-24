"""Fish Audio TTS: 줄마다 합성(캐시) → 쉼을 넣어 WAV로 이어 붙이기 → (ffmpeg가 있으면) MP3.

- 줄마다 따로 부르는 이유: 줄의 정확한 시작 시각(플레이어 대본 따라가기·챕터)을 알 수 있고, 한 줄만 실패해도 그 줄만 다시 부른다.
  Fish의 다중 화자 한 번 호출(<|speaker:0|> 표시)은 시각을 알 수 없어 쓰지 않는다.
- 캐시: (모델, 목소리, 읽기 문장, 말 빠르기 …) 해시 → cache_dir/<해시>.wav. 같은 문장은 다시 돈을 쓰지 않는다.
- 키는 FISH_API_KEY(환경변수)에서만 읽고 출력하지 않는다.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import struct
import subprocess
import time
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

from .episode import Line


class TTSError(RuntimeError):
    pass


class Synth(Protocol):
    provider: str
    model: str

    def voice(self, speaker: str) -> str: ...
    def __call__(self, text: str, speaker: str) -> bytes: ...


@dataclass
class Pcm:
    rate: int
    channels: int
    width: int
    frames: bytes

    @property
    def seconds(self) -> float:
        return len(self.frames) / (self.rate * self.channels * self.width)


def read_wav(data: bytes) -> Pcm:
    """WAV 바이트 → PCM. 스트리밍 응답처럼 data 크기가 0·최댓값으로 적힌 WAV도 읽는다."""
    if data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise TTSError("WAV가 아닌 응답이에요")
    pos, fmt = 12, None
    while pos + 8 <= len(data):
        cid, size = data[pos:pos + 4], struct.unpack("<I", data[pos + 4:pos + 8])[0]
        body = pos + 8
        if cid == b"fmt ":
            tag, ch, rate, _, _, bits = struct.unpack("<HHIIHH", data[body:body + 16])
            if tag not in (1, 0xFFFE):
                raise TTSError(f"PCM이 아닌 WAV 형식이에요 (format {tag})")
            fmt = (rate, ch, bits // 8)
        elif cid == b"data":
            if fmt is None:
                raise TTSError("WAV fmt 칸이 없어요")
            end = len(data) if size in (0, 0xFFFFFFFF) or body + size > len(data) else body + size
            frames = data[body:end]
            frames = frames[: len(frames) - len(frames) % (fmt[1] * fmt[2])]
            return Pcm(fmt[0], fmt[1], fmt[2], frames)
        pos = body + size + (size & 1)
    raise TTSError("WAV data 칸이 없어요")


def silence(seconds: float, like: Pcm) -> bytes:
    return b"\x00" * (int(seconds * like.rate) * like.channels * like.width)


def write_wav(path: Path, pcm: Pcm) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(pcm.channels)
        w.setsampwidth(pcm.width)
        w.setframerate(pcm.rate)
        w.writeframes(pcm.frames)


class FishTTS:
    provider = "fish"

    def __init__(self, cfg: dict, cache_dir: Path, api_key: str | None = None,
                 post: Callable[..., object] | None = None) -> None:
        self.cfg = cfg
        self.model = os.getenv("FISH_TTS_MODEL") or cfg.get("model") or "s2.1-pro"
        self.voices = {sp: (os.getenv(v.get("env", "")) or v.get("id") or "") for sp, v in (cfg.get("voices") or {}).items()}
        self.key = api_key or os.getenv("FISH_API_KEY") or ""
        self.cache = cache_dir
        self.cache.mkdir(parents=True, exist_ok=True)
        self._post = post
        self.calls = {"api": 0, "cached": 0, "chars": 0}

    def voice(self, speaker: str) -> str:
        return self.voices.get(speaker, "")

    def check_ready(self) -> list[str]:
        problems = []
        if not self.key:
            problems.append("FISH_API_KEY가 없어요 (.env)")
        for sp in ("A", "B"):
            if not self.voice(sp):
                problems.append(f"진행자 {sp} 목소리 id가 없어요 (.env FISH_VOICE_{sp} 또는 configs/studio_audio.yaml)")
        if self.voice("A") and self.voice("A") == self.voice("B"):
            problems.append("두 진행자 목소리가 같아요")
        return problems

    def body(self, text: str, speaker: str) -> dict:
        c = self.cfg
        return {"text": text, "reference_id": self.voice(speaker), "format": "wav",
                "sample_rate": int(c.get("sample_rate", 44100)), "latency": c.get("latency", "normal"),
                "normalize": bool(c.get("normalize", True)), "temperature": float(self._opt(speaker, "temperature", 0.7)),
                "top_p": float(self._opt(speaker, "top_p", 0.7)),
                "prosody": {"speed": float(self._opt(speaker, "speed", 1.0)), "volume": 0}}

    def _opt(self, speaker: str, name: str, default):
        """진행자별 값(voices.<A|B>.<name>)이 있으면 그것, 없으면 tts.<name>. 목소리마다 원래 빠르기가 달라서 따로 맞춘다."""
        v = ((self.cfg.get("voices") or {}).get(speaker) or {})
        return v[name] if v.get(name) is not None else self.cfg.get(name, default)

    def key_of(self, text: str, speaker: str) -> str:
        b = self.body(text, speaker)
        return hashlib.sha256(json.dumps([self.model, b], ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:32]

    def __call__(self, text: str, speaker: str) -> bytes:
        path = self.cache / f"{self.key_of(text, speaker)}.wav"
        if path.exists():
            self.calls["cached"] += 1
            return path.read_bytes()
        import requests
        post = self._post or requests.post
        headers = {"Authorization": f"Bearer {self.key}", "Content-Type": "application/json", "model": self.model}
        tries = int(self.cfg.get("retries", 3))
        last = ""
        for attempt in range(1, tries + 1):
            r = post(self.cfg.get("url", "https://api.fish.audio/v1/tts"), headers=headers, json=self.body(text, speaker),
                     timeout=float(self.cfg.get("timeout", 60)))
            if r.status_code == 200:
                data = r.content
                read_wav(data)                                  # 형식 확인 (깨진 파일은 캐시에 남기지 않는다)
                path.write_bytes(data)
                self.calls["api"] += 1
                self.calls["chars"] += len(text)
                return data
            last = f"HTTP {r.status_code} {str(getattr(r, 'text', ''))[:200]}"
            if r.status_code in (400, 401, 402, 404, 422):     # 다시 불러도 같은 오류 (키·크레딧·목소리 id·요청 형식)
                break
            time.sleep(min(2 ** attempt, 10))
        raise TTSError(f"Fish Audio 합성 실패 ({last})")


class FakeTTS:
    """시험용 가짜 합성: 읽기 문장 글자 수만큼의 짧은 신호음. API 없이 조립·시각 계산·플레이어를 확인한다."""
    provider = "fake"
    model = "fake"

    def __init__(self, cps: float = 5.5, rate: int = 22050) -> None:
        self.cps, self.rate = cps, rate
        self.calls = {"api": 0, "cached": 0, "chars": 0}

    def voice(self, speaker: str) -> str:
        return f"fake-{speaker}"

    def __call__(self, text: str, speaker: str) -> bytes:
        import math
        seconds = max(0.4, len(text) / self.cps)
        freq = 220 if speaker == "A" else 330
        step = int(self.rate * 0.1)                             # 0.1초 소리 + 0.033초 쉼을 되풀이 (말소리 흉내)
        tone = b"".join(struct.pack("<h", int(1500 * math.sin(2 * math.pi * freq * i / self.rate))) for i in range(step))
        unit = tone + b"\x00\x00" * (step // 3)
        n = int(seconds * self.rate) * 2
        frames = (unit * (n // len(unit) + 1))[:n]
        buf = io.BytesIO()
        write_wav_buf(buf, Pcm(self.rate, 1, 2, frames))
        self.calls["api"] += 1
        self.calls["chars"] += len(text)
        return buf.getvalue()


def write_wav_buf(buf: io.BytesIO, pcm: Pcm) -> None:
    with wave.open(buf, "wb") as w:
        w.setnchannels(pcm.channels)
        w.setsampwidth(pcm.width)
        w.setframerate(pcm.rate)
        w.writeframes(pcm.frames)


def synthesize(lines: list[Line], synth: Synth, cfg: dict, out_dir: Path,
               progress: Callable[[int, int], None] | None = None) -> dict:
    """줄마다 합성 → episode.wav (+ episode.mp3). 반환: starts(줄 시작 초)·duration·파일 경로."""
    parts: list[Pcm] = []
    for i, ln in enumerate(lines):
        parts.append(read_wav(synth(ln.tts_text, ln.speaker)))
        if progress:
            progress(i + 1, len(lines))
    base = parts[0]
    if any((p.rate, p.channels, p.width) != (base.rate, base.channels, base.width) for p in parts):
        raise TTSError("줄마다 오디오 형식이 달라요 (sample_rate 설정 확인)")
    from .episode import gap_before
    chunks, starts = [silence(float(cfg.get("lead", 0.3)), base)], []
    t, prev = float(cfg.get("lead", 0.3)), None
    for ln, p in zip(lines, parts):
        gap = gap_before(prev, ln, cfg)
        if gap:
            chunks.append(silence(gap, base))
            t += gap
        starts.append(round(t, 2))
        chunks.append(p.frames)
        t += p.seconds
        prev = ln
    chunks.append(silence(0.5, base))
    full = Pcm(base.rate, base.channels, base.width, b"".join(chunks))
    out_dir.mkdir(parents=True, exist_ok=True)
    wav_path = out_dir / "episode.wav"
    write_wav(wav_path, full)
    result = {"starts": starts, "duration": round(full.seconds, 2), "wav": str(wav_path), "path": str(wav_path),
              "mime": "audio/wav", "bytes": wav_path.stat().st_size}
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        mp3 = out_dir / "episode.mp3"
        r = subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-i", str(wav_path), "-codec:a", "libmp3lame",
                            "-b:a", str(cfg.get("mp3_bitrate", "128k")), str(mp3)], capture_output=True, text=True)
        if r.returncode == 0:
            result.update(path=str(mp3), mime="audio/mpeg", bytes=mp3.stat().st_size, mp3=str(mp3))
        else:
            result["mp3_error"] = r.stderr[-300:]
    return result
