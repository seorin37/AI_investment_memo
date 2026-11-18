"""외부 API 호출 재시도 도구 (지수 백오프·호출 간격)."""

from __future__ import annotations

import time
from typing import Callable, TypeVar


T = TypeVar("T")


def retry_call(
    fn: Callable[[], T],
    *,
    attempts: int = 3,
    base_delay: float = 1.0,
    retry_on: tuple[type[BaseException], ...] = (Exception,),
    should_retry: Callable[[BaseException], bool] | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """fn을 최대 attempts회 호출한다. 실패 사이에 base_delay × 2^(n-1)초 쉰다."""
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except retry_on as exc:
            if attempt >= attempts or (should_retry is not None and not should_retry(exc)):
                raise
            sleep(base_delay * (2 ** (attempt - 1)))
    raise AssertionError("unreachable")


class Throttle:
    """연속 호출 사이에 최소 interval초 간격을 둔다."""

    def __init__(self, interval: float, clock: Callable[[], float] = time.monotonic, sleep: Callable[[float], None] = time.sleep):
        self.interval = interval
        self.clock = clock
        self.sleep = sleep
        self._last: float | None = None

    def wait(self) -> None:
        now = self.clock()
        if self._last is not None:
            remaining = self.interval - (now - self._last)
            if remaining > 0:
                self.sleep(remaining)
                now = self.clock()
        self._last = now
