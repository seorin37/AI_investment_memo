"""export_evidence의 계산 함수 (DB 없이)."""

from datetime import date, datetime, timezone

from eval.memo_personas import export_evidence as ex


def test_won_format():
    assert ex.won(74_068_300_000_000) == "74조 683억원"
    assert ex.won(676_100_000_000) == "6,761억원"
    assert ex.won(-1_200_000_000_000) == "-1조 2,000억원"


def test_sub_months_clamps_day():
    assert ex.sub_months(date(2026, 5, 31), 3) == date(2026, 2, 28)
    assert ex.sub_months(date(2026, 1, 15), 1) == date(2025, 12, 15)


def test_price_block_returns_highs_and_spikes(cfg):
    rows = []
    d0 = date(2025, 9, 1)
    days = [d for d in (date.fromordinal(d0.toordinal() + i) for i in range(420)) if d.weekday() < 5]
    for i, d in enumerate(days):
        close = 10000 + i * 10
        vol = 1000 if i != len(days) - 5 else 5000
        rows.append({"trade_date": d, "open": close, "high": close + 5, "low": close - 5, "close": close, "volume": vol})
    as_of = days[-1]
    block, items, warn = ex.price_block("005930", rows, as_of, cfg)
    assert block["close"] == rows[-1]["close"]
    assert block["high_52w"]["date"] == str(as_of)
    assert block["returns"]["1주"]["pct"] > 0
    assert len(block["volume_spikes"]) == 1 and block["volume_spikes"][0]["ratio"] == 5.0
    assert block["volume_spikes"][0]["id"] == f"prices_daily:005930:{days[-5]}"
    assert all(i["ids"] for i in items)


def test_financial_block_derives_standalone_quarters():
    rows = [{"period_end": date(2025, 3, 31), "period_type": "q1", "fs_div": "consolidated", "revenue": 100,
             "operating_income": 10, "net_income": 8, "total_liabilities": 50, "total_equity": 100},
            {"period_end": date(2025, 6, 30), "period_type": "half", "fs_div": "consolidated", "revenue": 220,
             "operating_income": 18, "net_income": 15, "total_liabilities": 50, "total_equity": 100}]
    block, items = ex.financial_block("005930", rows, [])
    q2 = block["quarters"][-1]
    assert (q2["quarter"], q2["revenue"], q2["operating_income"]) == (2, 120, 8)
    assert q2["ids"] == ["financials:005930:2025-06-30:half", "financials:005930:2025-03-31:q1"]
    assert q2["op_margin_pct"] == round(8 / 120 * 100, 2)
    assert "단독(연결)" in items[-1]["text"]


def test_dedupe_news_titles():
    rows = [{"title": "[단독] 삼성전자 신고가"}, {"title": "삼성전자 신고가"}, {"title": "삼성전자 신고가!"}, {"title": "다른 기사"}]
    assert [r["title"] for r in ex.dedupe_news(rows, 15)] == ["[단독] 삼성전자 신고가", "다른 기사"]


def test_disclosure_excerpt_is_verbatim(cfg):
    text = "매출액은 79조 1,400억원으로 전년 대비 3.2% 증가했습니다. " * 20
    rows = [{"rcept_no": "20261014000123", "title": "분기보고서 (2026.09)", "kind": "quarterly",
             "period_end": date(2026, 9, 30), "rcept_dt": date(2026, 10, 14), "source_url": None}]
    chunks = [{"id": 5, "rcept_no": "20261014000123", "chunk_index": 3, "section": "경영진단 및 분석의견", "chunk_text": text}]
    out, items = ex.disclosure_block("005930", rows, chunks, cfg)
    exc = out[0]["chunks"][0]["excerpt"].rstrip(" …")
    assert text.startswith(exc) and len(exc) <= cfg["evidence"]["excerpt_chars"]
    assert out[0]["url"].endswith("rcpNo=20261014000123") and out[0]["url_from_db"] is False
    assert items[0]["ids"] == ["disclosures:20261014000123", "disclosure_chunks:5"]


def test_news_date_is_kst(cfg):
    rows = [{"id": 1, "title": "기사", "url": "u", "summary": None, "source_name": "연합뉴스",
             "published_at": datetime(2026, 10, 22, 16, 30, tzinfo=timezone.utc)}]
    out, items = ex.news_block("005930", rows, cfg)
    assert out[0]["date"] == "2026-10-23" and out[0]["summary"] == "없음"


def test_sqlalchemy_url():
    assert ex.sqlalchemy_url("postgresql://u:p@h:5432/d") == "postgresql+psycopg://u:p@h:5432/d"
    assert ex.sqlalchemy_url("postgres+psycopg2://u@h/d") == "postgresql+psycopg://u@h/d"
