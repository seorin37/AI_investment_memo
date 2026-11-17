"""주제 항목 처리 흐름 (지침서 Ⅰ-4): 후보 → 폴백 2(유사도 임계값) → 근거 준비 → LLM 카드 → 코드 검사 → 카드 또는 고정 문구.

- LLM이 no_update면 카드를 만들지 않는다 (제목·이유가 비고 summary·evidence가 빈 배열인지 형식 확인).
- 근거가 모두 이미 보여 준 출처면 LLM을 부르지 않는다 (already_shown).
- 형식·금지 표현·숫자·출처·확신도 검사에 걸리면 고정 문구 카드로 대체한다 (on_check_fail="fixed"; "drop"이면 만들지 않는다).
- LLM 호출이 실패해도 고정 문구로 대체하지만, CreditsExhausted는 대체하지 않고 그대로 올린다 (AI 업데이트 일시 중지).
- 크레딧 확인은 호출자가 call 함수 안에서 한다. call이 None이면 근거 준비까지만 한다.
- 옵션 verify_call: 코드 검사를 통과한 카드를 LLM이 한 번 더 문장별로 근거와 대조한다 (항목당 호출 +1). 하나라도 근거에 없다고 하면 검사 실패로 본다.
- 옵션 same_event(기사 ref → 공시 접수번호, same_event.link_same_event): 근거로 뽑힐 공시와 같은 사건 기사는 근거에서 빼고(LLM이 보지 않는다)
  그 공시를 쓴 공시 카드에 supporting_news(제목·매체·날짜·링크)로 붙인다. 기사 문장은 쓰지 않는다.
"""

from __future__ import annotations

import re
from typing import Callable

from .checks import check_card, check_no_update
from .evidence import build_evidence, evidence_options, pick_recent, rcept_of, related_news, split_same_event
from .fixed import fixed_card
from .judge import build_prompt, build_verify_prompt, parse_card, parse_verify
from .models import Candidate, CreditsExhausted, TopicOutcome, TrackingItem, UpdateDraft


# 형식만 어긴 카드는 한 번 고쳐 달라고 한다. FORMAT_REASON(memo_link·reason 길이·한 문장)은 2026-11-18부터
# (memo_link가 두 문장으로 나온 카드가 4번 중 1번 떨어졌다)
_FORMAT_CODES = {"FORMAT_TITLE", "FORMAT_SUMMARY", "FORMAT_EXPLANATION", "FORMAT_REASON"}
_REPAIR_REASON = {"FORMAT_TITLE": "title이 {title_max}자(공백 포함)를 넘었어요",
                  "FORMAT_REASON": "reason이 비었거나 {reason_max}자(공백 포함)를 넘었어요",
                  "FORMAT_SUMMARY": "summary가 {max_sentences}문장을 넘었거나, 한 문장이 [E#]를 뺀 {sentence_max_chars}자를 넘었거나, 문장 끝에 [E#]가 없어요"}


def _limits(cfg: dict) -> dict:
    """카드 규격 설정값. 프롬프트({title_max} 등)와 형식 재시도 안내 문구가 같은 값을 쓴다."""
    return {"title_max": cfg.get("title_max", 20), "max_sentences": cfg.get("max_sentences", 3),
            "sentence_max_chars": cfg.get("sentence_max_chars", 60), "reason_max": cfg.get("reason_max", 80),
            "explanation_max_sentences": (cfg.get("explanation") or {}).get("max_sentences", 4),
            "explanation_max_chars": (cfg.get("explanation") or {}).get("max_chars", 400)}


def _repair_prompt(prompt: str, raw: str, codes: list[str], cfg: dict) -> str:
    limits = _limits(cfg)
    reasons = "\n".join("- " + _REPAIR_REASON[c].format(**limits) for c in dict.fromkeys(codes))
    return (f"{prompt}\n\n# 수정 요청\n직전 답변이 아래 규칙을 어겼어요.\n{reasons}\n\n직전 답변:\n{raw}\n\n"
            "같은 근거만 사용하고 새 사실이나 숫자는 넣지 말고, 규칙을 지켜 JSON 하나로 다시 작성하세요. 문장은 줄이거나 나눠서 쓰세요.")


def _verify(card, evidence, call: Callable[[str], str], company: str = "",
            item: str = "") -> tuple[list[str], list[str]]:
    """카드 문장이 근거로 뒷받침되는지 LLM에게 다시 묻는다. (실패 코드, 막은 문장과 이유). 코드가 비면 통과.
    응답을 읽을 수 없으면 통과시키지 않는다 ("틀릴 바엔 말하지 않는다")."""
    try:
        raw = call(build_verify_prompt(card, evidence, company, item))
    except CreditsExhausted:
        raise
    except Exception as exc:
        return [f"VERIFY_CALL_FAILED:{type(exc).__name__}"], []
    rows = parse_verify(raw, len(card.summary))
    if rows is None:
        return ["VERIFY_PARSE"], [raw[:300]]
    notes = [f"{s} → {why or '(이유 없음)'}" for s, (ok, why) in zip(card.summary, rows) if not ok]
    return (["VERIFY_UNSUPPORTED"] if notes else []), notes


def thresholds(cfg: dict) -> tuple[dict[str, float], dict[str, float]]:
    """종류별 (최소 유사도, 강한 후보 기준). 키는 news | news_chunks(원문 청크) | disclosure(정기보고서) | event(수시공시).
    수시공시 값이 없으면 공시 값을, 원문 청크 값이 없으면 뉴스 값을 쓴다 (news.search: chunks는 보정 전에 켜지 않는다,
    news_search.check_mode). 강한 후보 기준이 없으면 1.01(아무도 못 넘음): 멈추지 않고 검색된 기간 전체에서 고른다."""
    base = cfg.get("min_similarity", 0.5)
    floor = {k: cfg.get(f"min_similarity_{k}", base) for k in ("news", "disclosure")}
    strong = {k: cfg.get(f"strong_similarity_{k}", 1.01) for k in ("news", "disclosure")}
    floor["event"] = cfg.get("min_similarity_event", floor["disclosure"])
    strong["event"] = cfg.get("strong_similarity_event", strong["disclosure"])
    floor["news_chunks"] = cfg.get("min_similarity_news_chunks", floor["news"])
    strong["news_chunks"] = cfg.get("strong_similarity_news_chunks", strong["news"])
    return floor, strong


def check_topic(item: TrackingItem, candidates: list[Candidate], call: Callable[[str], str] | None,
                banned: list[str], cfg: dict | None = None, same_event: dict[str, str] | None = None,
                extra_evidence: Callable[[list], list] | None = None) -> TopicOutcome:
    """extra_evidence(근거 목록) → 덧붙일 근거 (v2 compare_prior.prior_evidence, DB 연결은 호출자가 가진다)."""
    cfg = cfg or {}
    floor, strong = thresholds(cfg)
    if item.category == "ask" and cfg.get("prompt_path_ask"):
        # 실험(2026-11-16): 한 번 답하기 질문은 '최신 강한 후보에서 멈추기'를 하지 않는다. 답이 오래된 공시(3분기 잠정실적 등)에
        # 있어도 최근 기사에서 멈춰 빠지던 문제 (N03). 기간 전체에서 유사도 순으로 고른다 (build_evidence 상한은 그대로)
        strong = {k: 1.01 for k in strong}
    passed = pick_recent(candidates, floor, strong, cfg.get("stop_window_days", 0))
    grouped: list[tuple[Candidate, str]] = []
    options = evidence_options(cfg)
    if same_event:
        passed, grouped = split_same_event(passed, same_event, cfg.get("max_disclosure_evidence", 2), floor, **options)
    evidence = build_evidence(passed, cfg.get("max_disclosure_evidence", 2), cfg.get("max_news_evidence", 3),
                              cfg.get("news_dup_similarity", 0.7), cfg.get("max_text_chars_news", 600),
                              cfg.get("max_text_chars_disclosure", 800), floor, **options)
    if extra_evidence is not None and (evidence or item.category == "ask"):   # ask: 재무 표만으로도 답할 수 있다
        evidence = evidence + extra_evidence(evidence)
    schema = cfg.get("card_schema", "v1")
    out = _judge_v2(item, evidence, call, banned, cfg) if schema == "v2" else _judge(item, evidence, call, banned, cfg)
    out.grouped = grouped
    if grouped and out.draft is not None and out.draft.type == "disclosure":
        cited = {rcept_of(ref) for ref, _ in out.draft.sources if ref.startswith("disc:")}
        out.draft.supporting_news = [{"ref": c.ref, "title": c.title, "source": c.source, "date": c.date, "url": c.url}
                                     for c, rcept in grouped if rcept in cited]   # 카드가 쓴 공시의 기사만
    return out


def _judge(item: TrackingItem, evidence, call: Callable[[str], str] | None, banned: list[str], cfg: dict) -> TopicOutcome:
    """근거 → LLM 카드 → 코드 검사 → 카드 또는 고정 문구."""
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

    prompt = build_prompt(item, evidence, limits=_limits(cfg), rules=cfg.get("extra_rules"))   # 설정 파일이 없으면 여기서 바로 실패시킨다 (호출 실패로 숨기지 않는다)
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
        vcodes, notes = _verify(card, evidence, call, item.company_name or item.symbol, item.description)
        if vcodes:
            out = replace(vcodes, card, retried=retried)
            out.verify_notes = notes
            return out
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


_REPAIR_REASON_V2 = {"FORMAT_TITLE": "headline이 {title_max}자(공백 포함)를 넘었거나 비었어요",
                     "FORMAT_SUMMARY": "facts가 1~{max_sentences}개가 아니거나, 한 문장이 {sentence_max_chars}자를 넘었거나, text에 [E#] 표시가 있어요",
                     "FORMAT_EXPLANATION": "explanation이 비었거나, {explanation_max_sentences}문장·{explanation_max_chars}자를 넘었거나, [E#] 표시가 있어요",
                     "FORMAT_REASON": "memo_link가 비었거나, {reason_max}자(공백 포함)를 넘었거나, 한 문장이 아니에요"}
_COMPARE_WORDS = ("대비", "보다", "비교", "전년", "작년", "직전", "지난", "전기")


def _sentences(text: str) -> list[str]:
    """검수용 문장 분리. `2026.05.` 같은 숫자 날짜의 마침표는 문장 끝으로 보지 않는다."""
    return [s.strip() for s in re.split(r"(?<!\d\.)(?<=[.!?])\s+", text or "") if s.strip()]


def _repair_prompt_v2(prompt: str, raw: str, codes: list[str], cfg: dict) -> str:
    limits = _limits(cfg)
    reasons = "\n".join("- " + _REPAIR_REASON_V2[c].format(**limits) for c in dict.fromkeys(codes))
    return (f"{prompt}\n\n# 수정 요청\n직전 답변이 아래 규칙을 어겼어요.\n{reasons}\n\n직전 답변:\n{raw}\n\n"
            "같은 근거만 사용하고 새 사실이나 숫자는 넣지 말고, 규칙을 지켜 JSON 하나로 다시 작성하세요. 문장은 줄이거나 나눠서 쓰세요.")


def card_v2_json(card) -> dict:
    """CardV2 → LLM 응답과 같은 모양의 dict (judge.parse_card_v2로 다시 읽을 수 있다)."""
    return {"status": card.status, "headline": card.headline, "when": card.when,
            "facts": [{"text": t, "evidence_id": eid} for t, eid in card.facts], "explanation": card.explanation,
            "memo_link": card.memo_link, "sources": list(card.sources), "confidence": card.confidence}


def _judge_v2(item: TrackingItem, evidence, call: Callable[[str], str] | None, banned: list[str], cfg: dict) -> TopicOutcome:
    """v2 카드 판단 + 검사 기록. 코드 검사·검수 호출을 할 때마다 그때의 카드와 걸린 코드를 TopicOutcome.checks에 남긴다
    (2026-11-17, 형식 재요청 전 첫 카드·검사에서 떨어진 카드도 실행 결과에서 다시 볼 수 있게)."""
    log: list[dict] = []
    out = _judge_v2_run(item, evidence, call, banned, cfg, log)
    out.checks = log
    return out


def _judge_v2_run(item: TrackingItem, evidence, call: Callable[[str], str] | None, banned: list[str], cfg: dict,
                  log: list[dict]) -> TopicOutcome:
    """v2 카드 (judge.parse_card_v2 · checks.check_card_v2). 흐름(이미 보여 준 출처·호출 실패·형식 재요청·검수 호출·실패 처리)은 v1과 같다.
    비교를 원하는 메모(judge.wants_comparison)인데 카드에 비교 문장이 없으면 코드가 "비교 자료 없음"을 덧붙인다."""

    def rec(stage: str, card, codes: list[str], **extra) -> None:
        row = {"stage": stage, "card": card_v2_json(card) if card is not None else None, "codes": list(codes), **extra}
        if card is None and "raw" not in extra:
            row["raw"] = raw                                    # 읽지 못한 응답은 원문을 남긴다
        log.append(row)

    from .checks import check_card_v2, check_no_update_v2
    from .judge import NO_COMPARISON, parse_card_v2, wants_comparison
    from .models import Card

    if not evidence or all(e.candidate.doc == "compare" for e in evidence):
        return TopicOutcome("no_candidates", evidence)
    if item.already_shown_ids and all(e.candidate.ref in set(item.already_shown_ids)
                                      for e in evidence if e.candidate.doc != "compare"):
        return TopicOutcome("already_shown", evidence)
    if call is None:
        return TopicOutcome("not_called", evidence)
    raw = ""

    def replace(codes, card=None, retried=False) -> TopicOutcome:
        if cfg.get("on_check_fail", "fixed") == "drop":
            return TopicOutcome("no_update", evidence, card, codes, raw=raw, retried=retried)
        real = [e for e in evidence if e.candidate.doc != "compare"]
        draft = fixed_card(item, real)
        if draft is not None and draft.type == "disclosure":
            draft.related_news = related_news(real, set(), cfg.get("related_news_min_similarity", 0.6))
        return TopicOutcome("fixed_card", evidence, card, codes, draft, raw, retried)

    explain = bool((cfg.get("explanation") or {}).get("enabled"))
    from .judge import load_guide
    guide = load_guide(cfg["prompt_path_v2"]) if cfg.get("prompt_path_v2") else None   # 시험용 프롬프트 파일 (기본: v2 파일)
    if item.category == "ask" and cfg.get("prompt_path_ask"):   # 실험(2026-11-16): 한 번 답하기 질문은 전용 답변 지시문
        guide = load_guide(cfg["prompt_path_ask"])
    prompt = build_prompt(item, evidence, guide=guide, limits=_limits(cfg), rules=cfg.get("extra_rules"), schema="v2",
                          coverage=cfg.get("coverage"), explain=explain)
    try:
        raw = call(prompt)
    except CreditsExhausted:
        raise
    except Exception as exc:
        return replace([f"CALL_FAILED:{type(exc).__name__}"])
    card = parse_card_v2(raw)
    if card is None:
        rec("card", None, ["FORMAT_PARSE"])
        return replace(["FORMAT_PARSE"])
    if card.status == "no_update":
        codes = check_no_update_v2(card)
        rec("card", card, codes)
        return replace(codes, card) if codes else TopicOutcome("no_update", evidence, card, raw=raw)
    codes = check_card_v2(card, evidence, banned, cfg, item.memo_text)
    rec("card", card, codes)
    retried = False
    if codes and cfg.get("format_retry", 0) and set(codes) <= _FORMAT_CODES:
        retried = True
        try:
            raw = call(_repair_prompt_v2(prompt, raw, codes, cfg))
        except CreditsExhausted:
            raise
        except Exception as exc:
            return replace([f"CALL_FAILED:{type(exc).__name__}"], card)
        card2 = parse_card_v2(raw)
        if card2 is None:
            rec("format_retry", None, ["FORMAT_PARSE"])
            return replace(["FORMAT_PARSE"], card, retried=True)
        card = card2
        if card.status == "no_update":
            bad = check_no_update_v2(card)
            rec("format_retry", card, bad)
            return replace(bad, card, retried=True) if bad else TopicOutcome("no_update", evidence, card, raw=raw, retried=True)
        codes = check_card_v2(card, evidence, banned, cfg, item.memo_text)
        rec("format_retry", card, codes)
    if codes:
        return replace(codes, card, retried=retried)
    facts = [(t, eid) for t, eid in card.facts if eid]          # "비교 자료 없음"은 검수하지 않는다
    if cfg.get("verify_call"):
        extra = _sentences(card.explanation) if explain else []
        vcard = Card("update", card.headline, [t for t, _ in facts] + extra, card.memo_link, [(e, t) for t, e in facts],
                     card.confidence)   # 설명 문단 문장도 근거와 대조한다
        vcodes, notes = _verify(vcard, evidence, call, item.company_name or item.symbol, item.description)
        rec("verify", card, vcodes, notes=list(notes))
        if vcodes:
            out = replace(vcodes, card, retried=retried)
            out.verify_notes = notes
            return out
    by_id = {e.eid: e for e in evidence}
    fact_rows = [{"text": t, "ref": by_id[eid].candidate.ref} for t, eid in facts]
    has_no_cmp = any(t == NO_COMPARISON and not eid for t, eid in card.facts)
    compared = any(by_id[eid].candidate.doc == "compare" for _, eid in facts) or any(
        w in t for t, _ in facts for w in _COMPARE_WORDS)
    if has_no_cmp or (wants_comparison(item.memo_text) and not compared):
        fact_rows.append({"text": NO_COMPARISON, "ref": ""})
    sources: list[tuple[str, str | None]] = []
    for row in fact_rows:
        if not row["ref"]:
            continue
        if any(r == row["ref"] for r, _ in sources):
            sources = [(r, f"{q} {row['text']}" if r == row["ref"] else q) for r, q in sources]
        else:
            sources.append((row["ref"], row["text"]))
    kinds = {by_id[eid].candidate.kind for _, eid in facts if by_id[eid].candidate.doc != "compare"}
    utype = "disclosure" if "disclosure" in kinds else "news"
    related = related_news(evidence, {r for r, _ in sources}, cfg.get("related_news_min_similarity", 0.6)) \
        if utype == "disclosure" else []
    draft = UpdateDraft(item=item, type=utype, title=card.headline, summary=" ".join(r["text"] for r in fact_rows),
                        reason=card.memo_link, sources=sources, related_news=related,
                        card_schema="v2", when=card.when, facts=fact_rows, explanation=card.explanation if explain else "",
                        coverage=coverage_text(cfg.get("coverage"), any(by_id[eid].candidate.kind == "news" for _, eid in facts)))
    if item.category == "ask" and card.calc:                  # 실험(2026-11-17): 코드가 값을 근거와 대조한 뒤 계산 (calc.py)
        from .calc import compute
        draft.calculations = compute(card.calc, evidence)
    return TopicOutcome("update", evidence, card, [], draft, raw, retried)


def coverage_text(coverage: dict | None, uses_news: bool) -> str:
    """카드의 자료 범위 문구 (v2, 2026-11-11). 뉴스를 쓴 카드만: DB의 가장 오래된 발행일 → "10월 28일 이후 기사 기준"."""
    since = (coverage or {}).get("news_since")
    if not uses_news or not since:
        return ""
    _, month, day = since.split("-")
    return f"{int(month)}월 {int(day)}일 이후 기사 기준"


def memo_of(item_id: str) -> str:
    """항목 ID "M03:1:0" → 메모 "M03"."""
    return item_id.split(":", 1)[0]


def merge_same_source(drafts: list[UpdateDraft], memo_key=None) -> tuple[list[UpdateDraft], dict[str, str]]:
    """같은 메모 안에서 근거(비교용 근거 제외)가 겹치는 카드는 앞 카드 하나로 합친다 (v2). (남은 카드, 합쳐진 항목 → 남은 카드 항목).
    가격 카드·고정 문구 카드는 합치지 않는다. 합친 항목은 남은 카드의 merged_items에 적는다."""
    key = memo_key or memo_of                                  # DB 항목(숫자 id)은 호출자가 메모 id를 찾아 준다
    kept: list[UpdateDraft] = []
    merged: dict[str, str] = {}
    for d in drafts:
        refs = {r for r, _ in d.sources if not r.startswith("cmp:")}
        target = None
        if d.type != "price_condition" and d.origin == "llm" and refs:
            target = next((k for k in kept if k.type != "price_condition" and k.origin == "llm"
                           and key(k.item.item_id) == key(d.item.item_id)
                           and refs & {r for r, _ in k.sources if not r.startswith("cmp:")}), None)
        if target is None:
            kept.append(d)
            continue
        target.merged_items.append({"item_id": d.item.item_id, "description": d.item.description})
        merged[d.item.item_id] = target.item.item_id
    return kept, merged
