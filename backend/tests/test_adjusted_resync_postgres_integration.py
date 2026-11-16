"""수정주가 재동기화 적용·복원을 격리된 로컬 PostgreSQL에서만 확인한다 (운영 DB 금지).

ADJUSTED_RESYNC_INTEGRATION_DATABASE_URL이 없으면 건너뛴다. localhost·5432가 아닌 포트·DB 이름에 test가
들어간 경우에만 실행하고, DATABASE_URL·READONLY_DATABASE_URL과 같은 주소면 실패시킨다.
스키마는 alembic head가 적용돼 있어야 한다 (adjusted_prices_daily.volume은 0011).
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from pipelines.market import adjusted_resync as rs
from pipelines.market import corporate_actions as ca

ENV = "ADJUSTED_RESYNC_INTEGRATION_DATABASE_URL"
SYMBOL, OTHER = "999990", "999991"
KST = timezone(timedelta(hours=9))
NOW = datetime(2026, 11, 16, 15, 0, tzinfo=KST)
ORIGINAL_COLLECTED = datetime(2026, 10, 30, 18, 28, tzinfo=KST)
DAYS = [date(2026, 11, 10), date(2026, 11, 11), date(2026, 11, 12)]


def _url() -> str:
    raw = os.environ.get(ENV)
    if not raw:
        pytest.skip(f"{ENV} is not set")
    url = make_url(raw)
    if url.host not in {"127.0.0.1", "localhost"} or url.port in {None, 5432} or "test" not in (url.database or ""):
        pytest.fail("격리된 로컬 테스트 DB가 아닙니다.")
    for name in ("DATABASE_URL", "READONLY_DATABASE_URL"):
        other = os.environ.get(name)
        if other:
            o = make_url(other)
            if (o.host, o.port, o.database) == (url.host, url.port, url.database):
                pytest.fail(f"테스트 DB가 {name}과 같습니다.")
    return raw


@pytest.fixture()
def engine():
    eng = create_engine(_url(), pool_pre_ping=True)
    with eng.begin() as c:
        for s in (SYMBOL, OTHER):
            c.execute(text("DELETE FROM adjusted_prices_daily WHERE symbol = :s"), {"s": s})
            c.execute(text("DELETE FROM prices_daily WHERE symbol = :s"), {"s": s})
            c.execute(text("INSERT INTO stocks (symbol, name) VALUES (:s, 'resync test') ON CONFLICT (symbol) DO NOTHING"),
                      {"s": s})
            for d in DAYS:
                c.execute(text("""INSERT INTO prices_daily (symbol, trade_date, open, high, low, close, volume, source)
                                  VALUES (:s, :d, 100, 100, 100, 100, 500, 'KIS')"""), {"s": s, "d": d})
                c.execute(text("""INSERT INTO adjusted_prices_daily (symbol, trade_date, open, high, low, close, volume,
                                  source, adjustment_basis, collected_at)
                                  VALUES (:s, :d, 100, 100, 100, 100, 500, 'KIS', :b, :t)"""),
                          {"s": s, "d": d, "b": rs.ADJUSTMENT_BASIS, "t": ORIGINAL_COLLECTED})
    yield eng
    with eng.begin() as c:
        for s in (SYMBOL, OTHER):
            c.execute(text("DELETE FROM adjusted_prices_daily WHERE symbol = :s"), {"s": s})
            c.execute(text("DELETE FROM prices_daily WHERE symbol = :s"), {"s": s})
    eng.dispose()


def _plan():
    db = [{"trade_date": d, "raw_close": Decimal(100), "raw_volume": 500, "adj_open": Decimal(100),
           "adj_high": Decimal(100), "adj_low": Decimal(100), "adj_close": Decimal(100), "adj_volume": 500,
           "adjustment_basis": rs.ADJUSTMENT_BASIS} for d in DAYS]
    kis = [{"trade_date": d, "open": Decimal(500), "high": Decimal(500), "low": Decimal(500), "close": Decimal(500),
            "volume": 100} for d in DAYS]
    plan = rs.build_plan(SYMBOL, db, kis, zero_rows=0, duplicates=[], kis_fetched_at=NOW,
                         recheck_status=ca.HISTORY_RESYNC_CANDIDATE)
    assert plan["status"] == "ready"
    return plan


def _snap(engine, table, symbol=SYMBOL):
    cols = "trade_date, open, high, low, close, volume" + (", collected_at" if table == "adjusted_prices_daily" else "")
    with engine.connect() as c:
        return [tuple(r) for r in c.execute(text(f"SELECT {cols} FROM {table} WHERE symbol = :s ORDER BY trade_date"),
                                            {"s": symbol})]


def _all_snapshots(engine):
    return {(t, s): _snap(engine, t, s) for t in ("adjusted_prices_daily", "prices_daily") for s in (SYMBOL, OTHER)}


class _Proxy:
    """실제 연결을 감싸 N번째 UPDATE에서 실패하거나, 검증 직전에 값을 흐트러뜨린다."""

    def __init__(self, conn, fail_after=None, drift=False):
        self.conn, self.fail_after, self.drift, self.updates, self.selects = conn, fail_after, drift, 0, 0

    def execute(self, stmt, params=None):
        sql = str(stmt)
        if sql.lstrip().startswith("UPDATE adjusted_prices_daily"):
            self.updates += 1
            if self.fail_after is not None and self.updates > self.fail_after:
                raise RuntimeError("중간 실패 주입")
        if sql.lstrip().startswith("SELECT"):
            self.selects += 1
            if self.drift and self.selects == 2:
                # OHLC 순서 CHECK를 지키면서 계획과 다른 값으로 흐트러뜨린다
                self.conn.execute(text("UPDATE adjusted_prices_daily SET open = 1, high = 1, low = 1, close = 1 "
                                       "WHERE symbol = :s AND trade_date = :d"), {"s": SYMBOL, "d": DAYS[0]})
        return self.conn.execute(stmt, params)


def _begin(engine, **kw):
    @contextmanager
    def begin():
        with engine.begin() as conn:
            yield _Proxy(conn, **kw)
    return begin


# ---------------------------------------------------------------- 적용


def test_apply_updates_only_target_rows_and_verifies(engine, tmp_path):
    plan = _plan()
    before = _all_snapshots(engine)
    result = rs.apply_plan(engine.begin, plan, symbol=SYMBOL, confirm=plan["plan_sha256"], backup_dir=tmp_path, now=NOW)
    assert result["updated_rows"] == 3
    after = _snap(engine, "adjusted_prices_daily")
    assert [r[1:6] for r in after] == [(Decimal("500.00"),) * 4 + (100,)] * 3
    assert {r[6] for r in after} == {NOW}
    for key in [("adjusted_prices_daily", OTHER), ("prices_daily", SYMBOL), ("prices_daily", OTHER)]:
        assert _all_snapshots(engine)[key] == before[key], key


def test_mid_update_failure_rolls_back_everything(engine, tmp_path):
    plan = _plan()
    before = _all_snapshots(engine)
    with pytest.raises(RuntimeError, match="중간 실패"):
        rs.apply_plan(_begin(engine, fail_after=2), plan, symbol=SYMBOL, confirm=plan["plan_sha256"],
                      backup_dir=tmp_path, now=NOW)
    assert _all_snapshots(engine) == before


def test_fingerprint_mismatch_is_refused(engine, tmp_path):
    plan = _plan()
    with engine.begin() as c:
        c.execute(text("UPDATE adjusted_prices_daily SET open = 101, high = 101, low = 101, close = 101 "
                       "WHERE symbol = :s AND trade_date = :d"), {"s": SYMBOL, "d": DAYS[1]})
    before = _all_snapshots(engine)
    with pytest.raises(rs.StalePlan):
        rs.apply_plan(engine.begin, plan, symbol=SYMBOL, confirm=plan["plan_sha256"], backup_dir=tmp_path, now=NOW)
    assert _all_snapshots(engine) == before and list(tmp_path.iterdir()) == []


def test_sha256_mismatch_is_refused(engine, tmp_path):
    plan = _plan()
    before = _all_snapshots(engine)
    with pytest.raises(rs.PlanRejected):
        rs.apply_plan(engine.begin, plan, symbol=SYMBOL, confirm="0" * 64, backup_dir=tmp_path, now=NOW)
    assert _all_snapshots(engine) == before


def test_backup_failure_refuses_update(engine, tmp_path):
    plan = _plan()
    blocker = tmp_path / "not_a_dir"
    blocker.write_text("x")
    before = _all_snapshots(engine)
    with pytest.raises(OSError):
        rs.apply_plan(engine.begin, plan, symbol=SYMBOL, confirm=plan["plan_sha256"], backup_dir=blocker, now=NOW)
    assert _all_snapshots(engine) == before


def test_post_apply_verification_failure_rolls_back(engine, tmp_path):
    plan = _plan()
    before = _all_snapshots(engine)
    with pytest.raises(rs.ApplyVerificationError):
        rs.apply_plan(_begin(engine, drift=True), plan, symbol=SYMBOL, confirm=plan["plan_sha256"],
                      backup_dir=tmp_path, now=NOW)
    assert _all_snapshots(engine) == before


# ---------------------------------------------------------------- 복원


def _current_rows(engine):
    with engine.connect() as c:
        return [dict(r) for r in c.execute(text(rs.SELECT_FOR_UPDATE_SQL.replace("FOR UPDATE", "")), {"s": SYMBOL,
                                                                                                       "symbol": SYMBOL}).mappings()]


def test_restore_round_trip_and_rollback(engine, tmp_path):
    original = _all_snapshots(engine)
    plan = _plan()
    applied = rs.apply_plan(engine.begin, plan, symbol=SYMBOL, confirm=plan["plan_sha256"], backup_dir=tmp_path, now=NOW)
    backup = rs.load_backup(applied["backup_path"])
    preview = rs.plan_restore(backup, _current_rows(engine), symbol=SYMBOL)
    assert preview["status"] == "ready"
    after_apply = _all_snapshots(engine)
    # 복원 중간 실패 → 적용 직후 상태 그대로
    with pytest.raises(RuntimeError):
        rs.apply_restore(_begin(engine, fail_after=1), backup, symbol=SYMBOL, confirm=preview["restore_sha256"],
                         backup_dir=tmp_path / "pre1", now=NOW)
    assert _all_snapshots(engine) == after_apply
    # 정상 복원 → 원래 값과 collected_at까지 그대로
    result = rs.apply_restore(engine.begin, backup, symbol=SYMBOL, confirm=preview["restore_sha256"],
                              backup_dir=tmp_path / "pre2", now=NOW)
    assert result["restored_rows"] == 3
    assert _all_snapshots(engine) == original
