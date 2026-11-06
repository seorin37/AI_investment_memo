import tempfile
import unittest
from pathlib import Path

from pipelines.disclosures import parser
from tests.disclosure_fixtures import EXCLUDE_PATTERNS, SAMPLE_XML, zip_bytes


def parse(xml=SAMPLE_XML):
    return parser.parse_xml(xml.encode("utf-8"), "20260814003699", EXCLUDE_PATTERNS)


class ParserTest(unittest.TestCase):
    def test_meta_and_period(self):
        doc = parse()
        self.assertEqual(doc.document_name, "반기보고서")
        self.assertEqual(doc.corp_code, "00126380")
        self.assertEqual((doc.period_from, doc.period_to), ("20260101", "20260630"))

    def test_section_paths_and_library_is_transparent(self):
        sections = {tuple(block.section) for block in parse().blocks}
        self.assertEqual(
            sections,
            {
                ("I. 회사의 개요", "1. 회사의 개요"),
                ("III. 재무에 관한 사항", "2. 연결재무제표", "2-1. 연결 재무상태표"),
                ("III. 재무에 관한 사항", "3. 연결재무제표 주석", "5. 재고자산 (연결)"),
            },
        )

    def test_excluded_sections_cover_hidden_and_empty(self):
        texts = " ".join(block.text + " ".join(block.rows) for block in parse().blocks)
        for removed in ("확인서 본문", "별도 주석", "별도 본표", "별도 주석 본문", "표지 문구", "숨김 문단", "2026년 06월"):
            self.assertNotIn(removed, texts)
        paragraphs = [b.text for b in parse().blocks if b.section[-1] == "1. 회사의 개요"]
        self.assertEqual(paragraphs, ["첫 문단입니다.", "둘째 문단입니다."])

    def test_exclusion_uses_title_patterns_not_fixed_titles(self):
        custom = SAMPLE_XML.replace("I. 회사의 개요", "I. 지주회사의 개요")
        doc = parser.parse_xml(custom.encode("utf-8"), "1", EXCLUDE_PATTERNS + [r"지주회사"])
        self.assertFalse(any("지주회사" in " ".join(b.section) for b in doc.blocks))

    def test_rowspan_colspan_header_and_unit(self):
        table = next(b for b in parse().blocks if b.section[-1] == "2-1. 연결 재무상태표")
        self.assertEqual(table.block_type, "table")
        self.assertEqual(table.caption, "연결 재무상태표")
        self.assertEqual(table.unit, "(단위 : 백만원)")
        self.assertEqual(table.header, ["과목", "당기 / 3개월", "당기 / 누적"])
        self.assertEqual(
            table.rows,
            [
                "과목: 자산 | 당기 / 3개월: 10 | 당기 / 누적: 20",
                "과목: 자산 | 당기 / 3개월: 30 | 당기 / 누적: 40",
                "과목: 합계 | 당기 / 누적: 60",
            ],
        )

    def test_layout_table_is_unwrapped_and_unit_row_becomes_caption(self):
        blocks = [b for b in parse().blocks if b.section[-1] == "5. 재고자산 (연결)"]
        self.assertEqual(len(blocks), 1)
        table = blocks[0]
        self.assertEqual(table.caption, "재고자산의 내역은 다음과 같습니다. / 당반기말")
        self.assertEqual(table.unit, "(단위 : 백만원)")
        self.assertEqual(table.rows, ["구분: 제품 | 금액: 100"])

    def test_nfc_normalization(self):
        decomposed = "각"  # 각 (NFD)
        doc = parse(SAMPLE_XML.replace("첫 문단입니다.", decomposed))
        self.assertIn("각", [b.text for b in doc.blocks])

    def test_roundtrip_dict(self):
        doc = parse()
        self.assertEqual(parser.ParsedDocument.from_dict(doc.to_dict()), doc)

    def test_read_main_xml_ignores_attachments(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "005930_1.zip"
            path.write_bytes(zip_bytes("1.xml", SAMPLE_XML))
            self.assertIn(b"BODY", parser.read_main_xml(path, "1"))
            path.write_bytes(zip_bytes("1_00760.xml", SAMPLE_XML))
            with self.assertRaises(parser.ParseError):
                parser.read_main_xml(path, "1")

    def test_missing_body_raises(self):
        with self.assertRaises(parser.ParseError):
            parser.parse_xml(b"<DOCUMENT></DOCUMENT>", "1", EXCLUDE_PATTERNS)


def doc_xml(body: str) -> bytes:
    return f'<?xml version="1.0" encoding="utf-8"?><DOCUMENT><BODY>{body}</BODY></DOCUMENT>'.encode("utf-8")


def all_text(doc) -> str:
    return " ".join(b.text + " ".join(b.rows) + b.caption for b in doc.blocks)


class SanitizeTest(unittest.TestCase):
    """DART 원문의 이스케이프되지 않은 `<`·`&`, 깨진 속성 (WO-017)."""

    def test_unescaped_pseudo_tag_does_not_swallow_following_sections(self):
        # NAVER 사업보고서 실제 형태: 표 셀의 `<당기말>`이 닫히지 않아 뒤의 SECTION-1이 표 안으로 들어가던 문제
        xml = doc_xml(
            "<SECTION-1><TITLE>II. 사업의 내용</TITLE>"
            "<TABLE><TBODY><TR><TD><당기말></TD><TD>(단위: 천원)</TD></TR>"
            "<TR><TD>항목</TD><TD>1</TD></TR></TBODY></TABLE></SECTION-1>"
            "<SECTION-1><TITLE>III. 재무에 관한 사항</TITLE><P>재무 본문입니다.</P></SECTION-1>"
        )
        doc = parser.parse_xml(xml, "R", EXCLUDE_PATTERNS)
        self.assertEqual(doc.quality["recover_errors"], 0)
        self.assertEqual(doc.quality["nested_sections"], 0)
        self.assertIn(["III. 재무에 관한 사항"], [b.section for b in doc.blocks])
        self.assertIn("<당기말>", all_text(doc))

    def test_ampersands_and_html_entities_are_kept_as_text(self):
        xml = doc_xml("<SECTION-1><TITLE>I. 개요</TITLE><P>R&D 및 IT&인프라 &amp; S&P &reg; &#169; &nbsp;끝 &foo;</P></SECTION-1>")
        doc = parser.parse_xml(xml, "R", EXCLUDE_PATTERNS)
        self.assertEqual(all_text(doc), "R&D 및 IT&인프라 & S&P ® © 끝 &foo;")
        self.assertEqual(doc.quality["bare_amp"], 3)
        self.assertEqual(doc.quality["html_entities"], 3)  # reg, nbsp, foo(모르는 이름은 글자 그대로)

    def test_broken_attribute_quotes_are_repaired(self):
        xml = doc_xml(
            '<SECTION-1><TITLE>I. 개요</TITLE><TABLE><TBODY>'
            '<TR><TH ENG="Name">회사</TH><TH ENG="Provisions "" HEIGHT="46">충당부채</TH></TR>'
            '<TR><TE ENG=""Snow Corporation" WIDTH="1">스노우</TE><TE ENG="">10</TE></TR>'
            "</TBODY></TABLE></SECTION-1>"
        )
        doc = parser.parse_xml(xml, "R", EXCLUDE_PATTERNS)
        self.assertEqual(doc.quality["broken_attrs"], 2)
        self.assertEqual(doc.blocks[0].rows, ["회사: 스노우 | 충당부채: 10"])

    def test_even_number_of_inner_quotes_is_repaired(self):
        # 하나금융지주·유안타증권 2025~ 보고서: 따옴표 수가 짝수라 예전 검사(홀수·`""`)를 지나쳐 파싱이 실패했다
        xml = doc_xml(
            '<SECTION-1><TITLE>I. 개요</TITLE><TABLE><TBODY>'
            '<TR><TH ENG="Name">구분</TH><TH ENG="Expected probability of default applied with CVA ("PD")" WIDTH="351">손실율</TH></TR>'
            '<TR><TE>A</TE><TE>0.5</TE></TR>'
            "</TBODY></TABLE></SECTION-1>"
        )
        doc = parser.parse_xml(xml, "R", EXCLUDE_PATTERNS)
        self.assertEqual(doc.quality["broken_attrs"], 1)
        self.assertEqual(doc.quality["recover_errors"], 0)
        self.assertEqual(doc.blocks[0].rows, ["구분: A | 손실율: 0.5"])

    def test_bare_link_tag_is_text(self):
        # SP삼화 제품 코드: 속성 없는 `<A>`는 링크가 아니라 글자 (DART 링크는 늘 REFNO 등 속성이 있다)
        xml = doc_xml(
            '<SECTION-1><TITLE>I. 개요</TITLE><TABLE><TBODY>'
            "<TR><TH>과제</TH><TH>제품</TH></TR>"
            "<TR><TD>도료 개발</TD><TD>TP FLEX BLACK<A>#(KJ)SH22-3436K<A>#(BC1)</TD></TR>"
            '</TBODY></TABLE><P><A REFNO="XII">상세표 참조</A></P></SECTION-1>'
        )
        doc = parser.parse_xml(xml, "R", EXCLUDE_PATTERNS)
        self.assertEqual(doc.quality["recover_errors"], 0)
        self.assertEqual(doc.blocks[0].rows, ["과제: 도료 개발 | 제품: TP FLEX BLACK<A>#(KJ)SH22-3436K<A>#(BC1)"])
        self.assertEqual(doc.blocks[1].text, "상세표 참조")

    def test_uppercase_text_that_looks_like_a_tag_is_escaped_and_counted(self):
        xml = doc_xml("<SECTION-1><TITLE>I. 개요</TITLE><P>- 제11회 <ACI 세미나></P><P>뒤 문단</P></SECTION-1>")
        doc = parser.parse_xml(xml, "R", EXCLUDE_PATTERNS)
        self.assertEqual([b.text for b in doc.blocks], ["- 제11회 <ACI 세미나>", "뒤 문단"])
        self.assertEqual(doc.quality["stray_tag_like"], 1)

    def test_remaining_structure_problems_fail_the_document(self):
        nested = doc_xml("<SECTION-1><TITLE>I. 개요</TITLE><P>a<SECTION-1><TITLE>II. 안</TITLE><P>b</P></SECTION-1></P></SECTION-1>")
        with self.assertRaises(parser.ParseError) as caught:
            parser.parse_xml(nested, "R", EXCLUDE_PATTERNS, max_recover_errors=None)
        self.assertIn("구조 이상", str(caught.exception))
        self.assertEqual(caught.exception.quality["nested_sections"], 1)

    def test_recover_errors_over_limit_fail_unless_disabled(self):
        broken = doc_xml("<SECTION-1><TITLE>I. 개요</TITLE><P>닫히지 않은 문단</SECTION-1>")
        with self.assertRaises(parser.ParseError):
            parser.parse_xml(broken, "R", EXCLUDE_PATTERNS)
        doc = parser.parse_xml(broken, "R", EXCLUDE_PATTERNS, max_recover_errors=None)
        self.assertGreater(doc.quality["recover_errors"], 0)

    def test_single_letter_tag_names_followed_by_text_are_not_tags(self):
        xml = doc_xml("<SECTION-1><TITLE>I. 개요</TITLE><P>신용등급 <A 등급> 유지, <P 1> 참조</P><P><A HREF=\"x\">링크</A></P></SECTION-1>")
        doc = parser.parse_xml(xml, "R", EXCLUDE_PATTERNS)
        self.assertEqual([b.text for b in doc.blocks], ["신용등급 <A 등급> 유지, <P 1> 참조", "링크"])

    def test_unknown_real_markup_fails_document(self):
        # 닫는 태그까지 있는 화이트리스트 밖 이름은 본문 글자가 아니라 빠진 태그일 가능성이 높다
        xml = doc_xml("<SECTION-1><TITLE>I. 개요</TITLE><P>x <B>굵게</B></P></SECTION-1>")
        with self.assertRaises(parser.ParseError) as caught:
            parser.parse_xml(xml, "R", EXCLUDE_PATTERNS)
        self.assertEqual(caught.exception.quality["unknown_markup"], ["B"])

    def test_cdata_is_left_alone(self):
        xml = doc_xml("<SECTION-1><TITLE>I. 개요</TITLE><P><![CDATA[R&D <x>]]></P></SECTION-1>")
        self.assertEqual(parser.parse_xml(xml, "R", EXCLUDE_PATTERNS).blocks[0].text, "R&D <x>")

    def test_html5_entity(self):
        xml = doc_xml("<SECTION-1><TITLE>I. 개요</TITLE><P>&check; &NotEqual;</P></SECTION-1>")
        self.assertEqual(parser.parse_xml(xml, "R", EXCLUDE_PATTERNS).blocks[0].text, "\u2713 \u2260")

    def test_read_meta_has_no_quality_gate(self):
        nested = doc_xml('<COVER><TU AUNIT="PERIODTO" AUNITVALUE="20260630">x</TU></COVER><SECTION-1><TITLE>I</TITLE><P>a<SECTION-1><TITLE>II</TITLE></SECTION-1></P></SECTION-1>')
        self.assertEqual(parser.read_meta(nested)["period_to"], "20260630")

    def test_valid_markup_is_unchanged(self):
        self.assertEqual(parser.sanitize_xml(SAMPLE_XML.encode("utf-8"))[0], SAMPLE_XML.encode("utf-8"))


if __name__ == "__main__":
    unittest.main()
