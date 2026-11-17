
import logging
from datetime import date, timedelta

import exchange_calendars as xc


logger = logging.getLogger(__name__)


# 지원 범위. 끝 날짜를 넘기기 전에 범위를 늘리고 추가 휴장일을 다시 확인한다.
CALENDAR_START = date(2019, 1, 1)
CALENDAR_END = date(2027, 12, 31)

# 지원 범위 끝까지 남은 날이 이 값 이하이면 경고 로그를 남긴다.
RANGE_END_WARNING_DAYS = 30


# 한국거래소 기본 거래일 캘린더
XKRX_CALENDAR = xc.get_calendar(
    "XKRX",
    start=CALENDAR_START.isoformat(),
    end=CALENDAR_END.isoformat(),
)


# 공식 발표로 확인된 추가 휴장일
# exchange_calendars에 반영되지 않은 날짜만 등록
# TODO(2027): KRX 2027년 휴장일 공시가 나오면 라이브러리 결과와 대조한다.
#   exchange_calendars 4.13.2가 산출한 2027 평일 휴장일:
#   01-01, 02-08, 02-09, 03-01, 05-05, 05-13, 08-16, 09-14, 09-15, 09-16,
#   10-04, 10-11, 12-27, 12-31
#   제헌절(2027-07-17, 토요일)의 대체휴일 적용 여부는 확인되지 않았다.
ADDITIONAL_KRX_HOLIDAYS = {
    date(2026, 6, 3),   # 제9회 전국동시지방선거
    date(2026, 7, 17),  # 제헌절
}


_warned_dates: set[date] = set()


def _check_supported(target_date: date) -> None:
    if not CALENDAR_START <= target_date <= CALENDAR_END:
        raise ValueError(
            f"KRX 캘린더 지원 범위 밖: {target_date} "
            f"(지원 범위 {CALENDAR_START}~{CALENDAR_END}). "
            "pipelines/market/calendar.py의 CALENDAR_END와 추가 휴장일을 갱신하세요."
        )
    days_left = (CALENDAR_END - target_date).days
    if days_left <= RANGE_END_WARNING_DAYS and target_date not in _warned_dates:
        _warned_dates.add(target_date)
        logger.warning(
            "KRX 캘린더 지원 범위 끝(%s)까지 %d일 남았습니다 (조회일 %s). "
            "CALENDAR_END와 추가 휴장일을 갱신하세요.",
            CALENDAR_END,
            days_left,
            target_date,
        )


def is_krx_trading_day(target_date: date) -> bool:
    """한국거래소의 실제 거래일 여부를 판별한다."""

    # 캘린더 지원 범위를 벗어나면 오류
    _check_supported(target_date)

    # 공식적으로 확인된 추가 휴장일
    if target_date in ADDITIONAL_KRX_HOLIDAYS:
        return False

    # 라이브러리는 첫·마지막 세션 바깥 날짜를 받지 않는다.
    # 지원 범위 안이면서 세션 바깥인 날(예: 연말 휴장일)은 거래일이 아니다.
    first_session = XKRX_CALENDAR.first_session.date()
    last_session = XKRX_CALENDAR.last_session.date()
    if not first_session <= target_date <= last_session:
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
