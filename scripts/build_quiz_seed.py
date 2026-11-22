#!/usr/bin/env python3
"""시연용 주식 상식 퀴즈 30문제를 검증해 JSONL과 적재용 SQL로 만든다 (DB 접속 없음).

특정 날짜·종목에 묶이지 않는 기본 상식만 넣는다. 계산 문제의 숫자는 예시다.
실행: .venv/bin/python scripts/build_quiz_seed.py
"""
from __future__ import annotations

import json
import random
from collections import Counter
from itertools import zip_longest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/seed/quiz"
SOURCE = "투자 기초 상식"
CATEGORIES = {"chart": "차트 기초", "trading": "거래 기초", "financials": "재무 기초", "disclosure": "공시 기초"}

items: list[dict] = []


def add(slug, category, question, options, answer, explanation, concept):
    kind = "ox" if options == ["O", "X"] else "four"
    if kind == "four":
        options = list(options)
        random.Random(slug).shuffle(options)
    items.append({
        "slug": slug, "category": category, "quiz_type": kind, "label": CATEGORIES[category],
        "question": question, "options": options, "answer_index": options.index(answer),
        "explanation": explanation, "concept": concept, "source": SOURCE,
    })


def four(slug, category, question, answer, wrong, explanation, concept):
    add(slug, category, question, [answer, *wrong], answer, explanation, concept)


def ox(slug, category, question, truth, explanation, concept):
    add(slug, category, question, ["O", "X"], "O" if truth else "X", explanation, concept)


# ── 차트 ──
four("chart_bullish_candle", "chart", "국내 증권 앱에서 빨간색 캔들(양봉)은 무엇을 뜻할까요?", "종가가 시가보다 높게 끝났다",
     ["종가가 시가보다 낮게 끝났다", "거래량이 평소보다 많았다", "외국인이 주식을 샀다"],
     "양봉은 시작 가격보다 끝 가격이 높을 때 그려져요. 국내 앱은 보통 양봉을 빨간색, 음봉을 파란색으로 보여 줘요.",
     "캔들 하나에는 시가·고가·저가·종가가 모두 담겨 있어요.")
four("chart_upper_wick", "chart", "캔들의 위꼬리 끝은 무엇을 나타낼까요?", "그 기간의 고가",
     ["그 기간의 종가", "그 기간의 시가", "전날 종가"],
     "위꼬리 끝은 고가, 아래꼬리 끝은 저가예요. 몸통은 시가와 종가 사이를 나타내요.",
     "위꼬리가 길면 장중에 올랐던 가격이 다시 밀렸다는 뜻이에요.")
four("chart_ma20", "chart", "20일 이동평균선은 어떻게 만들까요?", "최근 20거래일 종가의 평균을 이은 선",
     ["20일 동안의 최고가를 이은 선", "20일 뒤 예상 가격을 이은 선", "20일 동안의 거래량을 더한 선"],
     "이동평균선은 정해진 기간의 종가 평균을 날마다 다시 계산해 이은 선이에요.",
     "기간이 짧을수록 주가에 민감하고, 길수록 큰 흐름을 보여 줘요.")
four("chart_doji", "chart", "시가와 종가가 거의 같아 몸통이 가로줄처럼 보이는 캔들은?", "도지",
     ["장대양봉", "장대음봉", "갭"],
     "도지는 시작 가격과 끝 가격이 거의 같을 때 나타나요. 위아래 꼬리 길이는 그날 움직임에 따라 달라요.",
     "도지는 사려는 힘과 팔려는 힘이 비슷했던 구간에서 자주 보여요.")
ox("ox_golden_cross", "chart", "골든크로스가 나오면 주가는 반드시 오른다.", False,
   "골든크로스는 과거 가격의 평균이 교차한 모양일 뿐, 앞으로의 상승을 보장하지 않아요.",
   "이동평균선은 이미 지난 가격으로 계산해요.")

# ── 거래 ──
four("trd_ask_price", "trading", "호가창의 매도호가는 무엇일까요?", "팔려는 사람들이 내놓은 가격과 수량",
     ["사려는 사람들이 내놓은 가격과 수량", "어제 마지막으로 거래된 가격", "증권사가 정한 추천 가격"],
     "매도호가는 팔겠다는 주문, 매수호가는 사겠다는 주문이에요. 두 가격이 맞으면 거래가 이뤄져요.",
     "호가창을 보면 지금 어떤 가격에 주문이 쌓여 있는지 알 수 있어요.")
four("trd_market_order", "trading", "시장가 주문의 특징은 무엇일까요?", "가격을 정하지 않고 지금 나와 있는 호가로 체결된다",
     ["내가 정한 가격에만 체결된다", "장이 끝난 뒤 종가로만 체결된다", "다음 거래일 시가로만 체결된다"],
     "시장가 주문은 빨리 체결되는 대신 가격을 정하지 않아요. 거래가 적은 종목은 예상보다 불리한 가격에 체결될 수 있어요.",
     "빠른 체결이 중요하면 시장가, 가격이 중요하면 지정가를 써요.")
four("trd_limit_order", "trading", "지정가 주문의 특징은 무엇일까요?", "정한 가격이나 그보다 유리한 가격에서만 체결된다",
     ["항상 바로 체결된다", "하루가 지나면 시장가로 바뀐다", "가장 불리한 가격으로 체결된다"],
     "지정가 주문은 원하는 가격을 정해 두는 주문이에요. 그 가격까지 오지 않으면 체결되지 않을 수 있어요.",
     "주문을 넣은 것과 체결된 것은 달라요.")
four("trd_market_cap", "trading", "시가총액은 어떻게 계산할까요?", "주가 × 발행주식 수",
     ["매출 × 영업이익률", "주가 × 하루 거래량", "순이익 ÷ 주식 수"],
     "시가총액은 지금 주가로 따진 회사 전체 주식의 값이에요.",
     "1주 가격이 높다고 큰 회사는 아니에요. 회사 크기는 시가총액으로 비교해요.")
four("trd_trade_value", "trading", "거래대금을 구하는 방법으로 가장 알맞은 것은?", "거래된 주식 수 × 거래 가격",
     ["주가 × 발행주식 수", "순이익 ÷ 주식 수", "고가 − 저가"],
     "거래대금은 하루 동안 실제로 오간 금액이에요. 주가 × 발행주식 수는 시가총액이에요.",
     "거래량은 주식 수, 거래대금은 금액이에요.")
four("trd_split", "trading", "주가 100,000원인 종목이 5대 1 액면분할을 하면 이론상 주가는?", "20,000원",
     ["100,000원", "500,000원", "50,000원"],
     "1주가 5주로 나뉘어 가격은 5분의 1이 돼요. 시가총액은 그대로예요.",
     "액면분할은 회사 가치를 바꾸지 않고 1주 가격만 낮춰요.")
four("trd_bonus_issue", "trading", "주가 20,000원인 종목이 1주당 1주 무상증자를 하면 권리락 후 이론 주가는?", "10,000원",
     ["20,000원", "40,000원", "15,000원"],
     "주식 수가 두 배가 되므로 이론 주가는 절반이 돼요.",
     "무상증자는 회사 안의 자본 항목을 옮기는 일이라 회사 가치가 늘지 않아요.")
ox("ox_ex_dividend", "trading", "배당락일에 처음 산 주식으로는 이번 회차 배당을 받을 수 없다.", True,
   "배당락일부터 산 주식은 이번 배당 권리가 없어요.",
   "배당을 받으려면 배당기준일에 주주로 올라 있어야 해요.")
ox("ox_bonus_value", "trading", "무상증자를 하면 회사의 전체 가치가 그만큼 늘어난다.", False,
   "주식 수만 늘고 회사가 가진 자산은 그대로예요.",
   "그래서 권리락 때 주가가 이론적으로 조정돼요.")
ox("ox_short_loss", "trading", "공매도는 주가가 오를수록 손실이 커질 수 있다.", True,
   "빌린 주식을 더 비싸게 사서 갚아야 하므로 주가가 오를수록 손실이 커져요.",
   "매수 손실은 투자금이 한도지만, 공매도 손실은 이론상 한도가 없어요.")

# ── 재무 ──
four("fin_roe_from_per_pbr", "financials", "PER이 10배, PBR이 2배인 기업의 ROE는 약 얼마일까요?", "20%",
     ["5%", "12%", "50%"],
     "ROE는 PBR을 PER로 나눈 값과 같아서 2 ÷ 10 = 20%예요.",
     "PBR = PER × ROE 관계를 알면 세 지표를 함께 읽을 수 있어요.")
four("fin_dilution", "financials", "1,000만 주 회사의 지분 10%를 가진 주주가 250만 주 유상증자에 불참하면 지분율은?", "8%",
     ["10%", "7.5%", "12.5%"],
     "보유 100만 주는 그대로인데 전체가 1,250만 주가 되어 100 ÷ 1,250 = 8%예요.",
     "새 주식이 늘어 기존 주주의 몫이 줄어드는 것을 희석이라고 해요.")
four("fin_retire_eps", "financials", "순이익 100억 원, 1,000만 주 회사가 200만 주를 소각하면 EPS는?", "1,250원",
     ["800원", "1,000원", "1,200원"],
     "주식이 800만 주로 줄어 100억 원 ÷ 800만 주 = 1,250원이에요. 이익이 같아도 1주 몫은 커져요.",
     "EPS는 순이익을 주식 수로 나눈 값이에요.")
four("fin_surprise", "financials", "시장 예상 영업이익이 1,000억 원인데 실제로 1,200억 원이 나왔어요. 예상을 몇 % 넘었을까요?", "20%",
     ["2%", "12%", "120%"],
     "초과분 200억 원을 예상치 1,000억 원으로 나누면 20%예요.",
     "시장 예상치를 크게 넘는 실적을 어닝 서프라이즈라고 불러요.")
four("fin_fx_exporter", "financials", "수출 대금 1,000만 달러를 받는 회사. 원/달러가 1,300원에서 1,400원이 되면 원화 매출은?", "10억 원 증가",
     ["10억 원 감소", "100억 원 증가", "변화 없음"],
     "130억 원에서 140억 원으로 10억 원 늘어요. 다만 원재료를 달러로 사면 비용도 함께 늘 수 있어요.",
     "환율은 수출 매출과 수입 비용에 동시에 영향을 줘요.")
four("fin_pbr_under_one", "financials", "PBR이 1배보다 낮다는 것은 무슨 뜻일까요?", "시가총액이 장부상 순자산보다 작다",
     ["회사가 적자다", "부채가 자산보다 많다", "주가가 반드시 오른다"],
     "PBR은 시가총액을 순자산으로 나눈 값이에요. 1배 미만이면 시장 가격이 장부 가치보다 낮다는 뜻이에요.",
     "저PBR이 곧 저평가는 아니에요. 수익성이 낮아서일 수도 있어요.")
four("fin_dividend_yield", "financials", "주가 40,000원, 주당 배당금 2,000원인 종목의 배당수익률은?", "5%",
     ["2%", "20%", "50%"],
     "2,000 ÷ 40,000 = 5%예요.",
     "배당수익률은 주가가 바뀌면 함께 달라져요.")
four("fin_rate_growth", "financials", "금리가 오를 때 성장주가 특히 부담을 받는다고 하는 이유는?", "먼 미래 이익의 현재 가치가 더 많이 줄어서",
     ["성장주는 배당을 꼭 줘야 해서", "금리가 오르면 매출이 0이 돼서", "거래가 제한돼서"],
     "미래 이익을 지금 가치로 바꿀 때 금리로 할인해요. 이익이 먼 미래에 몰린 기업일수록 영향이 커요.",
     "이 과정을 현금흐름 할인이라고 해요.")
ox("ox_op_profit_net_loss", "financials", "영업이익이 흑자여도 당기순이익은 적자일 수 있다.", True,
   "이자 비용, 환손실, 자산 손상 같은 영업 외 손실이 크면 순이익은 적자가 될 수 있어요.",
   "영업이익은 본업, 순이익은 모든 손익을 반영한 결과예요.")

# ── 공시 ──
four("dis_periodic", "disclosure", "상장사의 정기보고서는 1년에 몇 번 나올까요?", "4번",
     ["1번", "2번", "12번"],
     "사업보고서 1번, 반기보고서 1번, 분기보고서 2번으로 1년에 4번이에요.",
     "정기보고서는 회사의 사업과 재무 상태를 정해진 시기마다 알리는 공시예요.")
four("dis_provisional", "disclosure", "'영업(잠정)실적' 공시의 특징은 무엇일까요?", "정식 보고서 전에 알리는 숫자라 나중에 달라질 수 있다",
     ["감사가 끝난 확정 실적이다", "증권사가 낸 실적 예상치다", "다음 해 목표 실적이다"],
     "잠정실적은 감사나 검토가 끝나기 전의 숫자라 정식 보고서에서 달라질 수 있어요.",
     "실적 발표 시즌에 가장 먼저 확인하게 되는 공시예요.")
four("dis_correction", "disclosure", "공시 제목 앞의 [기재정정]은 무슨 뜻일까요?", "이미 낸 공시의 내용을 고쳐 다시 냈다",
     ["공시가 취소됐다", "실적이 시장 예상을 넘었다", "거래가 정지됐다"],
     "기재정정은 앞서 제출한 공시에서 바뀌거나 잘못된 내용을 고친 거예요. 무엇이 달라졌는지 비교해 보는 게 좋아요.",
     "정정 공시는 변경 전과 변경 후를 나란히 보여 주는 경우가 많아요.")
four("dis_retire", "disclosure", "'주식소각결정' 공시의 뜻은 무엇일까요?", "주식을 없애 발행주식 수를 줄인다",
     ["새 주식을 발행해 자금을 모은다", "주주에게 현금을 나눠 준다", "회사를 둘로 나눈다"],
     "주식 소각은 주식 자체를 없애는 결정이에요. 주식 수가 줄면 1주에 돌아가는 이익 몫이 커질 수 있어요.",
     "자사주를 사기만 하면 다시 팔 수 있지만, 소각하면 그 주식은 사라져요.")
four("dis_subsidiary", "disclosure", "공시 제목 끝의 '(자회사의 주요경영사항)'이 알려 주는 것은?", "공시 내용이 자회사에서 일어난 일이다",
     ["모회사가 직접 결정한 일이다", "자회사가 상장폐지된다", "모회사 주주가 주식을 무상으로 받는다"],
     "자회사에서 생긴 중요한 일을 모회사가 대신 알리는 공시예요. 모회사의 주식 수가 바로 바뀐다는 뜻은 아니에요.",
     "공시 제목의 괄호까지 읽어야 누구의 결정인지 정확히 알 수 있어요.")
four("dis_contract", "disclosure", "'단일판매·공급계약체결' 공시에서 먼저 확인할 내용은?", "계약 금액의 매출 대비 비중과 계약 기간",
     ["공시가 제출된 시각", "공시 담당자의 이름", "계약 상대방 본사의 층수"],
     "공급계약은 금액만 보면 크기를 알기 어려워요. 매출 대비 비중과 기간을 함께 봐야 실적에 미칠 영향을 가늠할 수 있어요.",
     "이 공시는 회사가 큰 수주나 판매 계약을 맺었을 때 나와요.")


def arrange():
    """시연에서 같은 주제가 몰리지 않도록 주제를 번갈아 배치한다."""
    groups = [[i for i in items if i["category"] == c] for c in CATEGORIES]
    ordered = [i for row in zip_longest(*groups) for i in row if i]
    for n, item in enumerate(ordered, 1):
        item["demo_order"] = n
    return ordered


def validate(rows):
    assert len(rows) == 30, len(rows)
    assert len({i["slug"] for i in rows}) == 30
    assert len({i["question"] for i in rows}) == 30
    for i in rows:
        assert len(i["options"]) == (2 if i["quiz_type"] == "ox" else 4), i["slug"]
        assert len(set(i["options"])) == len(i["options"]), i["slug"]
        assert 0 <= i["answer_index"] < len(i["options"]), i["slug"]
        assert all(i[k] for k in ("question", "explanation", "concept", "source")), i["slug"]


def lit(value):
    return "'" + str(value).replace("'", "''") + "'"


def sql(rows):
    columns = "slug, demo_order, category, quiz_type, label, question, options, answer_index, explanation, concept, source"
    values = []
    for i in rows:
        values.append("(" + ", ".join([
            lit(i["slug"]), str(i["demo_order"]), lit(i["category"]), lit(i["quiz_type"]), lit(i["label"]),
            lit(i["question"]), lit(json.dumps(i["options"], ensure_ascii=False)) + "::jsonb", str(i["answer_index"]),
            lit(i["explanation"]), lit(i["concept"]), lit(i["source"])]) + ")")
    updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in columns.split(", ")[1:])
    return ("-- 시연용 주식 상식 퀴즈 30문제. alembic upgrade head(0023) 후 실행. 다시 실행해도 slug 기준으로 갱신된다.\n"
            "-- scripts/build_quiz_seed.py가 생성한 파일이므로 직접 고치지 않는다.\nBEGIN;\n"
            f"INSERT INTO quiz_questions ({columns}) VALUES\n" + ",\n".join(values) +
            f"\nON CONFLICT (slug) DO UPDATE SET {updates}, updated_at = now();\nCOMMIT;\n")


if __name__ == "__main__":
    rows = arrange()
    validate(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "quiz_questions_demo.jsonl").write_text(
        "".join(json.dumps(i, ensure_ascii=False) + "\n" for i in rows), encoding="utf-8")
    (OUT / "quiz_questions_demo.sql").write_text(sql(rows), encoding="utf-8")
    print(len(rows), Counter(i["category"] for i in rows), Counter(i["quiz_type"] for i in rows))
    print("정답 위치", sorted(Counter(i["answer_index"] for i in rows if i["quiz_type"] == "four").items()))
