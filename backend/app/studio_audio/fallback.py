"""LLM이 두 번 다 검사를 못 넘기면 쓰는 규칙 대본. 카드 문장(이미 카드 검사를 통과한 사실)만 그대로 읽는다."""
from __future__ import annotations

import re

from .collect import Brief, day_label
from .prompt import config

MAX = 70


def _final(word: str) -> bool:
    """마지막 글자에 받침이 있는가 (한글이 아니면 읽는 이름으로 판단)."""
    spoken = (config().get("pronounce") or {}).get(word, word)
    ch = spoken.strip()[-1:] if spoken.strip() else ""
    if "가" <= ch <= "힣":
        return (ord(ch) - 0xAC00) % 28 != 0
    return ch.isdigit() and ch in "0136780"


def josa(word: str, pair: str) -> str:
    """josa('삼성전자', '은/는') → '삼성전자는'."""
    a, b = pair.split("/")
    return word + (a if _final(word) else b)


def _day(iso: str) -> str:
    return re.sub(r"\(.\)$", "", day_label(iso))


def _split(text: str) -> list[str]:
    """긴 문장은 문장 끝에서 나눈다 (그래도 길면 그대로 둔다)."""
    if len(text) <= MAX:
        return [text]
    parts = [p for p in re.split(r"(?<=[.?!요])\s+", text) if p]
    out, cur = [], ""
    for p in parts:
        if cur and len(cur) + 1 + len(p) > MAX:
            out.append(cur)
            cur = p
        else:
            cur = f"{cur} {p}".strip()
    return out + ([cur] if cur else [])


def _line(speaker: str, text: str, refs: list[str] | None = None, tone: str = "calm", cue: str = "") -> dict:
    return {"speaker": speaker, "text": text, "refs": refs or [], "tone": tone, "cue": cue}


def fallback(brief: Brief) -> dict:
    """새 구조(audio-v6)와 같은 구간 순서. 수다·농담 없이 인사 한 줄, recap은 카드 제목으로."""
    segs = []
    n = len(brief.stocks)
    period = _day(brief.end) if brief.start == brief.end else f"{_day(brief.start)}부터 {_day(brief.end)}까지"
    segs.append({"kind": "opening", "stock_code": "", "lines": [
        _line("A", "안녕하세요, 메모스 라디오예요.", tone="bright"),
        _line("B", f"{period}, 내 종목 {n}곳 소식이에요.", tone="warm")]})
    if brief.market:
        m = brief.market[0]
        segs.append({"kind": "market", "stock_code": "", "lines": [
            _line("B", f"{_day(m.last_date)} {josa(m.label, '은/는')} {m.last:,.2f}{m.unit}로 마감했어요.")]})
    for st in brief.news_stocks:
        memo = st.cards[0].memo_titles[0] if st.cards[0].memo_titles else (st.memos[0].title if st.memos else "")
        lines = [_line("A", f"{st.name} 소식이에요." + (f" \"{memo}\" 메모를 남기셨죠." if memo else ""), tone="warm",
                       cue="short_pause")]
        for c in st.cards:
            src = (c.sources[0]["source"] if c.sources else "") or ""
            if c.kind == "뉴스":
                head = f"{_day(c.data_date)} {src or '뉴스'} 기사예요."
            elif c.kind == "공시":
                head = f"{_day(c.data_date)} DART 공시예요."
            else:
                head = f"{_day(c.data_date)} {c.kind} 소식이에요."
            body = c.facts[0] if c.facts else c.headline
            for t in _split(f"{head} {body}"):
                lines.append(_line("B", t, [c.uid]))
            link = c.memo_link or f"메모의 '{c.item}' 항목과 이어지는 소식이에요."
            for t in _split(link):
                lines.append(_line("A", t, [c.uid]))
        if st.more_cards:
            lines.append(_line("B", f"그 밖에 {st.more_cards}건은 앱에서 볼 수 있어요."))
        if st.price:
            lines.append(_line("B", f"{_day(st.price.last_date)} 종가는 {st.price.last_close:,.0f}원이었어요."))
        segs.append({"kind": "stock", "stock_code": st.code, "lines": lines})
    if brief.quiet_stocks:
        names = ", ".join(s.name for s in brief.quiet_stocks)
        last = brief.quiet_stocks[-1].name
        segs.append({"kind": "no_news", "stock_code": "", "lines": [
            _line("A", f"{names[: -len(last)]}{josa(last, '은/는')} 이번 기간에 새 소식이 없었어요.", tone="warm")]})
    if len(brief.news_stocks) >= 2:                          # 종목마다 한 줄, 첫 카드 제목으로 (A·B 번갈아)
        recap = []
        for i, st in enumerate(brief.news_stocks):
            head = (st.cards[0].headline or "").rstrip(".")
            more = " 등" if len(st.cards) > 1 else ""         # 건수(숫자)는 말하지 않는다
            text = ("오늘 정리해 보면, " if i == 0 else "") + f"{josa(st.name, '은/는')} '{head}'{more} 소식이 있었어요."
            recap.append(_line("B" if i % 2 == 0 else "A", text, [c.uid for c in st.cards]))
        segs.append({"kind": "recap", "stock_code": "", "lines": recap})
    segs.append({"kind": "closing", "stock_code": "", "lines": [
        _line("B", "오늘은 여기까지예요. 자세한 내용은 앱의 업데이트 카드에서 볼 수 있어요.", tone="gentle"),
        _line("A", "판단은 메모와 원문을 직접 보고 해 주세요.", tone="gentle")]})
    return {"title": f"{_day(brief.end)}까지 메모스 라디오", "segments": segs}
