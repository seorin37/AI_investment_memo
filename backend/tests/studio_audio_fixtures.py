"""AI 오디오 통합 시험용 가짜 자료 (가상의 카드·기사·공시·시세). 실제 회사 사실이 아니다 — 수치는 모두 시험용.

seed_week로 만든 테스트 사용자의 메모에 추적 항목·카드를 직접 넣는다 (업데이트 파이프라인·LLM 없이 오디오 쪽만 시험할 때).
"""
from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

SEOUL = ZoneInfo("Asia/Seoul")

# (메모 key, 추적 항목, 카드 종류, 근거 종류, 근거 날짜 오프셋(기간 첫날부터), 제목, headline, facts, memo_link)
CARDS = [
    ("hynix-hbm", "HBM 생산 능력", "disclosure", "disc", 1, "신규시설투자등",
     "HBM 생산 시설에 투자", ["SK하이닉스가 신규 시설투자 2조 1,000억 원을 결정했어요.", "투자 기간은 2026년 11월부터 2028년 6월까지예요."],
     "메모에 적어 두신 'HBM 설비투자 금액·기간'이 이 공시에 나와 있어요."),
    ("hynix-hbm", "HBM 엔비디아 공급", "news", "news", 3, "SK하이닉스, HBM4 공급 물량 확대 합의",
     "HBM4 공급 확대 보도", ["한국경제는 SK하이닉스가 고객사와 HBM4 공급 물량을 늘리기로 합의했다고 보도했어요."],
     "메모의 'HBM4 양산·엔비디아 공급' 항목과 같은 주제의 기사예요."),
    ("hynix-fx", "환율과 수출 실적", "news", "news", 4, "원/달러 1,450원대…수출 기업 환차익 커져",
     "환율과 수출 기업 실적", ["매일경제는 원/달러 환율이 1,450원대로 오르면서 반도체 수출 기업의 원화 환산 매출이 커졌다고 보도했어요."],
     "메모에 쓰신 '환율이 실적에 주는 영향'을 다룬 기사예요."),
    ("samsung-buyback", "자사주 매입·소각", "disclosure", "disc", 2, "주요사항보고서(자기주식취득결정)",
     "자기주식 3조 원 취득 결정", ["삼성전자가 자기주식 3조 원어치를 취득하기로 결정했어요.", "취득 기간은 11월 18일부터 2027년 2월 17일까지예요."],
     "메모에 적어 두신 '자사주 매입 규모와 기간'이 이 공시에 나와 있어요."),
    ("kb-dividend", "분기 배당", "disclosure", "disc", 2, "현금ㆍ현물배당결정",
     "분기 배당 주당 1,000원", ["KB금융이 주당 1,000원의 분기 배당을 결정했어요.", "배당 기준일은 11월 30일이에요."],
     "메모의 '분기 배당 결정 공시' 항목이에요."),
    ("kb-dividend", "금리와 이자이익", "news", "news", 5, "기준금리 동결…은행 이자이익 영향은",
     "기준금리와 은행 이자이익", ["연합뉴스는 한국은행이 기준금리를 연 2.50%로 동결했다고 보도했어요."],
     "메모에 쓰신 '기준금리와 이자이익' 항목과 이어지는 기사예요."),
]
PRICES = {"000660": [170000, 172500, 177800, 179300, 180500], "005930": [70400, 69800, 71900, 72000, 71400],
          "035420": [214000, 216000, 213800, 212000, 212300], "105560": [118000, 119500, 121000, 120500, 122000]}
INDEX = {"KOSPI": [2598.1, 2610.4, 2633.9, 2641.0, 2650.35], "KOSDAQ": [855.2, 857.0, 860.3, 861.8, 862.1]}
USD = [1438.5, 1442.0, 1447.3, 1451.2, 1449.8]


def weekdays(start: date, end: date) -> list[date]:
    out, d = [], start
    while d <= end:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def insert(conn, created: dict) -> dict:
    """seed_week의 created.json 내용(dict)을 받아 항목·카드·시세를 넣는다. 반환: 넣은 id."""
    start, end = date.fromisoformat(created["period"]["start"]), date.fromisoformat(created["period"]["end"])
    days = weekdays(start, end)[-5:]
    for sym, closes in PRICES.items():
        for d, c in zip(days, closes):
            conn.execute("""INSERT INTO prices_daily (symbol, trade_date, open, high, low, close, volume, source)
                VALUES (%s, %s, %s, %s, %s, %s, 1000001, 'KIS') ON CONFLICT DO NOTHING""", (sym, d, c, c, c, c))
    for code, closes in INDEX.items():
        for d, c in zip(days, closes):
            conn.execute("INSERT INTO market_indices (code, trade_date, close) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                         (code, d, c))
    for d, v in zip(days, USD):
        conn.execute("""INSERT INTO economic_observations (indicator_code, observation_date, value) VALUES ('USD_KRW', %s, %s)
            ON CONFLICT DO NOTHING""", (d, v))
    out = {"items": [], "cards": [], "news": [], "disclosures": []}
    for n, (key, item, ctype, ekind, off, title, headline, facts, link) in enumerate(CARDS, 1):
        memo = created["memos"][key]
        mid = memo["id"]
        rev = conn.execute("SELECT id FROM memo_revisions WHERE memo_id = %s ORDER BY revision_no DESC LIMIT 1", (mid,)).fetchone()[0]
        iid = conn.execute("INSERT INTO tracking_items (memo_id, type, description) VALUES (%s, 'topic', %s) RETURNING id",
                           (mid, item)).fetchone()[0]
        trev = conn.execute("""INSERT INTO tracking_item_revisions (tracking_item_id, revision_no, type, description)
            VALUES (%s, 1, 'topic', %s) RETURNING id""", (iid, item)).fetchone()[0]
        out["items"].append(iid)
        eday = start + timedelta(days=off)
        details = {"card_schema": "v2", "headline": headline, "facts": [{"text": f, "evidence_id": "E1"} for f in facts],
                   "memo_link": link, "when": eday.isoformat(), "run_id": "fixture"}
        at = datetime.combine(eday + timedelta(days=1), time(6, 30), SEOUL)
        cid = conn.execute("""INSERT INTO tracking_updates (tracking_item_id, type, title, summary, reason, details, memo_revision_id,
                tracking_revision_id, created_at) VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s) RETURNING id""",
                           (iid, ctype, headline, facts[0], link, json.dumps(details, ensure_ascii=False), rev, trev, at)).fetchone()[0]
        out["cards"].append(cid)
        if ekind == "news":
            src = {"한국경제": 3, "매일경제": 2, "연합뉴스": 4}.get(facts[0].split("는")[0], 4)
            nid = conn.execute("""INSERT INTO news_articles (source_id, url, title, published_at) VALUES (%s, %s, %s, %s) RETURNING id""",
                               (src, f"https://example.invalid/news/fixture-{n}", title,
                                datetime.combine(eday, time(9, 0), SEOUL))).fetchone()[0]
            out["news"].append(nid)
            conn.execute("INSERT INTO update_sources (update_id, news_id, quote) VALUES (%s, %s, %s)", (cid, nid, facts[0]))
        else:
            rcept = f"2099{n:010d}"
            sym = memo["symbol"]
            conn.execute("""INSERT INTO disclosures (rcept_no, symbol, title, kind, rcept_dt) VALUES (%s, %s, %s, 'major', %s)""",
                         (rcept, sym, title, eday))
            out["disclosures"].append(rcept)
            conn.execute("INSERT INTO update_sources (update_id, disclosure_rcept_no, quote) VALUES (%s, %s, %s)", (cid, rcept, facts[0]))
    return out


def remove(conn, ids: dict) -> None:
    conn.execute("DELETE FROM tracking_updates WHERE id = ANY(%s)", (ids["cards"],))
    conn.execute("DELETE FROM tracking_items WHERE id = ANY(%s)", (ids["items"],))
    conn.execute("DELETE FROM news_articles WHERE id = ANY(%s)", (ids["news"],))
    conn.execute("DELETE FROM disclosures WHERE rcept_no = ANY(%s)", (ids["disclosures"],))
    conn.execute("DELETE FROM prices_daily WHERE volume = 1000001")             # 시험 행 표시 (거래량 1,000,001)
