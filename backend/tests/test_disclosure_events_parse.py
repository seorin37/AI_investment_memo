import unittest
from pathlib import Path

from pipelines.common.config import REPO_ROOT, load_config
from pipelines.disclosures.events_fields import (
    EventFieldRules,
    extract_correction,
    extract_fields,
    parse_date,
    parse_number,
    parse_unit,
)
from pipelines.disclosures.events_parse import EventParseError, Pair, parse_event_document, parse_event_zip


FIXTURES = Path(__file__).parent / "fixtures" / "events"
CONFIG = load_config(REPO_ROOT / "configs" / "disclosure_events.yaml")
RULES = EventFieldRules.from_config(CONFIG)


def html_doc(rows: str) -> bytes:
    return f"""<html><head><title>테스트</title></head><body><div class="xforms">
    <span class="noprint" style="display:none">숨김</span>
    <table>{rows}</table></div></body></html>""".encode("utf-8")


def v(text):
    return f'<td><span class="xforms_input">{text}</span></td>'


def by_path(event):
    return {pair.path: pair.value for pair in event.pairs}


class GridTest(unittest.TestCase):
    def test_rowspan_labels_carry_down(self):
        event = parse_event_document(html_doc(
            '<tr><td>1. 배당구분</td>' + v("분기배당") + '</tr>'
            '<tr><td rowspan="2">3. 1주당 배당금(원)</td><td>보통주식</td>' + v("160") + '</tr>'
            '<tr><td>종류주식</td>' + v("-") + '</tr>'
        ))
        self.assertEqual(event.doc_format, "html")
        self.assertEqual(by_path(event), {
            "1. 배당구분": "분기배당",
            "3. 1주당 배당금(원) > 보통주식": "160",
            "3. 1주당 배당금(원) > 종류주식": "-",
        })
        self.assertNotIn("숨김", event.text)

    def test_two_dimensional_table_uses_column_headers(self):
        event = parse_event_document(html_doc(
            '<tr><td colspan="4">1. 연결실적내용</td>' + v("단위 : 백만원") + '</tr>'
            '<tr><td colspan="2" rowspan="2">구분</td><td>당기실적</td><td>전기실적</td></tr>'
            '<tr>' + v("('26.3Q)") + v("('26.2Q)") + '</tr>'
            '<tr><td rowspan="2">매출액</td><td>당해실적</td>' + v("1,877,789") + v("1,576,998") + '</tr>'
            '<tr><td>누계실적</td>' + v("4,831,339") + '<td>-</td></tr>'
        ))
        paths = by_path(event)
        self.assertEqual(paths["매출액 > 당해실적 > 당기실적"], "1,877,789")
        self.assertEqual(paths["매출액 > 당해실적 > 전기실적"], "1,576,998")
        self.assertEqual(paths["매출액 > 누계실적"], "4,831,339")  # 값이 하나뿐인 행은 열 제목을 붙이지 않는다

    def test_full_width_note_uses_label_above_and_duplicates_are_numbered(self):
        event = parse_event_document(html_doc(
            '<tr><td>당기실적</td>' + v("2026-07-01") + '<td>~</td>' + v("2026-09-30") + '</tr>'
            '<tr><td colspan="4">9. 기타 투자판단과 관련한 중요사항</td></tr>'
            '<tr><td colspan="4"><span class="xforms_input">본 자료는 잠정치입니다.</span></td></tr>'
        ))
        self.assertEqual(by_path(event), {
            "당기실적": "2026-07-01",
            "당기실적#2": "2026-09-30",
            "9. 기타 투자판단과 관련한 중요사항": "본 자료는 잠정치입니다.",
        })

    def test_dart_xml_te_cells_with_acode(self):
        xml = """<?xml version="1.0" encoding="utf-8"?>
<DOCUMENT><DOCUMENT-NAME ACODE="11332">주요사항보고서(자기주식 취득 결정)</DOCUMENT-NAME><BODY>
<TABLE><TBODY>
<TR><TD ROWSPAN="2">1. 취득예정주식(주)</TD><TD>보통주식</TD><TE ACODE="ACQ_OSTK">150,000</TE></TR>
<TR><TD>기타주식</TD><TE ACODE="ACQ_ESTK">-</TE></TR>
<TR><TD COLSPAN="2">5. 취득목적</TD><TE ACODE="ACQ_PPS">주주가치 제고 &amp; 주가 안정</TE></TR>
</TBODY></TABLE></BODY></DOCUMENT>""".encode("utf-8")
        event = parse_event_document(xml)
        self.assertEqual(event.doc_format, "xml")
        self.assertEqual(event.document_title, "주요사항보고서(자기주식 취득 결정)")
        self.assertEqual(
            [(p.path, p.value, p.acode) for p in event.pairs],
            [
                ("1. 취득예정주식(주) > 보통주식", "150,000", "ACQ_OSTK"),
                ("1. 취득예정주식(주) > 기타주식", "-", "ACQ_ESTK"),
                ("5. 취득목적", "주주가치 제고 & 주가 안정", "ACQ_PPS"),
            ],
        )

    def test_cp949_html_is_decoded(self):
        raw = "<html><body><table><tr><td>1. 배당구분</td><td><span class=\"xforms_input\">결산배당</span></td></tr></table></body></html>".encode("cp949")
        self.assertEqual(by_path(parse_event_document(raw)), {"1. 배당구분": "결산배당"})

    def test_table_without_value_markers_falls_back_to_rightmost_cell(self):
        event = parse_event_document(html_doc("<tr><td>1. 취득목적</td><td>주주가치 제고</td></tr>"))
        self.assertEqual(event.doc_format, "html_plain")
        self.assertEqual(by_path(event), {"1. 취득목적": "주주가치 제고"})

    def test_document_without_any_values_fails(self):
        with self.assertRaises(EventParseError):
            parse_event_document(html_doc("<tr><td>제목만 있는 행</td></tr>"))
        with self.assertRaises(EventParseError):
            parse_event_document("<html><body><p>표 없음</p></body></html>".encode("utf-8"))


class ConvertTest(unittest.TestCase):
    def test_numbers(self):
        self.assertEqual(parse_number("1,877,789"), 1877789)
        self.assertEqual(parse_number("△2,137"), -2137)
        self.assertEqual(parse_number("(2,137)"), -2137)
        self.assertEqual(parse_number("-2,137"), -2137)
        self.assertEqual(parse_number("19.07"), 19.07)
        self.assertIsNone(parse_number("-"))
        with self.assertRaises(ValueError):
            parse_number("약 84.4조원")

    def test_dates(self):
        self.assertEqual(parse_date("2026-09-30"), "2026-09-30")
        self.assertEqual(parse_date("2026년 10월 23일"), "2026-10-23")
        self.assertEqual(parse_date("2026.1.5"), "2026-01-05")
        self.assertIsNone(parse_date("-"))
        with self.assertRaises(ValueError):
            parse_date("미정")

    def test_units(self):
        self.assertEqual(parse_unit("단위 : 백만원, %"), 10**6)
        self.assertEqual(parse_unit("(단위 : 억원)"), 10**8)
        self.assertEqual(parse_unit("단위: 십억원"), 10**9)
        self.assertEqual(parse_unit("단위 : 원"), 1)
        self.assertIsNone(parse_unit("단위 : %"))


class RulesTest(unittest.TestCase):
    def rules(self, spec):
        return EventFieldRules.from_config({"fields": {"t": spec}})

    def test_required_alternatives_and_partial(self):
        rules = self.rules({"required": ["a|b", "c"], "rules": {
            "a": {"path": "^가$", "type": "int"}, "b": {"path": "^나$"}, "c": {"path": "^다$", "type": "date"},
        }})
        ok = extract_fields("t", [Pair("나", "있음"), Pair("다", "2026-01-02")], rules)
        self.assertEqual((ok.parse_status, ok.missing), ("ok", []))
        bad = extract_fields("t", [Pair("가", "숫자아님"), Pair("다", "-")], rules)
        self.assertEqual(bad.parse_status, "partial")
        self.assertEqual(bad.missing, ["a|b", "c"])
        self.assertEqual(len(bad.errors), 1)

    def test_krw_scale_and_acode_priority(self):
        rules = self.rules({"rules": {
            "unit": {"path": "실적내용$", "type": "unit"},
            "revenue": {"path": "^매출액$", "type": "krw", "scale": "unit"},
            "shares": {"acode": "ACQ_OSTK", "path": "^주식수$", "type": "int"},
        }})
        result = extract_fields("t", [
            Pair("매출액", "15,755"), Pair("1. 연결실적내용", "단위 : 억원, %"),
            Pair("주식수", "1"), Pair("다른 경로", "150,000", acode="ACQ_OSTK"),
        ], rules)
        self.assertEqual(result.fields, {"unit": 10**8, "revenue": 1_575_500_000_000, "shares": 150000})

    def test_number_type_keeps_decimals_only_when_needed(self):
        rules = self.rules({"rules": {"dps": {"path": "^배당$", "type": "number"}}})
        self.assertEqual(extract_fields("t", [Pair("배당", "630.67")], rules).fields, {"dps": 630.67})
        whole = extract_fields("t", [Pair("배당", "1,165")], rules).fields["dps"]
        self.assertEqual((whole, type(whole)), (1165, int))

    def test_monthly_operating_report_is_partial_with_note(self):
        # 현대차·기아 월간 판매 공시: 잠정실적 양식이지만 매출·영업이익 칸은 비우고 판매대수를 적는다
        def pairs(start, end, revenue="-"):
            return [Pair("1. 실적내용", "단위 : 백만원, %"), Pair("당기실적", start), Pair("당기실적#2", end),
                    Pair("매출액 > 당해실적 > 당기실적", revenue), Pair("영업이익 > 당해실적 > 당기실적", "")]
        monthly = extract_fields("prelim_earnings", pairs("2026-10-01", "2026-10-31"), RULES)
        # 상태는 사실대로 partial, 사유만 붙는다 (ok는 늘 "필수 값이 다 있음")
        self.assertEqual((monthly.parse_status, monthly.note, monthly.missing), ("partial", "monthly_operating", ["revenue|op_income"]))
        self.assertEqual((monthly.fields["note"], monthly.fields["period_kind"]), ("monthly_operating", "month"))
        # 매출을 적은 월간 공시도 period_kind로 분기 실적과 구분된다
        monthly_with_revenue = extract_fields("prelim_earnings", pairs("2026-10-01", "2026-10-31", "1,000"), RULES)
        self.assertEqual((monthly_with_revenue.parse_status, monthly_with_revenue.fields["period_kind"]), ("ok", "month"))
        self.assertNotIn("note", monthly_with_revenue.fields)
        # 분기 잠정실적에서 빠지면 사유 없이 partial (검토 대상)
        quarterly = extract_fields("prelim_earnings", pairs("2026-07-01", "2026-09-30"), RULES)
        self.assertEqual((quarterly.parse_status, quarterly.note, quarterly.fields["period_kind"]), ("partial", None, "quarter"))

    def test_period_kind(self):
        from pipelines.disclosures.events_fields import period_kind
        self.assertEqual(period_kind("2026-01-01", "2026-06-30"), "half")
        self.assertEqual(period_kind("2026-01-01", "2026-12-31"), "year")
        self.assertEqual(period_kind("2026-01-01", "2026-10-31"), "other")
        self.assertIsNone(period_kind(None, "2026-10-31"))

    def test_withheld_amount_is_partial_with_note(self):
        # 아시아나항공 신규시설투자: 투자금액 공시유보
        base = [Pair("1. 투자구분", "신규시설투자"), Pair("2. 투자내역 > 자기자본(원)", "1,029,953,555,000")]
        withheld = extract_fields("facility_investment", base + [Pair("6. 공시유보 관련내용 > 유보사유", "경영상 비밀유지")], RULES)
        self.assertEqual((withheld.parse_status, withheld.note), ("partial", "amount_withheld"))
        not_withheld = extract_fields("facility_investment", base + [Pair("6. 공시유보 관련내용 > 유보사유", "-")], RULES)
        self.assertEqual((not_withheld.parse_status, not_withheld.note), ("partial", None))
        # 유보 대상이 정해진 종류에만 쓴다 — 다른 종류에서 빠진 값은 유보 사유가 있어도 사유를 붙이지 않는다
        other = extract_fields("dividend", [Pair("6. 공시유보 관련내용 > 유보사유", "경영상 비밀유지")], RULES)
        self.assertEqual((other.parse_status, other.note), ("partial", None))

    def test_type_without_rules_is_ok(self):
        result = extract_fields("value_up", [Pair("x", "y")], RULES)
        self.assertEqual((result.fields, result.parse_status), ({}, "ok"))

    def test_bad_config(self):
        for spec in (
            {"rules": {"a": {"type": "int"}}},  # path·acode 없음
            {"rules": {"a": {"path": "x", "type": "money"}}},
            {"rules": {"a": {"path": "x", "type": "krw"}}},  # scale 없음
            {"rules": {"a": {"path": "x", "type": "krw", "scale": "unit"}}},  # 없는 scale 필드
            {"required": ["zzz"], "rules": {"a": {"path": "x"}}},
        ):
            with self.subTest(spec=spec), self.assertRaises(ValueError):
                self.rules(spec)


class RealDocumentTest(unittest.TestCase):
    """2026-10-21~29 실제 공시 원문 8건 (tests/fixtures/events)."""

    def extract(self, event_type, name):
        rcept_no = name.split("_")[1]
        event = parse_event_zip(FIXTURES / f"{name}.zip", rcept_no)
        return event, extract_fields(event_type, event.pairs, RULES)

    def assertFields(self, result, expected):
        self.assertEqual(result.parse_status, "ok", (result.missing, result.errors))
        self.assertEqual({key: result.fields.get(key) for key in expected}, expected)

    def test_prelim_earnings(self):
        _, result = self.extract("prelim_earnings", "010120_20261021800151")  # LS ELECTRIC 3Q
        self.assertFields(result, {
            "unit": 10**6,
            "period_start": "2026-07-01",
            "period_end": "2026-09-30",
            "revenue": 1_877_789_000_000,
            "revenue_prev_q": 1_576_998_000_000,
            "revenue_prev_y": 1_216_295_000_000,
            "op_income": 233_543_000_000,
            "op_income_prev_y": 100_791_000_000,
            "net_income_owners": 141_244_000_000,
        })
        self.assertEqual(result.correction, {})

    def test_prelim_earnings_correction_uses_corrected_values(self):
        _, result = self.extract("prelim_earnings", "068270_20261027800047")  # 셀트리온 [기재정정], 억원 단위
        self.assertFields(result, {"unit": 10**8, "revenue": 1_575_500_000_000, "op_income": 525_300_000_000})
        self.assertEqual(result.correction["date"], "2026-10-26")
        self.assertEqual(result.correction["original_date"], "2026-10-12")
        self.assertIn("정정", result.correction["reason"])

    def test_correction_with_swapped_cells(self):
        # 한화오션 자회사 정정공시: 1번(서류명) 칸에 날짜, 2번(제출일) 칸에 서류명을 적었다
        swapped = [
            Pair("정정일자", "2026-10-30"),
            Pair("1. 정정관련 공시서류", "2026-09-18"),
            Pair("2. 정정관련 공시서류제출일", "타법인 주식 및 출자증권 처분결정(종속회사의 주요경영사항)"),
            Pair("3. 정정사유", "처분예정일자 변경"),
        ]
        self.assertEqual(extract_correction(swapped), {
            "date": "2026-10-30",
            "original_title": "타법인 주식 및 출자증권 처분결정(종속회사의 주요경영사항)",
            "original_date": "2026-09-18",
            "reason": "처분예정일자 변경",
        })

    def test_correction_with_non_date_original_is_not_used(self):
        pairs = [Pair("1. 정정관련 공시서류", "회사합병결정"), Pair("2. 정정관련 공시서류제출일", "원공시 참조")]
        self.assertEqual(extract_correction(pairs), {"original_title": "회사합병결정", "original_date_raw": "원공시 참조"})
        self.assertEqual(extract_correction([Pair("2. 정정관련 공시서류제출일", "-")]), {"original_date": None})

    def test_dividend(self):
        _, result = self.extract("dividend", "033920_20261022800228")  # 무학
        self.assertFields(result, {
            "dividend_kind": "분기배당",
            "dps_common": 160,
            "yield_common": 2.14,
            "total_krw": 4_388_307_840,
            "record_date": "2026-09-30",
            "pay_date": None,
            "board_date": "2026-10-22",
        })

    def test_treasury_buy_xml(self):
        event, result = self.extract("treasury_buy", "023150_20261022000102")  # MH에탄올
        self.assertEqual(event.doc_format, "xml")
        self.assertFields(result, {
            "shares_common": 150000,
            "amount_common": 329_250_000,
            "period_start": "2026-10-23",
            "period_end": "2027-01-22",
            "purpose": "주가 안정 및 주주가치 제고",
            "decision_date": "2026-10-22",
        })

    def test_treasury_trust_cancel(self):
        _, result = self.extract("treasury_sell", "483650_20261027000092")  # 달바글로벌 신탁계약 해지
        self.assertFields(result, {
            "trust_amount_before": 15_000_000_000,
            "cancel_shares_common": 90807,
            "purpose": "자기주식 취득 완료에 따른 중도 해지",
        })

    def test_supply_contract(self):
        _, result = self.extract("supply_contract", "051600_20261021800137")  # 한전KPS
        self.assertFields(result, {
            "contract_name": "한빛2호기 증기발생기 전열관 정비 용역",
            "contract_amount": 83_613_252_000,
            "revenue_pct": 5.3,
            "counterparty": "한국수력원자력(주)",
            "start_date": "2026-10-26",
            "end_date": "2027-12-31",
        })

    def test_rumor_clarification(self):
        _, result = self.extract("rumor_clarification", "000660_20261023800002")  # SK하이닉스
        self.assertFields(result, {"media": "한국경제", "rumor_date": "2026-08-05"})
        self.assertIn("솔리다임", result.fields["rumor"])
        self.assertIn("본 공시는", result.fields["clarification"])

    def test_subsidiary_report_without_value_markers_uses_rightmost_cell(self):
        # SK스퀘어가 올린 자회사 SK하이닉스의 자기주식 취득 결정: 값 칸 표시 없는 일반 HTML
        event, result = self.extract("treasury_buy", "402340_20261028800051")
        self.assertEqual(event.doc_format, "html_plain")
        self.assertTrue(event.warnings)
        self.assertFields(result, {
            "shares_common": 14_920_000,
            "amount_common": 20_007_720_000_000,
            "period_start": "2026-10-29",
            "period_end": "2027-01-28",
            "decision_date": "2026-10-28",
        })

    def test_supply_contract_termination(self):
        _, result = self.extract("supply_contract", "023350_20261021800352")  # 한국종합기술 계약 해지
        self.assertFields(result, {
            "contract_name": "경주 나산에너지 폐기물 유화사업",
            "contract_amount": 31_000_000_000,
            "revenue_pct": 7.77,
            "terminate_date": "2026-10-21",
        })
        self.assertIn("PF", result.fields["terminate_reason"])

    def test_business_plan(self):
        _, result = self.extract("business_plan", "005930_20261029800102")  # 삼성전자 2026 시설투자
        self.assertFields(result, {"plan": "2026년 시설투자 계획", "start_date": "2026-01-01", "end_date": "2026-12-31"})
        self.assertIn("84.4조원", result.fields["investment"])


if __name__ == "__main__":
    unittest.main()
