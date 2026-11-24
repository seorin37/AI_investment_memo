"""관련성 판정 파이프라인 연결 (2026-11-10). LLM·DB 없이 가짜 호출로 돈다."""

import json
import re
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from pipelines.updates.autolabel import load_prompt
from pipelines.updates.models import Candidate, CreditsExhausted, TrackingItem
from pipelines.updates.relevance import config, filter_candidates, judge_news, parse_scope

ITEM = TrackingItem("M01:0:0", "000660", "topic", "D램 업황", memo_text="메모리 업황 회복 보기")
FLOOR = {"news": 0.58, "news_chunks": 0.58, "disclosure": 0.64, "event": 0.58}


def news(ref, sim=0.7, title="t"):
    return replace(Candidate(ref, "news", "000660", "2026-11-01", title, "본문", "http://x", "매체", sim), doc="chunk")


def disc(ref="disc:R1#0", sim=0.7):
    return Candidate(ref, "disclosure", "000660", "2026-10-28", "공시", "본문", None, "DART", sim, "event")


def hybrid_disc(ref="disc:H1#0", sim=0.43, score=0.9):
    return Candidate(ref, "disclosure", "000660", "2026-10-28", "HBM3E 12H", "HBM 연구개발실적", None, "DART",
                     sim, "periodic", score, "hybrid")


def answer(verdicts: dict[str, bool], scope="industry"):
    """프롬프트의 후보 줄(C1 [kind] 날짜 · 제목)에서 제목으로 판정을 정한다 (섞인 순서와 관계없이)."""
    def call(prompt):
        call.prompts.append(prompt)
        labels = [{"id": cid, "relevant": verdicts[title], "code": "ON_TOPIC_EVENT" if verdicts[title] else "OFF_TOPIC"}
                  for cid, title in re.findall(r"^(C\d+) \[[^\]]+\] \S+ · (.+)$", prompt, re.M)]
        return json.dumps({"scope": scope, "labels": labels})
    call.prompts = []
    return call


class RelevanceTest(unittest.TestCase):
    def test_prompt_has_scope_rules(self):
        p = load_prompt(config(None)["prompt"])
        for text in ("`company`", "`industry`", '"scope":"company"', "industry 범위에서는 이 단계를 건너뜁니다"):
            self.assertIn(text, p)

    def test_prompt_examples_do_not_overlap_review_sets(self):
        from pipelines.common.config import resolve_path
        from pipelines.updates.relevance_compare import example_overlaps, read_csv
        sets = ["results/updates/run_20261109_173514/review_human_news2_chunks.csv",
                "results/updates/run_20261109_133043/review_human.csv",
                "results/updates/run_20261109_170506/review_human_news2.csv",
                "results/updates/run_20261110_154307/review_human_news3_chunks.csv"]
        rows = [r for s in sets if resolve_path(s).is_file() for r in read_csv(resolve_path(s))]
        if not rows:
            self.skipTest("검수 파일 없음")
        self.assertEqual(example_overlaps(load_prompt(config(None)["prompt"]), rows), [])

    def test_judge_and_filter(self):
        cands = [news("news:1", title="D램 가격 상승"), news("news:2", title="다른 이야기"),
                 news("news:3", sim=0.5, title="임계값 아래"), disc()]
        call = answer({"D램 가격 상승": True, "다른 이야기": False})
        kept, rel, stop = filter_candidates(ITEM, cands, FLOOR, call, config(None), "지시문")
        self.assertIsNone(stop)
        self.assertEqual([c.ref for c in kept], ["news:1", "disc:R1#0"])      # 임계값 아래 뉴스는 판정 없이 뺀다
        self.assertEqual(rel.scope, "industry")
        self.assertEqual((rel.judged, rel.below_floor), (2, 1))
        self.assertEqual(rel.labels["news:2"], (False, "OFF_TOPIC"))
        self.assertNotIn("0.7", call.prompts[0].split("# 후보")[1])          # 유사도는 보여 주지 않는다
        d = rel.to_dict()
        self.assertEqual((d["relevant"], d["dropped"], d["codes"]), (1, 1, {"ON_TOPIC_EVENT": 1, "OFF_TOPIC": 1}))

    def test_no_relevant_and_failures(self):
        cands = [news("news:1", title="a"), news("news:2", title="b")]
        kept, rel, stop = filter_candidates(ITEM, cands, FLOOR, answer({"a": False, "b": False}), config(None), "p")
        self.assertEqual((kept, stop), ([], "no_relevant_candidates"))
        # 공시가 남으면 멈추지 않는다
        _, _, stop = filter_candidates(ITEM, cands + [disc()], FLOOR, answer({"a": False, "b": False}), config(None), "p")
        self.assertIsNone(stop)
        # 판정할 뉴스가 없으면 호출하지 않는다
        never = answer({})
        kept, rel, stop = filter_candidates(ITEM, [disc()], FLOOR, never, config(None), "p")
        self.assertEqual((never.prompts, stop, rel.judged), ([], None, 0))
        # 호출·응답 실패: 카드를 만들지 않는다
        def boom(_):
            raise RuntimeError("x")
        self.assertEqual(filter_candidates(ITEM, cands, FLOOR, boom, config(None), "p")[2], "relevance_failed")
        self.assertEqual(filter_candidates(ITEM, cands, FLOOR, lambda _: "{}", config(None), "p")[1].failed, "parse_failed")
        def credits(_):
            raise CreditsExhausted("0")
        with self.assertRaises(CreditsExhausted):
            judge_news(ITEM, cands, credits, "p")

    def test_hybrid_disclosure_bypasses_dense_floor_and_is_judged(self):
        h = hybrid_disc()
        cfg = {**config(None), "include_disclosures": True}
        kept, rel, stop = filter_candidates(ITEM, [h], FLOOR, answer({"HBM3E 12H": True}), cfg, "p")
        self.assertEqual(([c.ref for c in kept], rel.judged, rel.below_floor, stop), ([h.ref], 1, 0, None))

    def test_parse_scope(self):
        self.assertEqual(parse_scope('{"scope":"company","labels":[]}'), "company")
        self.assertEqual(parse_scope('{"scope":"other"}'), "")
        self.assertEqual(parse_scope("x"), "")

    def test_response_and_csv_columns(self):
        from pipelines.updates.response import item_response
        from pipelines.updates.results import write_candidates_csv
        r = item_response(ITEM, "no_relevant_candidates", [], None, True)
        self.assertEqual((r.type, r.reason, r.user_visible), ("no_new_info", "no_relevant_candidates", False))
        self.assertEqual(item_response(ITEM, "relevance_failed", [], None, True).reason, "relevance_failed")
        with tempfile.TemporaryDirectory() as d:
            path = write_candidates_csv(Path(d), [(ITEM, news("news:1")), (ITEM, disc())],
                                        {("M01:0:0", "news:1"): ("O", "ON_TOPIC_EVENT", "industry")})
            lines = path.read_text(encoding="utf-8-sig").splitlines()
            self.assertTrue(lines[0].endswith("관련(O/X),판정(O/X),판정코드,판정범위"))
            self.assertTrue(lines[1].endswith(",O,ON_TOPIC_EVENT,industry"))
            self.assertTrue(lines[2].endswith(",,,"))
            plain = write_candidates_csv(Path(d), [(ITEM, disc())]).read_text(encoding="utf-8-sig").splitlines()[0]
            self.assertTrue(plain.endswith("관련(O/X)"))                     # 판정을 끄면 예전 열 그대로

    def test_prioritized_sample(self):
        from pipelines.updates.review_sample import is_industry, prioritized_sample
        row = lambda i, sym, item, scope="": {"item_id": item, "symbol": sym, "ref": f"news:{i}", "항목": item, "판정범위": scope}
        rows = ([row(i, "005930", "삼성 배당", "company") for i in range(10)]
                + [row(10 + i, "005930", "D램 업황") for i in range(3)]
                + [row(20 + i, "105560", "KB 배당", "company") for i in range(2)]
                + [row(30, "000660", "HBM 경쟁", "industry")])
        self.assertTrue(is_industry(rows[10]) and is_industry(rows[-1]) and not is_industry(rows[0]))
        picked = prioritized_sample(rows, 7, {"105560"})
        refs = {r["ref"] for r in picked}
        self.assertTrue({"news:10", "news:11", "news:12", "news:20", "news:21", "news:30"} <= refs)   # 우선 대상 6건 모두
        self.assertEqual(len(picked), 7)

    def test_quota_sample(self):
        from pipelines.updates.review_sample import quota_sample
        row = lambda i, sym, item, scope="company": {"item_id": item, "symbol": sym, "ref": f"news:{i}", "항목": item,
                                                    "판정범위": scope}
        rows = ([row(i, "005930", f"삼성 배당 {i % 3}") for i in range(30)]
                + [row(100 + i, "000660", f"HBM {i % 4}", "industry") for i in range(8)]
                + [row(200 + i, "105560", f"KB 배당 {i % 2}") for i in range(5)])
        picked = quota_sample(rows, 20, {"105560", "035420"}, 15, 10)
        self.assertEqual(len(picked), 20)
        self.assertEqual(sum(r["판정범위"] == "industry" for r in picked), 8)     # 모자라면 있는 만큼
        self.assertEqual(sum(r["symbol"] == "105560" for r in picked), 5)
        self.assertEqual(len({r["ref"] for r in picked}), 20)

    def test_subsidiary_rule_in_prompt(self):
        p = load_prompt(config(None)["prompt"])
        self.assertIn("자회사·계열사가 하는 사업 소식은 다른 회사로 보지 않고", p)
        self.assertNotIn("현대모비스", p)                                          # 계열사를 다른 회사로 본 옛 예시

    def test_sample_memos(self):
        from pipelines.updates.sample_memos import select, to_items
        mk = lambda mid, company, body, tracked=True: {"memo_id": mid, "company_primary": company, "memo_body": body,
                                                      "sentences": [{"expected_decision": "추적" if tracked else "추적 안 함"}]}
        memos = [mk("A", "삼성전자", "HBM 수요랑 D램 업황"), mk("B", "삼성전자", "배당 보기"), mk("C", "KB금융", "배당"),
                 mk("D", "NAVER", "광고 실적"), mk("E", "SK하이닉스", "HBM 경쟁사", tracked=False)]
        picked = [m["memo_id"] for m in select(memos, n_industry=5, per_company=1)]
        self.assertEqual(picked, ["A", "C", "D"])                               # 추적 문장 없는 E는 뺀다, B는 산업·우선 회사 아님
        j = [{"memo_id": "A", "symbol": "005930", "judged": [
            {"sentence_index": 0, "text": "t", "decision": "normal", "items": [{"type": "topic", "description": "HBM"}]},
            {"sentence_index": 1, "text": "u", "decision": "normal", "merge_into": 0, "items": [{"type": "topic"}]},
            {"sentence_index": 2, "text": "v", "decision": "full_fallback", "items": []}]},
             {"memo_id": "B", "symbol": "005930", "judged": []}]
        items = to_items(j)
        self.assertEqual([(m["memo_id"], [s["sentence_index"] for s in m["sentences"]]) for m in items], [("A", [0])])

    def test_default_config(self):
        from pipelines.common.config import load_config
        cfg = load_config("configs/updates.yaml")
        self.assertTrue(cfg["relevance"]["enabled"])
        self.assertFalse(cfg["recent"]["filters"]["news_require_company"])      # 제목 모드는 끈 채로


if __name__ == "__main__":
    unittest.main()
