"""LLM 사용량 기록 (2026-11-11, 파일). 가짜 클라이언트로 돈다."""

import csv
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from pipelines.updates.models import CreditsExhausted, TrackingItem
from pipelines.updates.usage import UsageTracker, stage_of, usd, write_usage
from pipelines.updates.usage_daily import summarize

ITEM = TrackingItem("M01:0:0", "005930", "topic", "HBM")
ITEM2 = TrackingItem("M02:0:0", "035420", "topic", "웹툰")


class FakeClient:
    model = "gpt-6.1-sol"

    def __init__(self, fail=None):
        self.calls, self.fail = [], fail

    def __call__(self, prompt):
        self.calls.append(SimpleNamespace(prompt_tokens=1000, output_tokens=100, reasoning_tokens=40))
        if self.fail:
            raise self.fail
        return "{}"


class UsageTest(unittest.TestCase):
    def test_stage_of(self):
        from pipelines.updates.judge import VERIFY_INSTRUCTION
        self.assertEqual(stage_of(VERIFY_INSTRUCTION + "\n[근거]"), "verify")
        self.assertEqual(stage_of("프롬프트\n\n# 수정 요청\n직전 답변이"), "format_retry")
        self.assertEqual(stage_of("당신은 투자 메모 서비스 memo's의 업데이트 카드 작성기입니다."), "card")

    def test_tracker_and_files(self):
        client = FakeClient()
        t = UsageTracker()
        t.caller(client, ITEM, "relevance")("판정")
        card = t.caller(client, ITEM)
        card("카드 프롬프트")
        card("카드 프롬프트\n# 수정 요청\n")
        t.caller(client, ITEM2)("카드")
        self.assertIsNone(t.caller(None, ITEM))
        rows = t.by_item()
        self.assertEqual([(r["item_id"], r["stage"], r["calls"]) for r in rows],
                         [("M01:0:0", "relevance", 1), ("M01:0:0", "card", 1), ("M01:0:0", "format_retry", 1),
                          ("M02:0:0", "card", 1)])
        self.assertAlmostEqual(rows[0]["usd"], usd("gpt-6.1-sol", 1000, 100))     # 1000×$2/1M + 100×$10/1M = $0.003
        self.assertAlmostEqual(rows[0]["usd"], 0.003)
        with tempfile.TemporaryDirectory() as d:
            run, log = Path(d) / "run_x", Path(d) / "usage_log.jsonl"
            run.mkdir()
            line = write_usage(t, run, log, items=10, topic_items=8, cards=2, fresh_items=0,
                               now=datetime(2026, 11, 11, 5, tzinfo=timezone.utc))
            self.assertEqual(line["total"]["calls"], 4)
            self.assertAlmostEqual(line["total"]["usd"], 0.012)
            self.assertEqual(line["stages"]["card"]["calls"], 2)
            self.assertEqual((line["items_with_calls"], line["cards"]), (2, 2))
            with (run / "usage_by_item.csv").open(encoding="utf-8-sig") as f:
                self.assertEqual(len(list(csv.DictReader(f))), 4)
            write_usage(t, run, log, items=10, topic_items=8, cards=0, fresh_items=8)
            self.assertEqual(len(log.read_text(encoding="utf-8").splitlines()), 2)   # 실행마다 한 줄 더한다

    def test_failed_and_credit_calls_are_counted(self):
        t = UsageTracker()
        with self.assertRaises(RuntimeError):
            t.caller(FakeClient(RuntimeError("x")), ITEM)("카드")
        with self.assertRaises(CreditsExhausted):
            t.caller(FakeClient(CreditsExhausted("0")), ITEM)("카드")
        self.assertEqual(len(t.rows), 2)


class DailyTest(unittest.TestCase):
    def test_summarize(self):
        rows = [{"run_at": "2026-11-11T10:00:00+09:00", "items": 10, "fresh_items": 0, "total": {"usd": 0.20}},
                {"run_at": "2026-11-11T11:00:00+09:00", "items": 10, "fresh_items": 8, "total": {"usd": 0.02}},
                {"run_at": "2026-11-11T12:00:00+09:00", "items": 10, "fresh_items": 8, "total": {"usd": 0.04}},
                {"run_at": "2026-11-12T10:00:00+09:00", "items": 5, "fresh_items": 5, "total": {"usd": None}}]
        s = summarize(rows, runs_per_day=24)
        self.assertEqual(s["runs"], 3)                                               # 비용을 모르는 실행은 뺀다
        self.assertAlmostEqual(s["per_item_per_run"]["first_check"], 0.02)
        self.assertAlmostEqual(s["per_item_per_run"]["follow_up"], 0.003)
        self.assertAlmostEqual(s["observed_daily"]["2026-11-11"]["per_item"], 0.026)
        self.assertAlmostEqual(s["estimated_daily_per_item"], 0.072)


if __name__ == "__main__":
    unittest.main()
