"""많이 찾는 종목 GET /api/v1/stocks/popular — 중앙 DB 없이 (가짜 저장소 · SQL 문장 확인)."""

from __future__ import annotations

import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.routes import get_auth_service, get_current_user
from app.stocks.repository import StockRepository
from app.stocks.routes import get_query_service, router
from app.stocks.service import POPULAR_MIN_USERS, StockService


def m(code, name, market="KOSPI"):
    return {"code": code, "name": name, "market": market}


class FakePopularRepo:
    """user_stocks 담은 사람 수 · 최신 시총 순서를 흉내 낸다 (SQL 의 HAVING · KOSPI · 제외는 여기서 같은 규칙)."""

    def __init__(self, holders: dict[str, int], caps: list[dict], masters: dict[str, dict]):
        self.holders = holders            # code → 서로 다른 사용자 수 (활성 행만)
        self.caps = caps                  # 최신 거래일 시총 큰 순 (KOSPI 만)
        self.masters = masters
        self.calls: list[tuple] = []

    def popular_by_users(self, *, min_users, limit):
        self.calls.append(("users", min_users, limit))
        rows = [(n, code) for code, n in self.holders.items() if n >= min_users and self.masters[code]["market"] == "KOSPI"]
        rows.sort(key=lambda r: (-r[0], r[1]))
        return [{**self.masters[code], "holders": n} for n, code in rows[:limit]]

    def top_market_cap(self, *, limit, exclude):
        self.calls.append(("cap", limit, tuple(exclude)))
        return [{**row, "market_cap": 10**12} for row in self.caps if row["code"] not in exclude][:limit]


MASTERS = {
    "000660": m("000660", "SK하이닉스"),
    "005930": m("005930", "삼성전자"),
    "035420": m("035420", "NAVER"),
    "247540": m("247540", "에코프로비엠", "KOSDAQ"),
    "373220": m("373220", "LG에너지솔루션"),
    "207940": m("207940", "삼성바이오로직스"),
    "005380": m("005380", "현대차"),
}
CAPS = [MASTERS["005930"], MASTERS["000660"], MASTERS["373220"], MASTERS["207940"], MASTERS["005380"]]


class PopularServiceTest(unittest.TestCase):
    def service(self, holders):
        self.repo = FakePopularRepo(holders, CAPS, MASTERS)
        return StockService(self.repo)

    def test_only_three_or_more_users_count_then_fill_by_market_cap(self):
        # 000660: 5명, 035420: 3명 → 인정 / 373220: 2명 → 인원으로는 불인정 (시총으로만 들어올 수 있음)
        got = self.service({"000660": 5, "035420": POPULAR_MIN_USERS, "373220": 2}).popular(5)
        self.assertEqual([r["code"] for r in got], ["000660", "035420", "005930", "373220", "207940"])
        self.assertEqual(self.repo.calls[0], ("users", 3, 5))
        self.assertEqual(self.repo.calls[1], ("cap", 3, ("000660", "035420")))

    def test_no_duplicates_between_users_and_market_cap(self):
        got = self.service({"005930": 9, "000660": 4}).popular(4)
        codes = [r["code"] for r in got]
        self.assertEqual(codes, ["005930", "000660", "373220", "207940"])
        self.assertEqual(len(codes), len(set(codes)))

    def test_kospi_only(self):
        got = self.service({"247540": 10}).popular(3)
        self.assertNotIn("247540", [r["code"] for r in got])
        self.assertTrue(all(r["market"] == "KOSPI" for r in got))

    def test_enough_users_skips_market_cap(self):
        got = self.service({"000660": 5, "005930": 4, "035420": 3}).popular(3)
        self.assertEqual([r["code"] for r in got], ["000660", "005930", "035420"])
        self.assertEqual([c[0] for c in self.repo.calls], ["users"])

    def test_limit_is_clamped_and_no_counts_in_result(self):
        got = self.service({}).popular(99)
        self.assertEqual(self.repo.calls[0], ("users", 3, 30))
        self.assertLessEqual(len(got), 30)
        for row in got:
            self.assertEqual(set(row), {"code", "name", "market"})


class PopularApiTest(unittest.TestCase):
    def setUp(self):
        service = StockService(FakePopularRepo({"000660": 5}, CAPS, MASTERS))
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_current_user] = lambda: {"id": "7"}
        app.dependency_overrides[get_query_service] = lambda: service
        self.client = TestClient(app)

    def test_default_limit_and_shape(self):
        res = self.client.get("/api/v1/stocks/popular")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body[0], {"code": "000660", "name": "SK하이닉스", "market": "KOSPI"})
        self.assertLessEqual(len(body), 12)
        self.assertTrue(all(set(r) == {"code", "name", "market"} for r in body))   # 인원 수 · 시총 없음

    def test_limit_param(self):
        self.assertEqual(len(self.client.get("/api/v1/stocks/popular?limit=2").json()), 2)
        self.assertEqual(self.client.get("/api/v1/stocks/popular?limit=0").status_code, 422)
        self.assertEqual(self.client.get("/api/v1/stocks/popular?limit=31").status_code, 422)

    def test_popular_is_not_taken_as_stock_code(self):
        # /{code} 보다 먼저 선언돼 있어야 한다
        self.assertEqual(self.client.get("/api/v1/stocks/popular").status_code, 200)

    def test_requires_authentication(self):
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_auth_service] = lambda: None
        app.dependency_overrides[get_query_service] = lambda: None
        self.assertEqual(TestClient(app).get("/api/v1/stocks/popular").status_code, 401)


class RecordingSession:
    def __init__(self):
        self.calls = []

    def execute(self, statement, params=None):
        self.calls.append((" ".join(str(statement).split()), params))
        return self

    def mappings(self):
        return self

    def all(self):
        return []


class PopularSqlTest(unittest.TestCase):
    def test_users_query_counts_distinct_active_users_kospi_with_threshold(self):
        s = RecordingSession()
        StockRepository(s).popular_by_users(min_users=3, limit=12)
        sql, params = s.calls[0]
        self.assertIn("us.deleted_at IS NULL", sql)
        self.assertIn("u.deleted_at IS NULL", sql)
        self.assertIn("s.market = 'KOSPI'", sql)
        self.assertIn("HAVING count(DISTINCT us.user_id) >= :min_users", sql)
        self.assertIn("ORDER BY count(DISTINCT us.user_id) DESC", sql)
        self.assertNotIn("count(DISTINCT us.user_id) AS", sql)                    # 인원 수를 돌려주지 않음
        self.assertEqual(params, {"min_users": 3, "limit": 12})

    def test_market_cap_query_uses_latest_date_with_market_cap_and_excludes(self):
        s = RecordingSession()
        StockRepository(s).top_market_cap(limit=5, exclude=["000660"])
        sql, params = s.calls[0]
        self.assertIn("SELECT max(p.trade_date) AS d FROM prices_daily p", sql)
        self.assertIn("WHERE s.market = 'KOSPI' AND p.market_cap IS NOT NULL )", sql)
        self.assertIn("NOT (btrim(s.symbol) = ANY(:exclude))", sql)
        self.assertIn("ORDER BY p.market_cap DESC", sql)
        self.assertNotIn("p.market_cap AS", sql)                                  # 시총 숫자를 돌려주지 않음
        self.assertEqual(params, {"limit": 5, "exclude": ["000660"]})


if __name__ == "__main__":
    unittest.main()
