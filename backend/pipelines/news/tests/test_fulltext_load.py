"""원문 적재(fulltext_load) 테스트. DB·모델 없이 가짜 저장소·가짜 인코더로 확인한다."""
import json
from datetime import datetime, timezone

import numpy as np

from backend.pipelines.disclosures.embedder import Encoded
from backend.pipelines.news import fulltext_load as fl

BODY = "삼성전자가 엔비디아에 6세대 고대역폭메모리(HBM4)를 공급한다. 업계는 내년 물량이 늘 것으로 본다. " * 30


class Tokens:                                         # 글자 2개 = 토큰 1개로 센다
    def count(self, text):
        return max(1, len(text) // 2)

    def offsets(self, text):
        return [(i, i + 2) for i in range(0, len(text), 2)]


class FakeStore:
    def __init__(self, urls, loaded=()):
        self.urls, self.loaded, self.bodies, self.chunks, self.writes = dict(urls), set(loaded), {}, {}, 0

    def article_urls(self, ids):
        return {i: self.urls[i] for i in ids if i in self.urls}

    def loaded_ids(self, ids):
        return {i for i in ids if i in self.loaded}

    def write(self, bodies, chunks):                  # ON CONFLICT DO NOTHING 흉내
        self.writes += 1
        for b in bodies:
            if b[0] not in self.bodies:
                self.bodies[b[0]] = b
                self.loaded.add(b[0])
        for c in chunks:
            self.chunks.setdefault((c[0], c[1]), c)


def encode(texts):
    out = []
    for i, _ in enumerate(texts):
        v = np.zeros(1024, dtype=np.float32)
        v[i % 1024] = 1.0
        out.append(Encoded(dense=v, sparse={"5": 0.3, "17": 0.1}))
    return out


def raw(i, status="ok", body=BODY, url=None):
    return {"news_id": i, "url": url or f"https://www.hankyung.com/article/{i}", "source_code": "hankyung",
            "fetch_method": "link", "title": f"제목 {i}", "published_at": "2026-11-05T09:00:00+09:00",
            "status": status, "reason": None, "subtitle": None, "body": body if status == "ok" else None,
            "body_chars": len(body), "body_hash": fl.hashlib.sha256(body.encode()).hexdigest(),
            "extractor_version": "hankyung-abc", "http_status": 200, "attempts": 1,
            "fetched_at": "2026-11-06T16:41:00+09:00"}


def write_jsonl(tmp_path, rows):
    path = tmp_path / "2026-11-05.jsonl"
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
    return path


IDENT = fl.embedding_identity({"name": "BAAI/bge-m3", "revision": "5617a9f6", "max_length": 512})


def test_read_ok_records_keeps_last_ok_per_id(tmp_path):
    path = write_jsonl(tmp_path, [raw(1, "failed"), raw(1), raw(2, "skipped"), raw(3)])
    recs = fl.read_ok_records([path])
    assert [r.news_id for r in recs] == [1, 3]


def test_plan_skips_loaded_missing_and_url_mismatch(tmp_path):
    recs = fl.read_ok_records([write_jsonl(tmp_path, [raw(1), raw(2), raw(3), raw(4), raw(5)])])
    store = FakeStore({1: recs[0].url, 2: recs[1].url, 3: "https://other/3", 5: recs[4].url}, loaded={2})
    p = fl.plan(recs, store)
    assert [r.news_id for r in p.todo] == [1, 5] and p.already == 1
    assert p.missing == [4] and p.url_mismatch == [3]                          # 4는 DB에 없음, 3은 다른 기사
    assert [r.news_id for r in fl.plan(recs, store, limit=1).todo] == [1]


def test_load_writes_bodies_and_chunks_with_metadata_and_is_idempotent(tmp_path):
    recs = fl.read_ok_records([write_jsonl(tmp_path, [raw(1), raw(2), raw(3)])])
    store = FakeStore({r.news_id: r.url for r in recs})
    items, bad = fl.chunk_records(fl.plan(recs, store).todo, Tokens())
    assert bad == [] and all(len(chunks) > 1 for _, chunks in items)          # 긴 본문은 여러 청크
    when = datetime(2026, 11, 6, tzinfo=timezone.utc)
    report = fl.load(items, encode, store, IDENT, group_size=2, now=lambda: when)
    assert report.articles == 3 and store.writes == 2                          # 2기사씩 한 번에 쓴다
    assert report.chunks == len(store.chunks) == sum(len(c) for _, c in items)
    news_id, idx, chunk_text, embed_text, start, end, ntok, chunker, dense, sparse, model, rev, chash, at = \
        store.chunks[(1, 0)]
    assert embed_text.startswith("[한국경제 2026-11-05 | 제목 1]\n") and embed_text.endswith(chunk_text)
    assert end > start and 1 <= ntok <= 512 and chunker == "news-1.0:400/80/512"
    assert dense.startswith("[") and len(dense.strip("[]").split(",")) == 1024
    assert json.loads(sparse) == {"17": 0.1, "5": 0.3}
    assert (model, rev, chash, at) == ("BAAI/bge-m3", "5617a9f6", IDENT.config_hash, when)
    assert store.bodies[1][:3] == (1, "hankyung", "link")
    # 다시 돌리면: 이미 들어간 news_id는 계획 단계에서 빠지고 중복 청크가 생기지 않는다
    again = fl.plan(recs, store)
    assert again.todo == [] and again.already == 3
    n = len(store.chunks)
    fl.load(items, encode, store, IDENT)                                       # 계획 없이 다시 넣어도 ON CONFLICT
    assert len(store.chunks) == n and len(store.bodies) == 3


def test_identity_matches_disclosure_rule():                # disclosures.pipeline·run_events.embedding_identity와 같은 식
    cfg = {"name": "BAAI/bge-m3", "revision": "5617a9f6", "max_length": 512, "batch_size": 4}
    keys = {"name": "BAAI/bge-m3", "revision": "5617a9f6", "max_length": 512}   # batch_size 등은 해시에 안 들어간다
    expected = fl.hashlib.sha256(json.dumps(keys, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    assert fl.embedding_identity(cfg) == fl.Identity("BAAI/bge-m3", "5617a9f6", expected)
    assert fl.embedding_identity({**cfg, "max_length": 1024}).config_hash != IDENT.config_hash


def test_bad_embedding_is_not_written(tmp_path):
    recs = fl.read_ok_records([write_jsonl(tmp_path, [raw(1)])])
    store = FakeStore({1: recs[0].url})
    items, _ = fl.chunk_records(recs, Tokens())

    def nan_encode(texts):
        return [Encoded(dense=np.full(1024, np.nan, dtype=np.float32), sparse={"5": 0.3}) for _ in texts]
    try:
        fl.load(items, nan_encode, store, IDENT)
        raise AssertionError("NaN 임베딩이 통과했다")
    except fl_errors():
        pass
    assert store.writes == 0 and store.bodies == {}


def fl_errors():
    from backend.pipelines.disclosures.embedder import EmbeddingQualityError
    return EmbeddingQualityError


def test_dsn_target_hides_credentials():
    assert fl.dsn_target("postgresql://memos:secret@127.0.0.1:5433/memos_test") == "127.0.0.1:5433/memos_test"
    assert "secret" not in fl.dsn_target("host=192.168.0.105 port=15432 dbname=memos user=u password=secret")
    assert fl.dsn_target("host=192.168.0.105 port=15432 dbname=memos password=secret") == "192.168.0.105:15432/memos"


def test_load_requires_matching_target(monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@192.168.0.105:15432/memos")
    assert fl.main(["--date", "2026-11-05", "--load"]) == 3                   # --target 없음
    assert fl.main(["--date", "2026-11-05", "--load", "--target", "127.0.0.1:5433"]) == 3
    out = capsys.readouterr().out
    assert "192.168.0.105:15432/memos" in out and "쓰지 않고 멈춥니다" in out and "p@" not in out
