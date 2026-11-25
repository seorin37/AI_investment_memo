from backend.pipelines.common.wait_db import wait_for_db


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def test_waits_until_db_accepts_connections():
    clock, calls = FakeClock(), []

    def connect():
        calls.append(clock.now)
        if len(calls) < 3:
            raise OSError("FATAL:  the database system is starting up")

    assert wait_for_db("dsn", timeout=60, interval=5, connect=connect, sleep=clock.sleep, clock=clock)
    assert calls == [0.0, 5.0, 10.0]


def test_gives_up_after_timeout():
    clock = FakeClock()

    def connect():
        raise OSError("connection refused")

    assert not wait_for_db("dsn", timeout=12, interval=5, connect=connect, sleep=clock.sleep, clock=clock)
    assert clock.now == 12.0
