"""AI 오디오 대본 프롬프트. 시스템 프롬프트는 configs/studio_audio_prompt.md (문구를 바꾸면 PROMPT_VERSION도 올린다).

LLM은 대본 줄(진행자·문장·참조 번호)만 쓴다. 챕터 이름·시각·출처 목록·메모 연결 카드는 코드가 채운다.
"""
from __future__ import annotations

import json
from functools import lru_cache

from .collect import Brief, CardIn, MarketRow, MemoIn, PriceIn, StockIn, day_label

PROMPT_VERSION = "audio-v4 (2026-11-23, 두 DJ 주고받기 + 말투 tone)"
CONFIG_PATH = "configs/studio_audio.yaml"


@lru_cache(maxsize=1)
def config() -> dict:
    from pipelines.common.config import load_config
    return load_config(CONFIG_PATH)


@lru_cache(maxsize=1)
def system_prompt() -> str:
    from pipelines.common.config import resolve_path
    return resolve_path(config()["script"]["prompt"]).read_text(encoding="utf-8").strip()


def target_seconds(brief: Brief, cfg: dict | None = None) -> int:
    s = (cfg or config())["script"]
    sec = s["base_seconds"] + s["quiet_seconds"] * len(brief.quiet_stocks)
    for st in brief.news_stocks:
        sec += s["per_stock_seconds"] + s["per_card_seconds"] * max(0, len(st.cards) - 1)
    return int(min(sec, s["max_seconds"]))


def target_chars(brief: Brief, cfg: dict | None = None) -> int:
    return int(target_seconds(brief, cfg) / 60 * (cfg or config())["script"]["chars_per_minute"])


def _num(v: float) -> str:
    return f"{v:,.0f}" if float(v).is_integer() else f"{v:,.2f}"


def _pct(v: float | None) -> str:
    return "-" if v is None else f"{v:+.2f}%"


def _market_line(m: MarketRow) -> str:
    prev = f", 전 거래일 대비 {_pct((m.last - m.prev) / m.prev * 100)}" if m.prev else ""
    first = (f", 기간 첫 거래일 {day_label(m.first_date)} {_num(m.first)}{m.unit} 대비 {_pct((m.last - m.first) / m.first * 100)}"
             if m.first_date != m.last_date and m.first else "")
    return f"- {m.label}: {day_label(m.last_date)} {_num(m.last)}{m.unit}{prev}{first}"


def _price_line(p: PriceIn) -> str:
    if p.change_pct is None:
        return f"[시세] {day_label(p.last_date)} 종가 {_num(p.last_close)}원"
    return (f"[시세] {day_label(p.last_date)} 종가 {_num(p.last_close)}원, 기간 첫 거래일 {day_label(p.first_date)} 종가 "
            f"{_num(p.first_close)}원 대비 {_pct(p.change_pct)}")


def _memo_line(m: MemoIn, i: int) -> str:
    items = "; ".join(m.items) if m.items else "없음"
    return f"- M{i} \"{m.title or '제목 없음'}\" ({day_label(m.created)} 작성)\n  본문: {m.body or '-'}\n  추적 항목: {items}"


def _card_lines(c: CardIn) -> list[str]:
    memo = ", ".join(f"\"{t}\"" for t in c.memo_titles if t) or "-"
    out = [f"- {c.uid} ({day_label(c.data_date)} · {c.kind} · 메모 {memo} · 추적 항목 \"{c.item}\")",
           f"  제목: {c.headline}"]
    out += [f"  사실 {i}: {f}" for i, f in enumerate(c.facts, 1)]
    if c.memo_link:
        out.append(f"  메모와의 연결: {c.memo_link}")
    for s in c.sources[:3]:
        out.append(f"  출처: {s['kind']} · {s['source']} · \"{s['title']}\" · {day_label(s['published_at']) if s['published_at'] else '-'}")
    return out


def build_user(brief: Brief, cfg: dict | None = None) -> str:
    sec, chars = target_seconds(brief, cfg), target_chars(brief, cfg)
    lines = ["[방송 정보]",
             f"- 기간: {day_label(brief.start)} 하루" if brief.start == brief.end
             else f"- 기간: {day_label(brief.start)} ~ {day_label(brief.end)}",
             f"- 종목: {len(brief.stocks)}개 (새 소식 있는 종목 {len(brief.news_stocks)}개, 없는 종목 {len(brief.quiet_stocks)}개)",
             f"- 길이 목표: 약 {sec // 60}분 {sec % 60}초 (대본 전체 약 {chars}자)"]
    if brief.market:
        lines += ["", "[증시]"] + [_market_line(m) for m in brief.market]
    for n, st in enumerate(brief.stocks, 1):
        lines += ["", f"[종목 {n}] {st.name} ({st.code}) · {st.hold}"]
        if st.price:
            lines.append(_price_line(st.price))
        lines.append("[메모]")
        lines += [_memo_line(m, i) for i, m in enumerate(st.memos, 1)] or ["- 없음"]
        lines.append("[새 업데이트]" if st.cards else "[새 업데이트] 없음")
        for c in st.cards:
            lines += _card_lines(c)
        if st.more_cards:
            lines.append(f"[그 밖의 업데이트 {st.more_cards}건]")
    return "\n".join(lines)


# ───────── 예시 (가상의 회사 · 숫자. 실제 종목 사실이 대본에 섞이지 않게)
FEWSHOT_BRIEF = Brief(
    user_id=0, start="2026-01-05", end="2026-01-11", made_at="2026-01-12T09:00:00+09:00",
    market=[MarketRow("코스피", "", "2026-01-09", 2510.4, 2490.1, "2026-01-05", 2470.0)],
    stocks=[
        StockIn("000001", "예시전자", "보유",
                memos=[MemoIn(1, "신공장 투자 계속 보기", "신공장 증설 공시 나오면 금액이랑 기간 확인하고 싶음. 배당도 궁금.",
                              "2026-01-05", ["신공장 증설 투자", "배당 정책"])],
                cards=[CardIn("U1", [1], "000001", "공시", "2026-01-07", "신공장에 3,200억 원 투자",
                              ["예시전자가 신규 시설투자 3,200억 원을 결정했어요.", "투자 기간은 2026년 1월부터 2027년 6월까지예요."],
                              "메모의 '신공장 증설 투자' 항목과 같은 주제의 공시예요.", "신공장 증설 투자", [1],
                              ["신공장 투자 계속 보기"],
                              [{"kind": "공시", "title": "신규시설투자등", "source": "DART", "published_at": "2026-01-07", "url": ""}]),
                       CardIn("U2", [2], "000001", "뉴스", "2026-01-09", "증권사, 배당 확대 가능성 언급",
                              ["예시증권은 예시전자의 주당 배당금이 500원으로 늘 수 있다고 전망했어요."],
                              "메모의 '배당 정책' 항목과 이어지는 기사예요.", "배당 정책", [1], ["신공장 투자 계속 보기"],
                              [{"kind": "뉴스", "title": "예시전자 배당 늘까", "source": "예시경제", "published_at": "2026-01-09", "url": ""}])],
                price=PriceIn("2026-01-05", 51000, "2026-01-09", 52300, 2.55)),
        StockIn("000002", "예시금융", "관심", memos=[MemoIn(2, "금리 바뀌면 다시 보기", "금리 내려가면 이자이익 어떻게 되는지.",
                                                       "2026-01-06", ["이자이익"])]),
    ])
FEWSHOT_ANSWER = {
    "title": "1월 첫째 주 내 종목 라디오",
    "segments": [
        {"kind": "opening", "stock_code": "", "lines": [
            {"speaker": "A", "text": "1월 5일부터 11일까지, 내 종목 라디오 시작할게요. 오늘은 두 종목이에요.", "refs": [], "tone": "warm"},
            {"speaker": "B", "text": "두 종목이면 커피 한 잔 다 마시기 전에 끝나겠는데요?", "refs": [], "tone": "warm"},
            {"speaker": "A", "text": "그럼 서둘러 볼까요. 먼저 증시부터 짚어 주세요.", "refs": [], "tone": "warm"}]},
        {"kind": "market", "stock_code": "", "lines": [
            {"speaker": "B", "text": "1월 9일 코스피는 2,510.4로 마감했어요. 기간 첫 거래일보다 1.64% 높아요.", "refs": [], "tone": "calm"},
            {"speaker": "A", "text": "깔끔하네요. 그럼 내 종목으로 넘어가 볼게요.", "refs": [], "tone": "warm"}]},
        {"kind": "stock", "stock_code": "000001", "lines": [
            {"speaker": "A", "text": "예시전자예요. 신공장 투자를 계속 보겠다는 메모 남기셨죠? 소식 있었어요?", "refs": [], "tone": "curious"},
            {"speaker": "B", "text": "있었어요. 1월 7일 DART에 신규 시설투자 공시가 올라왔어요.", "refs": ["U1"], "tone": "calm"},
            {"speaker": "A", "text": "오, 메모에 금액이랑 기간을 확인하고 싶다고 적어 두셨잖아요.", "refs": ["U1"], "tone": "curious"},
            {"speaker": "B", "text": "딱 그게 나왔어요. 금액은 3,200억 원, 기간은 2026년 1월부터 2027년 6월까지예요.", "refs": ["U1"], "tone": "calm"},
            {"speaker": "A", "text": "메모에 적어 둔 숙제가 한 번에 풀렸네요. 배당 얘기도 있었죠?", "refs": [], "tone": "curious"},
            {"speaker": "B", "text": "네, 1월 9일 예시경제 기사예요. 예시증권은 주당 배당금이 500원으로 늘 수 있다고 전망했어요.", "refs": ["U2"], "tone": "calm"},
            {"speaker": "A", "text": "증권사가 그렇게 봤다는 거죠? 메모의 배당 정책 항목과 이어지는 기사예요.", "refs": ["U2"], "tone": "curious"},
            {"speaker": "B", "text": "맞아요. 시세도 볼게요. 1월 9일 종가는 52,300원이었어요.", "refs": [], "tone": "calm"}]},
        {"kind": "no_news", "stock_code": "", "lines": [
            {"speaker": "A", "text": "예시금융은 이번 기간에 새 소식이 없었어요.", "refs": [], "tone": "calm"},
            {"speaker": "B", "text": "조용한 주도 있는 법이죠. 소식 생기면 바로 들고 올게요.", "refs": [], "tone": "warm"}]},
        {"kind": "closing", "stock_code": "", "lines": [
            {"speaker": "B", "text": "오늘 방송은 여기까지예요. 자세한 내용은 앱의 업데이트 카드에 있어요.", "refs": [], "tone": "gentle"},
            {"speaker": "A", "text": "판단은 메모와 원문을 직접 보고 해 주세요. 다음 주에 또 만나요!", "refs": [], "tone": "gentle"}]},
    ],
}


def messages(brief: Brief, fix: list[str] | None = None, cfg: dict | None = None) -> list[dict]:
    msgs = [
        {"role": "system", "content": system_prompt()},
        {"role": "user", "content": build_user(FEWSHOT_BRIEF, cfg)},
        {"role": "assistant", "content": json.dumps(FEWSHOT_ANSWER, ensure_ascii=False)},
        {"role": "user", "content": build_user(brief, cfg)},
    ]
    if fix:
        msgs.append({"role": "user", "content": "앞 대본에 이런 문제가 있어. 규칙에 맞게 처음부터 다시 써 줘.\n"
                                                + "\n".join(f"- {item}" for item in fix)})
    return msgs
