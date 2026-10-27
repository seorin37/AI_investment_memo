"""가격 조건 판정 — 종가와 조건가를 코드로 비교한다 (LLM 없음, 일봉 종가 기준, 지침서 Ⅴ-2).

reached : 조건 만족 (below: 종가 <= 조건가, above: 종가 >= 조건가)
near    : 조건 전이고, 조건가까지 남은 거리가 조건가의 near_pct% 이내
away    : 그 밖
카드는 상태가 '바뀌어' near 또는 reached가 될 때만 만든다 (같은 상태 반복·멀어짐은 카드 없음).
이전 상태는 마지막으로 저장한 상태(last_state)를 우선 쓰고, 없으면 전 거래일 종가로 계산한다.
DB 제약: price_condition 업데이트는 observed_trade_date·price_state·observed_value가 필수이고 update_sources를 쓰지 않는다.
"""

from __future__ import annotations

from .fixed import price_phrase
from .models import TrackingItem, UpdateDraft

NEAR_PCT_DEFAULT = 3.0


def remaining(direction: str, threshold: float, close: float) -> float:
    """조건 만족까지 남은 값. 0 이하면 이미 만족."""
    return close - threshold if direction == "below" else threshold - close


def price_state(direction: str, threshold: float, close: float, near_pct: float = NEAR_PCT_DEFAULT) -> str:
    rem = remaining(direction, threshold, close)
    if rem <= 0:
        return "reached"
    return "near" if rem / threshold * 100 <= near_pct else "away"


def check_price(item: TrackingItem, close: float, prev_close: float | None, trade_date: str,
                near_pct: float = NEAR_PCT_DEFAULT, last_state: str | None = None) -> UpdateDraft | None:
    direction = "below" if item.type == "price_below" else "above"
    threshold = item.price_threshold
    state = price_state(direction, threshold, close, near_pct)
    if state == "away":
        return None
    before = last_state or (price_state(direction, threshold, prev_close, near_pct) if prev_close is not None else None)
    if before == state:
        return None
    rem = max(remaining(direction, threshold, close), 0)
    remain_pct = round(rem / threshold * 100, 1)
    title, summary = price_phrase(state, int(threshold), close, trade_date, remain_pct)
    details = {"direction": direction, "close": close, "threshold": threshold, "remain": rem,
               "remain_pct": remain_pct, "prev_close": prev_close, "prev_state": before}
    return UpdateDraft(item=item, type="price_condition", title=title, summary=summary,
                       reason=f"메모에 적어 두신 {int(threshold):,}원 조건과 관련된 가격 변화예요",
                       price_state=state, details=details, observed_trade_date=trade_date, origin="fixed")
