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


# ---------------------------------------------------------------- 오래된 종가 (2026-11-10)
# 종목의 마지막 종가가 시장의 가장 최근 거래일보다 STALE_TRADING_DAYS 거래일 넘게 오래됐으면(거래정지 등)
# 가격 카드를 만들지 않고 no_data(stale_price)로 본다. 거래일은 prices_daily 전체의 거래일 목록으로 센다.
STALE_TRADING_DAYS = 3
MARKET_DATES_SQL = "SELECT DISTINCT trade_date FROM prices_daily WHERE trade_date >= %(since)s ORDER BY 1 DESC"


def market_dates(conn, lookback_days: int = 60) -> list:
    """최근 시장 거래일 (최신순). 종목별 종가가 몇 거래일 뒤처졌는지 세는 데 쓴다."""
    from datetime import date, timedelta

    with conn.cursor() as cur:
        cur.execute(MARKET_DATES_SQL, {"since": date.today() - timedelta(days=lookback_days)})
        return [d for (d,) in cur.fetchall()]


def trading_lag(day, dates: list) -> int:
    """day(종목의 마지막 거래일) 뒤에 있는 시장 거래일 수. dates는 최신순.
    dates가 비면 0 (판단할 수 없으면 오래됐다고 보지 않는다). day가 목록보다 오래되면 목록 길이 + 1."""
    if not dates:
        return 0
    lag = sum(1 for d in dates if d > day)
    return lag + 1 if day < dates[-1] else lag


def price_outcome(item: TrackingItem, rows: list, dates: list, near_pct: float = NEAR_PCT_DEFAULT,
                  stale_days: int = STALE_TRADING_DAYS) -> tuple[str, UpdateDraft | None, dict]:
    """가격 항목 판정. rows는 PRICE_SQL 결과(최신순 trade_date, close 최대 2개).
    반환 (결과 종류, 카드, 정보): price_no_data(종가 없음) | price_stale(오래된 종가) | price_card | price_no_card."""
    if not rows:
        return "price_no_data", None, {}
    (day, close), prev = rows[0], (float(rows[1][1]) if len(rows) > 1 else None)
    lag = trading_lag(day, dates)
    info = {"trade_date": str(day), "close": float(close), "lag_trading_days": lag,
            "market_latest": str(dates[0]) if dates else None}
    if lag > stale_days:
        return "price_stale", None, info
    draft = check_price(item, float(close), prev, str(day), near_pct)
    return ("price_card" if draft else "price_no_card"), draft, info
