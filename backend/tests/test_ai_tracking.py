"""설정 사용량 탭 종목별 추적 현황 GET /ai/tracking (2026-11-23). SQL 결과 묶기만 가짜 세션으로 확인한다."""
from __future__ import annotations

from app.stats.routes import tracking_status


class _Res:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def all(self):
        return self._rows


class FakeDb:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, stmt, params):
        assert params == {"u": 2}
        return _Res(self.rows)


def row(code, name, memo_id=None, title=None, content=None, type_=None, desc=None):
    return {"code": code, "name": name, "memo_id": memo_id, "title": title, "content": content, "type": type_, "description": desc}


def test_groups_items_by_stock_and_memo():
    out = tracking_status(FakeDb([
        row("005930", "삼성전자", 3, "", "삼성전자 왜 안 오르냐\n둘째 줄", "topic", "주가가 오르지 못하는 원인"),
        row("005930", "삼성전자", 3, "", "삼성전자 왜 안 오르냐\n둘째 줄", "price_below", "70,000원 아래로"),
        row("000660", "SK하이닉스"),                                        # 추적 메모 없는 종목도 남긴다
        row("035420", "NAVER", 1, "웹툰 메모", "본문", None, None),          # 항목 없는 메모는 빼고
    ]), 2)
    assert [s["stock_code"] for s in out] == ["005930", "000660", "035420"]
    assert out[0]["memos"] == [{"memo_id": "3", "title": "삼성전자 왜 안 오르냐",
                                "chips": ["공시·뉴스 · 주가가 오르지 못하는 원인", "가격 조건 · 70,000원 아래로"]}]
    assert out[1]["memos"] == [] and out[2]["memos"] == []
