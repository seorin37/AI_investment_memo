"""평가기준표 정렬 테스트 (DB 없음, 가짜 청크)."""

import json
import unittest

from pipelines.disclosures import eval_reference as er


def doc(rcept_no, chunks):
    return er.make_doc(rcept_no, [(i, text, section) for i, (text, section) in chunks.items()])


SALES = "[삼성전자 2025 사업보고서 | III > 2-2. 연결 손익계산서]\n[표] 손익계산서 (단위 : 백만원)\n매출액 | 제 57 기: 333,605,938 | 제 56 기: 300,870,903\n영업이익 | 제 57 기: 43,601,051 | 제 56 기: 32,725,961"


def row(evidence, alternatives=("매출액",), status="evidence_verified", target="R1"):
    return {
        "id": "Q-1",
        "symbol": "005930",
        "verification_status": status,
        "target_reports": [{"rcept_no": target, "period_end": "2025-12-31"}],
        "current_repaired_chunk_ids": ["R1:9"],
        "required_fact_groups": [
            {
                "group_id": "Q-1-F1",
                "required_fact": {"alternatives_or": list(alternatives)},
                "report_requirement": {"rcept_no": target},
                "valid_evidence_or": evidence,
            }
        ],
    }


def team_ev(rcept_no, index, excerpt):
    return {"rcept_no": rcept_no, "chunk_index": index, "excerpt": excerpt}


class AlignTest(unittest.TestCase):
    def test_content_match_moves_index_and_ignores_formatting(self):
        db = {"R1": doc("R1", {0: ("[h]\n다른 내용", "s0"), 5: (SALES, "III > 2-2. 연결 손익계산서")})}
        # 팀 청크는 공백·구분자가 다르고 번호도 다르다
        excerpt = SALES.replace(" | ", "  ").replace("\n", " ")
        new, report = er.align_row(row([team_ev("R1", 9, excerpt)]), db.get, {})
        group = new["required_fact_groups"][0]
        self.assertEqual(group["alignment_status"], "aligned")
        self.assertEqual([(e["rcept_no"], e["chunk_index"], e["alignment"]) for e in group["valid_evidence_or"]], [("R1", 5, "content")])
        self.assertEqual(group["valid_evidence_or"][0]["team_chunk_index"], 9)
        self.assertEqual(new["current_repaired_chunk_ids"], ["R1:5"])
        self.assertEqual(new["team_repaired_chunk_ids"], ["R1:9"])
        self.assertEqual((new["eval_status"], new["needs_human_check"]), ("scored", False))
        self.assertFalse(report[0]["same_index"])

    def test_fact_must_be_present_and_header_counts(self):
        body = "[KB금융 2026 1분기 | XI > 3. 제재 등과 관련된 사항]\n- 분기보고서 작성 시 기재를 생략하오니 사업보고서를 참고하시기 바랍니다."
        db = {"R1": doc("R1", {3: (body, "XI > 3. 제재 등과 관련된 사항")})}
        ok, _ = er.align_row(row([team_ev("R1", 1, body)], alternatives=("제재", "조치")), db.get, {})
        self.assertEqual(ok["required_fact_groups"][0]["alignment_status"], "aligned")  # 사실 표현이 섹션 제목에만 있어도 인정
        missing, _ = er.align_row(row([team_ev("R1", 1, body)], alternatives=("과징금",)), db.get, {})
        self.assertEqual(missing["required_fact_groups"][0]["alignment_status"], "unresolved")
        self.assertEqual((missing["eval_status"], missing["exclude_reason"]), ("excluded", "unresolved_after_alignment"))

    def test_number_fallback_picks_best_chunk_and_flags_review(self):
        holding = "[h]\n[표] <KB금융지주> BIS기준 자기자본비율 구분: 자기자본(a=b+e) | 2025년: 58,281 | 2024년: 56,849 구분: 총자본비율(a/f) | 2025년: 16.28"
        bank = "[h]\n[표] [KB국민은행] BIS기준 자기자본비율 구분: 총 자기자본(A) | 2025년: 432,475 구분: 총자본비율(A/B) | 2025년: 17.93 | 58,281 | 56,849"
        db = {"R1": doc("R1", {1: (holding, "s"), 2: (bank, "s")})}
        excerpt = "구분 2025년 2024년 자기자본(a=b+e) 58,281 56,849 총자본비율(a/f) 16.28"
        new, report = er.align_row(row([team_ev("R1", 7, excerpt)], alternatives=("총자본비율",)), db.get, {})
        group = new["required_fact_groups"][0]
        self.assertEqual([(e["chunk_index"], e["alignment"]) for e in group["valid_evidence_or"]], [(1, "numbers")])
        self.assertEqual(group["alignment_status"], "fallback")
        self.assertTrue(new["needs_human_check"])
        self.assertEqual(report[0]["method"], "numbers")

    def test_report_replacement_for_missing_amendment(self):
        db = {"NEW": doc("NEW", {4: (SALES, "s")})}
        new, _ = er.align_row(row([team_ev("OLD", 9, SALES)], target="OLD"), db.get, {"OLD": "NEW"})
        self.assertEqual(new["target_reports"][0], {"rcept_no": "NEW", "period_end": "2025-12-31", "team_rcept_no": "OLD"})
        self.assertEqual(new["required_fact_groups"][0]["report_requirement"]["rcept_no"], "NEW")
        self.assertEqual(new["required_fact_groups"][0]["valid_evidence_or"][0]["team_rcept_no"], "OLD")
        self.assertEqual(new["report_replacements"], {"OLD": "NEW"})
        self.assertTrue(new["needs_human_check"])

    def test_not_disclosed_question_is_excluded_and_input_untouched(self):
        original = row([], status="not_disclosed_in_scope")
        snapshot = json.dumps(original, ensure_ascii=False)
        new, _ = er.align_row(original, {}.get, {})
        self.assertEqual((new["eval_status"], new["exclude_reason"]), ("excluded", "not_disclosed_in_scope"))
        self.assertEqual(new["required_fact_groups"][0]["alignment_status"], "no_evidence")
        self.assertEqual(json.dumps(original, ensure_ascii=False), snapshot)
        verified_but_empty, _ = er.align_row(row([]), {}.get, {})
        self.assertEqual(verified_but_empty["exclude_reason"], "no_team_evidence")

    def test_number_tokens_skip_years_dates_and_short_numbers(self):
        self.assertEqual(er.number_tokens("2025년 3분기 58,281 16.28 12 2025.12.31 2025.12"), {"58281", "1628"})

    def test_numbers_compare_whole_tokens_not_substrings(self):
        # '58,281 | 56,849'를 붙이면 '5828156849'가 되어 '281'·'815'가 부분 일치하던 문제
        db = {"R1": doc("R1", {1: ("[h]\n총자본비율 58,281 | 56,849", "s")})}
        new, _ = er.align_row(row([team_ev("R1", 1, "총자본비율 281 815 999")], alternatives=("총자본비율",)), db.get, {})
        self.assertEqual(new["required_fact_groups"][0]["alignment_status"], "unresolved")

    def test_numbers_evidence_or_unaligned_team_evidence_needs_review_even_if_group_aligned(self):
        db = {"R1": doc("R1", {5: (SALES, "s")})}
        lost = team_ev("R1", 8, "원문에 없는 다른 문장으로 된 근거 발췌입니다 매출액")
        new, _ = er.align_row(row([team_ev("R1", 9, SALES), lost]), db.get, {})
        group = new["required_fact_groups"][0]
        self.assertEqual(group["alignment_status"], "aligned")
        self.assertEqual(len(group["unaligned_team_evidence"]), 1)
        self.assertTrue(new["needs_human_check"])

    def test_short_excerpt_is_not_a_content_probe(self):
        self.assertEqual(er.probes("해당사항 없음"), [])

    def test_header_company_name_does_not_satisfy_fact(self):
        db = {"R1": doc("R1", {1: ("[삼성전자 2025 사업보고서 | 사업의 개요]\n본문 내용이 충분히 길게 이어지는 문장입니다", "사업의 개요")})}
        new, _ = er.align_row(row([team_ev("R1", 1, "본문 내용이 충분히 길게 이어지는 문장입니다")], alternatives=("삼성전자",)), db.get, {})
        self.assertEqual(new["required_fact_groups"][0]["alignment_status"], "unresolved")


if __name__ == "__main__":
    unittest.main()
