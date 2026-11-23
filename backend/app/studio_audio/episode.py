"""브리프 → 대본(LLM → 검사 → 재시도 → 규칙 대본) → 줄 목록(화면 문장 + 읽기 문장) → 화면 결과(studio_items.content) 모양.

화면 결과 모양은 frontend/src/ui/screens/studio/Studio.mock.ts 의 mockAudioEpisode 와 같다:
hosts · dur · chapters [[초, 이름]] · script [[초, 'A'|'B', 문장]] · sources · market_source · memo_link
"""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import asdict, dataclass
from typing import Callable

from .collect import Brief, day_label
from .fallback import fallback
from .prompt import PROMPT_VERSION, config, messages
from .schema import check
from .speech import to_speech

log = logging.getLogger("studio_audio")
LLMCall = Callable[[list[dict]], dict]


class NoUpdatesError(LookupError):
    """고른 종목에 기간 안 새 업데이트가 없고 증시 요약도 끔 (오디오를 만들지 않고 크레딧도 쓰지 않는다).
    프론트 시트와 같은 규칙: 업데이트 0건이어도 증시 요약을 켜면 만든다."""


@dataclass
class Line:
    seg: int
    kind: str
    stock_code: str
    speaker: str
    text: str           # 화면 문장
    speech: str         # 읽기 문장 (숫자 → 한글)
    refs: list[str]
    tone: str = "calm"
    tag: str = ""       # 감정 태그 ([calm, clear news anchor tone]). 켜져 있을 때만

    @property
    def tts_text(self) -> str:
        """Fish Audio로 보내는 문장 = 태그 + 읽기 문장."""
        return f"{self.tag} {self.speech}" if self.tag else self.speech


def write_script(brief: Brief, llm: LLMCall | None, cfg: dict | None = None) -> tuple[dict, dict]:
    cfg = cfg or config()
    if not brief.news_stocks and not brief.market:
        raise NoUpdatesError("고른 종목에 기간 안 새 업데이트가 없고 증시 요약도 꺼져 있어요")
    meta = {"prompt": PROMPT_VERSION, "tries": 0, "errors": [], "usage": [], "source": "rules"}
    script, fix = None, None
    for attempt in range(1, int(cfg["script"].get("tries", 2)) + 1) if llm else []:
        meta["tries"] = attempt
        try:
            raw = llm(messages(brief, fix, cfg))
        except Exception as exc:
            meta["errors"].append(f"try{attempt}: {type(exc).__name__}: {str(exc)[:200]}")
            log.warning("audio llm error try=%s: %s", attempt, type(exc).__name__)
            continue
        meta["usage"].append(raw.pop("_usage", {}))
        errors = check(raw, brief, cfg)
        if not errors:
            script, meta["source"] = raw, "llm"
            break
        meta["errors"].append(f"try{attempt}: " + " | ".join(errors))
        meta.setdefault("rejected", []).append(raw)
        fix = errors
    if script is None:
        script = fallback(brief)
        leftover = check(script, brief, cfg)
        if leftover:                       # 규칙 대본도 걸리면 기록만 (카드 문장 자체가 이미 검사를 통과한 사실)
            meta["fallback_warnings"] = leftover
        log.warning("audio fallback errors=%s", meta["errors"])
    return script, meta


DEFAULT_TONE = {"opening": "warm", "market": "calm", "stock": "calm", "no_news": "calm", "closing": "gentle"}


def flatten(script: dict, cfg: dict | None = None, emotion: bool | None = None) -> list[Line]:
    """emotion: 감정 태그를 붙일지 (None이면 설정 tts.emotion). tone이 없는 예전 대본은 구간별 기본 톤."""
    cfg = cfg or config()
    words = cfg.get("pronounce") or {}
    tts = cfg.get("tts") or {}
    on = tts.get("emotion", False) if emotion is None else emotion
    tags = tts.get("tones") or {}
    out = []
    for i, g in enumerate(script["segments"]):
        for line in g["lines"]:
            text = " ".join(str(line["text"]).split())
            tone = line.get("tone") or DEFAULT_TONE.get(g["kind"], "calm")
            out.append(Line(i, g["kind"], g.get("stock_code") or "", line["speaker"], text, to_speech(text, words),
                            list(line.get("refs") or []), tone, tags.get(tone, "") if on else ""))
    return out


def text_hash(lines: list[Line], voices: dict[str, str], model: str) -> str:
    """대본·목소리·모델이 같으면 같은 값 (audio_assets.text_hash: 같은 대본은 다시 합성하지 않는다)."""
    body = json.dumps([[ln.speaker, ln.tts_text] for ln in lines] + [voices, model], ensure_ascii=False)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def chapter_label(brief: Brief, kind: str, code: str) -> str:
    if kind == "opening":
        return "오프닝"
    if kind == "market":
        last = brief.market[0].last_date if brief.market else brief.end
        return f"{day_label(last)[:-3]} 증시 요약"
    if kind == "stock":
        st = brief.stock(code)
        return st.name if st else code
    if kind == "no_news":
        return " · ".join(s.name for s in brief.quiet_stocks) + " · 새 소식 없음"
    return "마무리"


def _mmdd(iso: str) -> str:
    return f"{iso[5:7]}.{iso[8:10]}" if len(iso) >= 10 else iso


def to_content(brief: Brief, script: dict, lines: list[Line], starts: list[float], duration: float,
               meta: dict, cfg: dict | None = None) -> dict:
    """starts: 줄마다 시작 초 (TTS 조립 결과). TTS 없이 대본만 볼 때는 글자 수로 어림한 값."""
    cfg = cfg or config()
    hosts = cfg.get("hosts") or {}
    chapters, seen = [], set()
    for ln, t in zip(lines, starts):
        if ln.seg not in seen:
            seen.add(ln.seg)
            chapters.append([int(t), chapter_label(brief, ln.kind, ln.stock_code)])
    first_seek: dict[str, int] = {}
    for ln, t in zip(lines, starts):
        for r in ln.refs:
            first_seek.setdefault(r, int(t))
    sources, memo_link = [], None
    for st in brief.news_stocks:
        for c in st.cards:
            if c.uid not in first_seek:
                continue
            src = c.sources[0] if c.sources else {}
            sources.append({
                "kind": c.kind if c.kind in ("공시", "뉴스") else "업데이트",
                "text": " · ".join(x for x in [st.name, src.get("title") or c.headline, src.get("source") or "",
                                                _mmdd(c.data_date)] if x),
                "memo": f"연결된 메모 “{c.memo_titles[0]}”" if c.memo_titles and c.memo_titles[0] else "",
                "url": src.get("url"), "update_ids": [str(i) for i in c.card_ids], "seek": first_seek[c.uid]})
            if memo_link is None and c.memo_titles and c.memo_titles[0]:
                same = [x for x in st.cards if c.memo_titles[0] in x.memo_titles]
                kinds = {}
                for x in same:
                    kinds[x.kind] = kinds.get(x.kind, 0) + 1
                memo_link = {"head": f"{st.name} · AI 연결", "title": c.memo_titles[0], "memo_id": str(c.memo_ids[0]),
                             "body": c.memo_link or f"추적 항목 '{c.item}'과 연결된 소식이에요.", "seek": first_seek[c.uid],
                             "count": " · ".join(f"{k} {v}건" for k, v in kinds.items())}
    market_source = ""
    if brief.market:
        market_source = f"{_mmdd(brief.market[0].last_date)} " + "·".join(m.label.replace(" 환율", "") for m in brief.market) + " 종가"
    return {
        "title": str(script.get("title") or "내 종목 라디오").strip(),
        "period": {"start": brief.start, "end": brief.end},
        "stocks": [s.code for s in brief.stocks],
        "hosts": [hosts.get("A", "진행자 A"), hosts.get("B", "진행자 B")],
        "dur": int(round(duration)),
        "chapters": chapters,
        "script": [[int(t), ln.speaker, ln.text] for ln, t in zip(lines, starts)],
        "sources": sources,
        "market_source": market_source,
        "memo_link": memo_link,
        "source": meta.get("source"),
        "prompt_version": meta.get("prompt"),
    }


def estimate_starts(lines: list[Line], cfg: dict | None = None) -> tuple[list[float], float]:
    """TTS 없이 대본만 만들 때 쓰는 시각 어림 (읽기 문장 글자 수 ÷ 1분 글자 수)."""
    cfg = cfg or config()
    cpm = float(cfg["script"]["chars_per_minute"])
    tts = cfg.get("tts") or {}
    t, starts, prev = float(tts.get("lead", 0.3)), [], None
    for ln in lines:
        if prev is not None:
            t += float(tts.get("gap_segment", 0.7) if ln.seg != prev else tts.get("gap_line", 0.3))
        starts.append(t)
        t += len(ln.speech) / cpm * 60
        prev = ln.seg
    return starts, t


def lines_dict(lines: list[Line]) -> list[dict]:
    return [asdict(ln) for ln in lines]
