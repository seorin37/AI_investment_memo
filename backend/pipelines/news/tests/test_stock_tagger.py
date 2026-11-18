"""기사-종목 태그 확대(stock_tagger) 테스트. DB 없이 이름 목록·설정으로 확인한다."""
from pathlib import Path

import yaml

from backend.pipelines.news import stock_tagger as st

STOCKS = {"034730": "SK", "000660": "SK하이닉스", "017670": "SK텔레콤", "006260": "LS", "001680": "대상",
          "005930": "삼성전자", "005935": "삼성전자우", "035420": "NAVER", "000270": "기아", "003550": "LG",
          "066570": "LG전자", "030200": "KT", "103140": "풍산", "000150": "두산", "012030": "DB", "007980": "TP",
          "002380": "KCC", "006800": "미래에셋증권", "093050": "LF", "034120": "SBS"}
CFG = {"aliases": {"035420": ["네이버"], "000660": ["하이닉스"], "093050": ["LF몰"]}, "blockers": ["SK쉴더스", "SK그룹"],
       "group_names": ["SK", "LG", "두산", "LS"], "group_suffixes": ["그룹", "家", "회장"],
       "require_context": ["대상", "풍산", "SBS"], "short_ok": ["기아"],
       "context_words": ["주가", "실적", "공시", "㈜", "목표가"], "context_window": 20, "max_body_tags": 2, "lead_chars": 40,
       "sports_names": ["두산", "DB", "SK"], "sports_words": ["프로야구", "농구", "선수", "대표팀"],
       "prefix_check_max_len": 3, "title_only_words": ["증권"],
       "context_after_window": 10, "title_only_names": ["네이버", "NAVER"],
       "skip_title_patterns": [r"\[(인사|부고|동정|게시판)\]"],
       "group_list_words": ["삼성", "현대차", "SK", "LG", "LS", "두산"], "group_list_tail": ["그룹", "대기업", "재계"]}
RULES = st.build_rules(STOCKS, CFG, {"SK스퀘어", "SK하이닉스"})


def tags(title, body=None, rules=RULES):
    return {h.symbol: h.rule for h in st.match_article(title, body, rules)}


def test_longest_name_wins_and_preferred_maps_to_common():
    assert tags("SK하이닉스, HBM4 양산") == {"000660": "title"}                 # "SK"는 더 긴 이름 안
    assert tags("SK스퀘어 지분 매각") == {}                                       # 상장사 목록의 더 긴 이름이 자리를 차지
    assert tags("삼성전자우 급등") == {"005930": "title"}                          # 우선주는 보통주로
    assert "005935" not in RULES.names.values()
    assert tags("네이버, 웹툰 실적 발표") == {"035420": "title"}                    # 별칭
    assert tags("하이닉스·LG전자 동반 상승") == {"000660": "title", "066570": "title"}


def test_latin_boundary():
    assert tags("홍콩H지수 ELS 과징금 확정") == {}                                 # ELS 안의 LS
    assert tags("KTX 증편") == {}
    assert tags("LS, 전선 사업 분할") == {"006260": "title"}
    assert tags("KT 3분기 영업이익 증가") == {"030200": "title"}


def test_common_words_need_stock_context():
    assert tags("평생학습대상 우수상 수상") == {}
    assert tags("대상㈜, 3분기 실적 발표") == {"001680": "title"}
    assert tags("KB증권, 풍산 목표가 하향") == {"103140": "title"}
    assert tags("[풍산소식] 축제 개최") == {}
    assert "기아" not in RULES.require_context                                   # short_ok


def test_group_names():
    assert tags("SK그룹 인사 발표") == {}                                          # blockers
    assert tags("LG 회장 신년사") == {}                                            # 그룹을 뜻하는 말
    assert tags("SK, 자회사 지분 정리") == {"034730": "title"}
    body = "반도체 업황이 좋다. " * 5 + "SK는 지분을 늘렸다. SK는 또 투자를 발표했다."
    assert tags("업황 기사", body) == {}                                           # 지주사는 본문 2번 규칙으로 붙이지 않는다


def test_title_lead_body_rules_and_body_cap():
    lead = "기아가 신차를 공개했다. " + "업계 소식이다. " * 10
    assert tags("자동차 업계 소식", lead) == {"000270": "lead"}
    once = "업계 소식이다. " * 10 + "기아도 참여했다."
    assert tags("자동차 업계 소식", once) == {}                                    # 본문 1번(리드 밖)은 붙이지 않는다
    twice = "업계 소식이다. " * 10 + "기아도 참여했다. 기아는 또 발표했다."
    assert tags("자동차 업계 소식", twice) == {"000270": "body"}
    many = "업계 소식이다. " * 10 + "기아 기아 삼성전자 삼성전자 KT KT LG전자 LG전자"
    assert len(tags("시황", many)) == 2                                            # max_body_tags
    assert tags("기아 신차", "기아가 공개했다.")["000270"] == "title"                # 강한 규칙 하나만


def test_rules_from_sample_review():                 # 2026-11-09 오탐 표본 O/X
    assert tags("두산 최민석, 팔꿈치 부상으로 대표팀 낙마") == {}                     # 야구 선수
    assert tags("프로농구 SK-DB 경기") == {}
    assert tags("두산, 3분기 실적 발표") == {"000150": "title"}
    assert tags("LS오토, 대표 사장 승진") == {}                                    # 비상장 계열사 앞부분
    assert tags("KCC실리콘, 뷰티 소재 공략") == {}
    assert tags("기아대책-LG화학, 환경교육") == {}                                  # 기아대책은 기아가 아니다
    assert tags("기아는 신차를 공개했다") == {"000270": "title"}                     # 조사는 괜찮다
    assert tags("LF몰, 블랙프라이데이 행사") == {"093050": "title"}                  # 별칭
    body = "업계 소식이다. " * 10 + "미래에셋증권에 따르면 수익률이 높다. 미래에셋증권은 또 분석했다."
    assert tags("ETF 투자 비율", body) == {}                                       # 증권사는 제목에서만
    assert tags("미래에셋증권, 3분기 순이익 증가") == {"006800": "title"}
    assert tags("울산TP와 함께 스마트팜 홍보") == {}                                 # 2글자 영문 앞이 한글
    assert tags("SBS 예능 프로그램 방송") == {}
    assert tags("SBS 3분기 실적 발표") == {"034120": "title"}
    assert tags("현대重 대표, 글로벌품질경영인대상 수상") == {}                       # 다른 낱말의 뒷부분
    assert tags("LG생건·대상은 3분기 실적 개선") == {"001680": "title"}            # 앞이 구분 기호면 괜찮다


def test_rules_from_kospi_survey():                  # 2026-11-18 코스피 태깅 조사 오탐 표본
    pad = "업계 소식이다. " * 2
    # 흔한 단어 이름: 리드·본문은 바로 뒤 주식 낱말·종목코드·㈜만 ("지원 대상", "투자 대상"은 앞 낱말이라 세지 않는다)
    assert tags("현대차그룹, 선수단 차량 지원", pad + "어린이와 취약계층 등 지원 대상도 늘려나가겠다는 구상이다.") == {}
    assert tags("주주행동 검토", pad + "반도체 부품과 화학소재 기업 등이 투자 대상이라고 말했다. 투자 대상은 공개하지 않았다.") == {}
    assert tags("식품 업계 소식", pad + "대상(001680)은 3분기 영업이익이 늘었다.") == {"001680": "lead"}
    assert tags("식품 업계 소식", pad + "대상은 3분기 실적이 좋아졌다.") == {"001680": "lead"}
    assert tags("대상㈜, 3분기 실적 발표") == {"001680": "title"}                   # 제목은 그대로
    # 그룹·계열사
    assert tags("[단독] LG CNS, 인니 AI데이터센터서 최고 설계등급 획득") == {}       # 영문 계열사
    assert tags("수능날 난방설비 고장 안 나게…삼성·LG, 시험장 시스템에어컨 사전점검") == {}   # 그룹 나열
    lead = "16일 재계에 따르면 삼성·SK·LG그룹 등 주요 대기업은 AI를 활용한 부정행위를 막고 있다."
    assert tags("AI 커닝에 대기업 채용도 차단책", lead) == {}
    assert tags("SK, 자회사 지분 정리") == {"034730": "title"}                     # 지주사 자체 소식은 그대로
    assert tags("LG, 3분기 실적 발표") == {"003550": "title"}
    # [인사]·[부고] 제목은 건너뛴다
    assert tags("[인사] 경찰청 ; SK그룹 ; 두산 등", "▷두산 대표이사 홍길동 ▷LS 대표 김철수 ▷KT 상무 이영희") == {}
    # 네이버는 제목에서만 (4종목 RSS 태거 규칙을 옮김)
    assert tags("검색 서비스 소식", pad + "네이버에서 검색하면 나온다. 네이버 지도도 바뀌었다.") == {}
    assert tags("네이버, 3분기 실적 발표") == {"035420": "title"}


def test_precision_round2_with_project_config():     # 2026-11-18 정밀도 표본 2차 (실제 설정)
    cfg = yaml.safe_load(Path("configs/stock_aliases.yaml").read_text(encoding="utf-8"))
    stocks = {"034730": "SK", "000150": "두산", "024110": "기업은행", "000720": "현대건설", "180640": "한국공항",
              "139480": "이마트", "005180": "빙그레", "012330": "현대모비스", "002380": "KCC"}
    r = st.build_rules(stocks, cfg)
    t = lambda title, body=None: {h.symbol for h in st.match_article(title, body, r)}   # noqa: E731
    pad = "업계 소식이다. " * 2
    assert "034730" not in t("KCC, SK 꺾고 4연승…허웅, 4쿼터서 결정적 3점")             # 농구
    assert t("'FA 1호 계약' 양의지, 두산 잔류…2년 최대 55억원") == set()                # 야구
    assert t("배구 소식", pad + "정관장이 IBK기업은행을 세트 점수 3-1로 꺾었다.") == set()
    assert t("오늘의 경기", pad + "△프로배구= 우리카드-대한항공 현대건설-GS칼텍스(수원체육관)") == set()
    assert t("부고", pad + "전 빙그레 이글스 2군 감독이 별세했다.") == set()
    assert t("공항 통계", pad + "한국공항공사 공항통계에 따르면 이용객이 늘었다.") == set()   # 공사
    assert t("음악회", pad + "서울 예술의전당 IBK기업은행챔버홀에서 열린다.") == set()          # 시설
    assert t("편의점 소식", pad + "이마트24는 경량 패딩을 추가했다.") == set()                 # 숫자가 붙은 다른 회사
    # 진짜 기업 기사는 그대로 ("경기도", "금융감독원"은 스포츠 말이 아니다)
    assert t("현대건설, 경기 남양주 아파트 분양") == {"000720"}
    assert t("기업은행, 금융감독원 검사 결과 발표") == {"024110"}
    assert t("기업은행, 3분기 순이익 증가") == {"024110"}
    assert t("이마트, 3분기 영업이익 40% 증가") == {"139480"}


def test_precision_round3_with_project_config():     # 2026-11-18 정밀도 표본 3차 (실제 설정)
    cfg = yaml.safe_load(Path("configs/stock_aliases.yaml").read_text(encoding="utf-8"))
    stocks = {"003550": "LG", "034730": "SK", "000880": "한화", "012450": "한화에어로스페이스", "012030": "DB",
              "016610": "DB증권", "015760": "한국전력", "047810": "한국항공우주", "001680": "대상"}
    r = st.build_rules(stocks, cfg)
    t = lambda title, body=None: {h.symbol for h in st.match_article(title, body, r)}   # noqa: E731
    pad = "업계 소식이다. " * 2
    assert t("프로야구 FA 공시", pad + "박동원, 홍창기(이상 LG 트윈스), 박치국(두산 베어스)") == set()   # 구단 별칭
    assert t("빅매치", pad + "남자부 현대캐피탈과 한국전력, 여자부 IBK기업은행이 격돌한다.") == set()
    assert t("연극 '로스코'", pad + "LG아트센터 서울에서 초연된다.") == set()          # 시설 (띄어 쓴 "LG 시그니처홀"은 못 막음)
    assert t("판결", pad + "한국항공우주연구원 달탐사사업단 연구원들이 낸 소송") == set()            # 연구원
    assert t("범LG家 3세 구본현…8년 해외도피 끝 검거") == set()                                     # 그룹 일가
    assert t("동반성장데이", pad + "SK AX는 17일 경기 성남 SK u타워에서 행사를 열었다.") == set()    # 영문 계열사
    assert t("한화에어로, 육군본부 과장단 초청") == {"012450"}                                   # 약칭은 그 종목
    assert t("DB證, 스피어 랩스와 STO 실증사업 맞손") == {"016610"}
    assert t("한양증권, 한국PR대상 IR 부문 우수상") == set()                                    # 낱말 안의 대상
    assert t("한화, 3분기 실적 발표") == {"000880"} and t("LG, 3분기 실적 발표") == {"003550"}


def test_project_config_loads():
    cfg = yaml.safe_load(Path("configs/stock_aliases.yaml").read_text(encoding="utf-8"))
    rules = st.build_rules({**STOCKS, "005380": "현대차"}, cfg)
    assert rules.names["네이버"] == "035420"
    assert "대상" in rules.require_context and "남성" not in rules.names
    assert "상장" not in cfg["context_words"]
    assert st.match_article("기아대책, 초등학생 환경교육", None,
                            st.build_rules({"000270": "기아", "051910": "LG화학"}, cfg)) == []
    assert cfg["max_body_tags"] == 5 and cfg["lead_chars"] == 200
