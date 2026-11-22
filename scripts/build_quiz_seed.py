#!/usr/bin/env python3
"""시연용 오늘의 퀴즈 30문제를 검증해 JSONL과 적재용 SQL로 만든다 (DB 접속 없음).

시세·공시 문제의 정답과 수치는 company_ref.json(2026-11-04 팀 DB 스냅샷)에서 계산한다.
실행: .venv/bin/python scripts/build_quiz_seed.py
"""
from __future__ import annotations

import json
import random
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / "results/memo_personas/memos_kospi/company_ref.json"
OUT = ROOT / "data/seed/quiz"
AS_OF = "2026-11-04"
MARKET_SRC = "출처 · 국내 증시 종가 (2026.11.04 기준)"
BASIC_SRC = "투자 기초 개념 · 계산을 위한 예시 숫자"

companies = json.loads(REF.read_text(encoding="utf-8"))["companies"]
items: list[dict] = []


def add(slug, category, label, question, options, answer, explanation, concept, source,
        as_of=None, source_ref=None):
    kind = "ox" if options == ["O", "X"] else "four"
    if kind == "four":
        options = list(options)
        random.Random(slug).shuffle(options)
    items.append({
        "slug": slug, "demo_order": len(items) + 1, "category": category, "quiz_type": kind,
        "label": label, "question": question, "options": options,
        "answer_index": options.index(answer), "explanation": explanation, "concept": concept,
        "source": source, "source_ref": source_ref, "as_of_date": as_of,
    })


def josa(word, with_final, without_final):
    code = ord(word[-1]) - 0xAC00
    if 0 <= code <= 11171:
        return word + (with_final if code % 28 else without_final)
    return word + with_final


def jo(name):
    return f"{companies[name]['mcap'] / 1e12:.1f}조 원"


def vs(name, field):
    return (companies[name]["close"] / companies[name][field] - 1) * 100


def market(slug, question, names, key, describe, concept):
    winner = max(names, key=key)
    add(slug, "market", "11.04 증시 퀴즈", question, names, winner, describe(winner), concept,
        MARKET_SRC, AS_OF)


def disclosure(slug, name, rcept_no, question, answer, wrong, explanation, concept):
    found = [d for d in companies[name]["disclosures"] if d["rcept_no"] == rcept_no]
    if not found:
        raise ValueError(f"공시 없음: {name} {rcept_no}")
    d = found[0]
    add(slug, "disclosure", "실제 공시 퀴즈",
        f"{josa(name, '이', '가')} {d['rcept_dt'][5:7]}.{d['rcept_dt'][8:]}에 낸 '{d['title']}' 공시. {question}",
        [answer, *wrong], answer, explanation, concept, f"출처 · DART 전자공시 ({d['rcept_dt']})",
        d["rcept_dt"], rcept_no)


# ── 실제 시세 8문제 ──
market("mkt_ship_mcap", "다음 조선주 중 11.04 시가총액이 가장 컸던 곳은?",
       ["HD현대중공업", "한화오션", "삼성중공업", "HD한국조선해양"], lambda n: companies[n]["mcap"],
       lambda w: f"{w}의 시가총액은 약 {jo(w)}으로 보기 중 가장 컸어요.",
       "시가총액은 주가에 발행주식 수를 곱한 값으로, 시장이 매긴 회사 전체의 가격이에요.")
market("mkt_price_vs_mcap", "다음 중 11.04 종가, 즉 1주 가격이 가장 비쌌던 종목은?",
       ["효성중공업", "삼성바이오로직스", "삼성전기", "고려아연"], lambda n: companies[n]["close"],
       lambda w: f"{josa(w, '은', '는')} 1주 {companies[w]['close']:,.0f}원으로 가장 비쌌지만, 시가총액은 {jo(w)}으로 "
                 f"삼성바이오로직스({jo('삼성바이오로직스')})보다 작았어요.",
       "1주 가격이 높다고 큰 회사는 아니에요. 회사 크기는 시가총액으로 비교해요.")
market("mkt_near_high", "다음 중 11.04 종가가 52주 최고가에 가장 가까웠던 종목은?",
       ["KT&G", "HMM", "메리츠금융지주", "삼성화재"], lambda n: vs(n, "high_52w"),
       lambda w: f"{w}의 종가는 52주 최고가보다 {abs(vs(w, 'high_52w')):.1f}% 낮은 수준으로 네 종목 중 가장 가까웠어요.",
       "52주 최고가와의 거리는 지금 주가가 1년 범위에서 어디쯤인지 보여 줘요.")
market("mkt_above_ma20", "다음 중 11.04 종가가 20일 이동평균선보다 가장 높이 있던 종목은?",
       ["삼성바이오로직스", "현대글로비스", "삼성화재", "셀트리온"], lambda n: vs(n, "ma20"),
       lambda w: f"{w}의 종가는 20일 평균보다 {vs(w, 'ma20'):.1f}% 높아 네 종목 중 격차가 가장 컸어요.",
       "이동평균선과의 격차는 최근 평균 가격에서 얼마나 떨어져 있는지 보여 줘요.")
market("mkt_below_ma60", "다음 중 11.04 종가가 60일 이동평균선보다 가장 아래에 있던 종목은?",
       ["HD현대일렉트릭", "HD현대중공업", "한화오션", "두산에너빌리티"], lambda n: -vs(n, "ma60"),
       lambda w: f"{w}의 종가는 60일 평균보다 {abs(vs(w, 'ma60')):.1f}% 낮아 네 종목 중 격차가 가장 컸어요.",
       "60일선은 약 석 달의 평균 가격으로, 중기 흐름을 볼 때 자주 써요.")
market("mkt_bank_mcap", "다음 금융주 중 11.04 시가총액이 가장 컸던 곳은?",
       ["신한지주", "하나금융지주", "우리금융지주", "기업은행"], lambda n: companies[n]["mcap"],
       lambda w: f"{w}의 시가총액은 약 {jo(w)}으로 보기 중 가장 컸어요.",
       "금융지주는 은행·증권·보험 같은 자회사를 거느린 회사예요.")
market("mkt_auto_mcap", "다음 현대차그룹주 중 11.04 시가총액이 가장 컸던 곳은?",
       ["현대차", "기아", "현대모비스", "현대글로비스"], lambda n: companies[n]["mcap"],
       lambda w: f"{w}의 시가총액은 약 {jo(w)}으로 네 곳 중 가장 컸어요.",
       "같은 그룹이어도 완성차·부품·물류처럼 사업이 다르면 주가 흐름도 달라질 수 있어요.")
market("mkt_battery_mcap", "다음 2차전지주 중 11.04 시가총액이 가장 컸던 곳은?",
       ["LG에너지솔루션", "삼성SDI", "포스코퓨처엠", "엘앤에프"], lambda n: companies[n]["mcap"],
       lambda w: f"{w}의 시가총액은 약 {jo(w)}으로 네 곳 중 가장 컸어요.",
       "배터리를 만드는 셀 업체와 소재를 만드는 업체는 같은 테마여도 사업 구조가 달라요.")

# ── 실제 공시 6문제 ──
disclosure("dis_retire", "고려아연", "20261104800484", "이 공시의 뜻은?", "회사가 가진 주식을 없애 주식 수를 줄인다",
           ["새 주식을 발행해 자금을 모은다", "주주에게 현금을 나눠 준다", "회사를 둘로 나눈다"],
           "주식 소각은 주식 자체를 없애는 결정이에요. 주식 수가 줄면 1주에 돌아가는 이익 몫이 커질 수 있어요.",
           "자사주를 사기만 하면 다시 팔 수 있지만, 소각하면 그 주식은 사라져요.")
disclosure("dis_contract", "삼성바이오로직스", "20261103800043", "이 공시에서 먼저 확인할 내용은?",
           "계약 금액과 최근 매출 대비 비중, 계약 기간", ["공시가 제출된 시각", "공시 담당자의 이름", "계약 상대방 본사의 층수"],
           "공급계약은 금액만 보면 크기를 알기 어려워요. 매출 대비 비중과 기간을 함께 봐야 실적에 미칠 영향을 가늠할 수 있어요.",
           "단일판매·공급계약 공시는 회사가 큰 수주나 판매 계약을 맺었을 때 나와요.")
disclosure("dis_buyback", "크래프톤", "20261103000268", "이 공시의 뜻은?", "회사가 시장 등에서 자기 회사 주식을 사기로 했다",
           ["회사가 다른 회사를 인수했다", "대주주가 주식을 모두 팔았다", "회사가 새 주식을 발행했다"],
           "자기주식 취득은 회사 돈으로 자기 주식을 사는 결정이에요. 소각까지 이어지는지는 따로 확인해야 해요.",
           "취득은 회사가 사는 것이고, 처분은 갖고 있던 자사주를 내놓는 거예요.")
disclosure("dis_correction", "LG에너지솔루션", "20261103800087", "제목 앞 [기재정정]의 뜻은?", "이미 낸 공시의 내용을 고쳐 다시 냈다",
           ["실적이 시장 예상을 넘었다", "거래가 정지됐다", "감사 의견이 거절됐다"],
           "기재정정은 앞서 제출한 공시에서 바뀌거나 잘못된 내용을 고친 거예요. 무엇이 달라졌는지 비교해 보는 게 좋아요.",
           "정정 공시는 변경 전과 변경 후를 나란히 보여 주는 경우가 많아요.")
disclosure("dis_subsidiary", "하이브", "20261027800573", "괄호 속 문구가 알려 주는 것은?", "유상증자를 결정한 곳이 하이브의 종속회사다",
           ["하이브 본사가 새 주식을 발행한다", "하이브 주주가 무상으로 주식을 받는다", "하이브가 상장폐지된다"],
           "'종속회사의 주요경영사항'은 자회사에서 일어난 일을 모회사가 알리는 공시예요. 하이브 주식 수가 바로 늘어난다는 뜻은 아니에요.",
           "공시 제목의 괄호까지 읽어야 누구의 결정인지 정확히 알 수 있어요.")
disclosure("dis_disposal", "SK", "20261030000587", "이 공시의 뜻은?", "회사가 갖고 있던 자기주식을 내놓기로 했다",
           ["회사가 자기주식을 새로 사기로 했다", "자기주식을 모두 소각했다", "주주에게 현금 배당을 한다"],
           "자기주식 처분은 보유한 자사주를 시장이나 특정 상대에게 넘기는 결정이에요. 목적과 상대방을 함께 봐야 해요.",
           "같은 자사주 공시라도 취득·처분·소각은 주주에게 갖는 의미가 달라요.")

# ── 계산·개념 16문제 ──
def calc(slug, category, question, answer, wrong, explanation, concept):
    add(slug, category, "투자 개념 퀴즈", question, [answer, *wrong], answer, explanation, concept, BASIC_SRC)


def ox(slug, category, question, truth, explanation, concept):
    add(slug, category, "O/X 투자 퀴즈", question, ["O", "X"], "O" if truth else "X", explanation, concept, BASIC_SRC)


calc("fin_roe_from_per_pbr", "financials", "PER이 10배, PBR이 2배인 기업의 ROE는 약 얼마일까요?", "20%", ["5%", "12%", "50%"],
     "ROE는 PBR을 PER로 나눈 값과 같아서 2 ÷ 10 = 20%예요.", "PBR = PER × ROE 관계를 알면 세 지표를 함께 읽을 수 있어요.")
calc("fin_dilution", "financials", "1,000만 주 회사의 지분 10%를 가진 주주가 250만 주 유상증자에 불참하면 지분율은?", "8%", ["10%", "7.5%", "12.5%"],
     "보유 100만 주는 그대로인데 전체가 1,250만 주가 되어 100 ÷ 1,250 = 8%예요.", "새 주식이 늘어 기존 주주의 몫이 줄어드는 것을 희석이라고 해요.")
calc("fin_retire_eps", "financials", "순이익 100억 원, 1,000만 주 회사가 200만 주를 소각하면 EPS는?", "1,250원", ["800원", "1,000원", "1,200원"],
     "주식이 800만 주로 줄어 100억 원 ÷ 800만 주 = 1,250원이에요. 이익이 같아도 1주 몫은 커져요.", "EPS는 순이익을 주식 수로 나눈 값이에요.")
calc("fin_surprise", "financials", "시장 예상 영업이익이 1,000억 원인데 실제로 1,200억 원이 나왔어요. 예상을 몇 % 넘었을까요?", "20%", ["2%", "12%", "120%"],
     "초과분 200억 원을 예상치 1,000억 원으로 나누면 20%예요.", "시장 예상치를 크게 넘는 실적을 어닝 서프라이즈라고 불러요.")
calc("fin_fx_exporter", "financials", "수출 대금 1,000만 달러를 받는 회사. 원/달러가 1,300원에서 1,400원이 되면 원화 매출은?", "10억 원 증가", ["10억 원 감소", "100억 원 증가", "변화 없음"],
     "130억 원에서 140억 원으로 10억 원 늘어요. 다만 원재료를 달러로 사면 비용도 함께 늘 수 있어요.", "환율은 수출 매출과 수입 비용에 동시에 영향을 줘요.")
calc("fin_pbr_under_one", "financials", "PBR이 1배보다 낮다는 것은 무슨 뜻일까요?", "시가총액이 장부상 순자산보다 작다", ["회사가 적자다", "부채가 자산보다 많다", "주가가 반드시 오른다"],
     "PBR은 시가총액을 순자산으로 나눈 값이에요. 1배 미만이면 시장 가격이 장부 가치보다 낮다는 뜻이에요.", "저PBR이 곧 저평가는 아니에요. 수익성이 낮아서일 수도 있어요.")
calc("fin_dividend_yield", "financials", "주가 40,000원, 주당 배당금 2,000원인 종목의 배당수익률은?", "5%", ["2%", "20%", "50%"],
     "2,000 ÷ 40,000 = 5%예요.", "배당수익률은 주가가 바뀌면 함께 달라져요.")
calc("trd_split", "trading", "주가 100,000원인 종목이 5대 1 액면분할을 하면 이론상 주가는?", "20,000원", ["100,000원", "500,000원", "50,000원"],
     "1주가 5주로 나뉘어 가격은 5분의 1이 돼요. 시가총액은 그대로예요.", "액면분할은 회사 가치를 바꾸지 않고 1주 가격만 낮춰요.")
calc("trd_bonus_issue", "trading", "주가 20,000원인 종목이 1주당 1주 무상증자를 하면 권리락 후 이론 주가는?", "10,000원", ["20,000원", "40,000원", "15,000원"],
     "주식 수가 두 배가 되므로 이론 주가는 절반이 돼요.", "무상증자는 회사 안의 자본 항목을 옮기는 일이라 회사 가치가 늘지 않아요.")
calc("mac_rate_growth", "trading", "금리가 오를 때 성장주가 특히 부담을 받는다고 하는 이유는?", "먼 미래 이익의 현재 가치가 더 많이 줄어서", ["성장주는 배당을 꼭 줘야 해서", "금리가 오르면 매출이 0이 돼서", "거래가 제한돼서"],
     "미래 이익을 지금 가치로 바꿀 때 금리로 할인해요. 이익이 먼 미래에 몰린 기업일수록 영향이 커요.", "이 과정을 현금흐름 할인이라고 해요.")
calc("chart_volume", "trading", "거래대금을 구하는 방법으로 가장 알맞은 것은?", "거래된 주식 수 × 거래 가격", ["주가 × 발행주식 수", "순이익 ÷ 주식 수", "고가 − 저가"],
     "거래대금은 하루 동안 실제로 오간 금액이에요. 주가 × 발행주식 수는 시가총액이에요.", "거래량은 주식 수, 거래대금은 금액이에요.")
ox("ox_op_profit_net_loss", "financials", "영업이익이 흑자여도 당기순이익은 적자일 수 있다.", True,
   "이자 비용, 환손실, 자산 손상 같은 영업 외 손실이 크면 순이익은 적자가 될 수 있어요.", "영업이익은 본업, 순이익은 모든 손익을 반영한 결과예요.")
ox("ox_golden_cross", "trading", "골든크로스가 나오면 주가는 반드시 오른다.", False,
   "골든크로스는 과거 가격의 평균이 교차한 모양일 뿐, 앞으로의 상승을 보장하지 않아요.", "이동평균선은 이미 지난 가격으로 계산해요.")
ox("ox_ex_dividend", "trading", "배당락일에 처음 산 주식으로는 이번 회차 배당을 받을 수 없다.", True,
   "배당락일부터 산 주식은 이번 배당 권리가 없어요.", "배당을 받으려면 배당기준일에 주주로 올라 있어야 해요.")
ox("ox_bonus_value", "trading", "무상증자를 하면 회사의 전체 가치가 그만큼 늘어난다.", False,
   "주식 수만 늘고 회사가 가진 자산은 그대로예요.", "그래서 권리락 때 주가가 이론적으로 조정돼요.")
ox("ox_short_loss", "trading", "공매도는 주가가 오를수록 손실이 커질 수 있다.", True,
   "빌린 주식을 더 비싸게 사서 갚아야 하므로 주가가 오를수록 손실이 커져요.", "매수 손실은 투자금이 한도지만, 공매도 손실은 이론상 한도가 없어요.")


def validate():
    assert len(items) == 30, len(items)
    assert len({i["slug"] for i in items}) == 30
    assert len({i["question"] for i in items}) == 30
    for i in items:
        assert len(i["options"]) == (2 if i["quiz_type"] == "ox" else 4), i["slug"]
        assert len(set(i["options"])) == len(i["options"]), i["slug"]
        assert 0 <= i["answer_index"] < len(i["options"]), i["slug"]
        assert all(i[k] for k in ("question", "explanation", "concept", "source")), i["slug"]


def lit(value):
    return "NULL" if value is None else "'" + str(value).replace("'", "''") + "'"


def sql():
    columns = "slug, demo_order, category, quiz_type, label, question, options, answer_index, explanation, concept, source, source_ref, as_of_date"
    rows = []
    for i in items:
        date = "NULL" if i["as_of_date"] is None else f"DATE '{i['as_of_date']}'"
        rows.append("(" + ", ".join([
            lit(i["slug"]), str(i["demo_order"]), lit(i["category"]), lit(i["quiz_type"]), lit(i["label"]),
            lit(i["question"]), lit(json.dumps(i["options"], ensure_ascii=False)) + "::jsonb", str(i["answer_index"]),
            lit(i["explanation"]), lit(i["concept"]), lit(i["source"]), lit(i["source_ref"]), date]) + ")")
    updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in columns.split(", ")[1:])
    return ("-- 시연용 오늘의 퀴즈 30문제. alembic upgrade head(0023) 후 실행. 다시 실행해도 slug 기준으로 갱신된다.\n"
            "-- scripts/build_quiz_seed.py가 생성한 파일이므로 직접 고치지 않는다.\nBEGIN;\n"
            f"INSERT INTO quiz_questions ({columns}) VALUES\n" + ",\n".join(rows) +
            f"\nON CONFLICT (slug) DO UPDATE SET {updates}, updated_at = now();\nCOMMIT;\n")


if __name__ == "__main__":
    validate()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "quiz_questions_demo.jsonl").write_text(
        "".join(json.dumps(i, ensure_ascii=False) + "\n" for i in items), encoding="utf-8")
    (OUT / "quiz_questions_demo.sql").write_text(sql(), encoding="utf-8")
    print(len(items), Counter(i["category"] for i in items), Counter(i["quiz_type"] for i in items))
    print("정답 위치", sorted(Counter(i["answer_index"] for i in items if i["quiz_type"] == "four").items()))
