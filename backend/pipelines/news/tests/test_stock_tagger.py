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
       "skip_title_patterns": [r"\[(인사|부고|동정)\]"],
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


def test_recall_fixes_with_project_config():         # 2026-11-18 재현율 개선 6개 (실제 설정)
    cfg = yaml.safe_load(Path("configs/stock_aliases.yaml").read_text(encoding="utf-8"))
    stocks = {"035420": "NAVER", "000670": "영풍", "003550": "LG", "024110": "기업은행", "000720": "현대건설",
              "285130": "SK케미칼", "066570": "LG전자"}
    r = st.build_rules(stocks, cfg, {"영풍제지"})
    t = lambda title, body=None: {h.symbol for h in st.match_article(title, body, r)}   # noqa: E731
    pad = "업계 소식이다. " * 2
    # ① [게시판] 제목은 건너뛰지 않는다 ([인사]는 그대로)
    assert t("[게시판] SK케미칼, KCGS ESG 평가서 5년 연속 A+ 등급") == {"285130"}
    assert t("[인사] SK케미칼 ; LG전자") == set()
    # ② 본문의 네이버는 바로 뒤 주식 낱말·종목코드가 있을 때만
    assert t("주요공시", pad + "네이버(035420), 검색부터 예약·결제까지 AI가 대신") == {"035420"}
    assert t("포털 동향", pad + "네이버 주가가 이틀 연속 올랐다. 네이버 실적 발표를 앞두고 있다.") == {"035420"}
    assert t("이벤트", pad + "별도 네이버 폼을 통해 신청하면 된다. 네이버 스마트스토어도 있다.") == set()
    # ③ 영풍은 문맥 없이도, 영풍문고는 아니다
    assert t("고려아연 판결", pad + "영풍·MBK파트너스는 경영권 확보를 위해 소송을 냈다.") == {"000670"}
    assert t("서점가", pad + "영풍문고는 연말 행사를 연다. 영풍문고 매장도 늘린다.") == set()
    # ④ 그룹 이름 뒤 제품·매장 낱말
    assert t("“홈시네마의 대중화”… 블룸즈베리랩, 전국 LG 베스트샵 공식 입점") == set()
    assert t("LG 올레드 TV, 유럽 7개국 평가서 1위") == set()
    assert t("LG, 3분기 실적 발표") == {"003550"}
    # ⑤ 띄어 쓴 시설 이름
    assert t("음악회", pad + "예술의전당 IBK기업은행 챔버홀에서 열린 음악회") == set()
    assert t("연극", pad + "LG 시그니처홀에서 초연된다.") == set()
    # ⑥ 스포츠 문맥이 한 번이라도 있으면 그 구단 이름은 기사 전체에서 뺀다
    body = "V리그 여자부 현대건설과의 방문 경기를 앞두고 연승을 이어갔다. " + "선수 소식이다. " * 15 + "현대건설도 분위기가 좋다."
    assert t("김영래 감독 인터뷰", body) == set()
    assert t("현대건설, 한강변에 5000가구 대단지") == {"000720"}                       # 회사 기사는 그대로


def test_final_three_types_with_project_config():    # 2026-11-18 고정 세트 남은 오탐 세 유형 (실제 설정)
    cfg = yaml.safe_load(Path("configs/stock_aliases.yaml").read_text(encoding="utf-8"))
    stocks = {"004170": "신세계", "035510": "신세계 I&C", "034730": "SK", "096770": "SK이노베이션",
              "207940": "삼성바이오로직스", "0126Z0": "삼성에피스홀딩스", "090460": "비에이치", "000810": "삼성화재",
              "089590": "제주항공", "316140": "우리금융지주", "009240": "한샘", "008770": "호텔신라", "030200": "KT"}
    cfg = {**cfg, "aliases": {**cfg["aliases"], "207940": ["삼성바이오"]}}
    r = st.build_rules(stocks, cfg)
    t = lambda title, body=None: {h.symbol for h in st.match_article(title, body, r)}   # noqa: E731
    pad = "업계 소식이다. " * 2
    # ① 다른 회사 이름의 앞부분 → 더 긴 이름의 종목으로 (없으면 붙이지 않는다)
    assert t("상장 일정", pad + "신세계I&C(주식소각) 상장 변경") == {"035510"}
    assert t("SK이노, 사회문제 해결할 AI 스타트업 3곳 선정") == {"096770"}
    assert t("삼성바이오에피스, 지주사에 1천43억원 현금 배당") == {"0126Z0"}
    assert t("비에이치소프트 ‘에듀OK’, 얼굴인식 출결 지원") == set()
    assert t("신세계, 3분기 영업이익 증가") == {"004170"}
    # ② 삼성화재 배구·바둑
    assert t("변상일 '천적' 신진서 꺾고 삼성화재배 첫 결승 진출") == set()
    assert t("빅매치", pad + "◆18일(수)= 삼성화재-우리카드(대전 충무체육관)") == set()
    assert t("삼성화재, 3분기 순이익 증가") == {"000810"}
    # ③ 인물 직함·경력
    assert t("[부음] 홍정유씨 별세 외", "장주녀씨(제주항공 객실본부장) 시모상") == set()
    assert t("평가위원회", pad + "강일원 변호사, 김익중 우리금융지주 홍보실장, 김정형 학생") == set()
    assert t("“갱년기라 뒤척인다고요?”…한샘 출신 대표가 침대에 꽂힌 이유") == set()
    assert t("KT, AI 사업 확대", pad + "김영섭 KT 대표는 AI 투자를 늘린다고 밝혔다.") == {"030200"}   # 대표는 회사 소식


def test_timer_first_night_with_project_config():    # 2026-11-19 매시 태깅 첫날 오탐 7건 (실제 설정)
    cfg = yaml.safe_load(Path("configs/stock_aliases.yaml").read_text(encoding="utf-8"))
    stocks = {"000720": "현대건설", "012030": "DB", "025560": "미래산업", "088350": "한화생명", "028260": "삼성물산",
              "005380": "현대차", "030200": "KT", "005930": "삼성전자", "000660": "SK하이닉스", "003490": "대한항공"}
    r = st.build_rules(stocks, cfg)
    t = lambda title, body=None: {h.symbol for h in st.match_article(title, body, r)}   # noqa: E731
    pad = "업계 소식이다. " * 2
    # ① 경기 결과 기사: 제목이 경기 기사면 본문 구단 이름은 앞뒤 낱말 없이도 뺀다 / "1승 4패" 전적 표기
    assert t("[프로배구 전적] 18일", pad + "△ 여자부(SOOP 스타디움) SOOP(5패) 20 16 25 16 - 1 현대건설(1승 4패) 25 25 19 25 - 3") == set()
    assert t("오늘의 소식", pad + "현대건설(1승 4패)은 홈에서 졌다.") == set()
    assert t("현대건설, 한강변에 5000가구 대단지") == {"000720"}
    # ② 흔한 낱말 DB·미래산업
    assert t("개보위, '자바' 취약점 주의 당부", pad + "데이터베이스(DB) 접근권한이 넓으면 위험하다. DB 조회 권한을 줄여야 한다.") == set()
    assert t("대기업 계열사 수", pad + "AI·디지털 금융 등 미래산업 진출 목적이 주요 특징이다.") == set()
    assert t("DB, 3분기 실적 발표") == {"012030"}
    assert t("특징주", pad + "DB(012030) 주가가 올랐다.") == {"012030"}
    assert t("미래산업, 반도체 장비 수주 공시") == {"025560"}
    # ③ 떨어진 직함·"전 ○○ CIO/부사장"
    assert t("KIC 신임 CIO 내정", pad + "신임 CIO로 신민식 전 한화생명보험 CIO가 내정됐다.") == set()
    assert t("동곡상 시상식", pad + "지형근 삼성물산 건설부문 전략사업실장 부사장 등 4명이 수상했다.") == set()
    assert t("인터뷰", pad + "그는 前 삼성전자 부사장으로 일했다.") == set()
    assert t("KT, AI 사업 확대", pad + "김영섭 KT 대표는 AI 투자를 늘린다고 밝혔다.") == {"030200"}   # 현직 대표 발언은 회사 소식
    assert t("한화생명, 3분기 순이익 증가") == {"088350"}
    # ④ 협력사·이직 경력
    assert t("박대성 대표 인터뷰", pad + "1984년 현대차 1차 협력사인 화신으로 이직했다.") == set()
    assert t("인재 이동", pad + "삼성전자에서 SK하이닉스로 이직한 엔지니어가 늘었다.") == set()
    assert t("상생", pad + "현대차는 협력사 지원 프로그램을 확대했다.") == {"005380"}          # 회사가 주어인 협력사 기사는 그대로
    # 판사·주차장처럼 직함 낱말을 품은 다른 낱말은 직함이 아니다
    assert t("소송", pad + "삼성전자 사건을 맡은 부장판사가 판결했다.") == {"005930"}
    r_lgu = st.build_rules({**stocks, "032640": "LG유플러스", "015760": "한국전력", "031430": "신세계인터내셔날"}, cfg)
    t2 = lambda title, body=None: {h.symbol for h in st.match_article(title, body, r_lgu)}   # noqa: E731
    long_pad = "통신 업계 소식이다. " * 25
    # 전체 DB 다시 돌리기에서 찾은 과잉 차단 (2026-11-19)
    assert t2("[사설] 한전 2년 만에 적자, 이대로 ‘AI 3강’ 뒷받침되겠나",
              pad + "전력망 확충을 뒷받침해야 할 한국전력이 2년 만에 영업 손실을 냈다.") == {"015760"}   # "N강"은 제목 경기 낱말 아님
    assert t2("위성폰 영향", long_pad + "LG유플러스(032640)는 실적 설명회를 열었다. " + long_pad
              + "여명희 LG유플러스 CFO도 영향이 제한적이라고 했다.") == {"032640"}                   # CFO 발언은 회사 소식
    assert t2("대표 영입", long_pad + "허 대표는 신세계인터내셔날 코스메틱부문 대표를 겸한다. "
              + "그는 신세계인터내셔날과 동화면세점을 거쳐 CJ그룹으로 자리를 옮겼다.") == {"031430"}
    assert t("인터뷰", pad + "그는 삼성전자로 이직했다.") == set()
    # "차장" 앞이 주·정·승·하면 직함이 아니다, 띄어 쓴 낱말 사이 차장은 직함
    r_role = st.build_rules({"139480": "이마트"}, cfg)
    assert r_role.person_role_re.match("이마트 앞 주차장 일원", 3) is None
    assert r_role.person_role_re.match("이마트 영업 차장은", 3) is not None
    assert r_role.person_role_re.match("이마트 커뮤니케이션실장은", 3) is None                # 긴 붙은 말은 가르지 않는다


def test_large_cap_aliases_with_project_config():   # 2026-11-19 대형사 별칭 (종목명과 기사 표기가 다른 곳)
    cfg = yaml.safe_load(Path("configs/stock_aliases.yaml").read_text(encoding="utf-8"))
    stocks = {"005490": "POSCO홀딩스", "003670": "포스코퓨처엠", "010950": "S-Oil", "018260": "삼성에스디에스",
              "055550": "신한지주", "086790": "하나금융지주", "316140": "우리금융지주", "138040": "메리츠금융지주",
              "010120": "LS ELECTRIC", "006260": "LS", "015760": "한국전력", "001440": "대한전선", "105560": "KB금융"}
    r = st.build_rules(stocks, cfg)
    t = lambda title, body=None: {h.symbol for h in st.match_article(title, body, r)}   # noqa: E731
    pad = "업계 소식이다. " * 2
    # 별칭으로 붙는다
    assert t("포스코홀딩스, 3분기 영업익 9천400억원") == {"005490"}
    assert t("포스코, 中CATL에 리튬 공급") == {"005490"}
    assert t("에쓰오일, 3분기 영업익 1조4천억원") == {"010950"}
    assert t("하나증권, S-OIL 목표가 하향") == {"010950"}
    assert t("삼성SDS, 구미 AI 데이터센터 착공") == {"018260"}
    assert t("신한금융, 누적 순이익 '5조 클럽' 첫 입성") == {"055550"}
    assert t("하나·우리금융, 3분기 순이익 1조 돌파") == {"316140"}                   # "하나·"는 별칭이 아니다
    assert t("하나금융, 첫 개인주주 간담회") == {"086790"}
    assert t("LS일렉트릭, 100분기 연속 흑자") == {"010120"}
    assert t("LS일렉, 베트남 2공장 준공") == {"010120"}                               # 지주사 LS로 붙지 않는다
    assert t("중동전쟁 여파에 한전 3분기 영업익 70% 뚝") == {"015760"}
    assert t("송전망", pad + "한국전력공사는 변전소 용지를 확정했다.") == {"015760"}   # "공사" 뒤 글자 규칙에 걸리지 않는다
    # 포스코: 그룹 이름 규칙 (계열사·그룹 이야기는 빼고, 상장 계열사는 긴 이름이 이긴다)
    assert t("포스코이앤씨, 고창 해상풍력 2974억 투입") == set()
    assert t("포스코그룹 회장 신년사") == set()
    assert t("포스코DX, 로봇 자동화 수주") == set()
    assert t("포스코퓨처엠, 양극재 공급 계약") == {"003670"}
    # 금융지주 별칭을 품은 다른 회사 · 자회사 은행은 붙이지 않는다
    assert t("신한금융투자 리서치센터 전망") == set()
    assert t("우리금융캐피탈, 자동차 할부 금리 인하") == set()
    assert t("우리금융저축銀, 지주 계열 수익성 1위") == set()
    assert t("하나금융연구소 보고서") == set()
    assert t("신한은행, 소상공인 대출 확대") == set()
    # 한전: 더 긴 다른 이름의 일부 · 영문이 붙은 자회사
    assert t("대한전선, 해저케이블 수주") == {"001440"}
    assert t("대한전문건설협회 회장 선거") == set()
    assert t("한전KDN, 전력 ICT 사업 확대") == set()
    # 골프 대회 후원·선수 소속
    assert t("[KLPGA 최종순위] 에쓰오일 챔피언십") == set()
    assert t("이예원, KLPGA 에쓰오일 대회 2라운드서 단독 선두") == set()
    assert t("제네시스 대상 레이스", pad + "장유빈(신한금융그룹)이 KPGA 투어에서 준우승했다.") == set()


def test_project_config_loads():
    cfg = yaml.safe_load(Path("configs/stock_aliases.yaml").read_text(encoding="utf-8"))
    rules = st.build_rules({**STOCKS, "005380": "현대차"}, cfg)
    assert rules.names["네이버"] == "035420"
    assert "대상" in rules.require_context and "남성" not in rules.names
    assert "상장" not in cfg["context_words"]
    assert st.match_article("기아대책, 초등학생 환경교육", None,
                            st.build_rules({"000270": "기아", "051910": "LG화학"}, cfg)) == []
    assert cfg["max_body_tags"] == 5 and cfg["lead_chars"] == 200
