from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from pipelines.market import adjusted_recheck as rc
from pipelines.market import corporate_actions as ca
from scripts import adjusted_price_manager as cli

KST = timezone(timedelta(hours=9))
NOW = datetime(2026, 11, 16, 14, 30, tzinfo=KST)


def kis_raw(day: str, price, volume=0):
    p = str(price)
    return {"stck_bsop_date": day.replace("-", ""), "stck_oprc": p, "stck_hgpr": p, "stck_lwpr": p, "stck_clpr": p,
            "acml_vol": str(volume), "acml_tr_pbmn": "0"}


def db_row(symbol, day, raw, adj, volume=0, adj_volume=None):
    return {"symbol": symbol, "trade_date": date.fromisoformat(day), "raw_close": Decimal(str(raw)), "raw_volume": volume,
            "adj_open": Decimal(str(adj)), "adj_high": Decimal(str(adj)), "adj_low": Decimal(str(adj)),
            "adj_close": Decimal(str(adj)), "adj_volume": volume if adj_volume is None else adj_volume,
            "adjustment_basis": "KIS_FID_ORG_ADJ_PRC_0_V1"}


def kis_rows(symbol, pairs):
    return rc.rows_from_pages(symbol, [[kis_raw(d, p, v) for d, p, v in pairs]], date(2000, 1, 1), date(2100, 1, 1))[0]


DAYS_047400 = ["2026-11-09", "2026-11-10", "2026-11-11", "2026-11-12", "2026-11-13"]


# ---------------------------------------------------------------- 분류


def test_047400_window_is_history_resync_candidate():
    db = [db_row("047400", d, 746, 746) for d in DAYS_047400[:-1]] + [db_row("047400", DAYS_047400[-1], 746, 3730)]
    kis = kis_rows("047400", [(d, 3730, 0) for d in DAYS_047400])
    result = rc.compare_window("047400", date(2026, 11, 9), date(2026, 11, 13), db, kis)
    assert result["status"] == ca.HISTORY_RESYNC_CANDIDATE
    assert result["changed_dates"] == DAYS_047400[:-1]
    assert result["kis_ratio_levels"] == [5.0] and result["db_ratio_levels"] == [1.0, 5.0]
    assert result["kis_discontinuities"] == [] and result["db_discontinuities"]


def test_101140_reproduced_discontinuity_is_source_discontinuity():
    days = ["2024-11-11", "2024-11-12", "2024-11-13", "2024-11-14"]
    adj = [585, 585, 11700, 11700]
    db = [db_row("101140", d, 9340, a) for d, a in zip(days, adj)]
    kis = kis_rows("101140", [(d, a, 0) for d, a in zip(days, adj)])
    result = rc.compare_window("101140", date(2024, 11, 11), date(2024, 11, 14), db, kis)
    assert result["status"] == ca.SOURCE_DISCONTINUITY
    assert result["changed_dates"] == []
    assert result["kis_discontinuities"][0]["trade_date"] == "2024-11-13"


def test_unchanged_continuous_history_is_no_action():
    days = ["2026-05-06", "2026-05-07", "2026-05-08"]
    db = [db_row("000001", d, r, a, 100, 100) for d, r, a in zip(days, [50000, 50500, 10200], [10000, 10100, 10200])]
    kis = kis_rows("000001", [(d, a, 100) for d, a in zip(days, [10000, 10100, 10200])])
    result = rc.compare_window("000001", date(2026, 5, 6), date(2026, 5, 8), db, kis)
    assert result["status"] == ca.NO_ACTION


def test_missing_kis_date_is_reported_not_substituted():
    db = [db_row("047400", d, 746, 746) for d in DAYS_047400]
    kis = kis_rows("047400", [(d, 3730, 0) for d in DAYS_047400 if d != "2026-11-11"])
    result = rc.compare_window("047400", date(2026, 11, 9), date(2026, 11, 13), db, kis)
    assert result["status"] == ca.REVIEW_REQUIRED
    assert result["missing_in_kis"] == ["2026-11-11"]
    row = [r for r in result["rows"] if r["trade_date"] == "2026-11-11"][0]
    assert row["kis_adj"] is None


def test_error_window_is_review_required():
    db = [db_row("047400", d, 746, 746) for d in DAYS_047400]
    result = rc.compare_window("047400", date(2026, 11, 9), date(2026, 11, 13), db, [], error="KisApiError: x")
    assert result["status"] == ca.REVIEW_REQUIRED


def test_combine_windows_priority():
    assert rc.combine_windows([{"status": ca.NO_ACTION}, {"status": ca.SOURCE_DISCONTINUITY}]) == ca.SOURCE_DISCONTINUITY
    assert rc.combine_windows([{"status": ca.HISTORY_RESYNC_CANDIDATE}, {"status": ca.REVIEW_REQUIRED}]) == ca.REVIEW_REQUIRED


# ---------------------------------------------------------------- 요청 통제


class FakeClient:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def daily_page(self, symbol, start, end, *, adjusted):
        self.calls.append((symbol, start, end, adjusted))
        return self.pages.get(symbol, [])

    def close(self):
        pass

    def request_metrics(self):
        return {"total": len(self.calls)}


def test_budgeted_client_enforces_limit_symbol_and_adjusted_only():
    fake = FakeClient({"047400": [kis_raw("2026-11-13", 3730)]})
    b = rc.BudgetedClient(fake, max_requests=1, allowed_symbols={"047400"}, clock=lambda: NOW)
    with pytest.raises(rc.RecheckNotAllowed):
        b.daily_page("047400", date(2026, 11, 1), date(2026, 11, 13), adjusted=False)
    with pytest.raises(rc.RecheckNotAllowed):
        b.daily_page("005930", date(2026, 11, 1), date(2026, 11, 13), adjusted=True)
    assert b.daily_page("047400", date(2026, 11, 1), date(2026, 11, 13), adjusted=True)
    with pytest.raises(rc.RequestBudgetExceeded):
        b.daily_page("047400", date(2026, 11, 1), date(2026, 11, 13), adjusted=True)
    assert len(fake.calls) == 1 and fake.calls[0][3] is True
    assert b.log[0]["FID_ORG_ADJ_PRC"] == "0" and b.log[0]["output2"]


def test_lazy_client_is_not_created_when_cache_answers():
    created = []
    lazy, close, metrics, log = cli._lazy_budgeted(3, {"047400"}, client_factory=lambda: created.append(1) or FakeClient({}))
    assert metrics()["budget_used"] == 0 and created == [] and log() == []
    close()


def test_fetch_uses_existing_pagination_and_records_raw_pages():
    fake = FakeClient({"047400": [kis_raw(d, 3730) for d in reversed(DAYS_047400)]})
    lazy, close, metrics, log = cli._lazy_budgeted(5, {"047400"}, client_factory=lambda: fake)
    fetch = cli.make_fetch(lazy, clock=lambda: NOW)
    rows, zero, dup = fetch("047400", date(2026, 11, 9), date(2026, 11, 13))
    assert [r["trade_date"].isoformat() for r in rows] == DAYS_047400
    assert zero == 0 and dup == [] and len(log()) == 1 and metrics()["budget_used"] == 1


def test_fetch_refuses_during_collection_windows():
    lazy, *_ = cli._lazy_budgeted(5, {"047400"}, client_factory=lambda: FakeClient({}))
    for moment in (datetime(2026, 11, 17, 8, 0, tzinfo=KST), datetime(2026, 11, 17, 9, 0, tzinfo=KST),
                   datetime(2026, 11, 16, 20, 0, tzinfo=KST), datetime(2026, 11, 16, 18, 30, tzinfo=KST)):
        with pytest.raises(rc.RecheckNotAllowed):
            cli.make_fetch(lazy, clock=lambda m=moment: m)("047400", date(2026, 11, 9), date(2026, 11, 13))
    assert not rc.in_blackout(datetime(2026, 11, 16, 14, 30, tzinfo=KST))


def test_market_lock_not_acquired_means_no_work():
    class Conn:
        def __init__(self):
            self.sql = []

        def execute(self, sql, params=None):
            self.sql.append(sql)
            return self

        def fetchone(self):
            return (False,)

        def rollback(self):
            pass

    conn = Conn()
    with rc.market_lock(conn, 581094001) as acquired:
        assert acquired is False
    assert not any("unlock" in s for s in conn.sql)


# ---------------------------------------------------------------- 캐시·중복 억제


def test_cached_pages_from_previous_experiment_are_reused(tmp_path):
    path = tmp_path / "kis_raw_responses.json"
    path.write_text(json.dumps({"requests": [{
        "symbol": "047400", "FID_INPUT_DATE_1": "20261001", "FID_INPUT_DATE_2": "20261113",
        "requested_at_kst": "2026-11-16T14:06:39+09:00", "received_at_kst": "2026-11-16T14:06:40+09:00",
        "error": None, "output2": [kis_raw(d, 3730) for d in reversed(DAYS_047400)]}]}), encoding="utf-8")
    cache = rc.load_cached_pages([path])
    target = rc.RecheckTarget("047400", [(date(2026, 11, 9), date(2026, 11, 13))], "k", "new")
    db = [db_row("047400", d, 746, 746) for d in DAYS_047400[:-1]] + [db_row("047400", DAYS_047400[-1], 746, 3730)]

    def no_fetch(*_):
        raise AssertionError("캐시로 끝나야 한다")

    result = rc.recheck_symbol(target, load_db_rows=lambda *a: db, fetch=no_fetch, cache=cache,
                               cache_max_age=timedelta(days=7), now=NOW)
    assert result["status"] == ca.HISTORY_RESYNC_CANDIDATE
    assert result["windows"][0]["origin"]["source"] == "cache"
    # 오래된 캐시는 쓰지 않고 API 경로로 간다 (여기서는 그 호출이 실패 → 대체값 없이 검토 대상)
    stale = rc.recheck_symbol(target, load_db_rows=lambda *a: db, fetch=no_fetch, cache=cache,
                              cache_max_age=timedelta(hours=0), now=NOW)
    assert stale["windows"][0]["origin"]["source"] == "kis_api"
    assert stale["status"] == ca.REVIEW_REQUIRED and "캐시로 끝나야 한다" in stale["error"]


def test_truncated_cache_page_is_not_trusted():
    page = rc.CachedPage("047400", date(2020, 1, 1), date(2026, 11, 13), NOW,
                         [kis_raw(f"2026-07-{d:02d}", 1) for d in range(1, 29)] * 4, "x")
    assert len(page.output2) >= 100
    assert not page.covers("047400", date(2020, 1, 1), date(2026, 11, 13))


def item(symbol, findings=(), cands=(), terminal=None, windows=(("2026-11-07", "2026-11-18"),)):
    return {"symbol": symbol, "terminal_status": terminal, "recheck_recommended": True,
            "recheck_windows": [list(w) for w in windows],
            "price_findings": [{"trade_date": d, "assessment": a, "severity": "high"} for d, a in findings],
            "disclosure_candidates": list(cands)}


def test_source_discontinuity_is_not_rechecked_again_with_same_evidence():
    state = rc.empty_state()
    it = item("101140", [("2024-11-13", "adjusted_only_discontinuity")])
    result = {"symbol": "101140", "status": ca.SOURCE_DISCONTINUITY, "evidence_key": rc.evidence_key(it),
              "error": None, "checked_at": NOW.isoformat(), "windows": [{"start": "2024-11-07", "end": "2024-11-18"}]}
    rc.update_state(state, result, result_path="x", now=NOW)
    targets, skipped = rc.select_targets([it], state, now=NOW, max_symbols=5)
    assert targets == [] and skipped == [{"symbol": "101140", "reason": f"suppressed:{ca.SOURCE_DISCONTINUITY}"}]
    # 새 증거(새 가격 이상)가 생기면 다시 본다
    it2 = item("101140", [("2024-11-13", "adjusted_only_discontinuity"), ("2026-12-01", "adjusted_only_discontinuity")])
    targets, _ = rc.select_targets([it2], state, now=NOW, max_symbols=5)
    assert [t.symbol for t in targets] == ["101140"] and targets[0].reason == "new_evidence"


def test_hold_blocks_recheck_even_with_new_evidence_and_survives_state_updates():
    state = rc.empty_state()
    rc.set_hold(state, "047400", reason="기업행동 근거 미확인", now=NOW, by="test")
    it = item("047400", [("2026-11-13", "adjustment_basis_mixed_across_sessions"), ("2026-12-01", "x")])
    targets, skipped = rc.select_targets([it], state, now=NOW, max_symbols=5)
    assert targets == [] and skipped == [{"symbol": "047400", "reason": "on_hold"}]
    # 다른 경로로 상태가 갱신돼도 보류는 남는다
    rc.update_state(state, {"symbol": "047400", "status": ca.HISTORY_RESYNC_CANDIDATE, "evidence_key": "k", "error": None,
                            "checked_at": NOW.isoformat(), "windows": []}, result_path="x", now=NOW)
    assert rc.is_held(state["symbols"]["047400"])


def test_release_hold_requires_approver_and_note_and_keeps_history():
    state = rc.empty_state()
    rc.set_hold(state, "047400", reason="미확인", now=NOW, by="test")
    with pytest.raises(ValueError):
        rc.release_hold(state, "047400", approved_by="", note="x", now=NOW)
    rc.release_hold(state, "047400", approved_by="lead", note="공시 20261120000001 확인", now=NOW)
    entry = state["symbols"]["047400"]
    assert not rc.is_held(entry) and [h["action"] for h in entry["hold_history"]] == ["hold", "release"]
    with pytest.raises(ValueError):
        rc.release_hold(state, "047400", approved_by="lead", note="again", now=NOW)


def test_same_source_discontinuity_is_suppressed_even_if_evidence_key_changes():
    state = rc.empty_state()
    first = item("101140", [("2023-10-23", "zero_volume_price_reset"), ("2024-11-13", "adjusted_only_discontinuity")])
    targets, _ = rc.select_targets([first], state, now=NOW, max_symbols=5)
    result = {"symbol": "101140", "status": ca.SOURCE_DISCONTINUITY, "evidence_key": targets[0].evidence_key,
              "error": None, "checked_at": NOW.isoformat(), "windows": [], "finding_dates": targets[0].finding_dates}
    rc.update_state(state, result, result_path="x", now=NOW)
    # 판정 문자열만 바뀐 같은 날짜들 → 키는 달라도 요청하지 않는다
    relabeled = item("101140", [("2023-10-23", "other_label"), ("2024-11-13", "other_label")])
    assert rc.evidence_key(relabeled) != rc.evidence_key(first)
    targets, skipped = rc.select_targets([relabeled], state, now=NOW, max_symbols=5)
    assert targets == [] and skipped[0]["reason"] == "suppressed:same_source_discontinuity"
    # 새 날짜의 이상이 생기면 다시 본다
    newer = item("101140", [("2024-11-13", "adjusted_only_discontinuity"), ("2026-12-01", "adjusted_only_discontinuity")])
    assert [t.symbol for t in rc.select_targets([newer], state, now=NOW, max_symbols=5)[0]] == ["101140"]


def test_cli_hold_blocks_resync_plan_and_release_needs_explicit_approval(tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    rc.save_state(path, rc.empty_state())
    monkeypatch.setattr(cli, "STATE_PATH", path)
    monkeypatch.setattr(cli.price_cli, "connect_read_only", lambda: (_ for _ in ()).throw(AssertionError("DB 접속 금지")))
    assert cli.main(["hold", "--symbol", "047400", "--reason", "기업행동 근거 미확인"]) == 0
    state = rc.load_state(path)
    state["symbols"]["047400"]["status"] = ca.HISTORY_RESYNC_CANDIDATE
    rc.save_state(path, state)
    assert cli.main(["resync-plan", "--symbols", "047400"]) == 3
    base = ["release-hold", "--symbol", "047400", "--approved-by", "lead", "--note", "근거"]
    assert cli.main(base + ["--confirm-symbol", "047400"]) == 3            # 승인 플래그 없음
    assert cli.main(base + ["--confirm-symbol", "101140", "--i-approve-release"]) == 3  # 종목 재입력 불일치
    assert rc.is_held(rc.load_state(path)["symbols"]["047400"])
    assert cli.main(base + ["--confirm-symbol", "047400", "--i-approve-release"]) == 0
    assert not rc.is_held(rc.load_state(path)["symbols"]["047400"])


def test_new_trigger_date_creates_new_evidence():
    c = {"group_id": "g", "latest_rcept_no": "r", "recheck_recommended": True, "triggered_dates": ["2027-01-08"]}
    c2 = {**c, "triggered_dates": ["2027-01-08", "2027-01-12"]}
    assert rc.evidence_key(item("003520", cands=[c])) != rc.evidence_key(item("003520", cands=[c2]))


def test_error_retry_is_limited():
    key = "k"
    entry = {"evidence_key": key, "status": ca.REVIEW_REQUIRED, "error": "x", "attempts": 1,
             "retry_after": (NOW + timedelta(hours=1)).isoformat()}
    assert rc.should_recheck(entry, key, NOW) == (False, "retry_later")
    assert rc.should_recheck({**entry, "retry_after": (NOW - timedelta(minutes=1)).isoformat()}, key, NOW)[0]
    assert rc.should_recheck({**entry, "attempts": rc.MAX_ERROR_ATTEMPTS}, key, NOW) == (False, "error_attempts_exhausted")


def test_select_targets_limits_and_exclusions():
    items = [item("000300", [("2026-01-14", "raw_break_not_adjusted")]), item("004415", terminal="delisted"),
             item("047400", [("2026-11-13", "x")]), item("011810", [("2026-11-06", "x")])]
    items.append({**item("000001"), "recheck_recommended": False})
    targets, skipped = rc.select_targets(items, rc.empty_state(), now=NOW, max_symbols=2,
                                         latest_db_date=date(2026, 11, 13))
    assert [t.symbol for t in targets] == ["000300", "011810"]
    assert {"symbol": "004415", "reason": "terminal"} in skipped
    assert {"symbol": "047400", "reason": "max_symbols"} in skipped
    assert all(hi <= date(2026, 11, 13) for t in targets for _, hi in t.windows)


def test_budget_exhaustion_propagates_and_leaves_state_untouched():
    state = rc.empty_state()
    target = rc.RecheckTarget("047400", [(date(2026, 11, 9), date(2026, 11, 13))], "k", "new")

    def fetch(*_):
        raise rc.RequestBudgetExceeded("limit")

    with pytest.raises(rc.RequestBudgetExceeded):
        rc.recheck_symbol(target, load_db_rows=lambda *a: [db_row("047400", d, 746, 746) for d in DAYS_047400],
                          fetch=fetch, cache=[], cache_max_age=timedelta(days=7), now=NOW)
    assert state["symbols"] == {}


def test_state_round_trip(tmp_path):
    path = tmp_path / "state.json"
    state = rc.empty_state()
    state["symbols"]["047400"] = {"status": ca.HISTORY_RESYNC_CANDIDATE}
    rc.save_state(path, state)
    assert rc.load_state(path) == state
