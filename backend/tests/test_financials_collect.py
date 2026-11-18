"""WO-015 ①단계: DART 재무 원본 수집 (실제 API 호출 없음, FakeSession)."""

import io
import json
import logging
import os
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock

from app.dart_reports import DartError, DartRateLimitError
from pipelines.common.logging import REDACTOR
from pipelines.disclosures import financials_dart as fd
from pipelines.disclosures import financials_pipeline as fp
from tests.test_dart_reports import FakeResponse, FakeSession


API_KEY = "test-secret-key"
TARGET = fd.Target("005930", "00126380", "2025-06-30")


def body(status="000", message="정상", rows=None):
    data = {"status": status, "message": message}
    if rows is not None:
        data["list"] = rows
    return FakeResponse(content=json.dumps(data, ensure_ascii=False).encode("utf-8"))


def account(sj_div, account_id, account_nm, amount="1"):
    return {"sj_div": sj_div, "account_id": account_id, "account_nm": account_nm, "thstrm_amount": amount}


class TargetTest(unittest.TestCase):
    def test_reprt_codes_and_paths(self):
        codes = {p: fd.Target("000660", "c", p).reprt_code for p in ("2024-03-31", "2024-06-30", "2024-09-30", "2024-12-31")}
        self.assertEqual(codes, {"2024-03-31": "11013", "2024-06-30": "11012", "2024-09-30": "11014", "2024-12-31": "11011"})
        root = Path("/r")
        self.assertEqual(fd.statement_path(root, TARGET, "CFS"), root / "005930_2025_11012_CFS.json")
        self.assertEqual(fd.shares_path(root, TARGET), root / "005930_2025_11012.json")


class CollectStatementsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.statements = Path(self.tmp.name) / "financials"
        self.shares = Path(self.tmp.name) / "shares"

    def run_collect(self, session, refresh=False, targets=(TARGET,)):
        return fd.collect(list(targets), API_KEY, self.statements, self.shares, session=session, refresh=refresh)

    def test_cfs_success_skips_ofs_and_saves_raw_bytes(self):
        cfs = body(rows=[account("BS", "ifrs-full_Assets", "자산총계")])
        session = FakeSession([cfs, body(rows=[])])
        report = self.run_collect(session)
        self.assertEqual(report.calls, 2)
        url, params, _ = session.calls[0]
        self.assertTrue(url.endswith("/fnlttSinglAcntAll.json"))
        self.assertEqual(params, {"crtfc_key": API_KEY, "corp_code": "00126380", "bsns_year": "2025", "reprt_code": "11012", "fs_div": "CFS"})
        self.assertTrue(session.calls[1][0].endswith("/stockTotqySttus.json"))
        self.assertNotIn("fs_div", session.calls[1][1])
        saved = self.statements / "005930_2025_11012_CFS.json"
        self.assertEqual(saved.read_bytes(), cfs.content)  # 응답 그대로
        self.assertFalse((self.statements / "005930_2025_11012_OFS.json").exists())
        self.assertEqual(report.statements[("005930", "2025-06-30")].path.name, saved.name)
        self.assertEqual(report.failures, [])

    def test_cfs_013_retries_ofs_and_records_note(self):
        session = FakeSession([body("013", "조회된 데이타가 없습니다."), body(rows=[]), body(rows=[])])
        report = self.run_collect(session)
        self.assertEqual([c[1].get("fs_div") for c in session.calls], ["CFS", "OFS", None])
        self.assertEqual(report.calls, 3)
        self.assertEqual(report.statements[("005930", "2025-06-30")].path.name, "005930_2025_11012_OFS.json")
        self.assertTrue((self.statements / "005930_2025_11012_CFS.json").exists())  # 013 응답도 원본으로 보존
        self.assertIn("OFS", report.notes[0])

    def test_both_013_is_failure(self):
        session = FakeSession([body("013"), body("013"), body(rows=[])])
        report = self.run_collect(session)
        self.assertNotIn(("005930", "2025-06-30"), report.statements)
        self.assertIn("CFS·OFS 모두", report.failures[0])

    def test_cached_files_are_not_refetched_unless_refresh(self):
        self.run_collect(FakeSession([body(rows=[]), body(rows=[])]))
        again = FakeSession([])
        report = self.run_collect(again)
        self.assertEqual(again.calls, [])
        self.assertEqual(report.calls, 0)
        self.assertEqual(len(report.statements), 1)
        refreshed = FakeSession([body(rows=[]), body(rows=[])])
        self.assertEqual(self.run_collect(refreshed, refresh=True).calls, 2)

    def test_corrupt_cached_file_is_refetched(self):
        self.statements.mkdir(parents=True)
        (self.statements / "005930_2025_11012_CFS.json").write_text("{잘린 JSON", encoding="utf-8")
        session = FakeSession([body(rows=[]), body(rows=[])])
        report = self.run_collect(session)
        self.assertEqual(report.failures, [])
        self.assertEqual(session.calls[0][1]["fs_div"], "CFS")
        self.assertIsNone(fd.cached_statement(self.statements, fd.Target("005930", "", "2025-03-31")))

    def test_cached_cfs_013_only_calls_missing_ofs(self):
        self.run_collect(FakeSession([body("013"), body("013"), body(rows=[])]))
        session = FakeSession([body(rows=[])])
        report = self.run_collect(session)
        # CFS·OFS 013 원본이 이미 있으므로 재호출 없음
        self.assertEqual(session.calls, [])
        self.assertEqual(report.calls, 0)
        (self.statements / "005930_2025_11012_OFS.json").unlink()
        session = FakeSession([body(rows=[])])
        report = self.run_collect(session)
        self.assertEqual([c[1].get("fs_div") for c in session.calls], ["OFS"])

    def test_rate_limit_stops_everything_without_saving(self):
        second = fd.Target("000660", "00164779", "2025-06-30")
        session = FakeSession([body("020", "요청 제한을 초과하였습니다.")])
        with self.assertRaises(DartRateLimitError):
            self.run_collect(session, targets=(TARGET, second))
        self.assertEqual(len(session.calls), 1)
        self.assertFalse(self.statements.exists() and any(self.statements.iterdir()))

    def test_auth_error_stops_everything(self):
        session = FakeSession([body("010", "등록되지 않은 키입니다.")])
        with self.assertRaises(fd.DartAuthError):
            self.run_collect(session)

    def test_other_error_is_recorded_and_next_target_continues(self):
        second = fd.Target("000660", "00164779", "2025-06-30")
        session = FakeSession([body("100", "필드의 부적절한 값입니다."), body(rows=[]), body(rows=[]), body(rows=[])])
        report = self.run_collect(session, targets=(TARGET, second))
        self.assertEqual(len(session.calls), 4)
        self.assertTrue(report.failures[0].startswith("005930 2025-06-30"))
        self.assertIn(("000660", "2025-06-30"), report.statements)
        self.assertFalse((self.statements / "005930_2025_11012_CFS.json").exists())

    def test_non_json_response_is_failure(self):
        session = FakeSession([FakeResponse(content=b"<html>oops</html>"), body(rows=[])])
        report = self.run_collect(session)
        self.assertIn("JSON 응답이 아닙니다", report.failures[0])

    def test_shares_013_is_empty_result_with_note(self):
        session = FakeSession([body(rows=[]), body("013")])
        report = self.run_collect(session)
        self.assertEqual(report.shares[("005930", "2025-06-30")].status, "013")
        self.assertTrue((self.shares / "005930_2025_11012.json").exists())
        self.assertEqual(report.failures, [])
        self.assertIn("BPS NULL", report.notes[0])

    def test_api_key_not_in_failure_messages(self):
        session = FakeSession([body("100", f"bad key {API_KEY}"), body(rows=[])])
        report = self.run_collect(session)
        self.assertNotIn(API_KEY, "\n".join(report.failures))
        with self.assertRaises(DartError) as ctx:
            fd.fetch_json("fnlttSinglAcntAll.json", {}, API_KEY, FakeSession([body("800", f"점검 {API_KEY}")]))
        self.assertNotIn(API_KEY, str(ctx.exception))


class PlanAndInventoryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.statements = Path(self.tmp.name) / "financials"
        self.shares = Path(self.tmp.name) / "shares"

    def write(self, path, status="000", rows=None):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"status": status, "list": rows or []}), encoding="utf-8")

    def test_plan_counts_only_missing_files(self):
        targets = [fd.Target("005930", "", p) for p in ("2025-03-31", "2025-06-30", "2025-09-30")]
        self.write(fd.statement_path(self.statements, targets[0], "CFS"))
        self.write(fd.shares_path(self.shares, targets[0]))
        self.write(fd.statement_path(self.statements, targets[1], "CFS"), status="013")
        plan = fd.plan_calls(targets, self.statements, self.shares)
        self.assertEqual(plan["fnlttSinglAcntAll.json"], 2)  # targets[1] OFS, targets[2] CFS
        self.assertEqual(plan["stockTotqySttus.json"], 2)
        self.assertEqual(plan["min_calls"], 4)
        self.assertEqual(plan["possible_ofs_retries"], 1)
        self.assertEqual(fd.plan_calls(targets, self.statements, self.shares, refresh=True)["min_calls"], 6)

    def test_account_inventory(self):
        rows = [account("BS", "ifrs-full_Equity", "자본총계"), account("SCE", "ifrs-full_Equity", "자본총계")]
        self.write(self.statements / "105560_2025_11011_CFS.json", rows=rows)
        self.write(self.statements / "105560_2025_11012_CFS.json", rows=rows[:1])
        self.write(self.statements / "105560_2024_11011_CFS.json", status="013")
        inventory = fd.account_inventory(self.statements, ["105560"])["105560"]
        self.assertEqual(
            inventory,
            [
                {"sj_div": "BS", "account_id": "ifrs-full_Equity", "account_nm": "자본총계", "files": 2},
                {"sj_div": "SCE", "account_id": "ifrs-full_Equity", "account_nm": "자본총계", "files": 1},
            ],
        )


class RunFinancialsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        config = {
            "targets": {"periods": ["2025-06-30"]},
            "dart": {"request_interval_sec": 0},
            "paths": {"logs_dir": "logs", "financials_raw_dir": "raw/financials", "shares_raw_dir": "raw/shares", "financials_dir": "out"},
        }
        self.config = self.root / "common.yaml"
        self.config.write_text(json.dumps(config), encoding="utf-8")  # JSON은 YAML의 부분집합
        env = mock.patch.dict(os.environ, {}, clear=False)
        env.start()
        self.addCleanup(env.stop)
        for key in fp.ENV_KEYS:
            os.environ.pop(key, None)
        self.addCleanup(lambda: REDACTOR.secrets.clear())

    def run_main(self, *argv, session=None, corp_codes=None):
        stderr = io.StringIO()
        corp_codes = {"005930": "00126380"} if corp_codes is None else corp_codes
        with mock.patch.object(fp, "read_corp_codes", return_value=corp_codes), redirect_stderr(stderr):
            code = fp.main(["--config", str(self.config), "--root", str(self.root), "--symbols", "005930", *argv], engine=object(), session=session)
        logs = sorted((self.root / "logs").glob("financials_*.json"))
        return code, stderr.getvalue(), json.loads(logs[-1].read_text(encoding="utf-8")) if logs else None

    def test_dry_run_makes_no_calls_and_needs_no_key(self):
        session = FakeSession([])
        code, _, record = self.run_main("--steps", "collect", "--dry-run", session=session)
        self.assertEqual(code, 0)
        self.assertEqual(session.calls, [])
        self.assertEqual(record["collect_plan"]["min_calls"], 2)
        self.assertEqual(record["status"], "success")

    def test_missing_key_exits_2_without_calls(self):
        session = FakeSession([])
        code, err, _ = self.run_main("--steps", "collect", session=session)
        self.assertEqual(code, 2)
        self.assertIn("DART_API_KEY", err)
        self.assertEqual(session.calls, [])

    def test_collect_success_and_key_redacted_in_log(self):
        os.environ["DART_API_KEY"] = API_KEY
        session = FakeSession([body(rows=[]), body("013", f"없음 {API_KEY}")])
        code, err, record = self.run_main("--steps", "collect", session=session)
        self.assertEqual(code, 0, err)
        self.assertEqual(record["collect"]["calls"], 2)
        self.assertEqual(record["status"], "success")
        log_text = "".join(p.read_text(encoding="utf-8") for p in (self.root / "logs").glob("*.json"))
        self.assertNotIn(API_KEY, log_text + err)
        self.assertTrue((self.root / "raw/financials/005930_2025_11012_CFS.json").exists())

    def test_rate_limit_exits_1_and_logs_failure(self):
        os.environ["DART_API_KEY"] = API_KEY
        session = FakeSession([body("020", "한도 초과")])
        code, err, record = self.run_main("--steps", "collect", session=session)
        self.assertEqual(code, 1)
        self.assertEqual(record["status"], "failed")
        self.assertIn("수집 중단", record["failures"][0])

    def test_missing_corp_code_fails_without_calls(self):
        os.environ["DART_API_KEY"] = API_KEY
        session = FakeSession([])
        code, _, record = self.run_main("--steps", "collect", session=session, corp_codes={})
        self.assertEqual(code, 1)
        self.assertEqual(session.calls, [])
        self.assertIn("dart_corp_code", record["failures"][0])


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    unittest.main()
