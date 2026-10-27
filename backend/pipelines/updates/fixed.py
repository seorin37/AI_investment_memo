"""고정 문구 — LLM 없이 만드는 문구 (지침서 Ⅴ-2). 검사에서 버린 카드를 대신하고, 가격 카드·거절 답변에 처음부터 쓴다."""

from __future__ import annotations

from .models import Evidence, TrackingItem, UpdateDraft

NO_DATA = "지금 가진 자료로는 답하기 어려워요."
DECLINE_ADVICE = "매수·매도 판단은 드리지 않아요. 관련 공시와 실적 변화를 계속 알려 드릴게요."
DECLINE_FORECAST = "앞으로의 주가는 예측하지 않아요. 관련 변화가 생기면 알려 드릴게요."
CONFLICT = "확인된 자료의 내용이 서로 달라 지금은 답하기 어려워요."
NEED_CALC = "지금 준비된 계산 결과로는 답하기 어려워요."

# 즉시 답변의 reason_code → 고정 문구 (지침서 4)
FIXED_BY_REASON = {"investment_advice": DECLINE_ADVICE, "price_prediction": DECLINE_FORECAST,
                   "insufficient_evidence": NO_DATA, "evidence_conflict": CONFLICT, "calculation_required": NEED_CALC}


def fixed_card(item: TrackingItem, evidence: list[Evidence]) -> UpdateDraft | None:
    """공시가 있으면 공시, 없으면 가장 유사한 뉴스로 대체 카드를 만든다."""
    if not evidence:
        return None
    pick = next((e for e in evidence if e.candidate.kind == "disclosure"), evidence[0])
    c = pick.candidate
    if c.kind == "disclosure":
        title, summary = "새 공시가 올라왔어요", f"새 공시가 올라왔어요: {c.title} ({c.date})"
    else:
        title, summary = "관련 기사가 있어요", f"관련 기사가 있어요: {c.title} · {c.source} ({c.date})"
    return UpdateDraft(item=item, type="disclosure" if c.kind == "disclosure" else "news", title=title, summary=summary,
                       reason=f"추적 항목 '{item.description}'와 관련해 올라온 자료예요", sources=[(c.ref, None)], origin="fixed")


def price_phrase(state: str, threshold: int, close: float, trade_date: str, remain_pct: float) -> tuple[str, str]:
    """가격 조건 카드 (제목, 문구). 가까워짐·도달만 있다 (멀어짐은 카드를 만들지 않는다)."""
    if state == "reached":
        return "조건가에 도달했어요", f"{threshold:,}원에 도달했어요 ({trade_date} 종가 기준)"
    return "조건가에 가까워졌어요", f"{threshold:,}원에 가까워졌어요 ({trade_date} 종가 {close:,.0f}원, {remain_pct}% 남음)"
