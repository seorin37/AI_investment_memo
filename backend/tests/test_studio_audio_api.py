"""AI 오디오 API /studio/audio (2026-11-24). DB·LLM·Fish 없이 가짜 세션·규칙 대본·신호음으로 흐름만 확인한다."""
from __future__ import annotations

import json
from contextlib import contextmanager

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.routes import get_current_user
from app.db import get_read_db
from app.studio_audio import routes
from app.studio_audio.tts import FakeTTS
from pipelines.studio_audio.smoke import sample_brief

OPTIONS = {"stocks": [{"stock_code": "900001", "name": "샘플바이오", "news": [2, 2, 2], "hold": "보유"},
                      {"stock_code": "900002", "name": "샘플식품", "news": [1, 1, 1], "hold": "관심"},
                      {"stock_code": "900003", "name": "샘플건설", "news": [0, 0, 0], "hold": "관심"}],
           "periods": ["전날", "최근 3일", "최근 7일"], "last_close": "02.06(금)", "last_close_date": "2026-02-06"}


class _Res:
    def __init__(self, rows=None, scalar=None, rowcount=1):
        self._rows, self._scalar, self.rowcount = rows or [], scalar, rowcount

    def mappings(self):
        return self

    def first(self):
        return self._rows[0] if self._rows else None

    def scalar(self):
        return self._scalar


class FakeDb:
    def __init__(self, same=None, item=None, asset=None):
        self.same, self.item, self.asset, self.calls = same, item, asset, []

    def execute(self, stmt, params=None):
        sql = str(stmt).lstrip()
        self.calls.append((" ".join(sql.split()[:3]), params))
        if sql.startswith("SELECT id, status FROM studio_items"):
            return _Res([self.same] if self.same else [])
        if sql.startswith("INSERT INTO studio_items"):
            return _Res(scalar=42)
        if sql.startswith("SELECT id, status, title"):
            return _Res([self.item] if self.item else [])
        if sql.startswith("SELECT a.storage_path"):
            return _Res([self.asset] if self.asset else [])
        return _Res()

    def rollback(self):
        pass

    def ops(self, head):
        return [p for op, p in self.calls if op.startswith(head)]


def client(monkeypatch, tmp_path, db: FakeDb, balance=30, synth_ready=True):
    spent, generated = [], []

    @contextmanager
    def session():
        yield db

    def fake_synth(_cfg):
        if not synth_ready:
            raise RuntimeError("tts_not_ready: FISH_API_KEY가 없어요")
        return FakeTTS(cps=40, rate=8000)

    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[get_current_user] = lambda: {"id": 2}
    app.dependency_overrides[get_read_db] = lambda: db
    monkeypatch.setattr(routes, "DATA_DIR", tmp_path)
    monkeypatch.setattr(routes, "get_session", session)
    monkeypatch.setattr(routes, "get_read_session", session)
    monkeypatch.setattr(routes, "audio_options", lambda _db, _u, _now=None: OPTIONS)
    monkeypatch.setattr(routes, "collect_brief", lambda _db, _u, _s, _e, codes, **_k: sample_brief())
    monkeypatch.setattr(routes, "_llm", lambda _cfg: None)                    # 규칙 대본
    monkeypatch.setattr(routes, "_synth", fake_synth)
    monkeypatch.setattr(routes.ledger, "cost", lambda _r: 5)
    monkeypatch.setattr(routes.ledger, "refresh", lambda _db, _u: None)
    monkeypatch.setattr(routes.ledger, "balance", lambda _db, _u: balance)
    monkeypatch.setattr(routes.ledger, "spend", lambda _db, u, a, r, k=None, i=None: spent.append((u, a, r, k, i)) or a)
    orig = routes.generate
    monkeypatch.setattr(routes, "generate", lambda *a, **k: generated.append(a) or orig(*a, **k))
    return TestClient(app), spent, generated


def test_creates_generates_and_charges_once(monkeypatch, tmp_path):
    db = FakeDb()
    api, spent, generated = client(monkeypatch, tmp_path, db)
    res = api.post("/api/v1/studio/audio", json={"codes": ["900002", "900001"], "period": "최근 7일", "market": True})
    assert res.status_code == 202 and res.json() == {"item_id": "42", "status": "queued", "reused": False}
    assert generated == [(42, 2, ["900001", "900002"], "최근 7일", True)]       # 정렬된 종목
    assert db.ops("UPDATE studio_items SET") and db.ops("UPDATE studio_items SET")[0] == {"id": 42}   # generating
    assert spent == [(2, 5, "audio", "studio_item", 42)]                          # ready 때 한 번만
    ready = next(p for p in db.ops("UPDATE studio_items SET") if "content" in p)
    content = json.loads(ready["content"])
    assert content["options"] == {"codes": ["900001", "900002", "900003"], "period": "최근 7일", "market": True}
    assert content["script"] and content["chapters"][0][1] == "오프닝" and content["meta"].startswith("오디오 · 3종목 · 최근 7일 · ")
    assert "path" not in content["audio"]                                         # 서버 경로는 화면에 내보내지 않는다
    asset = db.ops("INSERT INTO audio_assets")[0]
    assert asset["path"].startswith("42/episode.") and (tmp_path / asset["path"]).is_file()
    assert asset["provider"] == "fake" and len(asset["hash"]) == 64


def test_reuses_same_day_same_options(monkeypatch, tmp_path):
    api, spent, generated = client(monkeypatch, tmp_path, FakeDb(same={"id": 7, "status": "ready"}))
    res = api.post("/api/v1/studio/audio", json={"codes": ["900001"]})
    assert res.json() == {"item_id": "7", "status": "ready", "reused": True}
    assert generated == [] and spent == []


def test_rejects_other_stock_no_news_and_low_credit(monkeypatch, tmp_path):
    api, _, generated = client(monkeypatch, tmp_path, FakeDb())
    assert api.post("/api/v1/studio/audio", json={"codes": ["035420"]}).status_code == 422
    res = api.post("/api/v1/studio/audio", json={"codes": ["900003"], "market": False})     # 소식 0건 + 증시 끔
    assert res.status_code == 422 and "새 소식" in res.json()["detail"]
    assert api.post("/api/v1/studio/audio", json={"codes": ["900003"], "period": "최근 4일"}).status_code == 422
    api, spent, generated = client(monkeypatch, tmp_path, FakeDb(), balance=4)
    assert api.post("/api/v1/studio/audio", json={"codes": ["900001"]}).status_code == 402
    assert spent == [] and generated == []


def test_tts_not_ready_marks_failed_without_credit(monkeypatch, tmp_path):
    db = FakeDb()
    api, spent, _ = client(monkeypatch, tmp_path, db, synth_ready=False)
    assert api.post("/api/v1/studio/audio", json={"codes": ["900001"]}).status_code == 202
    assert spent == []
    failed = [p for p in db.ops("UPDATE studio_items SET") if "error" in p]
    assert failed and failed[0]["error"].startswith("tts_not_ready")


def test_get_item_and_file(monkeypatch, tmp_path):
    (tmp_path / "42").mkdir()
    (tmp_path / "42" / "episode.wav").write_bytes(b"RIFFfake")
    item = {"id": 42, "status": "ready", "title": "02.08 내 종목 라디오", "period_start": "2026-02-02", "period_end": "2026-02-08",
            "symbols": ["900001"], "content": {"dur": 120, "script": [[0, "A", "안녕하세요"]]}, "error": None,
            "credits_used": 5, "created_at": None, "ready_at": None}
    db = FakeDb(item=item, asset={"storage_path": "42/episode.wav", "mime_type": "audio/wav"})
    api, _, _ = client(monkeypatch, tmp_path, db)
    got = api.get("/api/v1/studio/audio/42").json()
    assert got["status"] == "ready" and got["file_url"] == "/api/v1/studio/audio/42/file" and got["content"]["dur"] == 120
    res = api.get("/api/v1/studio/audio/42/file")
    assert res.status_code == 200 and res.content == b"RIFFfake" and res.headers["content-type"] == "audio/wav"
    db.asset = {"storage_path": "../../etc/passwd", "mime_type": "audio/wav"}       # 폴더 밖 경로는 내주지 않는다
    assert api.get("/api/v1/studio/audio/42/file").status_code == 404
    db.item = {**item, "status": "generating", "content": {"options": {"period": "전날"}, "script": ["x"]}}
    got = api.get("/api/v1/studio/audio/42").json()
    assert got["file_url"] is None and got["content"] == {"options": {"period": "전날"}}
    db.item = None
    assert api.get("/api/v1/studio/audio/9").status_code == 404
