"""LLM이 두 번 다 검사를 못 넘기면 쓰는 규칙 대본. 카드 문장(이미 카드 검사를 통과한 사실)만 그대로 읽는다."""
from __future__ import annotations

import re

from .collect import Brief, day_label
from .prompt import config

MAX = 80


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


def _line(speaker: str, text: str, refs: list[str] | None = None) -> dict:
    return {"speaker": speaker, "text": text, "refs": refs or []}


def fallback(brief: Brief) -> dict:
    segs = []
    n = len(brief.stocks)
    segs.append({"kind": "opening", "stock_code": "", "lines": [
        _line("A", f"{_day(brief.start)}부터 {_day(brief.end)}까지, 내 종목 {n}곳의 소식을 정리해 드릴게요.")]})
    if brief.market:
        m = brief.market[0]
        segs.append({"kind": "market", "stock_code": "", "lines": [
            _line("B", f"{_day(m.last_date)} {josa(m.label, '은/는')} {m.last:,.2f}{m.unit}로 마감했어요.")]})
    for st in brief.news_stocks:
        memo = st.cards[0].memo_titles[0] if st.cards[0].memo_titles else (st.memos[0].title if st.memos else "")
        lines = [_line("A", f"{st.name} 소식이에요." + (f" \"{memo}\" 메모를 남기셨죠." if memo else ""))]
        for c in st.cards:
            src = (c.sources[0]["source"] if c.sources else "") or ""
            if c.kind == "뉴스":
                head = f"{_day(c.data_date)} {src or '뉴스'} 기사예요."
            elif c.kind == "공시":
                head = f"{_day(c.data_date)} DART 공시예요."
            else:
                head = f"{_day(c.data_date)} {c.kind} 소식이에요."
            body = c.facts[0] if c.facts else c.headline
            for i, t in enumerate(_split(f"{head} {body}")):
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
            _line("A", f"{names[: -len(last)]}{josa(last, '은/는')} 이번 기간에 새 소식이 없었어요.")]})
    segs.append({"kind": "closing", "stock_code": "", "lines": [
        _line("B", "오늘은 여기까지예요. 자세한 내용은 앱의 업데이트 카드에서 볼 수 있어요."),
        _line("A", "판단은 메모와 원문을 직접 보고 해 주세요.")]})
    return {"title": f"{_day(brief.end)}까지 내 종목 라디오", "segments": segs}
