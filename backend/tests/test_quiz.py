"""오늘의 퀴즈 API (2026-11-22). 순서 계산은 DB 없이, 읽기는 가짜 세션으로 확인한다."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.routes import get_current_user
from app.db import get_read_db
from app.quiz.routes import quiz_index, router, today_quiz


def _utc(*args) -> datetime:
    return datetime(*args, tzinfo=timezone.utc)


def test_quiz_index_changes_at_10am_kst():
    # 한국 시간 11-22 09:59 = UTC 00:59, 10:00 = UTC 01:00
    before = quiz_index(_utc(2026, 11, 22, 0, 59), 30)
    after = quiz_index(_utc(2026, 11, 22, 1, 0), 30)
    assert after == (before + 1) % 30
    # 다음 날 09:59 까지는 같은 문제
    assert quiz_index(_utc(2026, 11, 23, 0, 59), 30) == after


def test_quiz_index_matches_frontend_formula():
    # 프론트 quizIndex: floor((ms + 9h - 10h) / 1day) mod total
    for now in (_utc(2026, 11, 22, 5, 0), _utc(2027, 1, 1, 0, 30), _utc(2026, 2, 28, 23, 0)):
        ms = now.timestamp() * 1000
        assert quiz_index(now, 30) == int((ms + 9 * 3600_000 - 10 * 3600_000) // 86400_000) % 30


def test_quiz_index_rejects_empty_bank():
    with pytest.raises(ValueError):
        quiz_index(_utc(2026, 11, 22), 0)


ROW = {"slug": "ox_short_loss", "category": "trading", "quiz_type": "ox", "label": "거래 기초",
       "question": "공매도는 주가가 오를수록 손실이 커질 수 있다.", "options": ["O", "X"], "answer_index": 0,
       "explanation": "설명", "concept": "개념", "source": "투자 기초 상식"}


class _Result:
    def __init__(self, scalar=None, row=None):
        self._scalar, self._row = scalar, row

    def scalar(self):
        return self._scalar

    def mappings(self):
        return self

    def one_or_none(self):
        return self._row


class FakeDb:
    def __init__(self, total: int, row: dict | None):
        self.total, self.row, self.offsets = total, row, []

    def execute(self, stmt, params=None):
        if "count(*)" in str(stmt):
            return _Result(scalar=self.total)
        self.offsets.append(params["i"])
        return _Result(row=self.row)


def test_today_quiz_reads_row_at_today_offset():
    db = FakeDb(30, ROW)
    now = _utc(2026, 11, 22, 3, 0)
    quiz = today_quiz(db, now)
    assert db.offsets == [quiz_index(now, 30)]
    assert quiz["slug"] == "ox_short_loss" and quiz["options"] == ["O", "X"]
    assert quiz["index"] == quiz_index(now, 30) and quiz["total"] == 30


def test_today_quiz_none_when_bank_empty():
    assert today_quiz(FakeDb(0, None)) is None


def _client(db) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_read_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: {"id": 1}
    return TestClient(app)


def test_route_returns_quiz_and_404_when_empty():
    res = _client(FakeDb(30, ROW)).get("/api/v1/quiz/today")
    assert res.status_code == 200 and res.json()["quiz_type"] == "ox"
    assert _client(FakeDb(0, None)).get("/api/v1/quiz/today").status_code == 404
