import tempfile
import unittest
from datetime import date
from pathlib import Path

from app import dart_reports
from pipelines.common.config import REPO_ROOT, load_config
from pipelines.disclosures import events_list
from pipelines.disclosures.events_list import EventRules, normalize_title, select_events
from tests.test_dart_reports import FakeResponse, FakeSession


API_KEY = "test-secret-key"
CONFIG = load_config(REPO_ROOT / "configs" / "disclosure_events.yaml")
RULES = EventRules.from_config(CONFIG)
KINDS = dict(CONFIG["list"]["pblntf_types"])


def item(report_nm, rcept_no="20261029000001", ty="I", stock_code="005930", rcept_dt="20261029", rm="유"):
    return {
        "corp_code": "00126380",
        "corp_name": "삼성전자",
        "stock_code": stock_code,
        "corp_cls": "Y",
        "report_nm": report_nm,
        "rcept_no": rcept_no,
        "rcept_dt": rcept_dt,
        "rm": rm,
        "_pblntf_ty": ty,
    }


class NormalizeTitleTest(unittest.TestCase):
    def test_prefix_spaces_and_major_wrapper(self):
        self.assertEqual(
            normalize_title("[기재정정]주요사항보고서(자기주식취득결정) (자회사의 주요경영사항)"),
            ("자기주식취득결정(자회사의주요경영사항)", "[기재정정]"),
        )
        self.assertEqual(normalize_title("연결재무제표기준영업(잠정)실적(공정공시)"), ("연결재무제표기준영업(잠정)실적(공정공시)", ""))
        self.assertEqual(normalize_title("[첨부정정][기재정정]현금ㆍ현물배당결정")[1], "[첨부정정][기재정정]")


class ClassifyTest(unittest.TestCase):
    # 2026-10-29·30·11-03 실제 목록에 나온 보고서명 (정규화 후)
    CASES = {
        "연결재무제표기준영업(잠정)실적(공정공시)": "prelim_earnings",
        "영업(잠정)실적(공정공시)": "prelim_earnings",
        "결산실적공시예고(안내공시)": "earnings_preannounce",
        "영업실적등에대한전망(공정공시)": "earnings_guidance",
        "현금ㆍ현물배당결정": "dividend",
        "부동산투자회사금전배당결정": "dividend",
        "자기주식취득결정": "treasury_buy",
        "자기주식취득신탁계약체결결정": "treasury_buy",
        "자기주식처분결정": "treasury_sell",
        "자기주식취득신탁계약해지결정": "treasury_sell",
        "주식소각결정": "share_cancel",
        "기업가치제고계획예고(안내공시)": "value_up",
        "단일판매ㆍ공급계약체결": "supply_contract",
        "단일판매ㆍ공급계약해지": "supply_contract",
        "신규시설투자등": "facility_investment",
        "타법인주식및출자증권취득결정": "equity_investment",
        "타법인주식및출자증권양수결정": "equity_investment",
        "유형자산양도결정": "asset_deal",
        "장래사업ㆍ경영계획(공정공시)": "business_plan",
        "투자판단관련주요경영사항(파브리병치료제(LAGLA)기술이전계약체결)": "material_event",
        "유상증자결정": "rights_offering",
        "전환사채권발행결정": "hybrid_bond",
        "교환사채권발행결정": "hybrid_bond",
        "회사합병결정": "restructuring",
        "주식교환ㆍ이전결정": "restructuring",
        "주식병합결정": "share_count_change",
        "최대주주변경": "control_change",
        "풍문또는보도에대한해명(미확정)": "rumor_clarification",
        "조회공시요구(현저한시황변동)": "inquiry",
        "투자유의안내(관리종목지정우려예고)": "market_warning",
        "기타시장안내(상장적격성실질심사결과안내)": "market_warning",
        "매매거래정지및정지해제(중요내용공시)": "trading_halt",
        "파산신청": "insolvency",
        "소송등의제기ㆍ신청(경영권분쟁소송)": "lawsuit",
        "기업설명회(IR)개최(안내공시)": "ir",
        # 2026-10-21~11-03 dry-run에서 미분류로 나와 추가한 것
        "연결재무제표기준영업실적등에대한전망(공정공시)": "earnings_guidance",
        "기타경영사항(종속회사의주요경영사항)": "material_event",
        "부동산투자회사부동산처분": "asset_deal",
        "불성실공시법인지정예고": "market_warning",
        "회계처리기준위반에따른검찰고발등조치": "market_warning",
        "기타시장안내(기업심사위원회심의대상제외결정안내)": "market_warning",
        "거래처와의거래중단": "operation_disruption",
        "생산재개(자율공시)": "operation_disruption",
        "중대재해발생": "operation_disruption",
        "감사보고서제출": "audit_report",
    }
    EXCLUDED = [
        "최대주주등소유주식변동신고서",
        "최대주주등소유주식변동신고서(최대주주변경시)",
        "현금ㆍ현물배당을위한주주명부폐쇄(기준일)결정",
        "주주총회소집결의",
        "임시주주총회결과",
        "금전대여결정(자회사의주요경영사항)",
        "자기전환사채만기전취득결정",
        "자기주식취득결과보고서",
        "유상증자또는주식관련사채등의발행결과(자율공시)",
    ]

    def test_known_titles(self):
        for title, expected in self.CASES.items():
            with self.subTest(title=title):
                self.assertEqual(RULES.classify(title)[0], expected)

    def test_excluded_titles(self):
        for title in self.EXCLUDED:
            with self.subTest(title=title):
                self.assertEqual(RULES.classify(title), ("excluded", None))

    def test_unknown_title_is_unclassified(self):
        self.assertEqual(RULES.classify("처음보는공시"), ("unclassified", None))

    def test_dividend_record_date_notice_is_not_dividend(self):
        self.assertNotEqual(RULES.classify("현금ㆍ현물배당을위한주주명부폐쇄(기준일)결정")[0], "dividend")

    def test_duplicate_type_rejected(self):
        bad = {"events": [{"type": "a", "topic": "x", "patterns": ["^a"]}, {"type": "a", "topic": "y", "patterns": ["^b"]}]}
        with self.assertRaises(ValueError):
            EventRules.from_config(bad)


class SelectEventsTest(unittest.TestCase):
    def test_select_and_report(self):
        items = [
            item("현금ㆍ현물배당결정", "20261029000001"),
            item("현금ㆍ현물배당결정", "20261029000001"),  # 같은 접수번호 중복
            item("[기재정정]주요사항보고서(자기주식처분결정)", "20261029000002", ty="B", rm=""),
            item("단일판매ㆍ공급계약체결(자회사의주요경영사항)", "20261029000003"),
            item("최대주주등소유주식변동신고서", "20261029000004"),
            item("처음보는공시", "20261029000005"),
            item("주식소각결정", "20261029000006", stock_code="999999"),
            item("주식소각결정", "20261029000007", stock_code=""),
        ]
        refs, report = select_events(items, RULES, KINDS, universe={"005930"})
        self.assertEqual([r.rcept_no for r in refs], ["20261029000001", "20261029000002", "20261029000003"])
        dividend, treasury, contract = refs
        self.assertEqual((dividend.kind, dividend.event_type, dividend.topic, dividend.rcept_dt), ("other", "dividend", "shareholder_return", "2026-10-29"))
        self.assertEqual((treasury.kind, treasury.event_type, treasury.is_correction), ("major", "treasury_sell", True))
        self.assertTrue(contract.is_subsidiary)
        self.assertFalse(dividend.is_subsidiary)
        self.assertEqual(dividend.source_url, "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20261029000001")
        data = report.to_dict()
        self.assertEqual(data["total_listed"], 7)
        self.assertEqual(data["duplicates"], 1)
        self.assertEqual(data["selected"], 3)
        self.assertEqual(data["corrections_selected"], 1)
        self.assertEqual(data["excluded_titles"], {"최대주주등소유주식변동신고서": 1})
        self.assertEqual(data["unclassified_titles"], {"처음보는공시": 1})
        self.assertEqual(data["not_in_universe"], {"999999": 1})
        self.assertEqual(data["no_stock_code"], 1)
        self.assertEqual(data["by_day"], {"2026-10-29": {"dividend": 1, "treasury_sell": 1, "supply_contract": 1}})

    def test_subsidiary_can_be_skipped(self):
        rules = EventRules.from_config({**CONFIG, "include_subsidiary": False})
        refs, report = select_events([item("주식소각결정(자회사의주요경영사항)")], rules, KINDS)
        self.assertEqual(refs, [])
        self.assertEqual(report.skipped_subsidiary, 1)

    def test_attachment_only_corrections_are_skipped(self):
        # [첨부정정]은 본문이 없어 DART가 014를 준다 → 목록 단계에서 뺀다. [기재정정]은 받는다.
        items = [
            item("[첨부정정]주요사항보고서(회사합병결정)", "1", ty="B"),
            item("[첨부추가]주요사항보고서(회사합병결정)", "2", ty="B"),
            item("[기재정정]주요사항보고서(회사합병결정)", "3", ty="B"),
        ]
        refs, report = select_events(items, RULES, KINDS)
        self.assertEqual([r.rcept_no for r in refs], ["3"])
        self.assertEqual(report.to_dict()["skipped_prefix"], {"[첨부정정]": 1, "[첨부추가]": 1})

    def test_report_accumulates_across_days(self):
        _, report = select_events([item("주식소각결정", "1")], RULES, KINDS)
        _, report = select_events([item("주식소각결정", "2", rcept_dt="20261030")], RULES, KINDS, report=report)
        self.assertEqual(report.by_event_type["share_cancel"], 2)
        self.assertEqual(set(report.by_day), {"2026-10-29", "2026-10-30"})


class FetchDayTest(unittest.TestCase):
    LIST_CONFIG = {"corp_cls": "Y", "pblntf_types": {"B": "major", "I": "other", "E": "other"}, "last_reprt_at": "N", "page_count": 100}

    def test_fetches_each_type_with_paging_and_caches_past_days(self):
        responses = [
            FakeResponse(json_data={"status": "000", "total_page": 1, "list": [item("유상증자결정", "1")]}),
            FakeResponse(json_data={"status": "000", "total_page": 2, "list": [item("주식소각결정", "2")]}),
            FakeResponse(json_data={"status": "000", "total_page": 2, "list": [item("파산신청", "3")]}),
            FakeResponse(json_data={"status": "013", "message": "없음"}),
        ]
        session = FakeSession(responses)
        with tempfile.TemporaryDirectory() as directory:
            raw = Path(directory)
            items = events_list.fetch_day(API_KEY, date(2026, 10, 29), self.LIST_CONFIG, raw, session=session)
            self.assertEqual([(i["rcept_no"], i["_pblntf_ty"]) for i in items], [("1", "B"), ("2", "I"), ("3", "I")])
            self.assertTrue((raw / "lists" / "20261029.json").exists())
            again = events_list.fetch_day(API_KEY, date(2026, 10, 29), self.LIST_CONFIG, raw, session=FakeSession([]))
        self.assertEqual(again, items)
        params = [call[1] for call in session.calls]
        self.assertEqual([p["pblntf_ty"] for p in params], ["B", "I", "I", "E"])
        self.assertEqual([p["page_no"] for p in params], [1, 1, 2, 1])
        first = params[0]
        self.assertEqual((first["bgn_de"], first["end_de"], first["corp_cls"], first["last_reprt_at"]), ("20261029", "20261029", "Y", "N"))
        self.assertNotIn("corp_code", first)
        self.assertNotIn("pblntf_detail_ty", first)

    def test_rate_limit_propagates(self):
        session = FakeSession([FakeResponse(json_data={"status": "020", "message": "limit"})])
        with tempfile.TemporaryDirectory() as directory, self.assertRaises(dart_reports.DartRateLimitError):
            events_list.fetch_day(API_KEY, date(2026, 10, 29), self.LIST_CONFIG, Path(directory), session=session)

    def test_days_between(self):
        self.assertEqual(len(events_list.days_between(date(2026, 10, 21), date(2026, 11, 3))), 14)
        with self.assertRaises(ValueError):
            events_list.days_between(date(2026, 11, 3), date(2026, 11, 1))


if __name__ == "__main__":
    unittest.main()
