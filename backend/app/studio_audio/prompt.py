"""AI 오디오 대본 프롬프트. 시스템 프롬프트는 configs/studio_audio_prompt.md (문구를 바꾸면 PROMPT_VERSION도 올린다).

LLM은 대본 줄(진행자·문장·참조 번호)만 쓴다. 챕터 이름·시각·출처 목록·메모 연결 카드는 코드가 채운다.
"""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache

from .collect import Brief, CardIn, MarketRow, MemoIn, PriceIn, StockIn, day_label

PROMPT_VERSION = "audio-v6 (2026-11-24, 메모스 라디오 티키타카)"
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


def opening_topic(brief: Brief, cfg: dict | None = None) -> str:
    """오프닝 수다 소재. brief.topic이 있으면 그것, 없으면 opening_topics에서 만든 시각(made_at)으로 하나.
    날짜만 쓰면 같은 날 여러 번 만든 방송이 모두 같은 소재라서 시각까지 쓴다 (같은 브리프는 늘 같은 소재)."""
    if brief.topic:
        return brief.topic
    topics = (cfg or config()).get("opening_topics") or []
    if not topics:
        return ""
    return topics[int(hashlib.sha256(brief.made_at.encode()).hexdigest(), 16) % len(topics)]


def build_user(brief: Brief, cfg: dict | None = None) -> str:
    sec, chars = target_seconds(brief, cfg), target_chars(brief, cfg)
    lines = ["[방송 정보]",
             f"- 오늘: {day_label(brief.made_at)}",
             f"- 기간: {day_label(brief.start)} 하루" if brief.start == brief.end
             else f"- 기간: {day_label(brief.start)} ~ {day_label(brief.end)}",
             f"- 종목: {len(brief.stocks)}개 (새 소식 있는 종목 {len(brief.news_stocks)}개, 없는 종목 {len(brief.quiet_stocks)}개)",
             f"- 길이 목표: 약 {sec // 60}분 {sec % 60}초 (대본 전체 약 {chars}자)"]
    topic = opening_topic(brief, cfg)
    if topic:
        lines += ["", f"[오늘의 오프닝 소재] {topic}"]
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
    ],
    topic="요일 이야기 (월요일이면 한 주 시작, 금요일이면 주말 앞)")


def _l(speaker: str, tone: str, text: str, refs: list[str] | None = None, cue: str = "") -> dict:
    return {"speaker": speaker, "text": text, "refs": refs or [], "tone": tone, "cue": cue}


FEWSHOT_ANSWER = {
    "title": "1월 첫째 주 메모스 라디오",
    "segments": [
        {"kind": "opening", "stock_code": "", "lines": [
            _l("A", "bright", "안녕하세요, 메모스 라디오예요!"),
            _l("B", "warm", "월요일 아침이에요. 주말 잘 쉬셨어요?"),
            _l("A", "bright", "저는 쉬긴 했는데, 메모는 하나도 안 썼어요.", cue="light_laugh"),
            _l("B", "warm", "괜찮아요. 그래서 저희가 대신 챙겨 왔잖아요.", cue="light_laugh"),
            _l("A", "warm", "오늘은 메모해 두신 신공장 투자 얘기가 진짜 나왔어요."),
            _l("B", "warm", "1월 5일부터 11일까지, 두 종목이에요. 증시부터 볼까요?")]},
        {"kind": "market", "stock_code": "", "lines": [
            _l("B", "calm", "1월 9일 코스피는 2,510.4로 마감했어요."),
            _l("A", "curious", "기간 첫 거래일보다는요?"),
            _l("B", "calm", "1.64% 높아요.")]},
        {"kind": "stock", "stock_code": "000001", "lines": [
            _l("A", "warm", "자, 예시전자부터 갈게요. 신공장 투자 계속 보겠다고 메모하셨잖아요.", cue="short_pause"),
            _l("B", "calm", "네, 마침 그 공시가 나왔어요. 1월 7일 DART예요.", ["U1"]),
            _l("A", "curious", "금액은요?"),
            _l("B", "calm", "3,200억 원이에요.", ["U1"]),
            _l("A", "surprised", "와, 3,200억이요?", ["U1"]),
            _l("B", "calm", "네. 기간은 2026년 1월부터 2027년 6월까지고요.", ["U1"]),
            _l("A", "curious", "메모에 금액이랑 기간 확인하고 싶다고 쓰셨는데, 둘 다 나온 거네요.", ["U1"]),
            _l("B", "calm", "빙고.", ["U1"]),
            _l("A", "curious", "그럼 이거 좋은 소식인 거예요?"),
            _l("B", "calm", "그건 메모하신 기준으로 직접 보셔야 하고요. 공시에 나온 건 금액과 기간까지예요.", ["U1"]),
            _l("A", "curious", "아, 근데 시설투자가 정확히 뭐예요?"),
            _l("B", "warm", "쉽게 말하면 공장이나 기계처럼 오래 쓸 설비를 새로 들이는 데 돈을 쓰는 거예요."),
            _l("A", "warm", "배당 얘기도 하나 있었죠?", ["U2"]),
            _l("B", "calm", "1월 9일 예시경제 기사에서, 예시증권은 주당 배당금이 500원으로 늘 수 있다고 전망했어요.", ["U2"]),
            _l("A", "curious", "회사가 정한 게 아니라 증권사 전망이라는 거죠?", ["U2"]),
            _l("B", "calm", "맞아요. 메모의 배당 정책 항목과 이어지는 기사예요.", ["U2"]),
            _l("A", "curious", "종가는요?"),
            _l("B", "calm", "1월 9일 52,300원이었어요.")]},
        {"kind": "no_news", "stock_code": "", "lines": [
            _l("A", "warm", "예시금융은 이번 기간에 새 소식이 없었어요.")]},
        {"kind": "closing", "stock_code": "", "lines": [
            _l("B", "gentle", "오늘은 여기까지예요."),
            _l("A", "bright", "벌써요? 숫자 얘기할 때 제일 신나 보이시던데요.", cue="light_laugh"),
            _l("B", "warm", "들켰네요.", cue="light_laugh"),
            _l("A", "gentle", "판단은 메모와 원문을 직접 보고 해 주세요. 다음에 또 만나요!")]},
    ],
}
# 소식 종목이 2개 이상일 때만 쓰는 recap 구간의 모양 (few-shot 브리프는 소식 종목이 1개라 답에는 넣지 않는다. 테스트·참고용)
FEWSHOT_RECAP = {"kind": "recap", "stock_code": "", "lines": [
    _l("B", "calm", "오늘 정리해 보면, 예시전자는 신공장 투자 공시와 배당 전망 기사가 있었어요.", ["U1", "U2"]),
    _l("A", "warm", "예시금융은 조용했고요.")]}


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
