"""주제 항목 처리 흐름 (지침서 Ⅰ-4): 후보 → 폴백 2(유사도 임계값) → 근거 준비 → LLM 카드 → 코드 검사 → 카드 또는 고정 문구.

- LLM이 no_update면 카드를 만들지 않는다 (제목·이유가 비고 summary·evidence가 빈 배열인지 형식 확인).
- 근거가 모두 이미 보여 준 출처면 LLM을 부르지 않는다 (already_shown).
- 형식·금지 표현·숫자·출처·확신도 검사에 걸리면 고정 문구 카드로 대체한다 (on_check_fail="fixed"; "drop"이면 만들지 않는다).
- LLM 호출이 실패해도 고정 문구로 대체하지만, CreditsExhausted는 대체하지 않고 그대로 올린다 (AI 업데이트 일시 중지).
- 크레딧 확인은 호출자가 call 함수 안에서 한다. call이 None이면 근거 준비까지만 한다.
- 옵션 verify_call: 코드 검사를 통과한 카드를 LLM이 한 번 더 문장별로 근거와 대조한다 (항목당 호출 +1). 하나라도 근거에 없다고 하면 검사 실패로 본다.
"""

from __future__ import annotations

from typing import Callable

from .checks import check_card, check_no_update
from .evidence import build_evidence, pick_recent, related_news
from .fixed import fixed_card
from .judge import build_prompt, build_verify_prompt, parse_card, parse_verify
from .models import Candidate, CreditsExhausted, TopicOutcome, TrackingItem, UpdateDraft


_FORMAT_CODES = {"FORMAT_TITLE", "FORMAT_SUMMARY"}
_REPAIR_REASON = {"FORMAT_TITLE": "title이 {title_max}자(공백 포함)를 넘었어요",
                  "FORMAT_SUMMARY": "summary가 {max_sentences}문장을 넘었거나, 한 문장이 [E#]를 뺀 {sentence_max_chars}자를 넘었거나, 문장 끝에 [E#]가 없어요"}


def _limits(cfg: dict) -> dict:
    """카드 규격 설정값. 프롬프트({title_max} 등)와 형식 재시도 안내 문구가 같은 값을 쓴다."""
    return {"title_max": cfg.get("title_max", 20), "max_sentences": cfg.get("max_sentences", 3),
            "sentence_max_chars": cfg.get("sentence_max_chars", 60)}


def _repair_prompt(prompt: str, raw: str, codes: list[str], cfg: dict) -> str:
    limits = _limits(cfg)
    reasons = "\n".join("- " + _REPAIR_REASON[c].format(**limits) for c in dict.fromkeys(codes))
    return (f"{prompt}\n\n# 수정 요청\n직전 답변이 아래 규칙을 어겼어요.\n{reasons}\n\n직전 답변:\n{raw}\n\n"
            "같은 근거만 사용하고 새 사실이나 숫자는 넣지 말고, 규칙을 지켜 JSON 하나로 다시 작성하세요. 문장은 줄이거나 나눠서 쓰세요.")


def _verify(card, evidence, call: Callable[[str], str]) -> list[str]:
    """카드 문장이 근거로 뒷받침되는지 LLM에게 다시 묻는다. 빈 목록이면 통과.
    응답을 읽을 수 없으면 통과시키지 않는다 ("틀릴 바엔 말하지 않는다")."""
    try:
        raw = call(build_verify_prompt(card, evidence))
    except CreditsExhausted:
        raise
    except Exception as exc:
        return [f"VERIFY_CALL_FAILED:{type(exc).__name__}"]
    flags = parse_verify(raw, len(card.summary))
    if flags is None:
        return ["VERIFY_PARSE"]
    return [] if all(flags) else ["VERIFY_UNSUPPORTED"]


def check_topic(item: TrackingItem, candidates: list[Candidate], call: Callable[[str], str] | None,
                banned: list[str], cfg: dict | None = None) -> TopicOutcome:
    cfg = cfg or {}
    base = cfg.get("min_similarity", 0.5)
    floor = {"news": cfg.get("min_similarity_news", base), "disclosure": cfg.get("min_similarity_disclosure", base)}
    # 강한 후보 기준이 없으면 1.01(아무도 못 넘음): 멈추지 않고 검색된 기간 전체에서 고른다
    strong = {k: cfg.get(f"strong_similarity_{k}", 1.01) for k in ("news", "disclosure")}
    passed = pick_recent(candidates, floor, strong)
    evidence = build_evidence(passed, cfg.get("max_disclosure_evidence", 2), cfg.get("max_news_evidence", 3),
                              cfg.get("news_dup_similarity", 0.7), cfg.get("max_text_chars_news", 600),
                              cfg.get("max_text_chars_disclosure", 800))
    if not evidence:
        return TopicOutcome("no_candidates")
    if item.already_shown_ids and all(e.candidate.ref in set(item.already_shown_ids) for e in evidence):
        return TopicOutcome("already_shown", evidence)           # 새 근거가 없다: LLM을 부르지 않는다 (크레딧 절약, 중복 방지)
    if call is None:
        return TopicOutcome("not_called", evidence)

    raw = ""

    def replace(codes: list[str], card=None, retried: bool = False) -> TopicOutcome:
        if cfg.get("on_check_fail", "fixed") == "drop":
            return TopicOutcome("no_update", evidence, card, codes, raw=raw, retried=retried)
        draft = fixed_card(item, evidence)
        if draft is not None and draft.type == "disclosure":
            draft.related_news = related_news(evidence, set(), cfg.get("related_news_min_similarity", 0.6))
        return TopicOutcome("fixed_card", evidence, card, codes, draft, raw, retried)

    prompt = build_prompt(item, evidence, limits=_limits(cfg))   # 설정 파일이 없으면 여기서 바로 실패시킨다 (호출 실패로 숨기지 않는다)
    try:
        raw = call(prompt)
    except CreditsExhausted:
        raise
    except Exception as exc:                                   # 재시도는 호출 함수 안에서 이미 했다
        return replace([f"CALL_FAILED:{type(exc).__name__}"])
    card = parse_card(raw)
    if card is None:
        return replace(["FORMAT_PARSE"])
    if card.status == "no_update":
        codes = check_no_update(card)
        return replace(codes, card) if codes else TopicOutcome("no_update", evidence, card)
    codes = check_card(card, evidence, banned, cfg)
    retried = False
    if codes and cfg.get("format_retry", 0) and set(codes) <= _FORMAT_CODES:
        # 제목·문장 길이처럼 형식만 어긴 경우에 한해 1회 고쳐 달라고 다시 부탁한다 (숫자·출처·금지어 위반은 다시 부탁하지 않는다)
        retried = True
        try:
            raw2 = call(_repair_prompt(prompt, raw, codes, cfg))
        except CreditsExhausted:
            raise
        except Exception as exc:
            return replace([f"CALL_FAILED:{type(exc).__name__}"], card)
        raw = raw2
        card2 = parse_card(raw2)
        if card2 is None:
            return replace(["FORMAT_PARSE"], card, retried=True)
        card = card2
        if card.status == "no_update":
            bad = check_no_update(card)
            return replace(bad, card, retried=True) if bad else TopicOutcome("no_update", evidence, card, raw=raw, retried=True)
        codes = check_card(card, evidence, banned, cfg)
    if codes:
        return replace(codes, card, retried=retried)
    if cfg.get("verify_call"):                                 # 코드 검사를 통과한 카드만 검수한다 (호출 +1)
        vcodes = _verify(card, evidence, call)
        if vcodes:
            return replace(vcodes, card, retried=retried)
    by_id = {e.eid: e for e in evidence}
    sources = [(by_id[sid].candidate.ref, fact) for sid, fact in card.evidence]
    kinds = {by_id[sid].candidate.kind for sid, _ in card.evidence}
    utype = "disclosure" if "disclosure" in kinds else "news"
    import re
    summary = " ".join(re.sub(r"\s*\[E\d+\]", "", s).strip() for s in card.summary)
    related = related_news(evidence, {ref for ref, _ in sources}, cfg.get("related_news_min_similarity", 0.6)) \
        if utype == "disclosure" else []
    draft = UpdateDraft(item=item, type=utype, title=card.title, summary=summary, reason=card.reason,
                        sources=sources, related_news=related)
    return TopicOutcome("update", evidence, card, [], draft, raw, retried)