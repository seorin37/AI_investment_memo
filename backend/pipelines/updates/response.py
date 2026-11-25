"""응답 유형 결정 (2026-11-10). LLM 응답 스키마·프롬프트는 그대로 두고 코드가 6개 유형 중 하나로 정한다.

유형: update_card | price_card | no_new_info | no_data | needs_confirmation | out_of_scope
결정 순서: 범위 밖 → 확인 필요 → 가격 카드 → 데이터 없음 → 새 소식 없음 → 업데이트 카드

- 범위 밖(out_of_scope)
  · full_fallback 문장: 문장 단위 응답을 내부 기록에만 남긴다 (user_visible=false).
  · 메모 전체에 추적 항목이 하나도 없고 확인 질문도 없을 때만 메모 단위 응답 1개를 보인다 (OUT_OF_SCOPE_MEMO).
    확인 필요 문장이 있으면 그 질문이 사용자에게 가므로 "찾지 못했어요"를 함께 보이지 않는다.
- 확인 필요(needs_confirmation): 메모 분석이 확인 필요로 판정한 문장. 질문(question)과 선택지(options, confirm.py).
- 가격 카드(price_card): 가격 항목이 가까워짐·도달로 바뀌었을 때.
- 데이터 없음(no_data): (a) 가격 항목인데 종가가 없음, 또는 종가가 시장 최근 거래일보다 3거래일 넘게 오래됨(stale_price)
  (b) 조회 기간 전체(recent.lookback_days, 기본 365일)에 그 종목의 뉴스·공시가 하나도 없음 (2026-11-10: 최근에만 없으면
  no_new_info). 새 자료만 받기(마지막 확인 이후)로 후보가 비어도 no_data가 아니다 — 기준은 언제나 조회 기간 전체.
- 새 소식 없음(no_new_info): 알림 대상이 아니다 (user_visible=false). 상태(type·reason)와 확인 시각만 남긴다.
  카드 생성·검수 실패(검사 실패·호출 실패·형식 오류·검수 실패)도 고정 문구 카드 대신 여기로 온다 (reason에 이유).
- 업데이트 카드(update_card): 나머지 (LLM 카드가 검사·검수를 통과).
크레딧 소진(CreditsExhausted)은 응답 유형이 아니라 예외로 올라가 AI 업데이트를 멈춘다 (topic.py 그대로).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from datetime import date, datetime, timedelta
from typing import Callable

from .fixed import NO_DATA
from .models import Response, TrackingItem

TYPES = ("update_card", "price_card", "no_new_info", "no_data", "needs_confirmation", "out_of_scope",
         "ask_no_answer")                                     # 실험(2026-11-17): 한 번 답하기 질문의 '자료 없음' 답
TRACKED = {"normal", "partial"}
OUT_OF_SCOPE_MEMO = "이 메모에서는 추적할 내용을 찾지 못했어요"

# 근거 자료 유무 (no_data b): 조회 기간에 그 종목에 연결된 기사나 공시가 한 건이라도 있는가. 검색과 같은 연결(news_stocks)을 쓴다.
SOURCE_SQL = """SELECT
  EXISTS (SELECT 1 FROM news_stocks ns JOIN news_articles a ON a.id = ns.news_id
          WHERE ns.symbol = %(symbol)s AND a.published_at >= %(since)s AND a.published_at < %(until)s),
  EXISTS (SELECT 1 FROM disclosures d
          WHERE d.symbol = %(symbol)s AND d.rcept_dt >= %(since_d)s AND d.rcept_dt <= %(until_d)s)"""


LOOKBACK_DAYS = 365


def lookback_since(cfg: dict | None, until: date) -> date:
    """no_data (b)의 조회 기간 시작일: until - recent.lookback_days(기본 365일)."""
    days = ((cfg or {}).get("recent") or {}).get("lookback_days", LOOKBACK_DAYS)
    return until - timedelta(days=days)


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def source_data(conn, symbol: str, since: date, until: date, disclosure_since: date | None = None) -> dict[str, bool]:
    """{"news": bool, "disclosure": bool}. until은 그날 포함 (뉴스는 한국 시간 기준 다음 날 0시 전까지).
    disclosure_since: 공시 조회 시작일이 뉴스와 다를 때 (experiment --disclosure-since)."""
    from zoneinfo import ZoneInfo

    kst = ZoneInfo("Asia/Seoul")
    with conn.cursor() as cur:
        cur.execute(SOURCE_SQL, {"symbol": symbol,
                                 "since": datetime.combine(since, datetime.min.time(), kst),
                                 "until": datetime.combine(until + timedelta(days=1), datetime.min.time(), kst),
                                 "since_d": disclosure_since or since, "until_d": until})
        news, disc = cur.fetchone()
    return {"news": bool(news), "disclosure": bool(disc)}


def failure_reason(codes: list[str]) -> str:
    """검사 실패 코드 → 응답 reason. 여러 개면 호출 > 형식 > 검수 > 검사 순으로 하나."""
    heads = [c.split(":")[0] for c in codes]
    if any(h in ("CALL_FAILED", "VERIFY_CALL_FAILED") for h in heads):
        return "call_failed"
    if any(h in ("FORMAT_PARSE", "VERIFY_PARSE") for h in heads):
        return "parse_failed"
    if "VERIFY_UNSUPPORTED" in heads:
        return "verify_failed"
    return "check_failed"


_NO_NEW = {"no_candidates": "no_candidates", "already_shown": "already_shown", "no_update": "llm_no_update",
           "not_called": "not_called", "price_no_card": "price_unchanged",
           "no_relevant_candidates": "no_relevant_candidates",      # 관련성 판정 뒤 남은 후보 없음 (relevance.py)
           "relevance_failed": "relevance_failed"}                  # 판정 호출·응답 실패: 카드를 만들지 않는다


def item_response(item: TrackingItem, kind: str, fail_codes: list[str], card: dict | None,
                  has_data: bool | None, memo_id: str = "", checked_at: str = "") -> Response:
    """추적 항목 하나의 결과(TopicOutcome.kind 또는 price_* 값) → 응답.
    card는 최종 카드(draft_to_dict 모양 또는 outcome_row의 card). has_data는 source_data 결과의 any (모르면 None)."""
    base = dict(scope="item", memo_id=memo_id, item_id=item.item_id, fail_codes=list(fail_codes),
                checked_at=checked_at or now_iso())
    if kind == "price_card" and card:
        return Response("price_card", reason="price_changed", message=card.get("title", ""), card=card, **base)
    if kind == "price_no_data":
        return Response("no_data", reason="no_price", message=NO_DATA, **base)
    if kind == "price_stale":                             # 마지막 종가가 3거래일 넘게 오래됨 (price.price_outcome)
        return Response("no_data", reason="stale_price", message=NO_DATA, **base)
    if kind == "update" and card and card.get("origin", "llm") in ("llm", "code"):   # code: 판단 질문의 주가 사실만 답 (2026-11-25)
        return Response("update_card", reason="card", message=card.get("title", ""), card=card, **base)
    if item.type == "topic" and has_data is False:
        if item.category == "ask":                            # 실험(2026-11-17): 질문이면 '자료 없음' 답
            return ask_no_answer(item, "no_source_data", base)
        return Response("no_data", reason="no_source_data", message=NO_DATA, **base)
    if fail_codes or kind == "fixed_card":                 # 카드 실패: 고정 문구 카드(on_check_fail=fixed)여도 보이지 않는다
        reason = failure_reason(fail_codes) if fail_codes else "check_failed"
    else:
        reason = _NO_NEW.get(kind, kind)
    if item.category == "ask" and reason in ASK_NO_ANSWER_REASONS:
        return ask_no_answer(item, reason, base)
    return Response("no_new_info", reason=reason, user_visible=False, **base)


# 실험(2026-11-17): 한 번 답하기(ask) 질문에 답을 만들지 못했을 때 아무것도 안 보이면 사용자는 질문이 처리됐는지 모른다.
# 자료에서 찾지 못했다는 고정 답을 보인다 (user_visible). 시스템 실패(call_failed·parse_failed·relevance_failed·not_called)는
# "자료 없음"이 아니므로 그대로 no_new_info(안 보임)로 두고 다음 실행에서 다시 본다.
ASK_NO_ANSWER = "ask_no_answer"
ASK_NO_ANSWER_REASONS = {"no_candidates", "llm_no_update", "no_relevant_candidates", "no_source_data",
                         "check_failed", "verify_failed"}
ASK_NO_ANSWER_TEXT = "물으신 내용은 지금 가진 공시·뉴스·재무 자료에서 확인되지 않았어요."


def ask_no_answer(item: TrackingItem, reason: str, base: dict) -> Response:
    question = (item.description or "").strip()
    return Response(ASK_NO_ANSWER, reason=reason, message=ASK_NO_ANSWER_TEXT, question=question, text=item.memo_text,
                    **base)


def sentence_responses(memo_id: str, judgments: list, confirm: Callable[[object], tuple[str, list, dict | None]],
                       checked_at: str = "") -> list[Response]:
    """문장 단위: full_fallback → 내부 기록 out_of_scope, needs_confirmation → 질문. confirm(judgment) → (질문, 선택지, 정보)."""
    out = []
    stamp = checked_at or now_iso()
    for j in judgments:
        if j.decision == "full_fallback":
            out.append(Response("out_of_scope", "sentence", memo_id, sentence_index=j.sentence_index, user_visible=False,
                                reason=j.category or j.reason_code or "full_fallback", text=j.text, checked_at=stamp))
        elif j.decision == "needs_confirmation":
            question, options, info = confirm(j)
            out.append(Response("needs_confirmation", "sentence", memo_id, sentence_index=j.sentence_index,
                                reason=j.reason_code or "needs_confirmation", message=question, question=question,
                                options=options, text=j.text, checked_at=stamp,
                                fail_codes=[] if info is None else [f"relative:{info['base']}"]))
    return out


def memo_response(memo_id: str, judgments: list, n_items: int, checked_at: str = "") -> Response | None:
    """추적 항목이 하나도 없고(추적 문장도 없음) 확인 질문도 없으면 메모 단위 out_of_scope 1개."""
    tracked = any(j.decision in TRACKED for j in judgments)
    asks = any(j.decision == "needs_confirmation" for j in judgments)
    if n_items or tracked or asks:
        return None
    return Response("out_of_scope", "memo", memo_id, reason="no_tracking_items", message=OUT_OF_SCOPE_MEMO,
                    checked_at=checked_at or now_iso())


def memo_analysis_responses(memo_id: str, judgments: list, n_items: int, price_rows: list[tuple] | None = None,
                            checked_at: str = "") -> list[Response]:
    """메모 저장 API용 (2026-11-11): 메모 분석 결과(judge_memo + LLM 판정)에서 사용자에게 바로 보여 줄 응답만 돌려준다.
    needs_confirmation(문장마다 질문·선택지)과 메모 단위 out_of_scope. DB에는 쓰지 않는다 (db_store 설명 참고).
    price_rows는 그 종목의 최근 일봉(confirm.price_window) — 확인 질문의 선택지(52주·20일 고저점)에 쓴다. 없으면 선택지 없이."""
    from .confirm import confirmation

    stamp = checked_at or now_iso()
    rows = price_rows or []
    out = [r for r in sentence_responses(memo_id, judgments, lambda j: confirmation(j.cleaned_text or j.text,
                                                                                   j.reason_code, rows), stamp)
           if r.type == "needs_confirmation"]
    whole = memo_response(memo_id, judgments, n_items, stamp)
    return out + ([whole] if whole else [])


# 마지막 확인 시각을 갱신해도 되는 '정상 종료' (2026-11-11). 실패(call_failed·parse_failed·check_failed·verify_failed·
# relevance_failed)와 확인하지 않음(not_called)은 갱신하지 않는다 → 다음 실행에서 같은 자료를 다시 본다.
NORMAL_NO_NEW = {"no_candidates", "already_shown", "llm_no_update", "price_unchanged", "no_relevant_candidates"}


def marks_checked(r: Response, failed_items: set[str] | frozenset = frozenset()) -> bool:
    """이 응답으로 그 항목의 last_checked_at을 갱신해도 되는가. failed_items: 카드 저장이 실패한 항목."""
    if r.scope != "item" or not r.item_id or r.item_id in failed_items:
        return False
    if r.type in ("update_card", "price_card", "no_data", "ask_no_answer"):
        return True
    return r.type == "no_new_info" and (r.reason in NORMAL_NO_NEW or r.reason.startswith("merged_into:"))


def order_key(r: Response) -> int:
    return TYPES.index(r.type) if r.type in TYPES else len(TYPES)


def to_dict(r: Response) -> dict:
    return asdict(r)


def summarize(responses: list[Response]) -> dict:
    visible = [r for r in responses if r.user_visible]
    asks = [r for r in responses if r.type == "needs_confirmation"]
    return {"responses": len(responses),
            "by_type": {t: sum(r.type == t for r in responses) for t in TYPES},
            "by_scope": dict(Counter(f"{r.type}/{r.scope}" for r in responses)),
            "user_visible": len(visible), "user_visible_by_type": dict(Counter(r.type for r in visible)),
            "reasons": {t: dict(Counter(r.reason for r in responses if r.type == t)) for t in TYPES
                        if any(r.type == t for r in responses)},
            "needs_confirmation": {"total": len(asks), "with_options": sum(bool(r.options) for r in asks),
                                   "with_already_reached": sum(any(o.get("status") == "already_reached" for o in r.options)
                                                               for r in asks),
                                   "relative_parsed": sum(any(c.startswith("relative:") for c in r.fail_codes) for r in asks)}}


NEWS_DISC = {"뉴스", "공시"}


def data_need_check(memos: list[dict]) -> dict:
    """메모 단위 no_data 검증. memos: {"memo_id", "data_need": [...], "no_data": bool, "no_data_reasons": [...]}.
    no_data(b)는 뉴스·공시가 없을 때라, data_need에 뉴스·공시가 있는 메모의 no_data는 '필요한 자료가 없음'으로 맞고,
    data_need가 재무·주가·거시뿐인 메모의 no_data(b)는 기준이 다른 것(뉴스·공시가 없어도 그 메모엔 상관없음)으로 센다."""
    rows = [m for m in memos if m.get("data_need") is not None]
    c = Counter()
    mismatch = []
    for m in rows:
        need = set(m["data_need"])
        wants_nd, wants_price = bool(need & NEWS_DISC), "주가·거래" in need
        reasons = set(m.get("no_data_reasons") or [])
        c["memos"] += 1
        c["no_data_memos"] += bool(m["no_data"])
        if "no_source_data" in reasons:
            key = "b_needs_news_or_disclosure" if wants_nd else "b_but_need_has_no_news_or_disclosure"
            c[key] += 1
            if not wants_nd:
                mismatch.append({"memo_id": m["memo_id"], "data_need": m["data_need"], "reason": "no_source_data"})
        if "no_price" in reasons:
            key = "a_needs_price" if wants_price else "a_but_need_has_no_price"
            c[key] += 1
            if not wants_price:
                mismatch.append({"memo_id": m["memo_id"], "data_need": m["data_need"], "reason": "no_price"})
        if not need:
            c["data_need_empty"] += 1
            c["data_need_empty_and_out_of_scope"] += bool(m.get("out_of_scope"))
    return {**dict(c), "mismatch": mismatch}
