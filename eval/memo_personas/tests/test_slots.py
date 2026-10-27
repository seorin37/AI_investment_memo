import copy
from collections import Counter

import pytest

from eval.memo_personas.common import load_personas
from eval.memo_personas.slots import build_design


@pytest.fixture(scope="module")
def setup(base_cfg, fake_packs):
    packs, macro = fake_packs
    by_name = {p["name"]: p for p in packs.values()}
    personas = load_personas(base_cfg)
    return base_cfg, personas, by_name, macro


@pytest.fixture(scope="module")
def design(setup):
    cfg, personas, packs, macro = setup
    return build_design(personas, packs, macro, cfg)


def test_totals_and_shares(design):
    slots = [s for p in design["persons"] for s in p["slots"]]
    assert len(slots) == 1000
    track = [s for s in slots if s["sentence_type"][0] == "A"]
    assert len(track) == 850
    per_person = Counter(sum(s["sentence_type"][0] != "A" for s in p["slots"]) for p in design["persons"])
    assert set(per_person) == {1, 2} and per_person[1] == 50 and per_person[2] == 50
    assert sum(s["evidence_type"] == "복합" for s in track) / len(track) >= 0.30
    assert abs(sum(s["answerability"] == "자료 부족" for s in track) / len(track) - 0.10) < 0.01
    assert Counter(s["sentence_type"] for s in slots if s["sentence_type"][0] != "A") == {
        t: 10 for t in [f"B{i}" for i in range(1, 11)] + [f"C{i}" for i in range(1, 6)]}


def test_slot_rules(design, setup):
    _, personas, _, _ = setup
    plan = {p["persona_id"]: {s["slot"]: s["company"] for s in p["slots"]} for p in personas}
    for p in design["persons"]:
        types = [s["sentence_type"] for s in p["slots"] if s["sentence_type"][0] != "A"]
        assert len(types) == len(set(types)), "한 사람 안 B·C 유형 중복"
        for s in p["slots"]:
            assert s["target_company"] == plan[p["persona_id"]][s["slot"]]
            assert s["expected_decision_draft"] == {"A": "normal", "B": "full_fallback", "C": "partial"}[s["sentence_type"][0]]
            if s["sentence_type"] == "A2":
                assert "주가·거래" in s["evidence_parts"] and s["price_levels"]
            if s["sentence_type"][0] == "B":
                assert s["evidence_ids"] == [] and s["answerability"] == "해당 없음"
            elif s["answerability"] == "자료 부족":
                assert s["evidence_ids"] == [] and s["missing_topic"]
            else:
                assert s["evidence_ids"] and s["answerability"] == "근거 있음"
            if s["evidence_type"] == "복합":
                assert len(set(s["evidence_parts"])) == 2


def test_deterministic(design, setup):
    cfg, personas, packs, macro = setup
    assert build_design(personas, packs, macro, cfg) == design


def test_pilot_mix(design, setup):
    _, personas, _, _ = setup
    by = {p["persona_id"]: p for p in personas}
    pilot = [by[x] for x in design["pilot"]]
    assert len(pilot) == 10
    assert min(Counter(p["primary_company"] for p in pilot).values()) >= 2
    assert len({p["age_bucket"] for p in pilot}) == 6
    assert len({p["experience_band"] for p in pilot}) >= 4


def test_missing_news_is_reallocated(setup):
    cfg, personas, packs, macro = setup
    packs = copy.deepcopy(packs)
    packs["NAVER"]["items"] = [i for i in packs["NAVER"]["items"] if i["type"] != "뉴스"]
    d = build_design(personas, packs, macro, cfg)
    naver = [s for p in d["persons"] for s in p["slots"] if s["target_company"] == "NAVER"]
    assert not any("뉴스" in s["evidence_parts"] for s in naver)
    assert any(a["company"] == "NAVER" for a in d["adjustments"])
