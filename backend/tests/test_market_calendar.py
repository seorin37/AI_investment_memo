import logging
from datetime import date

import pytest

from pipelines.market import calendar


@pytest.fixture(autouse=True)
def _reset_warnings():
    calendar._warned_dates.clear()
    yield
    calendar._warned_dates.clear()


def test_last_session_of_2026_is_trading_day():
    assert calendar.is_krx_trading_day(date(2026, 12, 30)) is True


def test_year_end_closure_2026_is_not_error():
    # 연말 휴장일. 과거에는 지원 범위 끝이라 ValueError가 났다.
    assert calendar.is_krx_trading_day(date(2026, 12, 31)) is False


def test_first_session_of_2027():
    assert calendar.is_krx_trading_day(date(2027, 1, 1)) is False
    assert calendar.is_krx_trading_day(date(2027, 1, 4)) is True
    assert calendar.previous_krx_trading_day(date(2027, 1, 4)) == date(2026, 12, 30)


def test_additional_holidays_still_apply():
    assert calendar.is_krx_trading_day(date(2026, 6, 3)) is False
    assert calendar.is_krx_trading_day(date(2026, 7, 17)) is False


def test_supported_range_end():
    assert calendar.CALENDAR_END >= date(2027, 12, 31)
    assert calendar.is_krx_trading_day(date(2027, 12, 30)) is True
    assert calendar.is_krx_trading_day(date(2027, 12, 31)) is False
    assert calendar.previous_krx_trading_day(date(2028, 1, 1)) == date(2027, 12, 30)


@pytest.mark.parametrize("out_of_range", [date(2028, 1, 3), date(2018, 12, 31)])
def test_out_of_range_raises_clear_error(out_of_range):
    with pytest.raises(ValueError, match="KRX 캘린더 지원 범위 밖") as excinfo:
        calendar.is_krx_trading_day(out_of_range)
    assert str(calendar.CALENDAR_END) in str(excinfo.value)
    assert "CALENDAR_END" in str(excinfo.value)


def test_warns_within_30_days_of_range_end(caplog):
    caplog.set_level(logging.WARNING, logger=calendar.__name__)
    calendar.is_krx_trading_day(date(2027, 12, 1))
    calendar.is_krx_trading_day(date(2027, 12, 1))
    warnings = [r for r in caplog.records if "지원 범위 끝" in r.getMessage()]
    assert len(warnings) == 1
    assert "30일" in warnings[0].getMessage()


def test_no_warning_far_from_range_end(caplog):
    caplog.set_level(logging.WARNING, logger=calendar.__name__)
    calendar.is_krx_trading_day(date(2026, 12, 30))
    calendar.is_krx_trading_day(date(2027, 11, 30))  # 31일 전
    assert not [r for r in caplog.records if "지원 범위 끝" in r.getMessage()]
