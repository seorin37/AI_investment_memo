from __future__ import annotations

import copy
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from pipelines.market import adjusted_history_diagnostics as diag
from pipelines.updates.preferred import build_map
from scripts import diagnose_adjusted_history as cli

T = diag.Thresholds()
KST = timezone(timedelta(hours=9))
parse_date = diag.parse_disclosure_date


DATE_SAMPLES = ["2027-01-12", "2027.01.12", "2027년 01월 12일", "2026년 12월 15일", " - ", "", "해당사항없음"]


def test_disclosure_date_parser_formats():
    assert [parse_date(v) for v in DATE_SAMPLES] == [
        "2027-01-12", "2027-01-12", "2027-01-12", "2026-12-15", None, None, None,
    ]
    with pytest.raises(ValueError):
        parse_date("보통주")


def test_disclosure_date_parser_matches_dart_rule_when_available():
    events_fields = pytest.importorskip("pipelines.disclosures.events_fields", reason="lxml 없는 환경")
    for value in DATE_SAMPLES + ["2027 . 1 . 5"]:
        assert parse_date(value) == events_fields.parse_date(value)


def at(day: str, hour: int = 10) -> datetime:
    return datetime.fromisoformat(day).replace(hour=hour, tzinfo=KST)


def row(symbol, day, raw, adj, volume=1000, collected="2026-10-30"):
    return diag.PriceRow(
        symbol, date.fromisoformat(day),
        None if raw is None else Decimal(str(raw)),
        None if adj is None else Decimal(str(adj)),
        volume, at(collected) if collected else None,
    )


def run(rows, counter=None):
    observations, issues = diag.build_observations(rows, counter)
    return diag.detect(observations, T, {"047400": "유니온머티리얼"}), issues


def by_date(findings):
    return {f.trade_date: f for f in findings}


# ---------------------------------------------------------------- 실제 사례 패턴


def test_047400_ratio_one_to_five_on_new_row_is_resync_candidate():
    rows = [
        row("047400", "2026-11-10", 746, 746, 0, "2026-11-11"),
        row("047400", "2026-11-11", 746, 746, 0, "2026-11-12"),
        row("047400", "2026-11-12", 746, 746, 0, "2026-11-13"),
        row("047400", "2026-11-13", 746, 3730, 0, "2026-11-16"),
    ]
    findings, _ = run(rows)
    assert list(by_date(findings)) == ["2026-11-13"]
    f = findings[0]
    assert {diag.RATIO_JUMP, diag.ADJUSTED_ONLY, diag.ZERO_VOLUME, diag.HISTORY_RESYNC} == set(f.types)
    assert f.resync_reasons == ["ratio_shift_across_collection_sessions"]
    assert (f.prev_ratio, f.ratio) == (1.0, 5.0)
    assert f.raw_return == 0.0 and f.adj_return == 4.0
    assert f.severity == "high"
    assert f.cause_status == "unverified"
    assert f.name == "유니온머티리얼"


def test_101140_twenty_fold_ratio_change_inside_one_backfill():
    rows = [
        row("101140", "2024-11-08", 9340, 585, 0),
        row("101140", "2024-11-11", 9340, 585, 0),
        row("101140", "2024-11-12", 9340, 585, 0),
        row("101140", "2024-11-13", 9340, 11700, 0),
        row("101140", "2024-11-14", 9340, 11700, 0),
    ]
    findings, _ = run(rows)
    f = by_date(findings)["2024-11-13"]
    assert diag.RATIO_JUMP in f.types and diag.ADJUSTED_ONLY in f.types
    assert f.ratio / f.prev_ratio == pytest.approx(20.0, rel=1e-3)
    # 같은 날 받은 백필 안의 단절: 신규 일봉 문제로 분류하지 않는다
    assert "ratio_shift_across_collection_sessions" not in f.resync_reasons
    assert f.severity == "high"
    assert len(findings) == 1


# ---------------------------------------------------------------- 오탐 방지


def test_normal_split_with_continuous_adjusted_price_is_info_only():
    # 5:1 분할: 원시는 -80%, 수정은 연속 (과거 수정가 = 원시/5)
    rows = [
        row("000001", "2026-05-06", 50000, 10000),
        row("000001", "2026-05-07", 50500, 10100),
        row("000001", "2026-05-08", 10200, 10200),
        row("000001", "2026-05-11", 10300, 10300),
    ]
    findings, _ = run(rows)
    assert len(findings) == 1
    f = findings[0]
    assert f.types == [diag.RATIO_JUMP]
    assert f.severity == "info" and f.assessment == "consistent_adjustment"
    assert diag.HISTORY_RESYNC not in f.types


def test_ordinary_limit_move_is_not_flagged():
    rows = [row("000002", "2026-10-01", 1000, 1000), row("000002", "2026-10-02", 1299, 1299)]
    findings, _ = run(rows)
    assert findings == []


def test_zero_volume_base_price_reset_is_flagged_but_nothing_is_modified():
    rows = [
        row("074610", "2025-12-26", 511, 511, 0),
        row("074610", "2025-12-29", 5110, 5110, 0),
    ]
    original = copy.deepcopy(rows)
    findings, _ = run(rows)
    f = findings[0]
    assert diag.ZERO_VOLUME in f.types and diag.HISTORY_RESYNC in f.types
    assert f.resync_reasons == ["unadjusted_raw_break"]
    assert f.assessment == "raw_break_not_adjusted"
    assert "자동 수정 금지" in f.recommended_action
    assert rows == original  # 입력 데이터를 고치지 않는다


def test_terminal_symbol_is_annotated_not_dropped():
    from pipelines.market.symbol_status import load_symbol_statuses

    rows = [row("004415", "2026-10-27", 1233, 1233, 115307), row("004415", "2026-10-28", 803, 803, 183731),
            row("004415", "2026-10-29", 321, 321, 185774)]
    findings, _ = run(rows)
    diag.annotate_symbol_status(findings, load_symbol_statuses())
    assert findings and all(f.symbol_status == "delisted" for f in findings)
    assert diag.summarize(findings, [])["terminal_symbol_findings"] == len(findings)


# ---------------------------------------------------------------- 묶기


def test_one_day_with_several_types_is_one_finding_and_near_findings_share_episode():
    rows = [row("009999", "2026-01-0%d" % d, 1000, 1000) for d in range(1, 6)]
    rows[2] = row("009999", "2026-01-03", 1000, 5000, 0)   # 수정만 급변
    rows[3] = row("009999", "2026-01-04", 1000, 1000, 0)   # 바로 되돌아감
    rows += [row("009999", f"2026-03-{d:02d}", 1000, 1000) for d in range(1, 20)]
    rows.append(row("009999", "2026-03-20", 1000, 3000, 0))
    findings, _ = run(rows)
    assert [f.trade_date for f in findings] == ["2026-01-03", "2026-01-04", "2026-03-20"]
    assert all(len(set(f.types)) == len(f.types) for f in findings)
    episodes = diag.group_episodes(findings, T.episode_rows)
    assert [e["finding_count"] for e in episodes] == [2, 1]
    assert findings[0].episode_id == findings[1].episode_id != findings[2].episode_id
    assert episodes[0]["severity"] == "high"


# ---------------------------------------------------------------- 누락·NULL·0


def test_missing_null_and_zero_prices_are_skipped_and_reported():
    rows = [
        row("000003", "2026-11-02", 1000, 1000),
        row("000003", "2026-11-03", None, 1000),   # 원시 없음
        row("000003", "2026-11-04", 1000, None),   # 수정 없음
        row("000003", "2026-11-05", 0, 1000),      # 0 가격
        row("000003", "2026-11-06", 1010, 1010),
    ]
    counter = cli.SessionCounter()
    observations, issues = diag.build_observations(rows, counter)
    assert issues["raw_missing"] == ["2026-11-03"]
    assert issues["adjusted_missing"] == ["2026-11-04"]
    assert issues["invalid_price"] == ["2026-11-05"]
    # 유효한 직전 행(11/02)과 비교하고, 그 사이 빠진 거래일 3일을 표시한다
    assert len(observations) == 1
    assert observations[0].prev_date == date(2026, 11, 2)
    assert observations[0].missing_sessions == 3
    assert issues["gaps"] == [{"from": "2026-11-02", "to": "2026-11-06", "missing_sessions": 3}]


def test_session_counter_skips_weekends_and_holidays():
    counter = cli.SessionCounter()
    assert counter(date(2026, 11, 6), date(2026, 11, 9)) == 0       # 주말
    assert counter(date(2026, 11, 6), date(2026, 11, 13)) == 4
    assert counter(date(2026, 9, 23), date(2026, 9, 28)) == 0      # 추석 연휴


def test_missing_collected_at_does_not_create_session_resync():
    rows = [row("000004", "2026-11-12", 1000, 1000, collected=None),
            row("000004", "2026-11-13", 1000, 2000, collected=None)]
    findings, _ = run(rows)
    assert diag.ADJUSTED_ONLY in findings[0].types
    assert diag.HISTORY_RESYNC not in findings[0].types


# ---------------------------------------------------------------- 공시 연결


MERGER_PAIRS = [
    {"path": "1. 주식병합의 내용 > 발행주식총수 > 보통주식(주) > 병합 전", "value": "182,892,731"},
    {"path": "1. 주식병합의 내용 > 발행주식총수 > 보통주식(주) > 병합 후", "value": "36,578,546"},
    {"path": "2. 주식병합의 일정 > 신주의 효력발생일", "value": "2027-01-12"},
    {"path": "2. 주식병합의 일정 > 매매거래정지기간 > 시작일", "value": "2027년 01월 08일"},
    {"path": "2. 주식병합의 일정 > 매매거래정지기간 > 종료일", "value": "2027.02.01"},
    {"path": "2. 주식병합의 일정 > 신주권상장예정일", "value": "2027-02-02"},
    {"path": "2. 주식병합의 일정 > 명의개서정지기간 > 시작일", "value": "-"},
    {"path": "4. 이사회결의일(결정일)", "value": "2026-11-03"},
]


def test_key_dates_separate_decision_from_adjustment_dates():
    dates = diag.extract_key_dates(MERGER_PAIRS, parse_date)
    assert dates["decision_date"] == ["2026-11-03"]
    assert dates["effective_date"] == ["2027-01-12"]
    assert dates["halt_start"] == ["2027-01-08"] and dates["halt_end"] == ["2027-02-01"]
    assert dates["listing_date"] == ["2027-02-02"]
    assert diag.share_count_ratio(MERGER_PAIRS) == pytest.approx(5.0, abs=1e-4)


def _event(rcept_no, symbol, rcept_dt, **kw):
    base = {"rcept_no": rcept_no, "symbol": symbol, "title": "주식병합결정", "rcept_dt": date.fromisoformat(rcept_dt),
            "event_type": "share_count_change", "is_subsidiary": False, "is_correction": False,
            "parse_status": "ok", "pairs": MERGER_PAIRS, "is_latest": True}
    base.update(kw)
    return base


def _finding(symbol, day):
    rows = [row(symbol, (date.fromisoformat(day) - timedelta(days=1)).isoformat(), 1000, 1000, 0),
            row(symbol, day, 1000, 5000, 0)]
    return run(rows)[0]


def test_link_prefers_latest_version_and_marks_subsidiary():
    findings = _finding("003520", "2026-11-13")
    events = [
        _event("A1", "003520", "2026-11-03", is_latest=False),                   # 정정본에 밀린 원본
        _event("A2", "003520", "2026-11-05", is_correction=True, title="[기재정정]주식병합결정"),
        _event("A3", "003520", "2026-11-10", is_subsidiary=True, title="감자결정(자회사의주요경영사항)",
               event_type="capital_reduction", pairs=[]),
    ]
    diag.link_disclosures(findings, events, T, coverage_start=date(2026, 10, 21),
                          common_symbol=lambda s: s, parse_date=parse_date)
    linked = findings[0].disclosures
    assert [d["rcept_no"] for d in linked] == ["A2", "A3"]
    assert linked[1]["is_subsidiary"] is True
    assert findings[0].cause_status == "unverified_disclosure_reference"
    assert findings[0].dart_coverage == "covered"


def test_findings_without_disclosure_are_kept_and_old_dates_marked_uncovered():
    findings = _finding("101140", "2024-11-13")
    diag.link_disclosures(findings, [], T, coverage_start=date(2026, 10, 21),
                          common_symbol=lambda s: s, parse_date=parse_date)
    assert len(findings) == 1
    assert findings[0].dart_coverage == "before_coverage"
    assert findings[0].cause_status == "unverified_no_disclosure"


def test_preferred_stock_uses_existing_preferred_mapping_for_disclosures():
    stocks = [("005930", "삼성전자", "00126380", "KOSPI"), ("005935", "삼성전자우", None, "KOSPI")]
    pref_map, _ = build_map(stocks)
    assert pref_map == {"005935": "005930"}
    findings = _finding("005935", "2026-11-13")
    diag.link_disclosures(findings, [_event("B1", "005930", "2026-11-03")], T,
                          coverage_start=date(2026, 10, 21),
                          common_symbol=lambda s: pref_map.get(s, s), parse_date=parse_date)
    assert [d["rcept_no"] for d in findings[0].disclosures] == ["B1"]
    assert findings[0].disclosures[0]["symbol"] == "005930"


# ---------------------------------------------------------------- 출력·읽기 전용


def test_output_never_overwrites(tmp_path):
    now = datetime(2026, 11, 16, 3, 0, tzinfo=timezone.utc)
    out = diag.new_output_dir(tmp_path, now)
    assert out.name == "20261116T120000"
    with pytest.raises(FileExistsError):
        diag.new_output_dir(tmp_path, now)
    findings = _finding("047400", "2026-11-13")
    report = {
        "meta": {"generated_at": now.isoformat(), "read_only_verified": True, "symbols_analyzed": 1,
                 "rows_loaded": 2, "start": None, "end": None, "dart_coverage_start": "2026-10-21"},
        "summary": diag.summarize(findings, diag.group_episodes(findings, 5)),
        "findings": diag.finding_dicts(findings),
    }
    json_path, md_path = diag.write_report(out, report, focus=["047400"])
    assert "047400" in md_path.read_text(encoding="utf-8")
    with pytest.raises(FileExistsError):
        diag.write_report(out, report)


def test_cli_refuses_without_readonly_url():
    with pytest.raises(cli.ReadOnlyRequired):
        cli.connect_read_only({"DATABASE_URL": "postgresql://writer@localhost/x"})


def test_cli_aborts_when_session_is_not_read_only():
    class FakeConn:
        closed = False

        def execute(self, sql):
            assert sql == "SHOW transaction_read_only"
            return self

        def fetchone(self):
            return ("off",)

        def close(self):
            self.closed = True

    conn = FakeConn()
    with pytest.raises(cli.ReadOnlyRequired):
        cli.verify_read_only(conn)
    assert conn.closed


def test_cli_sql_is_select_only():
    for sql in (cli.SYMBOLS_SQL, cli.PRICES_SQL, cli.COVERAGE_SQL, cli.EVENTS_SQL):
        head = sql.strip().split()[0].upper()
        assert head == "SELECT"
        assert not any(word in sql.upper() for word in ("INSERT ", "UPDATE ", "DELETE ", "ALTER ", "DROP "))
