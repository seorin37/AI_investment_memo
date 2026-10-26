"""문장 판정 평가용 메모 30개 (기준표 v0.2 정답 포함) 생성기.

출력: memo_eval_v0.jsonl (메모 1개 = 1줄), memo_eval_v0_review.md (검수용 표), 통계 출력.
"""

import collections
import json
import sys
from pathlib import Path

OUT = Path(sys.argv[1])

PERSONAS = {
    "P1": "대학생 입문자 (20대, 구어체·줄임말·오타)",
    "P2": "직장인 단타 (30대, 줄임말·비속어 섞임)",
    "P3": "배당·안정 투자자 (50대, 차분한 존댓말)",
    "P4": "반도체 성장주 투자자 (30대, 업계 용어)",
    "P5": "가치투자 숙련자 (40대, 회계 용어)",
    "P6": "은퇴자·리스크 점검형 (60대, 규제·소송 관심)",
}

DECISION = {"N": "normal", "P": "partial", "F": "full_fallback", "Q": "needs_confirmation"}


def T(desc, keywords, time=None):
    return {"type": "topic", "description": desc, "keywords": keywords, "price_threshold": None, "time_hint": time}


def PB(price):
    return {"type": "price_below", "description": f"{price:,}원 아래로", "keywords": None, "price_threshold": price, "time_hint": None}


def PA(price):
    return {"type": "price_above", "description": f"{price:,}원 위로", "keywords": None, "price_threshold": price, "time_hint": None}


def S(text, d, cat, reason, items=(), *, cleaned=None, flags=(), other=None, ref=None,
      note=None, merge=None, merge_update=None, suggest=None):
    return {
        "text": text,
        "cleaned_text": cleaned if cleaned is not None else text,
        "flags": list(flags),
        "decision": DECISION[d],
        "category": cat,
        "reason_code": reason,
        "other_symbol": other,
        "resolved_reference": ref,
        "items": list(items),
        "merge_into": merge,            # {"sentence_index", "item_index"}: 앞 문장 항목에 합침
        "merge_update": merge_update,   # 합칠 때 더하는 정보 (time_hint 등)
        "context_note": note,
        "suggestion": suggest,          # 확인 필요·다른 종목일 때 사용자에게 보일 제안
    }


MEMOS = [
    # ── P1 대학생 입문자 ──
    ("M01", "P1", "005930", " ", [
        S("삼전 첨 사봄 ㅎㅎ", "F", "B2", "PAST_FACT"),
        S("HBM이 뭔지 모르겠는데 이거 때문에 오른다는 듯", "P", "C4", "PREDICTION_MIXED",
          [T("HBM 관련 소식", ["HBM", "고대역폭메모리"])]),
        S("HBM 관련 뉴스 나오면 알려줘", "N", "A1", "TOPIC", merge={"sentence_index": 1, "item_index": 0}),
        S("ㅋㅋㅋㅋ", "F", "B7", "MEANINGLESS"),
    ]),
    ("M02", "P1", "035420", " ", [
        S("네이버 웹툰 요즘 인기 많던데 실적에도 도움 되나?", "N", "A4", "QUESTION",
          [T("웹툰 사업의 실적 기여", ["네이버웹툰", "웹툰 매출", "콘텐츠 부문"])]),
        S("그거 이번 분기 실적 나오면 확인해봐야지", "N", "A3", "EVENT", ref="웹툰 사업의 실적 기여",
          merge={"sentence_index": 0, "item_index": 0}, merge_update={"time_hint": "이번 분기 실적 발표"}),
        S("용돈 아껴서 10주 더 모으기", "F", "B4", "SELF_TODO"),
    ]),
    ("M03", "P1", "000660", " ", [
        S("하닉 40만 넘으면 반 팔자", "P", "C1", "USER_ACTION", [PA(400000)], note="반 팔자"),
        # WO-023: 남의 예측을 확인하려는 말은 그 근거를 추적 (사용자 판단)
        S("친구가 하닉은 무조건 간다는데 ㄹㅇ?", "N", "A4", "QUESTION",
          [T("SK하이닉스 주가 상승 근거", ["SK하이닉스", "주가", "실적 전망"])]),
        S("주말에 유튜브로 반도체 공부하기", "F", "B4", "SELF_TODO"),
    ]),
    ("M20", "P1", "000660", " ", [
        # WO-023 원칙 변경: 비교·선호가 드러나면 비교를 추적한다 (사용자 판단)
        S("삼전이 더 싸 보이는데 갈아탈까", "P", "C3", "OTHER_STOCK_MIXED",
          [T("삼성전자 대비 밸류에이션 비교", ["삼성전자", "밸류에이션", "PER", "PBR"])], other="005930",
          note="갈아탈까", suggest="삼성전자 메모를 만들까요?"),
        S("하닉은 일단 들고 있기", "F", "B4", "SELF_TODO"),
        S("음..", "F", "B7", "MEANINGLESS"),
    ]),
    ("M28", "P1", "105560", " ", [
        # WO-024: 비교 질문은 비교를 추적 (사용자 결정)
        S("KB랑 신한 중에 뭐가 나음?", "P", "C3", "OTHER_STOCK_MIXED",
          [T("KB금융·신한지주 비교", ["KB금융", "신한지주", "실적 비교"])], other="055550",
          suggest="신한지주 메모를 만들까요?"),
        S("배당 많이 주는 쪽이 좋을 듯", "P", "C3", "OTHER_STOCK_MIXED",
          [T("KB금융·신한지주 배당 비교", ["배당", "주당배당금", "신한지주"])], other="055550"),
    ]),
    # ── P2 직장인 단타 ──
    ("M04", "P2", "005930", " ", [
        # "~냐" 뒤에서 문장이 끝난다 (WO-021: 문장부호 없는 문장 끝 표현 분리). 두 번째 문장은 같은 대상이라 합친다.
        S("씨발 클코야 삼성전자 왜케 안 오르냐", "P", "C2", "EMOTION_MIXED",
          [T("주가 부진 원인과 최근 업황", ["삼성전자 주가", "실적", "업황", "수급"])],
          cleaned="삼성전자 왜케 안 오르냐", flags=["profanity", "vocative"]),
        S("요즘 뭐 상황 안좋아?", "N", "A4", "QUESTION", merge={"sentence_index": 0, "item_index": 0}),
        S("ㅅㅂ 7만 깨지면 손절함", "P", "C1", "USER_ACTION", [PB(70000)],
          cleaned="7만 깨지면 손절함", flags=["profanity"], note="손절함"),
        S("개빡치네 진짜", "F", "B7", "MEANINGLESS", cleaned="진짜", flags=["profanity"]),
    ]),
    ("M05", "P2", "035420", " ", [
        S("네이버 오늘 3% 먹고 나옴", "F", "B2", "PAST_FACT"),
        S("다음 주 실적발표 전에 다시 들어갈지 고민", "P", "C1", "USER_ACTION",
          [T("분기 실적 발표", ["네이버 실적", "잠정실적", "실적발표"], time="다음 주")], note="다시 들어갈지 고민"),
        S("리딩방 무료입장 010-1234-5678", "F", "B6", "SPAM",
          cleaned="리딩방 무료입장 [전화번호]", flags=["pii_masked"]),
    ]),
    ("M06", "P2", "000660", " ", [
        S("하닉 거래량 터지면 바로 알려줘", "Q", "-", "UNSUPPORTED_CONDITION",
          suggest="거래량 급증 조건은 아직 지원하지 않아요. SK하이닉스 관련 소식 추적으로 대신할까요?"),
        S("ㅅㅂ 오늘 장 최악", "F", "B1", "EMOTION", cleaned="오늘 장 최악", flags=["profanity"]),
        S("비트코인이나 할까", "F", "B5", "OUT_OF_SCOPE"),
    ]),
    ("M22", "P2", "005930", " ", [
        S("비트코인 오르니까 반도체 수요도 늘 듯", "P", "C5", "OUT_OF_SCOPE_MIXED",
          [T("반도체 수요 변화", ["반도체 수요", "메모리 수요"])]),
        S("근데 코인은 안 함", "F", "B9", "NEGATION"),
        S("52주 신저가 오면 알려줘", "Q", "-", "UNSUPPORTED_CONDITION",
          suggest="52주 신저가 조건은 아직 지원하지 않아요. 가격을 정해 주시면 추적할게요."),
    ]),
    ("M25", "P2", "035420", " ", [
        S("naver 웹툰 MAU 체크ㄱㄱ", "N", "A1", "TOPIC", [T("웹툰 MAU 추이", ["네이버웹툰", "MAU", "이용자 수"])]),
        S("떡상 가즈아", "F", "B8", "PRICE_GUESS"),
        S("ㅋㅋ", "F", "B7", "MEANINGLESS"),
    ]),
    # ── P3 배당·안정 투자자 ──
    ("M07", "P3", "105560", " ", [
        S("KB금융 배당성향 올린다고 했는데 실제로 지켜지는지 확인하고 싶습니다.", "N", "A1", "TOPIC",
          [T("배당성향·주주환원 정책 이행", ["배당성향", "주주환원", "밸류업"])]),
        S("분기배당 금액이 발표되면 작년과 비교해 보겠습니다.", "N", "A3", "EVENT",
          [T("분기 배당 금액", ["분기배당", "주당배당금"], time="분기 배당 발표 시")]),
        S("자사주 소각도 같이 보고요.", "N", "A1", "TOPIC", [T("자사주 매입·소각", ["자사주", "소각"])]),
        S("급하게 사고팔지 않기로 했습니다.", "F", "B3", "PRINCIPLE"),
    ]),
    ("M08", "P3", "005930", " ", [
        # WO-023: 감상이어도 관심 대상(배당)이 분명하면 추적 (사용자 판단)
        S("삼성전자 배당은 꾸준해서 좋네요.", "P", "C2", "EMOTION_MIXED",
          [T("삼성전자 배당 지속성", ["배당", "주당배당금", "주주환원"])]),
        S("다만 반도체 부진이 길어지면 배당이 줄어들 수 있는지 궁금합니다.", "N", "A4", "QUESTION",
          [T("반도체 실적과 배당 여력", ["반도체 실적", "배당", "주주환원"])]),
        S("6만 5천에서 7만 사이에서 조금씩 더 모으려 합니다.", "Q", "-", "UNSUPPORTED_CONDITION",
          note="조금씩 더 모으려 함", suggest="65,000원 아래, 70,000원 위 두 가지 가격 알림으로 만들까요?"),
    ]),
    ("M09", "P3", "105560", " ", [
        # WO-023: 결과가 아직 안 나온 일은 지난 일이 아니라 추적 대상
        S("금감원 정기검사가 연장됐다는 기사를 봤습니다.", "N", "A1", "TOPIC",
          [T("금감원 정기검사 결과와 제재", ["금융감독원", "정기검사", "제재"])]),
        S("결과에 따라 제재가 나오는지 지켜보겠습니다.", "N", "A1", "TOPIC", ref="금감원 정기검사",
          merge={"sentence_index": 0, "item_index": 0}),
        S("은행주는 원래 변동성이 작아서 마음이 편하네요.", "F", "B1", "EMOTION"),
    ]),
    ("M23", "P3", "000660", " ", [
        S("지금보다 10% 빠지면 조금 더 사겠습니다.", "Q", "-", "UNSUPPORTED_CONDITION",
          note="조금 더 사겠습니다", suggest="작성 시점 종가 기준 10% 아래 가격으로 알림을 만들까요?"),
        S("실적 발표일 일정도 알려주세요.", "N", "A3", "EVENT", [T("실적 발표 일정", ["실적발표", "잠정실적", "IR"])]),
        S("건강이 최고입니다.", "F", "B5", "OUT_OF_SCOPE"),
    ]),
    ("M30", "P3", "005930", "\n", [
        S("[ ] 배당 기준일 확인", "N", "A3", "EVENT", [T("배당 기준일", ["배당기준일", "배당"])]),
        S("[x] 증권사 계좌 개설", "F", "B4", "SELF_TODO"),
        # WO-023: 자료를 읽겠다는 말은 그 주제에 관심이 있다는 뜻 → 추적
        S("[ ] 사업보고서 위험요소 읽어보기", "N", "A1", "TOPIC",
          [T("사업보고서 위험요소 변화", ["위험요소", "사업보고서", "소송", "우발부채"])]),
    ]),
    # ── P4 반도체 성장주 투자자 ──
    ("M10", "P4", "000660", " ", [
        S("HBM4 엔비디아 퀄 통과 여부", "N", "A1", "TOPIC", [T("HBM4 엔비디아 품질 인증", ["HBM4", "엔비디아", "퀄테스트"])]),
        S("CAPEX 가이던스 상향되면 장비주도 같이 볼 것", "P", "C3", "OTHER_STOCK_MIXED",
          [T("설비투자 가이던스 변화", ["CAPEX", "설비투자", "가이던스"])], note="장비주도 같이 볼 것"),
        S("D램 현물가 반등 시그널 체크", "N", "A1", "TOPIC", [T("D램 현물 가격 추이", ["D램", "현물가", "DRAM 가격"])]),
        S("그리고 솔리다임 IPO 얘기도", "N", "A1", "TOPIC", [T("솔리다임 IPO", ["솔리다임", "IPO", "상장"])]),
    ]),
    ("M11", "P4", "005930", " ", [
        S("파운드리 2나노 수율 이슈랑 테슬라 수주 건 둘 다 체크", "N", "A1", "TOPIC",
          [T("파운드리 2나노 수율", ["파운드리", "2나노", "수율"]), T("테슬라 파운드리 수주", ["테슬라", "수주", "파운드리"])]),
        S("하닉 대비 HBM 점유율 격차 줄어드는지", "P", "C3", "OTHER_STOCK_MIXED",
          [T("HBM 점유율 (SK하이닉스 대비)", ["HBM", "점유율", "SK하이닉스"])], other="000660"),
        S("엔비디아 실적 발표 때 메모리 코멘트 나오면 같이 보기", "N", "A3", "EVENT",
          [T("엔비디아 실적 발표의 메모리 관련 언급", ["엔비디아", "실적발표", "메모리"], time="엔비디아 실적 발표 시")]),
    ]),
    ("M12", "P4", "000660", " ", [
        S("AI 서버 증설이 계속되는 한 HBM 수요는 꺾이기 어렵다고 봄", "N", "A5", "HYPOTHESIS",
          [T("AI 서버 증설과 HBM 수요", ["AI 서버", "HBM 수요", "데이터센터"])]),
        S("근데 중국 메모리 업체 증설은 리스크", "N", "A1", "TOPIC", [T("중국 메모리 업체 증설", ["CXMT", "중국 메모리", "증설"])]),
        S("이 논리 깨지면 미련 없이 정리", "P", "C1", "USER_ACTION", ref="AI 서버 증설과 HBM 수요",
          merge={"sentence_index": 0, "item_index": 0}, note="논리 깨지면 정리"),
    ]),
    ("M19", "P4", "005930", "\n", [
        S("- HBM3E 엔비디아 공급 비중", "N", "A1", "TOPIC", [T("HBM3E 엔비디아 공급 비중", ["HBM3E", "엔비디아", "공급"])]),
        S("- 파운드리 적자 축소", "N", "A1", "TOPIC", [T("파운드리 적자 규모", ["파운드리", "적자", "영업손실"])]),
        S("- 7만 돌파 시 알림", "N", "A2", "PRICE", [PA(70000)]),
    ]),
    ("M29", "P4", "035420", " ", [
        S("4분기 실적에서 커머스 수수료율 인상 효과 나오는지, 나오면 20만 넘을 듯", "P", "C4", "PREDICTION_MIXED",
          [T("커머스 수수료율 인상 효과", ["커머스", "수수료율", "스마트스토어"], time="4분기 실적 발표")]),
        S("20만 넘으면 일부 차익실현", "P", "C1", "USER_ACTION", [PA(200000)], note="일부 차익실현"),
    ]),
    # ── P5 가치투자 숙련자 ──
    ("M13", "P5", "005930", " ", [
        S("재고자산 평가충당금 증감 추이 확인", "N", "A1", "TOPIC",
          [T("재고자산 평가충당금 추이", ["재고자산", "평가충당금", "재고"])]),
        S("연결 기준 영업현금흐름 대비 CAPEX 비율도.", "N", "A1", "TOPIC",
          [T("영업현금흐름 대비 설비투자 비율", ["영업활동현금흐름", "CAPEX", "설비투자"])]),
        S("PBR 1배 근처면 분할 매수", "Q", "-", "UNSUPPORTED_CONDITION", note="분할 매수",
          suggest="PBR 조건은 아직 지원하지 않아요. 해당 가격을 정해 주시면 가격 알림으로 만들게요."),
        S("남들 공포일 때 사는 게 원칙", "F", "B3", "PRINCIPLE"),
    ]),
    ("M14", "P5", "035420", " ", [
        S("커머스 부문 거래액 성장률이 둔화되는지 본다", "N", "A1", "TOPIC",
          [T("커머스 거래액 성장률", ["커머스", "거래액", "GMV"])]),
        S("AI 투자로 영업이익률이 얼마나 깎이는지가 관건", "N", "A1", "TOPIC",
          [T("AI 투자비와 영업이익률", ["AI 투자", "영업이익률", "인프라 비용"])]),
        S("작년 사업보고서 주석의 우발부채 항목도 재확인", "N", "A1", "TOPIC",
          [T("우발부채·소송 변화", ["우발부채", "소송", "약정사항"])]),
    ]),
    ("M15", "P5", "105560", " ", [
        S("NIM 하락 속도와 대손충당금 전입액 추이", "N", "A1", "TOPIC",
          [T("순이자마진(NIM) 추이", ["NIM", "순이자마진"]), T("대손충당금 전입액 추이", ["대손충당금", "충당금 전입"])]),
        S("CET1 비율 13% 아래로 내려가면 주주환원 축소 가능성", "N", "A5", "HYPOTHESIS",
          [T("CET1 비율과 주주환원 여력", ["CET1", "보통주자본비율", "주주환원"])]),
        S("PER 5배는 너무 싼 거 아닌가 싶음", "N", "A4", "QUESTION",
          [T("밸류에이션(PER) 저평가 원인", ["PER", "밸류에이션", "저평가"])]),
    ]),
    ("M21", "P5", "035420", " ", [
        S("그거 결과 나오면 꼭 확인", "Q", "-", "UNRESOLVED_REF", suggest="어떤 결과를 추적할지 알려 주세요."),
        S("배당은 신경 안 씀", "F", "B9", "NEGATION"),
        S("검색 점유율이 AI 검색 때문에 떨어지는지가 핵심", "N", "A1", "TOPIC",
          [T("검색 점유율과 AI 검색 영향", ["검색 점유율", "AI 검색", "생성형 AI"])]),
    ]),
    ("M26", "P5", "005930", " ", [
        S("메모리 업황 회복, 파운드리 고객 확보, 그리고 갤럭시 판매량까지 세 가지는 분기마다 확인하고 싶다", "N", "A1", "TOPIC",
          [T("메모리 업황 회복", ["메모리", "업황", "D램 가격"], time="분기마다"),
           T("파운드리 고객 확보", ["파운드리", "고객", "수주"], time="분기마다"),
           T("갤럭시 판매량", ["갤럭시", "스마트폰 판매", "MX"], time="분기마다")]),
        S("작년에 너무 일찍 팔아서 후회했다", "F", "B1", "EMOTION"),
    ]),
    # ── P6 은퇴자·리스크 점검형 ──
    ("M16", "P6", "035420", " ", [
        S("라인야후 지분 문제 정리되는지 계속 봐야겠다", "N", "A1", "TOPIC",
          [T("라인야후 지분 문제", ["라인야후", "지분", "A홀딩스"])]),
        S("일본 정부 행정지도 관련 소식 나오면 바로", "N", "A1", "TOPIC",
          merge={"sentence_index": 0, "item_index": 0}, merge_update={"keywords_add": ["일본 총무성", "행정지도"]}),
        S("손주 학자금은 건드리지 말자", "F", "B3", "PRINCIPLE"),
    ]),
    ("M17", "P6", "105560", " ", [
        S("홍콩 ELS 배상 관련 충당금 추가로 쌓는지", "N", "A1", "TOPIC",
          [T("홍콩 ELS 배상 충당금", ["홍콩 ELS", "배상", "충당금"])]),
        S("배상 끝나면 그때 비중 늘리기", "P", "C1", "USER_ACTION", ref="홍콩 ELS 배상",
          merge={"sentence_index": 0, "item_index": 0}, note="배상 끝나면 비중 늘리기"),
        S("요즘 무릎이 아파서 병원 다녀옴", "F", "B5", "OUT_OF_SCOPE"),
    ]),
    ("M18", "P6", "005930", " ", [
        S("이재용 회장 재판 결과", "N", "A1", "TOPIC", [T("경영진 재판·사법 리스크", ["이재용", "재판", "사법 리스크"])]),
        S("노조 파업 다시 하는지도", "N", "A1", "TOPIC", [T("노조 파업", ["노조", "파업", "임단협"])]),
        S("무슨 일 생기면 전화 010-9876-5432로 아들한테 물어보기", "F", "B4", "SELF_TODO",
          cleaned="무슨 일 생기면 전화 [전화번호]로 아들한테 물어보기", flags=["pii_masked"]),
    ]),
    ("M24", "P6", "105560", " ", [
        S("KB 주주환원 정책 보기", "N", "A1", "TOPIC", [T("주주환원 정책", ["주주환원", "배당", "밸류업"])]),
        S("주주환원 확대 발표 나오면 체크", "N", "A3", "EVENT",
          merge={"sentence_index": 0, "item_index": 0}, merge_update={"time_hint": "주주환원 확대 발표 시"}),
        S("자사주 소각 규모도", "N", "A1", "TOPIC", [T("자사주 소각 규모", ["자사주", "소각"])]),
    ]),
    ("M27", "P6", "000660", " ", [
        S("카톡 오픈채팅 고수익 보장 링크 http://bit.ly/xxxx", "F", "B6", "SPAM"),
        S("솔리다임 매각설은 계속 볼 것", "N", "A1", "TOPIC", [T("솔리다임 매각설", ["솔리다임", "매각"])]),
    ]),
    # ── WO-021: 줄바꿈·문장부호 없이 한 줄로 이어 쓴 메모 (실제 사용자 습관) ──
    ("M31", "P2", "005930", "flat", [
        S("씨발 클코야 삼성전자 왜케 안 오르냐", "P", "C2", "EMOTION_MIXED",
          [T("주가 부진 원인과 최근 업황", ["삼성전자 주가", "실적", "업황", "수급"])],
          cleaned="삼성전자 왜케 안 오르냐", flags=["profanity", "vocative"]),
        S("요즘 뭐 상황 안좋아", "N", "A4", "QUESTION", merge={"sentence_index": 0, "item_index": 0}),
        # 같은 줄 끝의 ㅋㅋㅋ는 앞 문장에 붙는다 (군더더기는 판정에 영향 없음, 카드 메모에서는 뗌)
        S("ㅅㅂ 7만 깨지면 손절함 ㅋㅋㅋ", "P", "C1", "USER_ACTION", [PB(70000)],
          cleaned="7만 깨지면 손절함 ㅋㅋㅋ", flags=["profanity"], note="손절함"),
    ]),
    ("M32", "P1", "000660", "flat", [
        S("하닉 HBM 실적 계속 보고 싶음", "N", "A1", "TOPIC", [T("HBM 실적 변화", ["HBM", "실적"])]),
        S("40만 넘으면 반 팔자", "P", "C1", "USER_ACTION", [PA(400000)], note="반 팔자"),
        S("친구가 무조건 간다는데 ㄹㅇ", "N", "A4", "QUESTION",
          [T("SK하이닉스 주가 상승 근거", ["SK하이닉스", "주가", "실적 전망"])]),
    ]),
    ("M33", "P3", "035420", "flat", [
        S("네이버 커머스 거래액이 줄어드는지 궁금합니다", "N", "A4", "QUESTION",
          [T("커머스 거래액 추이", ["커머스", "거래액", "GMV"])]),
        S("배당은 크게 신경 쓰지 않습니다", "F", "B9", "NEGATION"),
        S("분기 실적이 나오면 확인하겠습니다", "N", "A3", "EVENT",
          [T("분기 실적 발표", ["분기 실적", "실적발표"], time="분기 실적 발표 시")]),
    ]),
    ("M34", "P6", "105560", "flat", [
        S("KB 홍콩 ELS 충당금 더 쌓는지 봐야 함", "N", "A1", "TOPIC", [T("홍콩 ELS 배상 충당금", ["홍콩 ELS", "충당금"])]),
        S("손주 용돈은 따로 모으자", "F", "B4", "SELF_TODO"),
        S("날씨가 추워짐", "F", "B5", "OUT_OF_SCOPE"),
    ]),
    ("M35", "P4", "005930", "flat", [
        S("파운드리 2나노 수율이랑 HBM4 공급 둘 다 체크", "N", "A1", "TOPIC",
          [T("파운드리 2나노 수율", ["파운드리", "2나노", "수율"]), T("HBM4 공급", ["HBM4", "공급"])]),
        S("7만 원 밑으로 가면 추가 매수 고민 음", "P", "C1", "USER_ACTION", [PB(70000)], note="추가 매수 고민"),
    ]),
]


def build():
    rows = []
    for memo_id, persona, symbol, sep, sentences in sorted(MEMOS, key=lambda m: m[0]):
        # 문장부호로 끝나지 않는 문장 뒤는 줄바꿈으로 잇는다 (모바일 메모처럼). 문장 분리 정답이 공정하도록.
        text = ""
        for k, s in enumerate(sentences):
            if k:
                prev = sentences[k - 1]["text"]
                if sep == "flat":
                    text += " "  # 한 줄로 이어 쓰기 (WO-021)
                else:
                    text += sep if sep == "\n" or prev.rstrip()[-1:] in ".?!" else "\n"
            text += s["text"]
        pos = 0
        out = []
        for i, s in enumerate(sentences):
            start = text.index(s["text"], pos)
            end = start + len(s["text"])
            pos = end
            out.append({"sentence_index": i, "span": [start, end], **s})
            if s["merge_into"]:
                assert s["merge_into"]["sentence_index"] < i, (memo_id, i)
                assert not s["items"], (memo_id, i)
            if s["decision"] == "full_fallback":
                assert not s["items"] and not s["merge_into"], (memo_id, i)
        rows.append({"memo_id": memo_id, "persona": persona, "symbol": symbol, "text": text, "sentences": out})
    return rows


def main():
    rows = build()
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "memo_eval_v0.jsonl").open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    sents = [s for r in rows for s in r["sentences"]]
    dec = collections.Counter(s["decision"] for s in sents)
    cat = collections.Counter(s["category"] for s in sents)
    reason = collections.Counter(s["reason_code"] for s in sents)
    flags = collections.Counter(f for s in sents for f in s["flags"])
    items = sum(len(s["items"]) for s in sents)
    merges = sum(1 for s in sents if s["merge_into"])
    splits = sum(1 for s in sents if len(s["items"]) >= 2)
    by_persona = collections.Counter(r["persona"] for r in rows)
    by_symbol = collections.Counter(r["symbol"] for r in rows)
    stats = {
        "memos": len(rows), "sentences": len(sents), "items": items,
        "decision": dict(dec), "category": dict(sorted(cat.items())), "reason": dict(sorted(reason.items())),
        "flags": dict(flags), "merge_sentences": merges, "split_sentences": splits,
        "persona": dict(sorted(by_persona.items())), "symbol": dict(sorted(by_symbol.items())),
    }
    (OUT / "memo_eval_v0_stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=1), encoding="utf-8")

    lines = ["# 문장 판정 평가 메모 v0 (검수용)", "",
             "기준표 v0.2 정답. 검수 시 `판정`·`분류`·`추적 항목` 열을 확인하고 이견은 비고에 적는다.", ""]
    for r in rows:
        lines += [f"## {r['memo_id']} · {r['persona']} {PERSONAS[r['persona']]} · {r['symbol']}", "",
                  "```", r["text"], "```", "",
                  "| # | 문장 | 판정 | 분류 | 추적 항목 / 처리 | 비고 |", "|---|---|---|---|---|---|"]
        for s in r["sentences"]:
            parts = []
            for it in s["items"]:
                t = f"{it['type']}: {it['description']}" + (f" ({it['time_hint']})" if it["time_hint"] else "")
                parts.append(t)
            if s["merge_into"]:
                parts.append(f"→ #{s['merge_into']['sentence_index']} 항목에 합침" + (f" {s['merge_update']}" if s["merge_update"] else ""))
            if s["resolved_reference"]:
                parts.append(f"참조: {s['resolved_reference']}")
            if s["context_note"]:
                parts.append(f"카드 메모: {s['context_note']}")
            if s["suggestion"]:
                parts.append(f"제안: {s['suggestion']}")
            if s["flags"]:
                parts.append(f"flags: {', '.join(s['flags'])}")
            lines.append(f"| {s['sentence_index']} | {s['text'].replace('|', '/')} | {s['decision']} | {s['category']} {s['reason_code']} | {'<br>'.join(parts) or '-'} | |")
        lines.append("")
    (OUT / "memo_eval_v0_review.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(stats, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
