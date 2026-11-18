"""매일 실행기 도우미 (2026-11-11). 파일만."""

import json
import tempfile
import unittest
from pathlib import Path

from pipelines.updates.daily import last_daily_since, spent_today, write_status


class DailyTest(unittest.TestCase):
    def test_spent_today_counts_only_daily_today(self):
        with tempfile.TemporaryDirectory() as d:
            log = Path(d) / "usage_log.jsonl"
            rows = [{"run_at": "2026-11-11T06:30:10+09:00", "job": "daily", "total": {"usd": 0.3}},
                    {"run_at": "2026-11-11T09:00:00+09:00", "job": "experiment", "total": {"usd": 0.5}},   # 실험 실행은 세지 않는다
                    {"run_at": "2026-11-10T06:30:00+09:00", "job": "daily", "total": {"usd": 0.9}},        # 어제
                    {"run_at": "2026-11-11T07:00:00+09:00", "job": "daily", "total": {"usd": None}}]
            log.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
            self.assertAlmostEqual(spent_today(log, "2026-11-11"), 0.3)
            self.assertEqual(spent_today(Path(d) / "none.jsonl", "2026-11-11"), 0.0)
            self.assertEqual(last_daily_since(log, "2026-11-11T06:30:00+09:00")["run_at"], "2026-11-11T07:00:00+09:00")
            self.assertIsNone(last_daily_since(log, "2026-11-12T00:00:00+09:00"))

    def test_write_status(self):
        with tempfile.TemporaryDirectory() as d:
            write_status(Path(d), {"started_at": "2026-11-11T06:30:00+09:00", "status": "success"})
            self.assertEqual(json.loads((Path(d) / "latest.json").read_text(encoding="utf-8"))["status"], "success")
            self.assertEqual(len(list(Path(d).glob("2026*.json"))), 1)


if __name__ == "__main__":
    unittest.main()
