
from datetime import date, timedelta

import exchange_calendars as xc


# 한국거래소 기본 거래일 캘린더
XKRX_CALENDAR = xc.get_calendar(
    "XKRX",
    start="2019-01-01",
    end="2026-12-31",
)


# 공식 발표로 확인된 추가 휴장일
# exchange_calendars에 반영되지 않은 날짜만 등록
ADDITIONAL_KRX_HOLIDAYS = {
    date(2026, 6, 3),   # 제9회 전국동시지방선거
    date(2026, 7, 17),  # 제헌절
}


def is_krx_trading_day(target_date: date) -> bool:
    """한국거래소의 실제 거래일 여부를 판별한다."""

    first_session = XKRX_CALENDAR.first_session.date()
    last_session = XKRX_CALENDAR.last_session.date()

    # 캘린더 지원 범위를 벗어나면 오류
    if not first_session <= target_date <= last_session:
        raise ValueError(
            f"KRX 캘린더 지원 범위 밖: {target_date}"
        )

    # 공식적으로 확인된 추가 휴장일
    if target_date in ADDITIONAL_KRX_HOLIDAYS:
        return False

    # 기본 캘린더 기준
    return bool(
        XKRX_CALENDAR.is_session(target_date.isoformat())
    )


def previous_krx_trading_day(reference_date: date) -> date:
    """Return the latest KRX session strictly before ``reference_date``."""

    candidate = reference_date - timedelta(days=1)
    first_session = XKRX_CALENDAR.first_session.date()
    while candidate >= first_session:
        if is_krx_trading_day(candidate):
            return candidate
        candidate -= timedelta(days=1)
    raise ValueError(f"이전 KRX 거래일을 찾을 수 없습니다: {reference_date}")
