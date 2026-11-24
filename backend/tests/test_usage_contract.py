"""GET /me/usage ↔ 프론트 CreditUsage 타입 계약 (DB 없이).

/me/usage 는 이번 달 기본량을 안 받았으면 호출할 때 지급(DB 쓰기)하므로, 여기서는 ledger.usage 를 가짜로 바꾸고
세션도 가짜를 넣어 공용 DB 에 닿지 않게 한다. 실제 SQL 은 tests/test_credits.py(TEST_DATABASE_URL)가 본다.
"""

from __future__ import annotations

import unittest
from datetime import date, datetime
from unittest import mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.routes import get_current_user
from app.credits import ledger
from app.credits.routes import router
from app.db import get_db
from pipelines.devtools.api_spec import FRONT_MODELS, TsTypes


class NoDbSession:
    def execute(self, *args, **kwargs):  # pragma: no cover - 불리면 실패
        raise AssertionError("이 테스트는 DB 에 닿으면 안 된다")


class UsageContractTest(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_current_user] = lambda: {"id": "7"}
        app.dependency_overrides[get_db] = lambda: NoDbSession()
        self.client = TestClient(app)
        self.sample = ledger.Usage(
            usage_percent=42, used=21, balance=29, period_start=date(2026, 11, 1),
            renews_at=datetime(2026, 12, 1, tzinfo=ledger.SEOUL), paused=False,
        )

    def test_response_matches_frontend_credit_usage_type(self):
        with mock.patch.object(ledger, "usage", return_value=self.sample) as fake:
            res = self.client.get("/api/v1/me/usage")
        self.assertEqual(res.status_code, 200)
        fake.assert_called_once()
        self.assertEqual(fake.call_args.args[1], 7)
        body = res.json()
        front = {f.name for f in TsTypes(FRONT_MODELS).interface_fields("CreditUsage")}
        self.assertEqual(set(body), front)
        self.assertEqual(body["renew_label"], "11.30 갱신")
        self.assertEqual((body["usage_percent"], body["paused"]), (42, False))

    def test_paused_when_balance_zero(self):
        spent = ledger.Usage(100, 30, 0, date(2026, 11, 1), datetime(2026, 12, 1, tzinfo=ledger.SEOUL), True)
        with mock.patch.object(ledger, "usage", return_value=spent):
            body = self.client.get("/api/v1/me/usage").json()
        self.assertEqual((body["usage_percent"], body["balance"], body["paused"]), (100, 0, True))


if __name__ == "__main__":
    unittest.main()
