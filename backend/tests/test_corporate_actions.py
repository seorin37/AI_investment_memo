from __future__ import annotations

from datetime import date

from pipelines.market import corporate_actions as ca
from pipelines.market.symbol_status import SymbolStatus
from pipelines.updates.preferred import build_map


MERGER_PAIRS = [
    {"path": "1. 주식병합의 내용 > 발행주식총수 > 보통주식(주) > 병합 전", "value": "182,892,731"},
    {"path": "1. 주식병합의 내용 > 발행주식총수 > 보통주식(주) > 병합 후", "value": "36,578,546"},
    {"path": "2. 주식병합의 일정 > 주주총회예정일", "value": "2026-12-11"},
    {"path": "2. 주식병합의 일정 > 신주의 효력발생일", "value": "2027-01-12"},
    {"path": "2. 주식병합의 일정 > 매매거래정지기간 > 시작일", "value": "2027년 01월 08일"},
    {"path": "2. 주식병합의 일정 > 매매거래정지기간 > 종료일", "value": "2027.02.01"},
    {"path": "2. 주식병합의 일정 > 신주권상장예정일", "value": "2027-02-02"},
    {"path": "4. 이사회결의일(결정일)", "value": "2026-11-03"},
]
REDUCTION_PAIRS = [
    {"path": "5. 감자비율 > 보통주식 (%)", "value": "90.00"},
    {"path": "6. 감자기준일", "value": "2026년 12월 15일"},
    {"path": "9. 감자일정 > 매매거래 정지예정기간 > 시작일", "value": "2026년 12월 14일"},
    {"path": "9. 감자일정 > 신주상장예정일", "value": "2027년 01월 11일"},
    {"path": "12. 이사회결의일(결정일)", "value": "2026년 11월 13일"},
]
BONUS_PAIRS = [
    {"path": "4. 신주배정기준일", "value": "2027년 01월 01일"},
    {"path": "5. 1주당 신주배정 주식수 > 보통주식 (주)", "value": "0.1111774"},
    {"path": "8. 신주의 상장 예정일", "value": "2027년 01월 20일"},
    {"path": "9. 이사회결의일(결정일)", "value": "2026년 11월 06일"},
]


def row(rcept_no, symbol="003520", event_type="share_count_change", pairs=MERGER_PAIRS, **kw):
    base = {
        "rcept_no": rcept_no, "symbol": symbol, "title": "주식병합결정", "base_title": "주식병합결정",
        "event_type": event_type, "rcept_dt": date(2026, 11, 3), "is_correction": False,
        "is_subsidiary": False, "corrects": None, "correction": None, "parse_status": "ok",
        "pairs": pairs, "fields": {},
    }
    base.update(kw)
    return base


# ---------------------------------------------------------------- 추출


def test_merger_dates_are_separate_and_ex_rights_not_computed():
    e = ca.extract_event(row("R1"))
    assert e.dates["decision_date"] == ["2026-11-03"]
    assert e.dates["shareholder_meeting_date"] == ["2026-12-11"]
    assert e.dates["effective_date"] == ["2027-01-12"]
    assert e.dates["halt_start"] == ["2027-01-08"] and e.dates["halt_end"] == ["2027-02-01"]
    assert e.dates["listing_date"] == ["2027-02-02"]
    assert e.rcept_dt == "2026-11-03"  # 공시일과 결정일은 따로
    assert "ex_rights_date" not in e.dates and e.ex_rights_status == "unconfirmed"
    assert e.ratios["share_count_ratio_before_after"] == 5.0


def test_reduction_and_bonus_values_come_only_from_source():
    red = ca.extract_event(row("R2", event_type="capital_reduction", pairs=REDUCTION_PAIRS))
    assert red.ratios == {"reduction_pct_common": 90.0}
    assert red.dates["record_date"] == ["2026-12-15"]
    assert "effective_date" not in red.dates  # 원문에 칸이 없으면 만들지 않는다
    bonus = ca.extract_event(row("R3", event_type="bonus_issue", pairs=BONUS_PAIRS))
    assert bonus.ratios == {"bonus_shares_per_share_common": 0.1111774}
    assert bonus.dates["record_date"] == ["2027-01-01"]
    assert bonus.ex_rights_status == "unconfirmed"  # 기준일 하루 전으로 계산하지 않는다


def test_rights_offering_reuses_existing_fields():
    e = ca.extract_event(row("R4", event_type="rights_offering", pairs=[], fields={
        "method": "제3자배정증자", "new_shares_common": 2057613, "shares_before_common": 20491286,
        "pay_date": "2027-04-16", "listing_date": "2027-05-06"}))
    assert e.ratios["method"] == "제3자배정증자"
    assert e.dates["payment_date"] == ["2027-04-16"] and e.dates["listing_date"] == ["2027-05-06"]


# ---------------------------------------------------------------- 정정공시


def test_latest_correction_selected_without_corrects_link():
    original = row("20261001000001", rcept_dt=date(2026, 10, 1))
    corrected_pairs = [p if "효력발생일" not in p["path"] else {**p, "value": "2027-01-19"} for p in MERGER_PAIRS]
    correction = row("20261026000002", title="[기재정정]주식병합결정", is_correction=True, rcept_dt=date(2026, 10, 26),
                     correction={"original_date": "2026-10-01"}, pairs=corrected_pairs)
    groups = ca.group_events([ca.extract_event(original), ca.extract_event(correction)])
    assert len(groups) == 1
    g = groups[0]
    assert g.latest_rcept_no == "20261026000002" and g.resolution == "resolved"
    assert g.schedule_changed and "effective_date" in g.changed_fields
    assert g.latest["dates"]["effective_date"] == ["2027-01-19"]


def test_correction_without_original_in_db_still_groups_by_decision_date():
    a = row("20261020000001", is_correction=True, correction={"original_date": "2026-08-01"})
    b = row("20261110000002", is_correction=True, correction={"original_date": "2026-10-20"})
    groups = ca.group_events([ca.extract_event(a), ca.extract_event(b)])
    assert len(groups) == 1 and groups[0].latest_rcept_no == "20261110000002"
    assert groups[0].original_missing


def test_ambiguous_original_is_left_for_review():
    pairs_a = [p for p in MERGER_PAIRS if "결정일" not in p["path"]]
    a = row("20261001000001", rcept_dt=date(2026, 10, 1), pairs=pairs_a)
    b = row("20261001000002", rcept_dt=date(2026, 10, 1), pairs=pairs_a)
    c = row("20261005000003", is_correction=True, rcept_dt=date(2026, 10, 5), pairs=pairs_a,
            correction={"original_date": "2026-10-01"})
    groups = ca.group_events([ca.extract_event(x) for x in (a, b, c)])
    flagged = [g for g in groups if "20261005000003" in g.members]
    assert flagged[0].resolution == "ambiguous_original"
    cands = ca.build_candidates(groups, as_of=date(2027, 2, 10), names={}, preferred_of_common={}, terminal={})
    amb = [c for c in cands if c.group_id == flagged[0].group_id][0]
    assert amb.status == ca.REVIEW_REQUIRED and amb.recheck_recommended is False


def test_failed_parse_does_not_become_latest():
    ok = row("20261101000001")
    failed = row("20261102000002", is_correction=True, parse_status="failed", pairs=[],
                 correction={"original_date": "2026-11-03"}, rcept_dt=date(2026, 11, 2), corrects="20261101000001")
    g = ca.group_events([ca.extract_event(ok), ca.extract_event(failed)])[0]
    assert g.latest_rcept_no == "20261101000001"


# ---------------------------------------------------------------- 후보


def test_subsidiary_event_is_separated_from_own_action():
    sub = row("S1", symbol="007460", event_type="capital_reduction", pairs=REDUCTION_PAIRS, is_subsidiary=True,
              base_title="감자결정(자회사의주요경영사항)")
    groups = ca.group_events([ca.extract_event(sub)])
    cands = ca.build_candidates(groups, as_of=date(2027, 2, 1), names={}, preferred_of_common={"007460": ["007465"]},
                                terminal={})
    assert len(cands) == 1  # 자회사 공시는 우선주 파생도 하지 않는다
    assert cands[0].status == ca.NO_ACTION and cands[0].recheck_recommended is False


def test_schedule_phase_and_recheck_recommendation():
    groups = ca.group_events([ca.extract_event(row("R1"))])
    upcoming = ca.build_candidates(groups, as_of=date(2026, 12, 20), names={}, preferred_of_common={}, terminal={})[0]
    assert upcoming.schedule_phase == "upcoming" and not upcoming.recheck_recommended
    assert upcoming.recheck_after == "2027-01-08"
    during = ca.build_candidates(groups, as_of=date(2027, 1, 15), names={}, preferred_of_common={}, terminal={})[0]
    assert during.schedule_phase == "in_progress" and during.recheck_recommended
    after = ca.build_candidates(groups, as_of=date(2027, 2, 10), names={}, preferred_of_common={}, terminal={})[0]
    assert after.schedule_phase == "passed" and after.recheck_recommended
    assert after.recheck_window == ["2026-12-29", "2027-02-10"]


def test_preferred_candidate_reuses_mapping_without_ratio_assumption():
    stocks = [("003520", "영진약품", "00123456", "KOSPI"), ("003525", "영진약품우", None, "KOSPI")]
    pref_map, _ = build_map(stocks)
    groups = ca.group_events([ca.extract_event(row("R1"))])
    cands = ca.build_candidates(groups, as_of=date(2027, 2, 10), names={}, terminal={},
                                preferred_of_common=ca.preferred_of_common(pref_map))
    pref = [c for c in cands if c.symbol == "003525"][0]
    assert pref.source == "disclosure_preferred" and pref.derived_from == "003520"
    assert pref.ratios == {}  # 보통주 비율을 옮기지 않는다
    assert pref.recheck_recommended


def test_trading_halt_is_auxiliary_signal_only_when_reason_matches():
    halt = lambda no, reason: row(no, event_type="trading_halt", base_title="매매거래정지및정지해제(중요내용공시)", pairs=[
        {"path": "3. 매매거래정지 일시", "value": "2026-11-06"},
        {"path": "4. 매매거래정지 해제일시", "value": "2026-11-09"},
        {"path": "5. 매매거래정지 사유", "value": reason},
    ], rcept_dt=date(2026, 11, 6))
    groups = ca.group_events([ca.extract_event(halt("H1", "무상증자(10%이상)"))])
    c = ca.build_candidates(groups, as_of=date(2026, 11, 16), names={}, preferred_of_common={}, terminal={})[0]
    assert c.status == ca.REVIEW_REQUIRED and c.recheck_recommended
    groups = ca.group_events([ca.extract_event(halt("H2", "중요내용공시(단일판매공급계약)"))])
    c = ca.build_candidates(groups, as_of=date(2026, 11, 16), names={}, preferred_of_common={}, terminal={})[0]
    assert c.status == ca.NO_ACTION and not c.recheck_recommended


def test_merger_record_date_alone_does_not_trigger_recheck():
    pairs = [
        {"path": "10. 합병일정 > 주주확정기준일", "value": "2026년 11월 10일"},
        {"path": "10. 합병일정 > 합병기일", "value": "2027년 03월 16일"},
        {"path": "10. 합병일정 > 신주의 상장예정일", "value": "2027년 03월 31일"},
        {"path": "4. 합병비율", "value": "(주)진에어 : 에어부산(주) = 1 : 0.2862684"},
        {"path": "14. 이사회결의일(결정일)", "value": "2026년 08월 21일"},
    ]
    groups = ca.group_events([ca.extract_event(row("M1", symbol="298690", event_type="restructuring", pairs=pairs,
                                                    base_title="회사합병결정"))])
    c = ca.build_candidates(groups, as_of=date(2026, 11, 16), names={}, preferred_of_common={}, terminal={})[0]
    assert c.schedule_phase == "in_progress"  # 기준일은 지났지만
    assert not c.recheck_recommended and c.recheck_after == "2027-03-16"
    assert c.ratios["ratio_text"].startswith("(주)진에어")  # 서술형 비율은 숫자로 확정하지 않는다


def test_third_party_rights_offering_is_reviewed_but_not_rechecked():
    e = row("RO1", event_type="rights_offering", pairs=[], fields={"method": "제3자배정증자", "listing_date": "2026-11-10"})
    c = ca.build_candidates(ca.group_events([ca.extract_event(e)]), as_of=date(2026, 11, 16), names={},
                            preferred_of_common={}, terminal={})[0]
    assert c.status == ca.REVIEW_REQUIRED and not c.recheck_recommended


# ---------------------------------------------------------------- 통합


def finding(symbol, day, assessment, severity, prev="2026-11-12"):
    return {"symbol": symbol, "name": None, "trade_date": day, "prev_date": prev, "types": [],
            "severity": severity, "assessment": assessment, "resync_reasons": []}


def test_normal_adjustments_are_not_queued_for_recheck():
    items = ca.integrate([finding("000001", "2026-05-08", "consistent_adjustment", "info")], [], terminal={})
    assert items[0]["status"] == ca.NORMAL_ADJUSTMENT and not items[0]["recheck_recommended"]


def test_resync_states_are_not_assigned_before_kis_recheck():
    items = ca.integrate([finding("047400", "2026-11-13", "adjustment_basis_mixed_across_sessions", "high")], [],
                         terminal={})
    it = items[0]
    assert it["status"] == ca.REVIEW_REQUIRED  # HISTORY_RESYNC_CANDIDATE는 재조회 뒤에만
    assert it["recheck_recommended"] and it["recheck_windows"] == [["2026-11-02", "2026-11-23"]]
    verified = {"047400": {"status": ca.HISTORY_RESYNC_CANDIDATE, "checked_at": "2026-11-16T14:06:39+09:00"}}
    it2 = ca.integrate([finding("047400", "2026-11-13", "adjustment_basis_mixed_across_sessions", "high")], [],
                       terminal={}, verified=verified)[0]
    assert it2["status"] == ca.HISTORY_RESYNC_CANDIDATE


def test_terminal_symbols_are_separated():
    status = SymbolStatus("004415", "delisted", None, "상장폐지", "test")
    items = ca.integrate([finding("004415", "2026-10-28", "raw_break_not_adjusted", "high")], [],
                         terminal={"004415": status})
    assert items[0]["status"] == ca.TERMINAL_EXCLUDED and not items[0]["recheck_recommended"]


def test_disclosure_only_candidate_is_managed_without_price_anomaly():
    groups = ca.group_events([ca.extract_event(row("R1"))])
    cands = ca.build_candidates(groups, as_of=date(2027, 2, 10), names={}, preferred_of_common={}, terminal={})
    items = ca.integrate([], cands, terminal={})
    assert items[0]["symbol"] == "003520" and items[0]["status"] == ca.REVIEW_REQUIRED
    assert items[0]["recheck_recommended"]


def test_merge_windows():
    assert ca.merge_windows([["2026-11-01", "2026-11-10"], ["2026-11-12", "2026-11-20"], ["2026-12-20", "2026-12-25"]]) == [
        ["2026-11-01", "2026-11-20"], ["2026-12-20", "2026-12-25"]]
