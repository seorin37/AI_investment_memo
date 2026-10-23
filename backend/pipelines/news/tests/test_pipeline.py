import os
import re
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from backend.pipelines.news import embedder, pipeline, scoring, tagger

STOCKS = {"005930": ["삼성전자", "삼전"], "000660": ["SK하이닉스"]}


def test_match_stocks_uses_title_and_summary():
    assert tagger.match_stocks("삼성전자 실적", None, STOCKS) == ["005930"]
    assert tagger.match_stocks("반도체 업황", "SK하이닉스와 삼전 모두 증가", STOCKS) == ["005930", "000660"]
    assert tagger.match_stocks("날씨", "맑음", STOCKS) == []


def test_scores():
    assert scoring.dense_score([1, 0], [0.6, 0.8]) == pytest.approx(0.6)
    assert scoring.sparse_score({"a": 2, "b": 1}, {"a": 0.5, "c": 9}) == pytest.approx(1.0)
    assert scoring.hybrid_score(0.6, 1.0) == pytest.approx(0.7 * 0.6 + 0.3 * 1.0)


def test_day_range_is_kst_midnight():
    s, e = pipeline.day_range(date(2026, 10, 20))
    assert s == datetime(2026, 10, 19, 15, 0, tzinfo=timezone.utc)
    assert e == datetime(2026, 10, 20, 15, 0, tzinfo=timezone.utc)


def test_vector_literal():
    assert embedder.to_vector_literal([0.5, 1.0]) == "[0.5,1]"


DSN = os.environ.get("TEST_DATABASE_URL")
db = pytest.mark.skipif(not DSN, reason="TEST_DATABASE_URL 없음")


@pytest.fixture
def conn():
    psycopg = pytest.importorskip("psycopg")
    with psycopg.connect(DSN, autocommit=True) as cn:
        cn.execute("DROP TABLE IF EXISTS news_embedding_variants")
        mig = Path(__file__).parents[4] / "alembic" / "versions" / "0006_news_embedding_variants.py"
        sql = re.search(r'UPGRADE_SQL = """(.*?)"""', mig.read_text(encoding="utf-8"), re.S).group(1)
        sql = sql.replace("vector(1024)", "text")  # pgvector 없는 DB에서도 돌도록 text로 대체
        sql = re.sub(r"CREATE INDEX[^;]*;", "", sql)
        cn.execute(sql)
        cn.execute("TRUNCATE news_stocks, news_articles, ingest_runs RESTART IDENTITY CASCADE")
        yield cn


def add(conn, title, url, when, summary="요약"):
    return conn.execute(
        """INSERT INTO news_articles (source_id, url, title, summary, content_hash, published_at)
           VALUES ((SELECT id FROM news_sources WHERE code='hankyung'), %s, %s, %s, %s, %s) RETURNING id""",
        (url, title, summary, url, when)).fetchone()[0]


@db
def test_tag_embed_cleanup_flow(conn):
    since, until = pipeline.day_range(date(2026, 10, 20))
    inside = datetime(2026, 10, 20, 1, 0, tzinfo=timezone.utc)
    a = add(conn, "삼성전자 HBM4 양산", "https://h/1", inside)
    add(conn, "날씨 맑음", "https://h/2", inside)
    add(conn, "삼성전자 어제 이전", "https://h/3", datetime(2026, 10, 18, 1, 0, tzinfo=timezone.utc))

    assert tagger.tag_window(conn, STOCKS, since, until) == (2, 1)
    assert tagger.tag_window(conn, STOCKS, since, until) == (1, 0)   # 태깅 안 된 기사만 다시 훑는다

    calls = []

    def fake(texts):
        calls.append(texts)
        return [([0.1] * 1024, {"1": 0.5}) for _ in texts]

    assert embedder.embed_window(conn, "hybrid", fake, since, until) == 1
    assert embedder.embed_window(conn, "hybrid", fake, since, until) == 0   # 재실행 안전
    assert embedder.embed_window(conn, "dense", lambda t: [([0.2] * 1024, None) for _ in t], since, until) == 1
    assert calls[0] == ["삼성전자 HBM4 양산\n요약"]
    rows = conn.execute("SELECT variant, sparse IS NULL FROM news_embedding_variants ORDER BY variant").fetchall()
    assert rows == [("dense", True), ("hybrid", False)]

    # 정리: 7일 넘고 종목 연결 없는 기사만 삭제
    conn.execute("UPDATE news_articles SET published_at = now() - interval '10 days'")
    assert pipeline.cleanup(conn, 0) == 0       # 0이면 지우지 않는다
    assert pipeline.cleanup(conn, 30) == 0      # 10일 된 기사는 30일 보관 기준에서는 남는다
    assert pipeline.cleanup(conn, 7) == 2       # 태깅된 a와 임베딩은 남는다
    assert conn.execute("SELECT id FROM news_articles").fetchall() == [(a,)]


def test_get_dsn_handles_sqlalchemy_url_and_parts():
    from backend.pipelines.common.db import get_dsn
    assert get_dsn({"DATABASE_URL": "postgresql+psycopg://u:p@localhost:5432/memos"}) == "postgresql://u:p@localhost:5432/memos"
    assert get_dsn({"DATABASE_URL": "postgresql://u:p@h/db"}) == "postgresql://u:p@h/db"
    dsn = get_dsn({"POSTGRES_USER": "memos", "POSTGRES_PASSWORD": "p@ss w", "POSTGRES_DB": "memos"})
    assert "dbname=memos" in dsn and "user=memos" in dsn and "host=localhost" in dsn
    assert get_dsn({}) is None


def test_dotenv_interpolates_database_url(tmp_path):
    from dotenv import dotenv_values
    f = tmp_path / ".env"
    f.write_text("POSTGRES_USER=memos\nPOSTGRES_PASSWORD=pw\nPOSTGRES_PORT=5432\nPOSTGRES_DB=memos\n"
                 "DATABASE_URL=postgresql+psycopg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@localhost:${POSTGRES_PORT}/${POSTGRES_DB}\n")
    from backend.pipelines.common.db import get_dsn
    assert get_dsn(dotenv_values(f)) == "postgresql://memos:pw@localhost:5432/memos"


def test_title_only_ignores_summary_mentions():
    stocks = {"035420": ["네이버", "NAVER"], "005930": ["삼성전자"]}
    only = {"035420"}
    assert tagger.match_stocks("아이폰 듀오", "네이버 블로그에서 후기가 화제", stocks, only) == []
    assert tagger.match_stocks("네이버 노조 집회", None, stocks, only) == ["035420"]
    assert tagger.match_stocks("반도체", "삼성전자 실적", stocks, only) == ["005930"]


def test_lazy_encoder_loads_model_once_and_only_when_used(monkeypatch):
    calls = []

    def fake_make(variant, use_fp16=False):
        calls.append(variant)
        return lambda texts: [([0.0], None) for _ in texts]

    monkeypatch.setattr(embedder, "make_bge_m3_encoder", fake_make)
    enc = pipeline.LazyEncoder("hybrid")
    assert calls == []            # 만들기만 해서는 모델을 불러 오지 않는다
    enc(["a"]); enc(["b", "c"])
    assert calls == ["hybrid"]    # 여러 번 써도 한 번만 불러 온다


def test_run_hourly_survives_embedding_failure(monkeypatch):
    monkeypatch.setattr(pipeline, "_collect_rss", lambda dsn: 0)

    def boom(*a, **k):
        raise RuntimeError("embed down")

    monkeypatch.setattr(pipeline, "embed_recent", boom)
    # 임베딩이 실패해도 수집 결과(0)를 그대로 돌려주고 예외를 밖으로 내보내지 않는다
    assert pipeline.run_hourly("dsn", embed=True) == 0


def test_run_hourly_without_embed_does_not_touch_embedding(monkeypatch):
    monkeypatch.setattr(pipeline, "_collect_rss", lambda dsn: 0)
    monkeypatch.setattr(pipeline, "embed_recent", lambda *a, **k: (_ for _ in ()).throw(AssertionError("호출되면 안 됨")))
    assert pipeline.run_hourly("dsn") == 0


def test_loop_hourly_runs_each_cycle_and_survives_errors(monkeypatch):
    calls = {"run": 0, "sleep": []}

    def fake_run(dsn, embed, variant, days, stocks, encoder):
        calls["run"] += 1
        if calls["run"] == 1:
            raise RuntimeError("일시 오류")   # 한 번 실패해도 반복이 멈추면 안 된다

    def fake_sleep(sec):
        calls["sleep"].append(sec)
        if len(calls["sleep"]) >= 3:
            raise KeyboardInterrupt

    class FakeConn:
        def __enter__(self): return self
        def __exit__(self, *a): return False

    import psycopg as _pg  # noqa: F401  (loop_hourly가 정리 단계에서 import)
    monkeypatch.setattr(pipeline, "run_hourly", fake_run)
    monkeypatch.setattr(pipeline.clock, "sleep", fake_sleep)
    monkeypatch.setattr(pipeline, "cleanup", lambda conn, days: 0)
    monkeypatch.setattr(_pg, "connect", lambda *a, **k: FakeConn())
    with pytest.raises(KeyboardInterrupt):
        pipeline.loop_hourly("dsn", 1800, True, "hybrid", 3, Path("stocks.yaml"), 7)
    assert calls["run"] == 3
    assert all(1.0 <= s <= 1800 for s in calls["sleep"])


class _FakeCur:
    def __init__(self, inserted):
        self.inserted, self.rowcount = inserted, 0

    def __enter__(self): return self
    def __exit__(self, *a): return False

    def execute(self, sql, params):
        self.inserted.append(params[0])
        self.rowcount = 1


class _FakeConn:
    def __init__(self): self.inserted = []
    def cursor(self): return _FakeCur(self.inserted)


def test_embed_window_skips_a_poison_article_and_keeps_going(monkeypatch):
    rows = [(i, f"제목{i}", "요약") for i in range(1, 6)]
    monkeypatch.setattr(embedder, "pending_articles", lambda *a, **k: rows)
    since = until = datetime(2026, 10, 22, tzinfo=timezone.utc)

    def encode(texts):
        if any("제목3" in t for t in texts):
            raise RuntimeError("bad text")
        return [([0.1], {"1": 0.5}) for _ in texts]

    conn = _FakeConn()
    done = embedder.embed_window(conn, "hybrid", encode, since, until)
    assert done == 4                       # 3번 기사 하나만 건너뛰고 나머지는 저장
    assert sorted(conn.inserted) == [1, 2, 4, 5]
