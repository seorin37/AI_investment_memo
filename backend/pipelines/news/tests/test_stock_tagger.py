"""기사-종목 태그 확대(stock_tagger) 테스트. DB 없이 이름 목록·설정으로 확인한다."""
from pathlib import Path

import yaml

from backend.pipelines.news import stock_tagger as st

STOCKS = {"034730": "SK", "000660": "SK하이닉스", "017670": "SK텔레콤", "006260": "LS", "001680": "대상",
          "005930": "삼성전자", "005935": "삼성전자우", "035420": "NAVER", "000270": "기아", "003550": "LG",
          "066570": "LG전자", "030200": "KT", "103140": "풍산"}
CFG = {"aliases": {"035420": ["네이버"], "000660": ["하이닉스"]}, "blockers": ["SK쉴더스", "SK그룹"],
       "group_names": ["SK", "LG"], "group_suffixes": ["그룹", "家", "회장"], "require_context": ["대상", "풍산"],
       "short_ok": ["기아"], "context_words": ["주가", "실적", "공시", "㈜", "목표가"], "context_window": 20,
       "max_body_tags": 2, "lead_chars": 40}
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


def test_project_config_loads():
    cfg = yaml.safe_load(Path("configs/stock_aliases.yaml").read_text(encoding="utf-8"))
    rules = st.build_rules({**STOCKS, "005380": "현대차"}, cfg)
    assert rules.names["네이버"] == "035420"
    assert "대상" in rules.require_context and "남성" not in rules.names
    assert cfg["max_body_tags"] == 5 and cfg["lead_chars"] == 200
