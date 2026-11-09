from datetime import date
from types import SimpleNamespace

from pipelines.disclosures.periodic_updates import (
    FIRST_SINCE,
    LOOKBACK_DAYS,
    MAX_BODY_ATTEMPTS,
    UpdateState,
    build_plan,
    make_selector,
    parse_filings,
)
from pipelines.disclosures.run_periodic_updates import body_outcomes


def item(rcept_no, title, stock_code="005930", rcept_dt="20261114", **extra):
    return {"rcept_no": rcept_no, "report_nm": title, "stock_code": stock_code, "corp_code": "00126380",
            "corp_name": "삼성전자", "rcept_dt": rcept_dt, **extra}


def test_parse_filings_keeps_only_periodic_reports():
    items = [
        item("20261114000001", "분기보고서 (2026.09)"),
        item("20261114000002", "[기재정정]사업보고서 (2025.12)"),
        item("20261114000003", "반기보고서 (2026.06)", stock_code="000660"),
        item("20261114000004", "증권발행실적보고서"),
        item("20261114000005", "분기보고서 (2026.09)", stock_code=""),
        item("20261114000006", "분기보고서 (2026.09)", stock_code="999999"),
        item("20261114000001", "분기보고서 (2026.09)"),  # 같은 접수번호가 두 번
    ]
    filings, skipped = parse_filings(items, universe={"005930", "000660"})

    assert [(f.rcept_no, f.kind, f.period_end, f.prefix) for f in filings] == [
        ("20261114000001", "quarterly", "2026-09-30", ""),
        ("20261114000002", "annual", "2025-12-31", "[기재정정]"),
        ("20261114000003", "half", "2026-06-30", ""),
    ]
    assert filings[0].rcept_dt == "2026-11-14"
    assert skipped == {"not_periodic": 1, "no_period": 0, "attachment_only": 0, "before_window": 0,
                       "no_stock_code": 1, "not_in_universe": 1, "duplicates": 1}


def test_attachment_only_and_old_periods_are_skipped():
    filings, skipped = parse_filings([
        item("1", "[첨부추가]반기보고서 (2026.06)"),
        item("2", "[첨부정정]사업보고서 (2025.12)"),
        item("3", "[기재정정]사업보고서 (2023.12)"),
        item("4", "[기재정정]반기보고서 (2026.06)"),
    ], min_period="2024-01-01")
    assert [f.rcept_no for f in filings] == ["4"]
    assert skipped["attachment_only"] == 2 and skipped["before_window"] == 1


def test_non_december_period_uses_month_end():
    filings, _ = parse_filings([item("1", "분기보고서 (2026.08)")])
    assert filings[0].period_end == "2026-08-31"


def test_build_plan_skips_known_and_marks_amendments():
    filings, _ = parse_filings([
        item("A", "분기보고서 (2026.09)"),
        item("B", "[기재정정]사업보고서 (2025.12)"),
        item("C", "반기보고서 (2026.06)"),
    ])
    plan = build_plan(filings, known_rcept_nos={"C"}, existing_slots={("005930", "annual", "2025-12-31"): "0"})

    assert plan.slots == {"005930": {("quarterly", "2026-09-30"), ("annual", "2025-12-31")}}
    assert plan.amended == {("005930", "annual", "2025-12-31")}
    assert plan.known == 1
    summary = plan.to_dict()
    assert summary["new_slots"] == 1 and summary["amended_slots"] == 1


def test_older_filing_than_db_slot_is_known():
    filings, _ = parse_filings([item("20260814000001", "반기보고서 (2026.06)")])
    plan = build_plan(filings, set(), {("005930", "half", "2026-06-30"): "20260920000001"})  # DB에는 정정본
    assert plan.slots == {} and plan.known == 1


def test_selector_keeps_only_planned_slots():
    filings, _ = parse_filings([item("20261114000001", "분기보고서 (2026.09)")])
    plan = build_plan(filings, set(), {})
    company_items = {"A003": [
        {"rcept_no": "20261114000001", "report_nm": "분기보고서 (2026.09)", "rcept_dt": "20261114"},
        {"rcept_no": "20260814000001", "report_nm": "반기보고서 (2026.06)", "rcept_dt": "20260814"},
        {"rcept_no": "20260310000001", "report_nm": "사업보고서 (2025.12)", "rcept_dt": "20260310"},
    ]}
    grouped, missing = make_selector(plan)("005930", "00126380", company_items)

    assert missing == []
    assert list(grouped) == [("quarterly", "2026-09-30")]
    ref = grouped[("quarterly", "2026-09-30")][0]
    assert ref.rcept_no == "20261114000001" and ref.period_label == "3분기"
    assert make_selector(plan)("000660", "x", company_items) == ({}, [])


def test_selector_orders_amendment_first():
    filings, _ = parse_filings([item("20261120000001", "[기재정정]분기보고서 (2026.09)", rcept_dt="20261120")])
    plan = build_plan(filings, set(), {("005930", "quarterly", "2026-09-30"): "20261114000001"})
    company_items = {"A003": [
        {"rcept_no": "20261114000001", "report_nm": "분기보고서 (2026.09)", "rcept_dt": "20261114"},
        {"rcept_no": "20261120000001", "report_nm": "[기재정정]분기보고서 (2026.09)", "rcept_dt": "20261120"},
        {"rcept_no": "20260310000001", "report_nm": "사업보고서 (2025.12)", "rcept_dt": "20260310"},
    ]}
    grouped, _ = make_selector(plan)("005930", "00126380", company_items)
    assert [r.rcept_no for r in grouped[("quarterly", "2026-09-30")]] == ["20261120000001", "20261114000001"]


def test_state_since_and_failures(tmp_path):
    state = UpdateState(tmp_path / "state.json")
    assert state.default_since() == date.fromisoformat(FIRST_SINCE)
    state.data["last_until"] = "2026-11-14"
    assert (date(2026, 11, 14) - state.default_since()).days == LOOKBACK_DAYS

    filings, _ = parse_filings([item("A", "분기보고서 (2026.09)")])
    key = ("005930", "quarterly", "2026-09-30")
    results = [state.record_failure(key, filings, "2026-11-15T02:00:00+09:00", "download: 014") for _ in range(MAX_BODY_ATTEMPTS)]
    assert results == [False] * (MAX_BODY_ATTEMPTS - 1) + [True]
    assert state.handled["A"]["status"] == "gave_up"
    assert state.attempts == {}

    state.add_financials("005930", "2026-09-30", "2026-11-15")
    state.save()
    reloaded = UpdateState(tmp_path / "state.json")
    assert reloaded.pending_financials["005930|2026-09-30"]["refresh"] is True
    assert reloaded.expired_financials(date(2026, 11, 20)) == []
    assert reloaded.expired_financials(date(2026, 12, 1)) == ["005930|2026-09-30"]


def test_body_outcomes_splits_success_and_failure():
    filings, _ = parse_filings([
        item("A", "분기보고서 (2026.09)"),
        item("B", "분기보고서 (2026.09)", stock_code="000660"),
        item("C", "분기보고서 (2026.09)", stock_code="035420"),
        item("D", "[기재정정]사업보고서 (2025.12)", stock_code="035420"),
    ])
    plan = build_plan(filings, set(), {})
    run = SimpleNamespace(
        record={"collected": [
            {"symbol": "005930", "kind": "quarterly", "period_end": "2026-09-30", "rcept_no": "A"},
            {"symbol": "000660", "kind": "quarterly", "period_end": "2026-09-30", "rcept_no": "B"},
        ]},
        failed_items=[
            {"symbol": "000660", "stage": "parse", "reason": "ParseError: x", "period_end": "2026-09-30", "kind": "quarterly", "rcept_no": "B"},
            {"symbol": "035420", "stage": "download", "reason": "014", "period_end": "2026-09-30", "kind": "quarterly", "rcept_no": "C"},
        ],
    )
    ok, failed = body_outcomes(plan, ["000660", "005930", "035420"], run)

    assert list(ok) == [("005930", "quarterly", "2026-09-30")]
    assert failed == {
        ("000660", "quarterly", "2026-09-30"): "parse: ParseError: x",
        ("035420", "quarterly", "2026-09-30"): "download: 014",
        ("035420", "annual", "2025-12-31"): "회사 목록에서 이 슬롯 후보를 찾지 못함",
    }
