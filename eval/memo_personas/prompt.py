"""생성 프롬프트 — 1명당 1회 호출로 메모 10개. 슬롯 설계(slots.py)를 그대로 JSON으로 넣는다."""

from __future__ import annotations

import json
import re

from .llm import SLOTS_BEGIN, SLOTS_END

TYPE_GUIDE = {
    "A1": "주제 관찰 — 앞으로 바뀔 수 있는 사업·실적·이슈를 계속 지켜보겠다는 메모",
    "A2": "가격 조건 — 어떤 가격(또는 '고점 근처', '10% 빠지면' 같은 상대 가격)에 닿으면 알고 싶다는 메모",
    "A3": "예정 이벤트 — 실적 발표·공시·배당처럼 앞으로 있을 일을 챙기는 메모",
    "A4": "궁금증 — 왜 그런지, 어떻게 될지 궁금한 점을 적은 메모",
    "A5": "투자 가설 — '~면 ~할 것'이라는 내 가설과 그 근거를 지켜보는 메모",
    "B1": "감정 — 대상 없이 기분만 (이유를 묻지 않는다. '왜'를 쓰지 않는다)",
    "B2": "지난 매매 — 이미 끝난 매수·매도 사실",
    "B3": "원칙 — 내 매매 원칙·다짐",
    "B4": "본인 할 일 — 공부·앱 설정처럼 내가 할 일 (회사 정보를 확인하는 일은 아님)",
    "B5": "범위 밖 — 주식과 상관없는 일상 (배정 기업 이름을 쓰지 않는다)",
    "B6": "광고·스팸 — 리딩방·광고 문구를 붙여 넣은 듯한 메모",
    "B7": "의미 없음 — 'ㅋㅋ', '..' 같은 의미 없는 입력 (기업 이름 없음)",
    "B8": "단순 가격 예측 — 근거도 숫자도 없는 예측 ('곧 간다')",
    "B9": "부정·무관심 — 이 이슈는 신경 안 쓴다는 말",
    "B10": "다른 종목만 — 배정 기업은 말하지 않고 '다른 종목'만 이야기",
    "C1": "조건+행동 — 가격 조건과 내 매매 행동 ('~ 깨지면 조금 더 담기')",
    "C2": "대상+감정 — 회사의 지표·사업 이야기와 내 감정이 섞임",
    "C3": "비교 — 배정 기업을 '다른 종목'과 비교하거나 어느 쪽이 나은지",
    "C4": "예측 — 근거(또는 가격 예시)가 있는 예측",
    "C5": "범위 밖 단어 — 추적할 대상 이야기에 주식과 무관한 말이 섞임",
}
LENGTH_GUIDE = {"짧게": "5~10단어", "보통": "한 문장", "길게": "2~3문장"}

RULES = """[메모 작성 규칙]
- 증권 앱 메모장에 나 혼자 보려고 적는 메모다. 남에게 설명하는 글이 아니다.
- 자기소개 금지: "~로서", "제 투자 목적은", "저는 ~입니다" 같은 말을 쓰지 않는다. 나이·직업·자금 목적은 말투와 관심사로만 드러낸다.
- 계기가 드러나게 쓴다: 슬롯의 trigger(뉴스 보고, 공시 보고, 거래량 터진 거 보고, 지인 말 듣고 등)를 자연스럽게 녹인다.
- 근거는 사람이 기억하는 방식으로 쓴다("52주 신고가 근처", "영업이익 꺾였던데"). memo_hint는 그런 표현의 예시다.
- 숫자를 쓰면 근거(evidence)에 있는 값과 같아야 한다. 반올림은 '7만원대', '3% 넘게'처럼 자연스럽게만.
- 근거에 없는 사실·수치·날짜를 지어내지 않는다. 날짜는 근거에 있는 날짜만 쓰고, 그 밖에는 "지난달", "어제" 같은 상대 표현을 쓴다.
- 가격 조건(A2·C1·C4)은 price_levels의 가격이나 "고점 근처 오면", "10% 빠지면" 같은 상대 표현만 쓴다.
- answerability가 '자료 부족'인 슬롯은 missing_topic을 궁금해하거나 확인하려는 메모다. 그 주제에 대한 사실·숫자를 단정하지 않는다.
- 길이는 슬롯의 length를 따른다: 짧게=5~10단어, 보통=한 문장, 길게=2~3문장. 10개의 길이가 섞여야 한다.
- 기업은 call_names 중 하나로 부른다(첫 번째 우선). 메모마다 같은 이름만 반복하지 말고 섞는다.
  B5·B7·B10은 배정 기업 이름을 쓰지 않는다. B10과 C3는 other_company를 말한다.
- 금지 표현: "분석해 주세요", "종합적으로", "~에 대해 알려주세요". 궁금한 점도 AI에게 시키는 말투가 아니라 혼잣말로 쓴다.
- 오타는 일부러 넣지 않는다(나중에 따로 넣는다). 반말·ㅋㅋ·말줄임표는 '표현 선호'를 따른다.
- 같은 사람의 메모 10개가 같은 문장 틀로 반복되지 않게 한다.
[좋은 예] 하닉 지난달 거래량 터진 날 hbm 기사 같이 나왔던데 다음 실적에 찍히는지 보기
[좋은 예] kb 배당 보고 산건데 반기보고서에 주주환원 얘기 더 있나 확인
[나쁜 예] SK하이닉스의 HBM 사업 전망과 주가 흐름을 종합적으로 분석해 주세요.
"""


def first_sentences(text: str | None, n: int) -> str:
    if not text:
        return ""
    parts = re.split(r"(?<=다\.)\s+", text.strip())
    return " ".join(parts[:n])


def persona_block(p: dict) -> str:
    nem = p.get("nemotron") or {}
    job = p["occupation"] + (f" ({p['unemployed_type']}" + (", 살림 담당" if p.get("household_role") else "") + ")"
                             if p.get("unemployed_type") else "")
    yn = lambda b: "예" if b else "아니오"  # noqa: E731
    interest = ", ".join(f"{c}({s})" for c, s in (p.get("interest_statuses") or {}).items()) or "없음"
    return "\n".join([
        "[나는 이런 사람이다 — 메모에 직접 쓰지 말고 말투·관심사로만 반영]",
        f"- {p['age']}세 {p['sex']}, {p['province_full']} 거주, 직업: {job}, 가족: {p['family_type']}",
        f"- 투자 경력 {p['experience_years']}년({p['experience_band']}), 방식 {p['invest_style']}, 성향 {p['risk_profile']}, "
        f"기간 {p['investment_horizon']}",
        f"- 자금 목적 {p['fund_purpose']}, 자금 원천 {p['fund_source']}, 정보는 주로 {p['info_source']}, "
        f"요즘 알고 싶은 것 {', '.join(p['learning_interest'])}",
        f"- 종목: 대표 {p['primary_company']}({p['primary_status']}), 관심 {interest}",
        f"- 표현 선호: 반말 {yn(p['w_banmal'])}, ㅋㅋ {yn(p['w_laugh'])}, 말줄임표 {yn(p['w_ellipsis'])}, 평소 길이 {p['w_length']}",
        f"- 원본 인물 설명(참고): {first_sentences(nem.get('persona'), 1)} {first_sentences(nem.get('professional_persona'), 1)}",
    ])


def slot_payload(person: dict, design: dict, items: dict[str, dict]) -> dict:
    slots = []
    for s in design["slots"]:
        ev = [{"ids": items[k]["ids"][:3], "text": items[k]["text"], "memo_hint": items[k]["memo_hint"]}
              for k in s["evidence_keys"]]
        rec = {"slot": s["slot"], "target_company": s["target_company"], "call_names": s["call_names"],
               "sentence_type": s["sentence_type"], "type_guide": TYPE_GUIDE[s["sentence_type"]],
               "trigger": s["trigger"], "length": f"{s['length']}({LENGTH_GUIDE[s['length']]})",
               "answerability": s["answerability"], "evidence": ev}
        for k in ("missing_topic", "price_levels", "other_company"):
            if s.get(k):
                rec[k] = s[k]
        slots.append(rec)
    return {"persona_id": person["persona_id"], "slots": slots}


def build_prompt(person: dict, design: dict, items: dict[str, dict], feedback: list[str] | None = None) -> str:
    payload = slot_payload(person, design, items)
    lines = [
        "너는 아래 사람이 되어, 증권 앱 메모장에 혼자 적는 짧은 메모 10개를 쓴다.",
        "",
        persona_block(person),
        "",
        RULES,
        "[슬롯] 슬롯마다 메모 1개. 기업·문장 유형·계기·길이·근거는 코드가 정했으니 그대로 따른다.",
        SLOTS_BEGIN,
        "{" + f'"persona_id": {json.dumps(payload["persona_id"])}, "slots": [\n'
        + ",\n".join(json.dumps(x, ensure_ascii=False) for x in payload["slots"]) + "\n]}",
        SLOTS_END,
        "",
        '[출력] JSON 하나: {"memos": [{"slot": 슬롯 번호, "memo_text": "메모"}]} — 슬롯 10개 모두, 번호는 그대로.',
    ]
    if feedback:
        lines += ["", "[이전 응답에서 고쳐야 할 점 — 이번에는 지킨다]"] + [f"- {f}" for f in feedback[:12]]
    return "\n".join(lines)
