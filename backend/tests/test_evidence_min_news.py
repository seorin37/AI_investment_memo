"""근거 고르기의 뉴스 최소 자리 (evidence.build_evidence min_news, 2026-11-18).

실험 설정에서 공시(5건×3청크)가 근거 상한을 다 채워 관련 뉴스가 0건이 되던 문제.
"""

import unittest

from pipelines.updates.evidence import build_evidence
from pipelines.updates.models import Candidate


def disc(n: int, chunk: int, sim: float) -> Candidate:
    return Candidate(ref=f"disc:2026000000{n:02d}#{chunk}", kind="disclosure", symbol="005930", date="2026-11-01",
                     title=f"분기보고서 {n}", text="공시 본문", url=None, source="DART", similarity=sim)


def news(n: int, sim: float, title: str | None = None) -> Candidate:
    return Candidate(ref=f"news:{n}", kind="news", symbol="005930", date="2026-11-10",
                     title=title or f"기사 제목 {n} 전혀 다른 사건 {n * 7}", text="기사 요약", url=None, source="매체", similarity=sim)


DISCS = [disc(n, c, 0.9 - n * 0.01 - c * 0.001) for n in range(5) for c in range(3)]   # 공시 5건 × 3청크 = 15


class MinNewsTest(unittest.TestCase):
    def kinds(self, ev):
        return [e.candidate.kind for e in ev].count("disclosure"), [e.candidate.kind for e in ev].count("news")

    def test_without_min_news_disclosures_fill_everything(self):
        ev = build_evidence(DISCS + [news(i, 0.7) for i in range(4)], mode="all", max_disclosure_docs=5,
                            max_chunks_per_disclosure=3, max_total=8)
        self.assertEqual(self.kinds(ev), (15, 0))            # 예전 동작 (운영 설정에서는 min_news 0이라 그대로)

    def test_min_news_reserves_slots_and_keeps_total(self):
        ev = build_evidence(DISCS + [news(i, 0.7) for i in range(4)], mode="all", max_disclosure_docs=5,
                            max_chunks_per_disclosure=2, max_total=8, min_news=3)
        self.assertEqual(self.kinds(ev), (5, 3))
        kept = {e.candidate.ref for e in ev if e.candidate.kind == "disclosure"}
        self.assertIn("disc:202600000000#0", kept)            # 점수 높은 공시부터 남는다

    def test_fewer_news_than_reserve_gives_room_back(self):
        ev = build_evidence(DISCS + [news(1, 0.7)], mode="all", max_disclosure_docs=5, max_chunks_per_disclosure=2,
                            max_total=8, min_news=3)
        self.assertEqual(self.kinds(ev), (7, 1))
        ev = build_evidence(DISCS, mode="all", max_disclosure_docs=5, max_chunks_per_disclosure=2, max_total=8, min_news=3)
        self.assertEqual(self.kinds(ev), (8, 0))               # 뉴스가 없으면 공시가 다 쓴다

    def test_duplicate_news_counted_once(self):
        same = [news(i, 0.7 - i * 0.01, title="삼성전자 HBM4 양산 시작") for i in range(3)]
        ev = build_evidence(DISCS + same, mode="all", max_disclosure_docs=5, max_chunks_per_disclosure=2,
                            max_total=8, min_news=3)
        self.assertEqual(self.kinds(ev), (7, 1))               # 같은 사건 기사는 하나로


if __name__ == "__main__":
    unittest.main()
