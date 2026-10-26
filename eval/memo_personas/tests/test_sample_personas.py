"""3단계 페르소나 규칙 ([A] 수정분)과 커밋된 결과."""

import pandas as pd

from eval.memo_personas import sample_personas as sp
from eval.memo_personas.common import REPO_ROOT


def ctx(**kw):
    base = {"persona_id": "P", "uuid": "u", "age": 70, "family_type": "배우자와 거주", "marital_status": "배우자있음",
            "has_child": False, "jobless": True, "tenure": "미상", "tenure_basis": "", "averse": False,
            "averse_basis": None, "left_job": False}
    return {**base, **kw}


def test_unemployed_65_plus_defaults_to_retired():
    assert sp.classify_unemployed(70, "평생 살림을 도맡아 온 할머니")[::2] == ("은퇴", "살림 담당")
    assert sp.classify_unemployed(66, "재취업을 위해 일자리를 찾고 있다")[0] == "구직"
    t, _, role = sp.classify_unemployed(40, "38세 전업주부로 살림을 한다")
    assert (t, role) == ("주부", "살림 담당")
    assert sp.classify_unemployed(70, "조용히 지낸다")[2] is None


def test_housing_label_follows_tenure():
    rec = {"invest_style": "배당"}
    assert sp.field_violations("fund_purpose", sp.HOUSING_MOVE, rec, ctx(tenure="미상"))
    assert sp.field_violations("fund_purpose", sp.HOUSING_BUY, rec, ctx(tenure="자가"))
    assert not sp.field_violations("fund_purpose", sp.HOUSING_MOVE, rec, ctx(tenure="자가"))
    assert not sp.field_violations("fund_purpose", sp.HOUSING_BUY, rec, ctx(tenure="임차"))


def test_severance_needs_job_history_for_homemakers():
    rec = {"unemployed_type": "은퇴", "household_role": "살림 담당"}
    assert sp.field_violations("fund_source", "퇴직금", rec, ctx())
    assert not sp.field_violations("fund_source", "퇴직금", rec, ctx(left_job=True))
    assert not sp.field_violations("fund_source", "퇴직금", {"unemployed_type": "은퇴", "household_role": float("nan")}, ctx())


def test_committed_personas_follow_rules():
    p = pd.read_csv(REPO_ROOT / "results/memo_personas/personas_100/personas.csv")
    housing = p[p.fund_purpose.str.startswith("주거 자금")]
    assert ((housing.fund_purpose == sp.HOUSING_MOVE) == (housing.tenure == "자가")).all()
    old_jobless = p[(p.occupation == "무직") & (p.age >= 65)]
    assert old_jobless.unemployed_type.isin(["은퇴", "구직"]).all()
    assert p[p.occupation != "무직"].household_role.isna().all()
