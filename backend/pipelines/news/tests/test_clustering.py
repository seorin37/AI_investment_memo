from datetime import datetime, timedelta, timezone

import pytest

from backend.pipelines.news.clustering import (Candidate, ClusterParams, Member, RepresentativeInfo,
                                               choose_cluster, cosine_similarity, is_standalone_title,
                                               pick_representative, rule_conflict, title_amounts,
                                               title_regions)

T0 = datetime(2026, 10, 22, 9, 0, tzinfo=timezone.utc)
P = ClusterParams(threshold=0.65)
T0_KST_NOON = datetime(2026, 10, 22, 3, 0, tzinfo=timezone.utc)   # 한국 시간 22일 12:00


def m(news_id, vec, hours=0, title=""):
    return Member(news_id, T0 + timedelta(hours=hours), vec, title=title)


def test_cosine_similarity_basic():
    assert cosine_similarity([1, 0], [1, 0]) == pytest.approx(1.0)
    assert cosine_similarity([1, 0], [0, 1]) == pytest.approx(0.0)
    with pytest.raises(ValueError):
        cosine_similarity([0, 0], [1, 0])
    with pytest.raises(ValueError):
        cosine_similarity([1, 0], [1, 0, 0])


def test_new_cluster_when_no_candidates():
    assert choose_cluster(m(1, [1, 0]), [], P).cluster_id is None


def test_joins_only_when_similar_to_all_members():
    # A-B 0.80, B-C 0.80인데 A-C는 0.28 → C는 [A, B] 묶음에 못 들어간다 (사슬 방지)
    a, b = m(1, [1.0, 0.0]), m(2, [0.8, 0.6])
    c = m(3, [0.28, 0.96])
    assert cosine_similarity(b.dense, c.dense) >= 0.65
    assert choose_cluster(c, [Candidate(10, (a, b))], P).cluster_id is None
    d = m(4, [0.95, 0.31])
    decision = choose_cluster(d, [Candidate(10, (a, b))], P)
    assert decision.cluster_id == 10
    assert decision.min_similarity == pytest.approx(min(cosine_similarity(d.dense, a.dense),
                                                        cosine_similarity(d.dense, b.dense)))


def test_picks_highest_mean_then_lowest_id():
    new = m(9, [1.0, 0.0])
    near = Candidate(20, (m(1, [0.99, 0.14]),))
    far = Candidate(5, (m(2, [0.8, 0.6]),))
    assert choose_cluster(new, [far, near], P).cluster_id == 20
    twin_a, twin_b = Candidate(7, (m(3, [0.9, 0.1]),)), Candidate(3, (m(4, [0.9, 0.1]),))
    assert choose_cluster(new, [twin_a, twin_b], P).cluster_id == 3


def test_time_window_and_max_size():
    new = m(9, [1.0, 0.0], hours=0)
    old = Candidate(1, (m(1, [1.0, 0.0], hours=-25),))
    assert choose_cluster(new, [old], P).cluster_id is None
    edge = Candidate(2, (m(2, [1.0, 0.0], hours=-24),))
    assert choose_cluster(new, [edge], ClusterParams(threshold=0.65, same_day=False)).cluster_id == 2
    assert choose_cluster(new, [edge], P).decided_by == "rule"            # 기본은 다른 날이면 안 묶음
    full = Candidate(3, tuple(m(100 + i, [1.0, 0.0]) for i in range(P.max_size)))
    assert choose_cluster(new, [full], P).cluster_id is None


def test_threshold_boundary_is_inclusive():
    params = ClusterParams(threshold=0.8)
    new = m(9, [1.0, 0.0])
    assert choose_cluster(new, [Candidate(1, (m(1, [0.8, 0.6]),))], params).cluster_id == 1
    assert choose_cluster(new, [Candidate(1, (m(1, [0.79, 0.61]),))], params).cluster_id is None


@pytest.mark.parametrize("title", [
    "[전국 주요 신문 톱뉴스](22일 석간)", "[연합뉴스 이 시각 헤드라인] - 18:00",
    "오늘의 프리미엄9 콘텐츠 다이제스트(10월 21일)", "스페이스X·테슬라 합병 공식화 [글로벌 모닝 브리핑]",
    "[부고] 한영우(예탁결제원 팀장)씨 부친상", "[인사] 국가철도공단", "[게시판] 신한증권, 세미나 개최",
    "[표] 코스피 지수선물·옵션 시세표(21일)-1", "[오늘의 운세] 10월 22일 띠별 운세", "[오늘의 국감](22일)",
])
def test_standalone_titles(title):
    assert is_standalone_title(title)


@pytest.mark.parametrize("title", [
    "[속보] 한은, 기준금리 연 3.00%로 동결", "스페이스X 훈풍에 기술주 강세…나스닥 1.05% ↑ [뉴욕증시 브리핑]",
    "[포토] 우리금융, 동반성장에 35조 지원", "\"전설의 사운드를 한눈에\"… 삼성전자, 음향 명가 총출동", None,
])
def test_regular_titles(title):
    assert not is_standalone_title(title)


def test_standalone_articles_never_join_or_get_joined():
    same = [1.0, 0.0]
    briefing = Member(1, T0, same, standalone=True)
    normal = m(2, same)
    assert choose_cluster(briefing, [Candidate(10, (normal,))], P).cluster_id is None
    assert choose_cluster(normal, [Candidate(11, (briefing,))], P).cluster_id is None


def test_rejects_article_already_in_candidate():
    with pytest.raises(ValueError):
        choose_cluster(m(1, [1, 0]), [Candidate(1, (m(1, [1, 0]),))], P)


def test_same_input_same_result():
    new = m(9, [0.9, 0.3])
    cands = [Candidate(i, (m(i, [0.9, 0.3 + i / 100]),)) for i in range(1, 6)]
    assert len({choose_cluster(new, cands, P) for _ in range(5)}) == 1


def test_params_validation_and_version():
    with pytest.raises(ValueError):
        ClusterParams(threshold=1.5)
    with pytest.raises(ValueError):
        ClusterParams(window=timedelta(0))
    with pytest.raises(ValueError):
        ClusterParams(threshold=0.8, llm_below=0.7)
    assert ClusterParams().method_version == "complete-link-v4:t0.70:w24h:k10:m30:day:rules:nollm"
    assert ClusterParams(use_llm=True).method_version.endswith(":rules:llm0.85")


def test_title_regions_and_amounts():
    assert title_regions("강화·인천 북부에 한파주의보 해제") == {"인천"}
    assert title_regions("충주 등 충청북도 12곳") == {"충북"}
    assert title_regions("고양 등 경기 11곳 한파주의보 해제") == {"경기"}
    assert title_regions("경기 침체 우려에 코스피 하락") == set()          # 경제 뜻의 '경기'는 지역 아님
    assert title_amounts("에이루트, 17억원 유상증자") == {17.0}
    assert title_amounts("시큐레터, 7억원 유상증자") == {7.0}               # 17억의 7억으로 잘못 잡지 않음
    assert title_amounts("1조 규모 투자, 2,500억 회사채") == {10000.0, 2500.0}


def test_rule_conflict():
    base = Member(1, T0_KST_NOON, [1, 0], title="고양 등 경기 11곳 한파주의보 해제")
    def other(title, hours=0):
        return Member(2, T0_KST_NOON + timedelta(hours=hours), [1, 0], title=title)
    assert rule_conflict(base, other("원주 등 강원 18곳 한파주의보 해제"), P) == "region"
    assert rule_conflict(base, other("시흥 등 경기 10곳 한파주의보 해제"), P) is None
    assert rule_conflict(base, other("한파주의보 해제 잇따라"), P) is None       # 한쪽에만 있으면 비교 안 함
    assert rule_conflict(base, other("시흥 등 경기 10곳", hours=12), P) == "day"   # 한국 시간 다음 날 0시
    assert rule_conflict(base, other("시흥 등 경기 10곳", hours=11), P) is None
    a = Member(3, T0_KST_NOON, [1, 0], title="에이루트, 17억원 유상증자")
    assert rule_conflict(a, Member(4, T0_KST_NOON, [1, 0], title="시큐레터, 7억원 유상증자"), P) == "amount"
    assert rule_conflict(a, Member(4, T0_KST_NOON, [1, 0], title="에이루트, 17억 규모 유상증자 실시"), P) is None


def test_rule_blocks_join_and_next_cluster_is_tried():
    new = Member(9, T0_KST_NOON, [1.0, 0.0], title="원주 등 강원 18곳 한파주의보 해제")
    gyeonggi = Candidate(1, (Member(1, T0_KST_NOON, [1.0, 0.0], title="고양 등 경기 11곳 한파주의보 해제"),))
    gangwon = Candidate(2, (Member(2, T0_KST_NOON, [0.9, 0.44], title="강원 산지 한파주의보 해제"),))
    assert choose_cluster(new, [gyeonggi], P) == choose_cluster(new, [gyeonggi], P)
    assert choose_cluster(new, [gyeonggi], P).decided_by == "rule"
    d = choose_cluster(new, [gyeonggi, gangwon], P)                       # 평균이 더 높은 경기는 규칙에 걸림
    assert (d.cluster_id, d.decided_by) == (2, "dense")


class FakeJudge:
    def __init__(self, *answers):
        self.answers, self.asked = list(answers), []

    def __call__(self, new, members):
        self.asked.append(tuple(x.news_id for x in members))
        return self.answers.pop(0)


def test_llm_only_for_ambiguous_band():
    params = ClusterParams(threshold=0.70, llm_below=0.85, use_llm=True)
    new = m(9, [1.0, 0.0])
    sure = Candidate(1, (m(1, [0.9, 0.436]),))                            # 0.90 → LLM 안 물음
    judge = FakeJudge()
    assert choose_cluster(new, [sure], params, judge).decided_by == "dense" and judge.asked == []
    vague = Candidate(2, (m(2, [0.75, 0.661]),))                          # 0.75 → LLM
    assert choose_cluster(new, [vague], params, FakeJudge(True)).decided_by == "llm-same"
    d = choose_cluster(new, [vague], params, FakeJudge(False))
    assert (d.cluster_id, d.decided_by) == (None, "llm-different")
    d = choose_cluster(new, [vague], params, FakeJudge(None))             # 답을 못 받으면 합류 안 함
    assert (d.cluster_id, d.decided_by) == (None, "llm-unavailable")
    assert choose_cluster(new, [vague], params).decided_by == "dense"    # judge가 없으면 규칙까지만


def test_llm_tries_next_cluster_up_to_limit():
    params = ClusterParams(threshold=0.70, llm_below=0.85, llm_per_article=2, use_llm=True)
    new = m(9, [1.0, 0.0])
    c1, c2, c3 = (Candidate(i, (m(i, [0.8 - i / 100, (1 - (0.8 - i / 100) ** 2) ** 0.5]),)) for i in (1, 2, 3))
    judge = FakeJudge(False, True)
    d = choose_cluster(new, [c3, c2, c1], params, judge)
    assert judge.asked == [(1,), (2,)] and (d.cluster_id, d.decided_by) == (2, "llm-same")
    judge = FakeJudge(False, False, True)
    d = choose_cluster(new, [c3, c2, c1], params, judge)
    assert len(judge.asked) == 2 and (d.cluster_id, d.decided_by) == (None, "llm-different")


def test_representative_prefers_summary_then_earliest_then_source():
    long = "가" * 40
    rows = [
        RepresentativeInfo(1, T0, "yonhap", None),                          # 요약 없음
        RepresentativeInfo(2, T0 + timedelta(hours=1), "hankyung", long),
        RepresentativeInfo(3, T0 + timedelta(hours=1), "yonhap", long),     # 같은 시각이면 연합 우선
        RepresentativeInfo(4, T0 + timedelta(hours=2), "mk", long),
    ]
    assert pick_representative(rows) == 3
    assert pick_representative(rows[:1]) == 1
    with pytest.raises(ValueError):
        pick_representative([])
