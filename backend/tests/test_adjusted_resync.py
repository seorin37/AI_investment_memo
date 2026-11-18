from __future__ import annotations

import copy
import json
import re
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from pipelines.market import adjusted_recheck as rc
from pipelines.market import adjusted_resync as rs
from pipelines.market import corporate_actions as ca
from scripts import adjusted_price_manager as cli

KST = timezone(timedelta(hours=9))
NOW = datetime(2026, 11, 16, 15, 0, tzinfo=KST)
BASIS = "KIS_FID_ORG_ADJ_PRC_0_V1"
DAYS = ["2026-10-26", "2026-10-27", "2026-11-12", "2026-11-13"]
RAW = [746, 746, 746, 746]
RAW_VOL = [148076, 0, 0, 0]


def db_rows(adj=(746, 746, 746, 3730), adj_vol=(148076, 0, 0, 0), days=DAYS):
    return [{"symbol": "047400", "trade_date": date.fromisoformat(d), "raw_close": Decimal(r), "raw_volume": rv,
             "adj_open": Decimal(a), "adj_high": Decimal(a), "adj_low": Decimal(a), "adj_close": Decimal(a),
             "adj_volume": av, "adjustment_basis": BASIS}
            for d, r, rv, a, av in zip(days, RAW, RAW_VOL, adj, adj_vol)]


def kis_rows(adj=(3730, 3730, 3730, 3730), vol=(29615, 0, 0, 0), days=DAYS):
    return [{"trade_date": date.fromisoformat(d), "open": Decimal(a), "high": Decimal(a), "low": Decimal(a),
             "close": Decimal(a), "volume": v} for d, a, v in zip(days, adj, vol)]


def plan_047400(**kw):
    return rs.build_plan("047400", db_rows(), kis_rows(), zero_rows=0, duplicates=[], kis_fetched_at=NOW,
                         recheck_status=ca.HISTORY_RESYNC_CANDIDATE, **kw)


# ---------------------------------------------------------------- 계획(dry-run)


def test_047400_plan_is_ready_with_all_checks_passing():
    plan = plan_047400()
    assert plan["status"] == "ready", plan["blocking_failures"]
    assert plan["changed_rows"] == 3 and plan["changed_range"] == ["2026-10-26", "2026-11-12"]
    assert [lv["ratio"] for lv in plan["ratio_levels_db"]] == [1.0, 5.0]
    assert [lv["ratio"] for lv in plan["ratio_levels_kis"]] == [5.0]
    assert all(c["passed"] for c in plan["checks"])
    assert plan["new_rows"][0] == {"trade_date": "2026-10-26", "open": "3730.00", "high": "3730.00", "low": "3730.00",
                                   "close": "3730.00", "volume": 29615}
    assert rs.plan_hash(plan) == plan["plan_sha256"]


def test_source_discontinuity_blocks_plan():
    days = ["2024-11-11", "2024-11-12", "2024-11-13", "2024-11-14"]
    db = [{**r, "raw_close": Decimal(9340), "raw_volume": 0, "symbol": "101140"}
          for r in db_rows(adj=(585, 585, 11700, 11700), adj_vol=(0, 0, 0, 0), days=days)]
    kis = kis_rows(adj=(585, 585, 11700, 11700), vol=(0, 0, 0, 0), days=days)
    plan = rs.build_plan("101140", db, kis, zero_rows=0, duplicates=[], kis_fetched_at=NOW,
                         recheck_status=ca.SOURCE_DISCONTINUITY)
    assert plan["status"] == "blocked"
    assert {"recheck_status_is_resync_candidate", "kis_history_continuous"} <= set(plan["blocking_failures"])
    assert plan["new_rows"] == []  # 보정값을 만들지 않는다


@pytest.mark.parametrize("mutate, failure", [
    (lambda db, kis: (db, kis[:-1]), "date_set_equal"),
    (lambda db, kis: (db, kis + [{**kis[0], "trade_date": date(2026, 11, 14)}]), "date_set_equal"),
    (lambda db, kis: (db, [{**kis[1], "volume": 5}] + kis[:1] + kis[2:]), "volume_zero_consistent"),
    (lambda db, kis: (db, [{**kis[0], "low": Decimal(4000)}] + kis[1:]), "kis_prices_valid"),
])
def test_invalid_kis_history_blocks_plan(mutate, failure):
    db, kis = mutate(db_rows(), kis_rows())
    plan = rs.build_plan("047400", db, kis, zero_rows=0, duplicates=[], kis_fetched_at=NOW,
                         recheck_status=ca.HISTORY_RESYNC_CANDIDATE)
    assert plan["status"] == "blocked" and failure in plan["blocking_failures"]


def test_duplicates_and_zero_rows_block_plan():
    plan = rs.build_plan("047400", db_rows(), kis_rows(), zero_rows=1, duplicates=["2026-10-26"], kis_fetched_at=NOW,
                         recheck_status=ca.HISTORY_RESYNC_CANDIDATE)
    assert {"no_duplicate_dates", "no_zero_ohlc_rows"} <= set(plan["blocking_failures"])


def test_unchanged_history_is_no_change():
    plan = rs.build_plan("047400", db_rows(adj=(3730,) * 4, adj_vol=(29615, 0, 0, 0)), kis_rows(), zero_rows=0,
                         duplicates=[], kis_fetched_at=NOW, recheck_status=ca.HISTORY_RESYNC_CANDIDATE)
    assert plan["status"] == "no_change" and plan["new_rows"] == []


# ---------------------------------------------------------------- 적용 전 승인 검증


def test_apply_requires_matching_symbol_hash_fresh_ready_plan():
    plan = plan_047400()
    ok = dict(symbol="047400", confirm=plan["plan_sha256"], now=NOW, max_age=timedelta(hours=24))
    rs.validate_for_apply(plan, **ok)
    with pytest.raises(rs.PlanRejected):
        rs.validate_for_apply(plan, **{**ok, "symbol": "101140"})
    with pytest.raises(rs.PlanRejected):
        rs.validate_for_apply(plan, **{**ok, "confirm": "0" * 64})
    with pytest.raises(rs.PlanRejected):
        rs.validate_for_apply(plan, **{**ok, "now": NOW + timedelta(hours=25)})
    tampered = copy.deepcopy(plan)
    tampered["new_rows"][0]["close"] = "1.00"
    with pytest.raises(rs.PlanRejected):
        rs.validate_for_apply(tampered, **ok)
    blocked = rs.build_plan("047400", db_rows(), kis_rows()[:-1], zero_rows=0, duplicates=[], kis_fetched_at=NOW,
                            recheck_status=ca.HISTORY_RESYNC_CANDIDATE)
    with pytest.raises(rs.PlanRejected):
        rs.validate_for_apply(blocked, **{**ok, "confirm": blocked["plan_sha256"]})


# ---------------------------------------------------------------- 적용 (가짜 DB)


class Result:
    def __init__(self, rows=None, rowcount=0):
        self._rows, self.rowcount = rows or [], rowcount

    def mappings(self):
        return self

    def all(self):
        return self._rows


class FakeDB:
    """adjusted_prices_daily 한 종목만 가진 가짜 DB. begin()은 예외가 나면 이전 상태로 되돌린다."""

    def __init__(self, rows, fail_on_update: int | None = None):
        self.adjusted = {r["trade_date"]: dict(r) for r in rows}
        self.prices_daily_untouched = True
        self.statements = []
        self.fail_on_update = fail_on_update
        self.commits = 0
        self.rollbacks = 0

    @contextmanager
    def begin(self):
        snapshot = copy.deepcopy(self.adjusted)
        try:
            yield self
            self.commits += 1
        except Exception:
            self.adjusted = snapshot
            self.rollbacks += 1
            raise

    def execute(self, sql, params):
        self.statements.append(sql)
        if sql is rs.SELECT_FOR_UPDATE_SQL:
            return Result([dict(v) for _, v in sorted(self.adjusted.items())])
        if sql in (rs.UPDATE_SQL, rs.RESTORE_UPDATE_SQL):
            writes = [s for s in self.statements if s in (rs.UPDATE_SQL, rs.RESTORE_UPDATE_SQL)]
            if self.fail_on_update is not None and len(writes) > self.fail_on_update:
                return Result(rowcount=0)
            row = self.adjusted.get(params["trade_date"])
            source = params.get("source", "KIS")
            if row is None or params["adjustment_basis"] != row["adjustment_basis"] or source != row["source"]:
                return Result(rowcount=0)
            row.update({k: params[k] for k in ("open", "high", "low", "close", "volume", "collected_at")})
            return Result(rowcount=1)
        raise AssertionError(f"예상하지 못한 SQL: {sql}")


ORIGINAL_COLLECTED = datetime(2026, 10, 30, 18, 28, tzinfo=KST)


def fake_rows():
    return [{"trade_date": r["trade_date"], "open": r["adj_open"], "high": r["adj_high"], "low": r["adj_low"],
             "close": r["adj_close"], "volume": r["adj_volume"], "adjustment_basis": BASIS, "source": "KIS",
             "collected_at": ORIGINAL_COLLECTED} for r in db_rows()]


def test_apply_updates_in_one_transaction_with_backup_and_verification(tmp_path):
    plan = plan_047400()
    db = FakeDB(fake_rows())
    result = rs.apply_plan(db.begin, plan, symbol="047400", confirm=plan["plan_sha256"], backup_dir=tmp_path,
                           now=NOW, text=lambda s: s)
    assert result["updated_rows"] == 4 and result["verified_in_transaction"]
    assert db.commits == 1 and db.rollbacks == 0
    assert rs.canonical_rows(list(db.adjusted.values())) == plan["new_rows"]
    backup = json.loads(open(result["backup_path"], encoding="utf-8").read())
    assert backup["table"] == "adjusted_prices_daily" and backup["row_count"] == 4
    assert backup["rows"][0]["close"] == "746.00"  # 갱신 전 원본
    assert set(db.statements) == {rs.SELECT_FOR_UPDATE_SQL, rs.UPDATE_SQL}


def test_apply_failure_rolls_back_everything(tmp_path):
    plan = plan_047400()
    db = FakeDB(fake_rows(), fail_on_update=2)
    before = copy.deepcopy(db.adjusted)
    with pytest.raises(rs.ApplyVerificationError):
        rs.apply_plan(db.begin, plan, symbol="047400", confirm=plan["plan_sha256"], backup_dir=tmp_path, now=NOW,
                      text=lambda s: s)
    assert db.adjusted == before and db.rollbacks == 1 and db.commits == 0


def test_apply_refuses_when_db_changed_after_plan(tmp_path):
    plan = plan_047400()
    rows = fake_rows()
    rows[0]["close"] = Decimal(747)
    db = FakeDB(rows)
    with pytest.raises(rs.StalePlan):
        rs.apply_plan(db.begin, plan, symbol="047400", confirm=plan["plan_sha256"], backup_dir=tmp_path, now=NOW,
                      text=lambda s: s)
    assert rs.UPDATE_SQL not in db.statements and list(tmp_path.iterdir()) == []


def test_post_update_verification_mismatch_rolls_back(tmp_path, monkeypatch):
    plan = plan_047400()
    db = FakeDB(fake_rows())
    original = db.execute

    def drifting(sql, params):
        result = original(sql, params)
        if sql is rs.UPDATE_SQL and params["trade_date"] == date(2026, 11, 12):
            db.adjusted[params["trade_date"]]["close"] = Decimal(1)  # 다른 값이 들어간 상황
        return result

    db.execute = drifting
    with pytest.raises(rs.ApplyVerificationError):
        rs.apply_plan(db.begin, plan, symbol="047400", confirm=plan["plan_sha256"], backup_dir=tmp_path, now=NOW,
                      text=lambda s: s)
    assert rs.canonical_rows(list(db.adjusted.values())) == rs.canonical_rows(fake_rows())


def test_backup_failure_prevents_any_update(tmp_path):
    plan = plan_047400()
    db = FakeDB(fake_rows())
    not_a_dir = tmp_path / "file"
    not_a_dir.write_text("x")
    with pytest.raises(OSError):
        rs.apply_plan(db.begin, plan, symbol="047400", confirm=plan["plan_sha256"], backup_dir=not_a_dir, now=NOW,
                      text=lambda s: s)
    assert rs.UPDATE_SQL not in db.statements and db.rollbacks == 1
    assert rs.canonical_rows(list(db.adjusted.values())) == rs.canonical_rows(fake_rows())


def test_apply_sets_collected_at_to_kis_fetch_time(tmp_path):
    plan = plan_047400()
    db = FakeDB(fake_rows())
    rs.apply_plan(db.begin, plan, symbol="047400", confirm=plan["plan_sha256"], backup_dir=tmp_path, now=NOW,
                  text=lambda s: s)
    assert {r["collected_at"] for r in db.adjusted.values()} == {NOW}


# ---------------------------------------------------------------- 백업·복원


def _applied(tmp_path):
    plan = plan_047400()
    db = FakeDB(fake_rows())
    result = rs.apply_plan(db.begin, plan, symbol="047400", confirm=plan["plan_sha256"], backup_dir=tmp_path,
                           now=NOW, text=lambda s: s)
    return db, rs.load_backup(result["backup_path"]), result["backup_path"]


def _current(db):
    return [dict(v) for _, v in sorted(db.adjusted.items())]


def test_backup_contains_restore_fields_and_integrity_hashes(tmp_path):
    _, backup, _ = _applied(tmp_path)
    assert backup["schema_version"] == 2 and backup["table"] == "adjusted_prices_daily"
    row = backup["rows"][0]
    assert row["source"] == "KIS" and row["adjustment_basis"] == BASIS
    assert datetime.fromisoformat(row["collected_at"]) == ORIGINAL_COLLECTED
    assert backup["expected_after_fingerprint"] == rs.fingerprint(plan_047400()["new_rows"])


@pytest.mark.parametrize("tamper", [
    lambda b: b["rows"][0].update(close="1.00"),
    lambda b: b.update(table="prices_daily"),
    lambda b: b.update(row_count=3),
])
def test_tampered_backup_is_rejected(tmp_path, tamper):
    _, _, path = _applied(tmp_path)
    payload = json.loads(open(path, encoding="utf-8").read())
    tamper(payload)
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(rs.BackupInvalid):
        rs.load_backup(bad)


def test_restore_round_trip_returns_original_values_and_collected_at(tmp_path):
    db, backup, _ = _applied(tmp_path)
    preview = rs.plan_restore(backup, _current(db), symbol="047400")
    assert preview["status"] == "ready" and preview["rows_to_restore"] == 3
    result = rs.apply_restore(db.begin, backup, symbol="047400", confirm=preview["restore_sha256"],
                              backup_dir=tmp_path / "pre", now=NOW + timedelta(minutes=5), text=lambda s: s)
    assert result["restored_rows"] == 4
    assert rs.canonical_rows(_current(db)) == rs.canonical_rows(fake_rows())
    assert {r["collected_at"] for r in db.adjusted.values()} == {ORIGINAL_COLLECTED}
    pre = rs.load_backup(result["pre_restore_backup"])  # 복원 직전 값도 남는다
    assert pre["reason"] == "pre-restore" and pre["rows_fingerprint"] == backup["expected_after_fingerprint"]
    assert rs.plan_restore(backup, _current(db), symbol="047400")["status"] == "already_restored"


def test_restore_is_blocked_when_db_changed_after_apply(tmp_path):
    db, backup, _ = _applied(tmp_path)
    db.adjusted[date(2026, 11, 13)]["close"] = Decimal(3800)
    assert rs.plan_restore(backup, _current(db), symbol="047400")["status"] == "blocked"
    extra = _current(db) + [{**_current(db)[-1], "trade_date": date(2026, 11, 16)}]
    assert rs.plan_restore(backup, extra, symbol="047400")["status"] == "blocked"
    assert rs.plan_restore(backup, _current(db), symbol="101140")["status"] == "blocked"


def test_restore_requires_token_matching_current_state(tmp_path):
    db, backup, _ = _applied(tmp_path)
    with pytest.raises(rs.RestoreRejected):
        rs.apply_restore(db.begin, backup, symbol="047400", confirm="0" * 64, backup_dir=tmp_path / "pre", now=NOW,
                         text=lambda s: s)
    assert rs.RESTORE_UPDATE_SQL not in db.statements


def test_restore_failure_rolls_back(tmp_path):
    db, backup, _ = _applied(tmp_path)
    token = rs.plan_restore(backup, _current(db), symbol="047400")["restore_sha256"]
    applied_state = rs.canonical_rows(_current(db))
    db.fail_on_update = len([s for s in db.statements if s is rs.UPDATE_SQL]) + 2  # 복원 3번째 행에서 실패
    with pytest.raises(rs.ApplyVerificationError):
        rs.apply_restore(db.begin, backup, symbol="047400", confirm=token, backup_dir=tmp_path / "pre", now=NOW,
                         text=lambda s: s)
    assert rs.canonical_rows(_current(db)) == applied_state


def test_cli_restore_requires_approved_apply_record(tmp_path, monkeypatch):
    _, backup, path = _applied(tmp_path)
    _state(tmp_path, monkeypatch, ca.HISTORY_RESYNC_CANDIDATE)  # 적용 기록 없음
    assert cli.main(["resync-restore", "--backup", str(path), "--symbol", "047400"]) == 3


def test_cli_restore_dry_run_reads_only(tmp_path, monkeypatch):
    db, backup, path = _applied(tmp_path)
    state_path = tmp_path / "state.json"
    state = rc.empty_state()
    state["symbols"]["047400"] = {"status": ca.NO_ACTION, "applied_plan": backup["plan_sha256"], "backup_path": path}
    rc.save_state(state_path, state)
    monkeypatch.setattr(cli, "STATE_PATH", state_path)
    monkeypatch.setattr(cli, "OUTPUT_ROOT", tmp_path / "out")
    runs = []

    def run_dir(step):
        path = tmp_path / "out" / f"{len(runs)}_{step}"
        path.mkdir(parents=True)
        runs.append(path)
        return path

    monkeypatch.setattr(cli, "new_run_dir", run_dir)

    class Cursor:
        description = [type("C", (), {"name": n})() for n in
                       ("trade_date", "open", "high", "low", "close", "volume", "adjustment_basis", "source", "collected_at")]

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def execute(self, sql, params):
            assert sql.strip().upper().startswith("SELECT") and "FOR UPDATE" not in sql.upper()

        def fetchall(self):
            return [tuple(r[c.name] for c in Cursor.description) for r in _current(db)]

    class Conn:
        def cursor(self):
            return Cursor()

        def rollback(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(cli.price_cli, "connect_read_only", lambda: Conn())
    called = []
    monkeypatch.setattr(cli, "_execute_restore", lambda *a: called.append(1) or 0)
    assert cli.main(["resync-restore", "--backup", str(path), "--symbol", "047400"]) == 0
    assert called == []  # 확인 플래그 없으면 쓰지 않는다
    preview = json.loads((runs[0] / "restore_preview.json").read_text(encoding="utf-8"))
    assert preview["status"] == "ready" and preview["dry_run"] is True
    assert cli.main(["resync-restore", "--backup", str(path), "--symbol", "047400", "--confirm", "x" * 64,
                     "--i-understand-this-writes-db"]) == 3  # 승인 값 불일치
    assert called == []


def test_sql_targets_only_adjusted_prices_daily():
    for sql in rs.SQL_STATEMENTS:
        tables = set(re.findall(r"\b(?:FROM|UPDATE|INTO|JOIN)\s+([a-z_]+)", sql, re.IGNORECASE))
        assert tables == {"adjusted_prices_daily"}
    assert not re.search(r"\b(INSERT|DELETE|TRUNCATE|ALTER|DROP)\b", " ".join(rs.SQL_STATEMENTS), re.IGNORECASE)


# ---------------------------------------------------------------- CLI 차단


def _state(tmp_path, monkeypatch, status):
    path = tmp_path / "state.json"
    state = rc.empty_state()
    if status:
        state["symbols"]["047400"] = {"status": status}
    rc.save_state(path, state)
    monkeypatch.setattr(cli, "STATE_PATH", path)
    monkeypatch.setattr(cli.price_cli, "connect_read_only", lambda: (_ for _ in ()).throw(AssertionError("DB 접속 금지")))


def test_resync_plan_refuses_non_candidate_without_touching_db_or_api(tmp_path, monkeypatch):
    _state(tmp_path, monkeypatch, ca.SOURCE_DISCONTINUITY)
    assert cli.main(["resync-plan", "--symbols", "047400"]) == 3


def test_resync_apply_requires_explicit_write_flag_and_candidate_state(tmp_path, monkeypatch):
    _state(tmp_path, monkeypatch, ca.HISTORY_RESYNC_CANDIDATE)
    plan_path = tmp_path / "plan.json"
    plan = plan_047400()
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    base = ["resync-apply", "--plan", str(plan_path), "--symbol", "047400", "--confirm", plan["plan_sha256"]]
    assert cli.main(base) == 3  # 쓰기 확인 플래그 없음
    _state(tmp_path, monkeypatch, None)
    assert cli.main(base + ["--i-understand-this-writes-db"]) == 3  # 승인 대상(재동기화 후보)이 아님
