"""B 그룹 API 테스트: 기업 정보·재무·시장 개요·고정 메모·휴지통 (중앙 DB 없이)."""

from __future__ import annotations

import unittest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.routes import get_auth_service, get_current_user
from app.board.routes import get_query_service as get_board_query_service
from app.board.routes import router as board_router
from app.board.service import BoardService
from app.marketdata.routes import get_marketdata_service, router as marketdata_router
from app.marketdata.service import MarketDataService
from app.trash.routes import (
    get_trash_command_service,
    get_trash_query_service,
    router as trash_router,
)
from app.trash.service import TrashService


def _prices(n: int) -> list[dict]:
    return [
        {
            "trade_date": date(2026, 1, 1) + timedelta(days=i),
            "open": Decimal(1000 + i),
            "high": Decimal(1100 + i),
            "low": Decimal(900 + i),
            "close": Decimal(1050 + i),
            "volume": 10,
            "trade_value": None,
            "market_cap": None,
            "listed_shares": None,
        }
        for i in range(n)
    ]


class FakeMarketRepo:
    def __init__(self) -> None:
        self.stocks = {
            "005930": {
                "code": "005930", "name": "삼성전자", "market": "KOSPI",
                "description": "  전자 기업  ", "shares_outstanding": 1_000,
            },
            "105560": {
                "code": "105560", "name": "KB금융", "market": "KOSPI",
                "description": None, "shares_outstanding": None,
            },
        }
        self.prices = {"005930": _prices(300), "105560": _prices(3)}
        self.snapshots = {
            "005930": {
                "per": Decimal("30.070000"), "pbr": Decimal("3.080000"),
                "eps": Decimal("6564.0000"), "bps": Decimal("63997.0000"),
                "w52_high": Decimal("374500.00"), "w52_low": Decimal("94500.00"),
                "market_cap": Decimal("1154055400000000"), "listed_shares": 5_846_278_608,
            }
        }
        self.annual = {
            "005930": [
                {
                    "period_end": date(2024, 12, 31), "fs_div": "consolidated",
                    "revenue": Decimal(1000), "operating_income": Decimal(109),
                    "net_income": Decimal(112), "total_equity": Decimal(2000), "metric_roe": None,
                },
                {
                    "period_end": date(2025, 12, 31), "fs_div": "consolidated",
                    "revenue": Decimal(3000), "operating_income": Decimal(393),
                    "net_income": Decimal(399), "total_equity": Decimal(4000), "metric_roe": Decimal("10.14"),
                },
            ],
            "105560": [
                {
                    "period_end": date(2025, 12, 31), "fs_div": "consolidated",
                    "revenue": None, "operating_income": Decimal(85),
                    "net_income": Decimal(58), "total_equity": Decimal(600), "metric_roe": None,
                }
            ],
        }
        # 기업정보 분기 재무 (UI v2, 2026-11-21): 13분기 중 최근 12개만, 2026-03은 자본잠식
        self.quarters = {
            "005930": [
                {
                    "period_end": date(2023 + (i + 2) // 4, 3 * ((i + 2) % 4) + 3, 30 if (3 * ((i + 2) % 4) + 3) in (6, 9) else 31),
                    "fs_div": "consolidated",
                    "revenue": Decimal(100_000_000_000) * (i + 1), "operating_income": Decimal(12_345_678_901),
                    "net_income": Decimal(-5_000_000_000) if i == 0 else Decimal(9_000_000_000),
                    "operating_margin": Decimal("12.34"), "net_margin": Decimal("9.01"), "roe": Decimal("10.14"),
                    "total_equity": Decimal(-1) if i == 11 else Decimal(500_000_000_000),
                }
                for i in range(13)
            ],
            "105560": [
                {
                    "period_end": date(2026, 9, 30), "fs_div": "consolidated", "revenue": None,
                    "operating_income": Decimal(2_000_000_000_000), "net_income": Decimal(1_500_000_000_000),
                    "operating_margin": Decimal("30.0"), "net_margin": Decimal("20.0"), "roe": Decimal("9.5"),
                    "total_equity": Decimal(60_000_000_000_000),
                }
            ],
        }
        self.metrics = {
            "005930": {
                "period_end": date(2026, 9, 30), "fs_div": "consolidated",
                "debt_ratio": Decimal("28.94"), "current_ratio": Decimal("309.83"),
                "quick_ratio": Decimal("256.01"), "interest_coverage": Decimal("858.68"),
                "reserve_ratio": Decimal("65323.50"), "interest_coverage_basis": "cf_paid",
            },
            "105560": {
                "period_end": date(2026, 9, 30), "fs_div": "consolidated",
                "debt_ratio": Decimal("954.0"), "current_ratio": Decimal("1"), "quick_ratio": Decimal("1"),
                "interest_coverage": Decimal("2"), "reserve_ratio": Decimal("1165.0"), "interest_coverage_basis": "cf_paid",
            },
        }
        self.series = {
            ("index", "KOSPI"): [{"day": date(2026, 11, 19) - timedelta(days=299 - i), "value": Decimal(5000 + i)} for i in range(300)],
            ("index", "KOSDAQ"): [{"day": date(2026, 11, 18), "value": Decimal("680")}, {"day": date(2026, 11, 19), "value": Decimal("700")}],
            ("observation", "USD_KRW"): [{"day": date(2026, 11, 19), "value": Decimal("1330")}],
            ("observation", "KR_POLICY_RATE"): [{"day": date(2026, 5, 1), "value": Decimal("2.75")}, {"day": date(2026, 8, 27), "value": Decimal("3.00")}],
            ("observation", "KR_GOV_3Y"): [{"day": date(2026, 11, 18), "value": Decimal("3.74")}, {"day": date(2026, 11, 19), "value": Decimal("3.72")}],
            ("commodity", "04020000"): [{"day": date(2026, 11, 18), "value": Decimal("162090")}, {"day": date(2026, 11, 19), "value": Decimal("159750")}],
        }

    def stock(self, code):
        return self.stocks.get(code)

    def recent_prices(self, code, limit):
        return self.prices.get(code, [])[-limit:]

    def latest_snapshot(self, code):
        return self.snapshots.get(code)

    def annual_financials(self, code, limit):
        return self.annual.get(code, [])[-limit:]

    def latest_metrics(self, code):
        return self.metrics.get(code)

    def financial_profile(self, code):
        sectors = {"005930": ("general", None), "105560": ("financial", "holding"), "005935": ("general", None)}
        if code not in self.stocks and code != "005935":
            return None
        sector, fin_type = sectors.get(code, ("general", None))
        return {"code": code, "sector": sector, "fin_type": fin_type, "source_code": "005930" if code == "005935" else code}

    def quarterly_financials(self, code, limit):
        return self.quarters.get(code, [])[-limit:]

    def index_closes(self, code, limit):
        return self.series.get(("index", code), [])[-limit:]

    def observations(self, code, limit):
        return self.series.get(("observation", code), [])[-limit:]

    def commodity_closes(self, code, limit):
        return self.series.get(("commodity", code), [])[-limit:]


def _client(router, overrides) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: {"id": "7"}
    app.dependency_overrides.update(overrides)
    return TestClient(app)


class ProfileFinancialsOverviewTest(unittest.TestCase):
    def setUp(self):
        self.repo = FakeMarketRepo()
        self.client = _client(
            marketdata_router, {get_marketdata_service: lambda: MarketDataService(self.repo)}
        )

    def test_profile_shape_uses_snapshot_values(self):
        res = self.client.get("/api/v1/stocks/005930/profile")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(
            set(body),
            {
                "code", "name", "market", "overview", "prev_close", "open", "high", "low", "volume",
                "trading_value", "per", "pbr", "eps", "bps", "market_cap", "shares_outstanding",
                "week52_low", "week52_high",
            },
        )
        self.assertEqual(body["overview"], "전자 기업")
        self.assertEqual((body["prev_close"], body["open"]), (1050 + 298, 1000 + 299))
        self.assertEqual(body["trading_value"], (1050 + 299) * 10)
        self.assertEqual((body["per"], body["pbr"], body["eps"], body["bps"]), (30.07, 3.08, 6564, 63997))
        self.assertEqual(body["market_cap"], 1154055400000000)
        self.assertEqual(body["shares_outstanding"], 5_846_278_608)
        self.assertEqual((body["week52_low"], body["week52_high"]), (94500, 374500))

    def test_profile_falls_back_without_snapshot(self):
        body = self.client.get("/api/v1/stocks/105560/profile").json()
        self.assertEqual(body["overview"], "기업 개요를 준비 중이에요.")
        self.assertIsNone(body["per"])
        self.assertEqual(body["week52_low"], 900)
        self.assertEqual(body["week52_high"], 1102)
        self.assertIsNone(body["market_cap"])

    def test_profile_unknown_stock_is_404(self):
        self.assertEqual(self.client.get("/api/v1/stocks/999999/profile").status_code, 404)

    def test_financials_quarters_for_company_info(self):
        """UI v2 기업정보 (11-21 결정): 최근 12분기, 억원, 달력 분기 라벨, 자본잠식 분기 ROE null, ROA 없음."""
        res = self.client.get("/api/v1/stocks/005930/financials")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual((body["financial"], body["preparing"], body["sector"]), (False, False, "general"))
        self.assertEqual(body["basis"], "2026년 09월 기준 · 연결재무제표")
        qs = body["quarters"]
        self.assertEqual(len(qs), 12)                                 # 13개 중 최근 12개
        self.assertEqual((qs[0]["period_end"], qs[-1]["period_end"]), ("2023-12-31", "2026-09-30"))
        self.assertEqual((qs[-1]["q"], qs[-1]["label"]), ("26.3Q", "2026년 3분기"))
        self.assertEqual(qs[-1]["revenue"], 13000)                     # 1.3조원 = 13,000억원
        self.assertEqual((qs[-1]["op"], qs[-1]["net"]), (123, 90))
        self.assertEqual((qs[-1]["op_margin"], qs[-1]["net_margin"]), (12.3, 9.0))
        self.assertIsNone(qs[-2]["roe"])                               # 자본총계 0 이하 분기
        self.assertEqual(qs[-1]["roe"], 10.1)
        self.assertNotIn("roa", qs[-1])
        self.assertEqual(body["health"], {"debt": 28.9, "current": 309.8, "quick": 256.0, "interest": 858.7,
                                          "reserve": 65323.5})
        self.assertEqual((body["health_as_of"], body["interest_coverage_basis"]), ("2026-09-30", "cf_paid"))

    def test_financials_financial_company_hides_revenue_and_liquidity(self):
        body = self.client.get("/api/v1/stocks/105560/financials").json()
        self.assertTrue(body["financial"])
        q = body["quarters"][0]
        self.assertIsNone(q["revenue"])
        self.assertEqual(q["op"], 20000)                               # 영업이익은 보여 준다 (①)
        self.assertIsNone(q["op_margin"])
        self.assertEqual(body["health"], {"debt": 954.0, "current": None, "quick": None, "interest": None,
                                          "reserve": 1165.0})
        self.assertIsNone(body["interest_coverage_basis"])

    def test_financials_preferred_uses_common_and_empty_is_preparing(self):
        body = self.client.get("/api/v1/stocks/005935/financials").json()
        self.assertEqual((body["code"], body["source_code"], len(body["quarters"])), ("005935", "005930", 12))
        self.repo.stocks["000001"] = {**self.repo.stocks["105560"], "code": "000001"}
        empty = self.client.get("/api/v1/stocks/000001/financials")
        self.assertEqual(empty.status_code, 200)
        self.assertEqual((empty.json()["preparing"], empty.json()["quarters"]), (True, []))
        self.assertEqual(self.client.get("/api/v1/stocks/999999/financials").status_code, 404)

    def test_market_overview_shape(self):
        res = self.client.get("/api/v1/market/overview")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["as_of"], "2026-11-19T15:30:00+09:00")
        kospi, kosdaq, usd = body["indices"]
        self.assertEqual((kospi["key"], kospi["label"], kospi["flag"]), ("KOSPI", "코스피", "kr"))
        self.assertEqual({k: len(v) for k, v in kospi["series"].items()}, {"1D": 2, "1W": 5, "1M": 22, "1Y": 250})
        self.assertEqual((kosdaq["value"], kosdaq["change"], kosdaq["change_pct"]), (700.0, 20.0, 2.94))
        self.assertEqual((usd["key"], usd["flag"], usd["change"]), ("USDKRW", "us", 0.0))
        macro = {m["key"]: m for m in body["macro"]}
        # 데이터가 없는 지표(US10Y, WTI)는 빠진다
        self.assertEqual(set(macro), {"BASE_RATE", "KR3Y", "GOLD"})
        self.assertEqual(macro["BASE_RATE"], {"key": "BASE_RATE", "label": "기준금리", "value": 3.0, "unit": "%", "change": 0.25})
        self.assertEqual((macro["GOLD"]["label"], macro["GOLD"]["unit"]), ("금", "원/g"))
        # % 가 아닌 단위는 등락률(%): (159750 - 162090) / 162090 = -1.44%
        self.assertEqual(macro["GOLD"]["change"], -1.44)

    def test_requires_authentication(self):
        app = FastAPI()
        app.include_router(marketdata_router)
        app.dependency_overrides[get_auth_service] = lambda: None
        app.dependency_overrides[get_marketdata_service] = lambda: None
        client = TestClient(app)
        for path in ("/api/v1/stocks/005930/profile", "/api/v1/stocks/005930/financials", "/api/v1/market/overview"):
            with self.subTest(path=path):
                self.assertEqual(client.get(path).status_code, 401)


# ─── 고정 메모
class FakeBoardRepo:
    db = None

    def __init__(self, rows):
        self.rows = rows

    def list_pinned(self, user_id):
        return self.rows

    def tags(self, memo_id):
        return ["반도체"]


class FakeTracking:
    def price_conditions(self, memo_id):
        return []

    def unread_updates(self, memo_id):
        return 2


class PinnedMemosTest(unittest.TestCase):
    def test_pinned_memo_shape(self):
        now = datetime(2026, 11, 20, tzinfo=timezone.utc)
        rows = [
            {
                "id": 5, "symbol": "000660", "kind": "note", "title": "HBM 메모", "content": "본문",
                "color": "blue", "is_pinned": True, "ai_linked": True, "ai_linked_at": now,
                "created_at": now, "updated_at": now, "position": 2, "stock_name": "SK하이닉스",
            }
        ]
        service = BoardService(FakeBoardRepo(rows), tracking=FakeTracking(), llm_factory=lambda: None)
        client = _client(board_router, {get_board_query_service: lambda: service})
        res = client.get("/api/v1/memos/pinned")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(
            res.json(),
            [
                {
                    "id": "5", "stock_code": "000660", "title": "HBM 메모", "position": 2,
                    "created_at": "2026-11-20T00:00:00+00:00", "updated_at": "2026-11-20T00:00:00+00:00",
                    "kind": "memo", "body": "본문", "tags": ["반도체"], "color": "blue", "pinned": True,
                    "ai_linked": True, "ai_linked_at": "2026-11-20T00:00:00+00:00", "price_conditions": [],
                    "unread_updates": 2, "stock_name": "SK하이닉스",
                }
            ],
        )


# ─── 휴지통
class FakeTrashRepo:
    def __init__(self):
        t = lambda h: datetime(2026, 11, 20, h, tzinfo=timezone.utc)
        self.memos = {
            10: {"id": 10, "kind": "note", "title": "", "content": "\n첫 줄 내용\n둘째", "symbol": "000660", "stock_name": "SK하이닉스", "deleted_at": t(1)},
            11: {"id": 11, "kind": "checklist", "title": "매수 전 확인", "content": "", "symbol": "005930", "stock_name": "삼성전자", "deleted_at": t(3)},
        }
        self.stocks = {"035420": {"symbol": "035420", "stock_name": "네이버", "deleted_at": t(2)}}
        self.usage = set()
        self.restored_stocks_for_memo = []
        self.journals: dict[int, dict] = {}

    def deleted_memos(self, user_id):
        return list(self.memos.values())

    def deleted_journals(self, user_id):
        return list(self.journals.values())

    def restore_journal(self, user_id, entry_id):
        return self.journals.pop(entry_id, None) is not None

    def purge_journal(self, user_id, entry_id):
        return self.journals.pop(entry_id, None) is not None

    def deleted_stocks(self, user_id):
        return list(self.stocks.values())

    def restore_memo(self, user_id, memo_id):
        row = self.memos.pop(memo_id, None)
        if row:
            self.restored_stocks_for_memo.append(row["symbol"])
        return row and row["symbol"]

    def restore_stock(self, user_id, symbol):
        return self.stocks.pop(symbol, None) is not None

    def deleted_memo_exists(self, user_id, memo_id):
        return memo_id in self.memos

    def memo_has_usage_events(self, memo_id):
        return memo_id in self.usage

    def purge_memo(self, user_id, memo_id):
        return self.memos.pop(memo_id, None) is not None

    def purge_stock(self, user_id, symbol):
        return self.stocks.pop(symbol, None) is not None


class TrashApiTest(unittest.TestCase):
    def setUp(self):
        self.repo = FakeTrashRepo()
        service = TrashService(self.repo)
        self.client = _client(
            trash_router,
            {get_trash_query_service: lambda: service, get_trash_command_service: lambda: service},
        )

    def test_list_matches_trash_item_shape_newest_first(self):
        res = self.client.get("/api/v1/trash")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(
            res.json(),
            [
                {"id": "memo-11", "kind": "checklist", "title": "매수 전 확인", "context": "삼성전자 / 체크리스트", "deleted_at": "2026-11-20T03:00:00+00:00"},
                {"id": "stock-035420", "kind": "stock", "title": "네이버", "context": "종목", "deleted_at": "2026-11-20T02:00:00+00:00"},
                {"id": "memo-10", "kind": "memo", "title": "첫 줄 내용", "context": "SK하이닉스 / 메모", "deleted_at": "2026-11-20T01:00:00+00:00"},
            ],
        )

    def test_restore_memo_and_stock(self):
        self.assertEqual(self.client.post("/api/v1/trash/memo-10/restore").status_code, 204)
        self.assertEqual(self.repo.restored_stocks_for_memo, ["000660"])
        self.assertEqual(self.client.post("/api/v1/trash/stock-035420/restore").status_code, 204)
        self.assertEqual([i["id"] for i in self.client.get("/api/v1/trash").json()], ["memo-11"])

    def test_restore_unknown_or_malformed_is_404(self):
        for trash_id in ("memo-999", "stock-000000", "t1", "memo-abc", "stock-12"):
            with self.subTest(trash_id=trash_id):
                self.assertEqual(self.client.post(f"/api/v1/trash/{trash_id}/restore").status_code, 404)

    def test_purge(self):
        self.assertEqual(self.client.delete("/api/v1/trash/memo-11").status_code, 204)
        self.assertEqual(self.client.delete("/api/v1/trash/stock-035420").status_code, 204)
        self.assertEqual(self.client.delete("/api/v1/trash/memo-11").status_code, 404)

    def test_purge_blocked_by_usage_events_is_409_and_keeps_item(self):
        self.repo.usage.add(10)
        self.assertEqual(self.client.delete("/api/v1/trash/memo-10").status_code, 409)
        self.assertIn(10, self.repo.memos)

    def test_requires_authentication(self):
        app = FastAPI()
        app.include_router(trash_router)
        app.dependency_overrides[get_auth_service] = lambda: None
        app.dependency_overrides[get_trash_query_service] = lambda: None
        app.dependency_overrides[get_trash_command_service] = lambda: None
        client = TestClient(app)
        self.assertEqual(client.get("/api/v1/trash").status_code, 401)
        self.assertEqual(client.post("/api/v1/trash/memo-1/restore").status_code, 401)
        self.assertEqual(client.delete("/api/v1/trash/memo-1").status_code, 401)


if __name__ == "__main__":
    unittest.main()
