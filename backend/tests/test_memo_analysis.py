"""메모 저장 시 분석 (2026-11-11). DB·LLM 없이: 선택지 서명, 다음 실행 시각, 서비스 흐름(가짜 저장소)."""

from __future__ import annotations

import os
import unittest
from datetime import datetime
from unittest import mock

from app.board.analysis import AnalysisError, AnalysisResult, next_update_at, read_option, sign_option
from app.board.schemas import MemoCreate
from app.board.service import BoardService, InvalidBoardPatchError, StaleConfirmationError
from app.board.tracking import item_key

SEOUL = __import__("zoneinfo").ZoneInfo("Asia/Seoul")


class SignTest(unittest.TestCase):
    def setUp(self):
        self.env = mock.patch.dict(os.environ, {"MEMO_CONFIRM_SECRET": "x" * 40})
        self.env.start()

    def tearDown(self):
        self.env.stop()

    def test_round_trip_and_tamper(self):
        payload = {"m": 3, "r": 2, "s": 1, "i": {"type": "price_below", "description": "15만원 아래로", "price_threshold": 150000}}
        oid = sign_option(payload)
        self.assertEqual(read_option(oid), payload)
        body, sig = oid.rsplit(".", 1)
        self.assertIsNone(read_option(body + "." + ("0" * len(sig))))
        self.assertIsNone(read_option(None))
        self.assertIsNone(read_option("garbage"))
        with mock.patch.dict(os.environ, {"MEMO_CONFIRM_SECRET": "y" * 40}):
            self.assertIsNone(read_option(oid))                                  # 다른 키로는 통과하지 않는다

    def test_no_secret(self):
        with mock.patch.dict(os.environ, {"MEMO_CONFIRM_SECRET": "", "AUTH_JWT_SECRET": ""}):
            with self.assertRaises(AnalysisError):
                sign_option({"m": 1})


class NextUpdateTest(unittest.TestCase):
    def test_next_run(self):
        self.assertEqual(next_update_at(datetime(2026, 11, 11, 5, 0, tzinfo=SEOUL), "06:30"),
                         datetime(2026, 11, 11, 6, 30, tzinfo=SEOUL))
        self.assertEqual(next_update_at(datetime(2026, 11, 11, 14, 0, tzinfo=SEOUL), "06:30"),
                         datetime(2026, 11, 12, 6, 30, tzinfo=SEOUL))

    def test_item_key(self):
        self.assertEqual(item_key({"type": "topic", "description": " HBM  소식 ", "price_threshold": None}),
                         item_key({"type": "topic", "description": "HBM 소식"}))
        self.assertEqual(item_key({"type": "price_below", "description": "x", "price_threshold": "70000.00"})[2], 70000)


class FakeDB:
    def __init__(self):
        self.commits = self.rollbacks = 0

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class FakeRepo:
    def __init__(self):
        self.db, self.rows = FakeDB(), {}

    def owns_stock(self, user_id, symbol):
        return True

    def create(self, **kw):
        row = {"id": len(self.rows) + 1, "symbol": kw["symbol"], "kind": kw["kind"], "title": kw["title"],
               "content": kw["content"], "color": kw.get("color"), "is_pinned": kw.get("pinned"),
               "ai_linked": kw.get("ai_linked"), "ai_linked_at": None, "created_at": datetime(2026, 11, 11),
               "updated_at": datetime(2026, 11, 11), "position": 0}
        self.rows[row["id"]] = row
        return row

    def replace_tags(self, *a):
        pass

    def tags(self, memo_id):
        return []

    def get_owned(self, user_id, memo_id):
        return self.rows.get(memo_id)

    def update_base(self, user_id, memo_id, values):
        r = self.rows[memo_id]
        if "body" in values:
            r["content"] = values["body"]
        if "color" in values:
            r["color"] = values["color"]
        return True

    def set_ai_link(self, user_id, memo_id, enabled):
        self.rows[memo_id]["ai_linked"] = enabled
        return True


class FakeTracking:
    def __init__(self):
        self.items_list, self.statuses, self.created, self.changed = [], [], [], True

    def items(self, memo_id, statuses=("active", "paused")):
        return [i for i in self.items_list if i["status"] in statuses]

    def latest_revision(self, memo_id):
        return {"revision_no": 1}

    def stock_name(self, symbol):
        return "삼성전자"

    def price_window(self, symbol):
        return []

    def price_conditions(self, memo_id):
        return []

    def unread_updates(self, memo_id):
        return 0

    def changed_since_analysis(self, memo_id):
        return self.changed

    def sync(self, memo_id, new_items, confirmations):
        created = [{**i, "id": 100 + n, "status": "active"} for n, i in enumerate(new_items)]
        self.items_list = created
        return {"kept": [], "created": created, "done": []}

    def set_memo_status(self, memo_id, frm, to):
        self.statuses.append((frm, to))
        return 2

    def create_item(self, memo_id, item):
        self.created.append(item)
        return {"id": 200, "status": "active", **item}


def fake_analyze(*args, **kw):
    return AnalysisResult(items=[{"type": "topic", "description": "HBM 소식", "price_threshold": None}], llm_calls=1)


class ServiceTest(unittest.TestCase):
    def svc(self, llm=lambda: (lambda p: "[]")):
        self.repo, self.track = FakeRepo(), FakeTracking()
        return BoardService(self.repo, self.track, llm_factory=llm)

    def test_create_ai_on_and_off(self):
        s = self.svc()
        with mock.patch("app.board.service.analyze_memo", side_effect=fake_analyze) as a:
            on = s.create_memo(1, "005930", MemoCreate(title="t", body="HBM 소식", ai_linked=True))
            off = s.create_memo(1, "005930", MemoCreate(title="t", body="HBM 소식", ai_linked=False))
        self.assertEqual(a.call_count, 1)                                      # AI 끈 메모는 분석하지 않는다
        self.assertEqual((on["analysis"]["status"], on["analysis"]["created"]), ("done", 1))
        self.assertIsNotNone(on["analysis"]["next_update_at"])
        self.assertEqual(off["analysis"]["status"], "skipped")
        self.assertGreaterEqual(self.repo.db.commits, 2)                       # 메모 저장을 먼저 확정한다

    def test_analysis_failure_keeps_memo(self):
        s = self.svc()
        with mock.patch("app.board.service.analyze_memo", side_effect=AnalysisError("llm_failed", "x")):
            out = s.create_memo(1, "005930", MemoCreate(title="t", body="b", ai_linked=True))
        self.assertEqual((out["analysis"]["status"], out["analysis"]["error"]), ("failed", "llm_failed"))
        self.assertIn(int(out["id"]), self.repo.rows)
        self.assertEqual(self.repo.db.commits, 1)                              # 메모 저장은 커밋됨

    def test_update_only_reanalyzes_changed_body(self):
        s = self.svc()
        with mock.patch("app.board.service.analyze_memo", side_effect=fake_analyze) as a:
            m = s.create_memo(1, "005930", MemoCreate(title="t", body="HBM 소식", ai_linked=True))
            mid = int(m["id"])
            self.assertEqual(s.update(1, mid, {"color": "blue"})["analysis"]["status"], "unchanged")
            self.assertEqual(s.update(1, mid, {"body": "HBM 소식"})["analysis"]["status"], "unchanged")
            self.assertEqual(s.update(1, mid, {"body": "파운드리 소식"})["analysis"]["status"], "done")
        self.assertEqual(a.call_count, 2)

    def test_ai_toggle(self):
        s = self.svc()
        with mock.patch("app.board.service.analyze_memo", side_effect=fake_analyze) as a:
            mid = int(s.create_memo(1, "005930", MemoCreate(title="t", body="b", ai_linked=True))["id"])
            off = s.set_ai_link(1, mid, False)
            self.track.changed = False
            on = s.set_ai_link(1, mid, True)
            self.track.changed = True
            again = s.set_ai_link(1, mid, True)
        self.assertEqual((off["analysis"]["status"], off["analysis"]["paused"]), ("skipped", 2))
        self.assertEqual((on["analysis"]["status"], on["analysis"]["resumed"]), ("unchanged", 2))
        self.assertEqual(again["analysis"]["status"], "done")                  # 바뀌었으면 다시 분석
        self.assertEqual(self.track.statuses, [("active", "paused"), ("paused", "active")])
        self.assertEqual(a.call_count, 2)

    def test_confirm(self):
        s = self.svc()
        with mock.patch.dict(os.environ, {"MEMO_CONFIRM_SECRET": "z" * 40}), \
                mock.patch("app.board.service.analyze_memo", side_effect=fake_analyze):
            mid = int(s.create_memo(1, "005930", MemoCreate(title="t", body="b", ai_linked=True))["id"])
            item = {"type": "price_below", "description": "150,000원 아래로", "price_threshold": 150000}
            out = s.confirm(1, mid, sign_option({"m": mid, "r": 1, "s": 1, "i": item}))
            self.assertEqual(out["analysis"]["items"][0]["price_threshold"], 150000)
            with self.assertRaises(StaleConfirmationError):
                s.confirm(1, mid, sign_option({"m": mid, "r": 0, "s": 1, "i": item}))
            with self.assertRaises(InvalidBoardPatchError):
                s.confirm(1, mid, sign_option({"m": mid + 1, "r": 1, "s": 1, "i": item}))   # 다른 메모의 선택지
            with self.assertRaises(InvalidBoardPatchError):
                s.confirm(1, mid, "not-signed.0000")


if __name__ == "__main__":
    unittest.main()
