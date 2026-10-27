"""export_evidence SQL을 임시 Postgres(pgserver)에서 실제로 실행한다.
레포 Alembic 마이그레이션을 끝까지 적용한 스키마에 가짜 행을 넣고 결과·읽기 전용·원본 ID를 확인한다.
pgserver가 없으면 건너뛴다: pip install -r eval/memo_personas/requirements-dev.txt
"""

from datetime import date, timedelta

import pytest

pgserver = pytest.importorskip("pgserver")

from eval.memo_personas import export_evidence as ex  # noqa: E402
from eval.memo_personas.devtools import fake_data, fake_db  # noqa: E402


@pytest.fixture(scope="module")
def db(tmp_path_factory):
    srv, url = fake_db.start(tmp_path_factory.mktemp("pg"))
    try:
        fake_db.migrate(url)
        fake_db.seed(url)
        yield url
    finally:
        srv.cleanup()


@pytest.fixture(scope="module")
def result(db, base_cfg):
    with ex.make_engine(db).connect() as conn:
        assert ex.check_schema(conn) == {}
        return ex.build_all(conn, base_cfg)


def test_schema_and_read_only(db):
    from sqlalchemy import text

    with ex.make_engine(db).connect() as conn:
        with pytest.raises(Exception, match="read-only"):
            conn.execute(text("INSERT INTO stocks (symbol, name) VALUES ('999999', 'x')"))


def test_prices_match_source_rows(result):
    rows = [r for r in fake_data.all_rows()["prices"] if r["symbol"] == "005930"]
    pack = result["packs"]["005930"]
    assert pack["as_of_date"] == "2026-10-23"
    assert pack["price"]["close"] == rows[-1]["close"]
    base = [r for r in rows if r["trade_date"] <= date(2026, 10, 16)][-1]["close"]
    assert pack["price"]["returns"]["1주"]["pct"] == round((rows[-1]["close"] / base - 1) * 100, 2)
    hi = max((r for r in rows if r["trade_date"] > date(2026, 10, 23) - timedelta(days=364)),
             key=lambda r: (r["high"], r["trade_date"]))
    assert pack["price"]["high_52w"]["price"] == hi["high"]


def test_news_disclosures_financials(result, base_cfg):
    pack = result["packs"]["005930"]
    titles = [n["title"] for n in pack["news"]]
    assert len(titles) <= base_cfg["evidence"]["news_max"]
    assert not any(t.startswith("[단독]") for t in titles) and "삼성전자 옛날 기사" not in titles
    discs = pack["disclosures"]
    assert len(discs) == base_cfg["evidence"]["disclosures_max"]
    assert [d["rcept_dt"] for d in discs] == sorted([d["rcept_dt"] for d in discs], reverse=True)
    assert discs[0]["chunks"][0]["section"] == "경영진단 및 분석의견"  # 80자 미만 '표지' 청크는 뒤로
    fin = {(q["year"], q["quarter"]): q for q in pack["financials"]["quarters"]}
    src = {(r["period_end"], r["period_type"]): r for r in fake_data.financials("005930")}
    q2 = fin[(2026, 2)]
    assert q2["revenue"] == src[(date(2026, 6, 30), "half")]["revenue"] - src[(date(2026, 3, 31), "q1")]["revenue"]
    kb = result["packs"]["105560"]
    assert kb["financials"]["financial_sector"] != "없음"
    assert len(result["macro"]["items"]) == 5


def test_every_id_exists_in_db(db, result):
    from sqlalchemy import text

    ids = {x for p in result["packs"].values() for i in p["items"] for x in i["ids"]} | \
          {x for i in result["macro"]["items"] for x in i["ids"]}
    checks = {
        "prices_daily": "SELECT 1 FROM prices_daily WHERE symbol = :a AND trade_date = CAST(:b AS date)",
        "disclosures": "SELECT 1 FROM disclosures WHERE rcept_no = :a",
        "disclosure_chunks": "SELECT 1 FROM disclosure_chunks WHERE id = CAST(:a AS bigint)",
        "news_articles": "SELECT 1 FROM news_articles WHERE id = CAST(:a AS bigint)",
        "financials": "SELECT 1 FROM financials WHERE symbol = :a AND period_end = CAST(:b AS date) AND period_type = CAST(:c AS report_period)",
        "financials_fin": "SELECT 1 FROM financials_fin WHERE symbol = :a AND period_end = CAST(:b AS date) AND period_type = CAST(:c AS report_period)",
        "economic_observations": "SELECT 1 FROM economic_observations WHERE indicator_code = :a AND observation_date = CAST(:b AS date)",
    }
    with ex.make_engine(db).connect() as conn:
        for i in ids:
            table, *key = i.split(":")
            params = dict(zip("abc", key))
            assert conn.execute(text(checks[table]), params).first(), i
