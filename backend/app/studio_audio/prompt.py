"""AI 오디오 대본 프롬프트. 시스템 프롬프트는 configs/studio_audio_prompt.md (문구를 바꾸면 PROMPT_VERSION도 올린다).

LLM은 대본 줄(진행자·문장·참조 번호)만 쓴다. 챕터 이름·시각·출처 목록·메모 연결 카드는 코드가 채운다.
"""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache

from .collect import Brief, CardIn, MarketRow, MemoIn, PriceIn, StockIn, day_label

PROMPT_VERSION = "audio-v8 (2026-11-24, 질문을 따라가는 대화 + 오프닝·클로징 수다)"
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


# audio-v8: 본론은 v7처럼 숫자를 하나씩 되묻거나 앞말을 되풀이하지 않고, 메모의 질문 → 답 → 그 답에서 생기는 다음 질문으로 잇는다.
# 앞뒤(opening·closing)는 v6처럼 가벼운 수다와 웃음. 종가는 메모와 이어지는 맥락이 없어서 넣지 않았다.
FEWSHOT_ANSWER = {
    "title": "1월 첫째 주 메모스 라디오",
    "segments": [
        {"kind": "opening", "stock_code": "", "lines": [
            _l("A", "bright", "안녕하세요, 메모스 라디오예요."),
            _l("B", "bright", "월요일 아침이에요. 한 주 시작, 커피는 챙기셨죠?"),
            _l("A", "bright", "저는 커피보다 메모가 급해요. 지난주에 하나도 못 썼거든요.", cue="light_laugh"),
            _l("B", "warm", "괜찮아요. 그래서 저희가 대신 챙겨 왔잖아요.", cue="light_laugh"),
            _l("A", "curious", "오늘은 예시전자 신공장에 얼마를, 언제까지 쓰는지부터 볼게요."),
            _l("B", "warm", "1월 5일부터 11일까지 나온 자료에 답이 있었어요. 증시부터 짧게 볼게요.")]},
        {"kind": "market", "stock_code": "", "lines": [
            _l("A", "warm", "코스피는 어떻게 끝났어요?"),
            _l("B", "calm", "1월 9일 2,510.4로 마감했어요. 전 거래일보다 0.82% 올랐어요."),
            _l("B", "calm", "기간 첫 거래일과 비교하면 1.64% 올랐고요.")]},
        {"kind": "stock", "stock_code": "000001", "lines": [
            _l("A", "warm", "예시전자 메모에는 신공장 증설 금액이랑 기간을 확인하고 싶다고 적혀 있었어요.", cue="short_pause"),
            _l("B", "calm", "둘 다 1월 7일 공시에 나왔어요. 신규 시설투자 3,200억 원을 결정했어요.", ["U1"]),
            _l("B", "calm", "투자 기간은 2026년 1월부터 2027년 6월까지예요.", ["U1"]),
            _l("A", "curious", "그럼 시설투자는 정확히 어디에 쓰는 돈이에요?"),
            _l("B", "warm", "공장이나 기계처럼 오래 쓸 설비를 새로 들이는 데 쓰는 돈이에요."),
            _l("A", "calm", "메모에 적은 금액과 기간은 이번 공시로 확인된 거네요.", ["U1"]),
            _l("B", "calm", "공시로 확인되는 건 거기까지예요. 공장을 언제 다 짓는지는 적혀 있지 않았어요.", ["U1"]),
            _l("A", "warm", "아, 완공은 아직이군요. 메모에 배당도 궁금하다고 쓰셨는데, 그쪽 자료도 있었어요?"),
            _l("B", "calm", "1월 9일 예시경제 기사에서, 예시증권은 주당 배당금이 500원으로 늘 수 있다고 전망했어요.", ["U2"]),
            _l("A", "curious", "회사가 배당을 정한 건 아니고요?"),
            _l("B", "calm", "네, 예시증권이 그렇게 본 거예요. 회사가 배당을 정했다는 내용은 자료에 없어요.", ["U2"])]},
        {"kind": "no_news", "stock_code": "", "lines": [
            _l("A", "warm", "예시금융은 이번 기간에 새 소식이 없었어요.")]},
        {"kind": "closing", "stock_code": "", "lines": [
            _l("B", "gentle", "남은 질문은 배당이에요. 회사가 직접 정했는지는 아직 확인되지 않았어요.", ["U2"]),
            _l("A", "bright", "근데 배당 얘기 나올 때 목소리가 좀 커지시던데요?", cue="light_laugh"),
            _l("B", "warm", "들켰네요. 다음에도 꼼꼼히 챙겨 올게요.", cue="light_laugh"),
            _l("A", "gentle", "판단은 메모와 원문을 직접 보고 해 주세요. 다음에 또 만나요!")]},
    ],
}
# 소식 종목이 2개 이상일 때만 쓰는 recap 구간의 모양 (few-shot 브리프는 소식 종목이 1개라 답에는 넣지 않는다. 테스트·참고용)
# audio-v7: 종목별로 다시 읽지 않고, 가장 기억할 사실이나 아직 확인되지 않은 질문 하나만
FEWSHOT_RECAP = {"kind": "recap", "stock_code": "", "lines": [
    _l("B", "calm", "오늘 기억할 건 예시전자 신공장 투자 금액과 기간이 공시로 나왔다는 거예요.", ["U1"]),
    _l("A", "curious", "공장을 언제 다 짓는지는 아직 확인되지 않았고요.")]}

RETRY_NOTE = ("앞에서 쓴 대본에 아래 문제가 있어요. 이 문제만 고치고, 메모의 질문에서 답으로 이어지는 흐름은 살려서 "
              "대본 전체를 같은 JSON 형식으로 다시 써 주세요.\n"
              "고치면서 빈 질문, 맞장구, 앞 문장을 되풀이하는 줄을 새로 끼우지 마세요. "
              "줄이 길면 사실 하나씩 두 줄로 나누고, 입력에 없는 숫자는 빼거나 입력의 숫자로 바꾸세요.\n")


def messages(brief: Brief, fix: list[str] | None = None, cfg: dict | None = None,
             prev: dict | None = None) -> list[dict]:
    """fix: 검사에 걸린 문제(재시도 때). prev: 그때 받은 대본 — 무엇을 고칠지 보이게 assistant 차례로 넣는다."""
    msgs = [
        {"role": "system", "content": system_prompt()},
        {"role": "user", "content": build_user(FEWSHOT_BRIEF, cfg)},
        {"role": "assistant", "content": json.dumps(FEWSHOT_ANSWER, ensure_ascii=False)},
        {"role": "user", "content": build_user(brief, cfg)},
    ]
    if fix:
        if prev:
            msgs.append({"role": "assistant", "content": json.dumps(prev, ensure_ascii=False)})
        msgs.append({"role": "user", "content": RETRY_NOTE + "\n".join(f"- {item}" for item in fix)})
    return msgs
