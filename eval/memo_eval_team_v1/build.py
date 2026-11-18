"""팀원 작성 문장 판정 평가셋 v1 (메모 30개, 4종목) — 팀원 표를 채점 형식(jsonl)으로 옮긴 것.

원본: 팀원이 작성한 표 (2026-10-23, 기준표 v0.2 기준, 로직을 속이는 함정 포함).
옮기면서 정한 것 (원본과 다른 점은 note_conversion에 남긴다):
- 같은 줄 끝의 ㅋㅋ는 앞 문장에 붙인다 (우리 문장 분리 규칙, WO-021). H08은 원본 2문장 → 1문장.
- [경계] 표시 문장은 원본의 '잠정' 정답을 쓰고 boundary=true로 둔다 (별도 집계).
- N04처럼 기준표에 없는 코드(C6 부정+대상)는 category "-"로 두고 판정만 채점한다.
- 원본 정답이 D-048(관심사가 보이면 추적) 이전 기준인 문장은 원본대로 두고 conflict_d048=true로 표시한다.

    python eval/memo_eval_team_v1/build.py eval/memo_eval_team_v1
"""

import collections
import json
import sys
from pathlib import Path

OUT = Path(sys.argv[1])
DECISION = {"N": "normal", "P": "partial", "F": "full_fallback", "Q": "needs_confirmation"}


def T(desc, keywords, time=None):
    return {"type": "topic", "description": desc, "keywords": keywords, "price_threshold": None, "time_hint": time}


def PB(price):
    return {"type": "price_below", "description": f"{price:,}원 아래로", "keywords": None, "price_threshold": price, "time_hint": None}


def PA(price):
    return {"type": "price_above", "description": f"{price:,}원 위로", "keywords": None, "price_threshold": price, "time_hint": None}


def S(text, d, cat, reason, items=(), *, cleaned=None, flags=(), other=None, ref=None, note=None, merge=None,
      boundary=False, conflict=False, conversion=None):
    return {"text": text, "cleaned_text": cleaned if cleaned is not None else text, "flags": list(flags),
            "decision": DECISION[d], "category": cat, "reason_code": reason, "other_symbol": other,
            "resolved_reference": ref, "items": list(items), "merge_into": merge, "merge_update": None,
            "context_note": note, "suggestion": None, "boundary": boundary, "conflict_d048": conflict,
            "note_conversion": conversion}


MEMOS = [
    # ── 삼성전자 ──
    ("S01", "005930", "근데 HBM4 엔비디아 퀄 통과햇나? 이거 계속 체크해줘", [
        S("근데 HBM4 엔비디아 퀄 통과햇나?", "N", "A4", "QUESTION", [T("HBM4 엔비디아 퀄테스트 결과", ["HBM4", "엔비디아", "퀄테스트"])]),
        S("이거 계속 체크해줘", "N", "A1", "TOPIC", ref="HBM4 엔비디아 퀄테스트", merge={"sentence_index": 0, "item_index": 0}),
    ]),
    ("S02", "005930", "6만전자 오면 줍줍 고민해볼까 ㅋㅋ", [
        S("6만전자 오면 줍줍 고민해볼까 ㅋㅋ", "P", "C1", "USER_ACTION", [PB(60000)], note="줍줍 고민"),
    ]),
    ("S03", "005930", "아니 씨발 외국인 왜 계속 팔아 ㅋㅋ 요즘 수급 어케 되는거야", [
        S("아니 씨발 외국인 왜 계속 팔아 ㅋㅋ", "P", "C2", "EMOTION_MIXED", [T("외국인 순매도 원인", ["외국인", "순매도", "수급"])],
          cleaned="아니 외국인 왜 계속 팔아 ㅋㅋ", flags=["profanity"]),
        S("요즘 수급 어케 되는거야", "N", "A4", "QUESTION", [T("수급 동향", ["수급", "외국인", "기관"])]),
    ]),
    ("S04", "005930", "파운드리 적자 줄어드는지랑 테일러 공장 가동 시점 이 두개는 꼭 봐야함", [
        S("파운드리 적자 줄어드는지랑 테일러 공장 가동 시점 이 두개는 꼭 봐야함", "N", "A1", "TOPIC",
          [T("파운드리 손익", ["파운드리", "적자"]), T("테일러 공장 가동 일정", ["테일러", "공장", "가동"])]),
    ]),
    ("S05", "005930", "하닉이 HBM 다 먹는거 보면 삼전은 확실히 늦은듯. 근데 HBM4부터는 따라잡을 수 있을지가 관건", [
        S("하닉이 HBM 다 먹는거 보면 삼전은 확실히 늦은듯.", "P", "C3", "OTHER_STOCK_MIXED",
          [T("HBM 진행 (SK하이닉스 대비)", ["HBM", "SK하이닉스", "점유율"])], other="000660"),
        S("근데 HBM4부터는 따라잡을 수 있을지가 관건", "N", "A4", "QUESTION", [T("HBM4 경쟁력", ["HBM4", "경쟁력"])]),
    ]),
    ("S06", "005930", "HBM4 양산 들어가면 무조건 8만 간다", [
        S("HBM4 양산 들어가면 무조건 8만 간다", "P", "C4", "PREDICTION_MIXED", [T("HBM4 양산 소식", ["HBM4", "양산"])]),
    ]),
    ("S07", "005930", "어제 6만9천에 10주 물타기함 ㅠㅠ 개쫄리네", [
        S("어제 6만9천에 10주 물타기함 ㅠㅠ", "F", "B2", "PAST_FACT"),
        S("개쫄리네", "F", "B1", "EMOTION", conversion="원본은 '개' 제거를 욕설 정제로 봤으나 어절 단위 정제와 맞지 않아 flags 없이 판정만 채점"),
    ]),
    ("S08", "005930", "하닉 HBM 점유율 얼마나 되는지 확인해봐", [
        S("하닉 HBM 점유율 얼마나 되는지 확인해봐", "P", "C3", "OTHER_STOCK_MIXED",
          [T("HBM 점유율 (경쟁사 대비)", ["HBM", "점유율", "SK하이닉스"])], other="000660", boundary=True),
    ]),
    # ── SK하이닉스 ──
    ("H01", "000660", "엔비디아 실적 잘 나오면 하닉도 같이 가는 구조니까 엔비디아 가이던스 체크. 아님 걍 엔비디아를 사버릴까 ㅋㅋ", [
        S("엔비디아 실적 잘 나오면 하닉도 같이 가는 구조니까 엔비디아 가이던스 체크.", "N", "A5", "HYPOTHESIS",
          [T("엔비디아 가이던스와 HBM 수요", ["엔비디아", "가이던스", "HBM 수요"])]),
        S("아님 걍 엔비디아를 사버릴까 ㅋㅋ", "F", "B5", "OUT_OF_SCOPE"),
    ]),
    ("H03", "000660", "30만 뚫으면 일부 익절, 25만 깨지면 손절 이렇게 가자", [
        S("30만 뚫으면 일부 익절, 25만 깨지면 손절 이렇게 가자", "P", "C1", "USER_ACTION", [PA(300000), PB(250000)],
          note="일부 익절, 손절"),
    ]),
    ("H04", "000660", "D램 고정가 계속 오르는지 매달 봐야됨 ㅇㅇ", [
        S("D램 고정가 계속 오르는지 매달 봐야됨 ㅇㅇ", "N", "A1", "TOPIC", [T("D램 고정거래가격 추이", ["D램", "고정거래가격"], time="매월")]),
    ]),
    ("H05", "000660", "곧 50만닉스 간다 ㅋㅋㅋ", [
        # WO-027 사용자 결정: 목표 가격이 있는 예측은 그 가격 도달 여부를 추적 (숫자 없는 예측만 B8)
        S("곧 50만닉스 간다 ㅋㅋㅋ", "P", "C4", "PREDICTION_MIXED",
          [T("SK하이닉스 주가 50만원 도달 여부", ["SK하이닉스", "주가", "50만원"])],
          conversion="원본 B8 → 사용자 결정으로 목표가 도달 추적"),
    ]),
    ("H06", "000660", "실적때문에 오를듯 ㅇㅇ", [
        S("실적때문에 오를듯 ㅇㅇ", "P", "C4", "PREDICTION_MIXED", [T("실적 추이", ["실적"])], boundary=True),
    ]),
    ("H07", "000660", "52주 신고가 찍으면 알려줘", [
        S("52주 신고가 찍으면 알려줘", "Q", "-", "UNSUPPORTED_CONDITION"),
    ]),
    ("H08", "000660", "아 ㅅㅂ 오늘 -8% 실화냐. ㅋㅋㅋㅋㅋ", [
        S("아 ㅅㅂ 오늘 -8% 실화냐. ㅋㅋㅋㅋㅋ", "F", "B1", "EMOTION", cleaned="아 오늘 -8% 실화냐. ㅋㅋㅋㅋㅋ", flags=["profanity"],
          conversion="원본 2문장(B1, B7) → 같은 줄 끝 ㅋㅋ는 앞 문장에 붙이는 규칙에 따라 1문장"),
    ]),
    # ── NAVER ──
    ("N01", "035420", "네이버 하이퍼클로바X로 돈 버는 구조가 나오긴 하는거야? AI 매출 따로 공개되면 그거 체크", [
        S("네이버 하이퍼클로바X로 돈 버는 구조가 나오긴 하는거야?", "N", "A4", "QUESTION", [T("하이퍼클로바X 수익화", ["하이퍼클로바X", "AI 수익화"])]),
        S("AI 매출 따로 공개되면 그거 체크", "N", "A3", "EVENT", [T("AI 매출 별도 공개", ["AI 매출", "공개"], time="공개 시")]),
    ]),
    ("N02", "035420", "커머스 수수료 올린거 거래액 빠지는지 봐야됨. 쿠팡이랑도 비교", [
        S("커머스 수수료 올린거 거래액 빠지는지 봐야됨.", "N", "A1", "TOPIC", [T("수수료 인상 후 커머스 거래액", ["커머스", "수수료", "거래액"])]),
        S("쿠팡이랑도 비교", "P", "C5", "OUT_OF_SCOPE_MIXED", [T("커머스 경쟁 동향 (쿠팡)", ["쿠팡", "커머스", "경쟁"])]),
    ]),
    ("N03", "035420", "클코야 네이버 요즘 왜이렇게 지지부진함? 20만원대 회복 언제하냐 진짜", [
        S("클코야 네이버 요즘 왜이렇게 지지부진함?", "N", "A4", "QUESTION", [T("주가 부진 원인", ["네이버 주가", "실적", "업황"])],
          cleaned="네이버 요즘 왜이렇게 지지부진함?", flags=["vocative"]),
        S("20만원대 회복 언제하냐 진짜", "N", "A2", "PRICE", [PA(200000)]),
    ]),
    ("N04", "035420", "배당은 쥐꼬리라 관심없고 AI 쪽 capex 얼마나 쓰는지만 보면 됨", [
        S("배당은 쥐꼬리라 관심없고 AI 쪽 capex 얼마나 쓰는지만 보면 됨", "P", "-", "NEGATION_MIXED",
          [T("AI 설비투자 규모", ["AI", "capex", "설비투자"])], conversion="기준표에 없는 C6(부정+대상) 제안 → category 미채점"),
    ]),
    ("N05", "035420", "네이버 지분 관련 공시 뜨면 바로 알려줘 이거 중요함. 알림은 abc1234@naver.com 으로도 보내주고", [
        S("네이버 지분 관련 공시 뜨면 바로 알려줘 이거 중요함.", "N", "A3", "EVENT", [T("지분 관련 공시", ["지분", "공시"])]),
        S("알림은 abc1234@naver.com 으로도 보내주고", "F", "B5", "OUT_OF_SCOPE",
          cleaned="알림은 [이메일] 으로도 보내주고", flags=["pii_masked"]),
    ]),
    ("N06", "035420", "주말에 네이버 사업보고서 AI 부분 정독하기. 웹툰은 이제 관심없음", [
        # WO-028 사용자 결정: 읽겠다는 자료는 그 주제를 추적 (D-048과 일치)
        S("주말에 네이버 사업보고서 AI 부분 정독하기.", "N", "A1", "TOPIC",
          [T("네이버 AI 사업 현황", ["AI", "사업보고서", "하이퍼클로바X"])],
          conversion="원본 B4 → 사용자 결정으로 추적 (D-048)"),
        S("웹툰은 이제 관심없음", "F", "B9", "NEGATION"),
    ]),
    ("N07", "035420", "경영진 진짜 일 안하네 개XX들. 그거 결과 나오면 다시 판단하자", [
        S("경영진 진짜 일 안하네 개XX들.", "Q", "-", "LOW_CONFIDENCE", cleaned="경영진 진짜 일 안하네", flags=["profanity"]),
        # WO-027 사용자 결정: "그거"가 무엇의 결과인지 모호하므로 확인 필요 (WO-026 결정 철회, 원본 정답으로)
        S("그거 결과 나오면 다시 판단하자", "Q", "-", "UNRESOLVED_REF"),
    ]),
    # ── KB금융 ──
    ("K01", "105560", "케이비 NIM 계속 빠지는지랑 금리 인하 속도 같이 봐야될듯", [
        S("케이비 NIM 계속 빠지는지랑 금리 인하 속도 같이 봐야될듯", "N", "A1", "TOPIC",
          [T("NIM 추이", ["NIM", "순이자마진"]), T("금리 인하 경로", ["금리 인하", "기준금리"])]),
    ]),
    ("K02", "105560", "밸류업 공시대로 주주환원율 50% 진짜 맞추는지 매 분기 체크", [
        S("밸류업 공시대로 주주환원율 50% 진짜 맞추는지 매 분기 체크", "N", "A1", "TOPIC",
          [T("주주환원율 이행", ["밸류업", "주주환원율"], time="매 분기")]),
    ]),
    ("K03", "105560", "홍콩 ELS 과징금 확정되면 실적에 얼마나 반영되는지 보기", [
        S("홍콩 ELS 과징금 확정되면 실적에 얼마나 반영되는지 보기", "N", "A3", "EVENT",
          [T("ELS 과징금 확정과 실적 영향", ["홍콩 ELS", "과징금", "실적"])]),
    ]),
    ("K04", "105560", "배당 받으려고 들고있는거니까 단기 등락엔 흔들리지 말자", [
        S("배당 받으려고 들고있는거니까 단기 등락엔 흔들리지 말자", "F", "B3", "PRINCIPLE"),
    ]),
    ("K05", "105560", "KB 9만원 밑으로 빠지면 추매, 근데 CET1 13% 밑이면 그땐 다시 생각해봐야", [
        S("KB 9만원 밑으로 빠지면 추매, 근데 CET1 13% 밑이면 그땐 다시 생각해봐야", "P", "C1", "USER_ACTION",
          [PB(90000), T("CET1 비율 13% 하회", ["CET1", "자본비율"])], note="추매, 재검토"),
    ]),
    ("K06", "105560", "음.. 신한지주가 더 싼거 같기도 하고", [
        S("음.. 신한지주가 더 싼거 같기도 하고", "P", "C3", "OTHER_STOCK_MIXED",
          [T("KB금융·신한지주 밸류에이션 비교", ["신한지주", "밸류에이션", "PBR"])], other="055550",
          conversion="원본 2문장(B7, B10) → 맨 앞 군더더기는 뒤 문장에 붙이는 규칙에 따라 1문장. "
                     "원본 B10 → 사용자 결정으로 비교 추적 (D-048)"),
    ]),
    ("K07", "105560", "리딩방 VIP 무료체험 open.kakao.com/xxxx 010-9876-5432 연락주세요", [
        S("리딩방 VIP 무료체험 open.kakao.com/xxxx 010-9876-5432 연락주세요", "F", "B6", "SPAM",
          cleaned="리딩방 VIP 무료체험 open.kakao.com/xxxx [전화번호] 연락주세요", flags=["pii_masked"]),
    ]),
    ("K08", "105560", "KB 지금 들어가도 됨?", [
        S("KB 지금 들어가도 됨?", "N", "A4", "QUESTION", [T("매수 판단 근거", ["KB금융", "밸류에이션", "실적"])], boundary=True),
    ]),
]


def main():
    rows = []
    for memo_id, symbol, text, sentences in MEMOS:
        pos, out = 0, []
        for i, s in enumerate(sentences):
            start = text.index(s["text"], pos)
            end = start + len(s["text"])
            pos = end
            out.append({"sentence_index": i, "span": [start, end], **s})
            if s["decision"] == "full_fallback":
                assert not s["items"] and not s["merge_into"], (memo_id, i)
        rows.append({"memo_id": memo_id, "persona": "team", "symbol": symbol, "text": text, "sentences": out})
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "memo_eval_team_v1.jsonl").open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    sents = [s for r in rows for s in r["sentences"]]
    stats = {"memos": len(rows), "sentences": len(sents), "items": sum(len(s["items"]) for s in sents),
             "decision": dict(collections.Counter(s["decision"] for s in sents)),
             "boundary": sum(s["boundary"] for s in sents), "conflict_d048": sum(s["conflict_d048"] for s in sents)}
    (OUT / "memo_eval_team_v1_stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(stats, ensure_ascii=False))


if __name__ == "__main__":
    main()
