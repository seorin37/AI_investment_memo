import io
import logging
import tempfile
import time
import unittest
from pathlib import Path

import requests

from app import dart_reports
from pipelines.common.logging import RedactFilter
from pipelines.common.retry import Throttle, retry_call
from pipelines.disclosures import dart
from tests.disclosure_fixtures import zip_bytes
from tests.test_dart_reports import FakeResponse, FakeSession


API_KEY = "test-secret-key"
PERIODS = [f"{y}-{m}" for y in (2024, 2025) for m in ("03-31", "06-30", "09-30", "12-31")] + ["2026-03-31", "2026-06-30"]


def item(report_nm, rcept_no, rcept_dt="20250101"):
    return {"report_nm": report_nm, "rcept_no": rcept_no, "rcept_dt": rcept_dt}


def corp_xml(entries):
    return ("<result>" + "".join(
        f"<list><corp_code>{c}</corp_code><stock_code>{s}</stock_code></list>" for s, c in entries
    ) + "</result>").encode("utf-8")


def full_listing():
    annual = [item("사업보고서 (2023.12)", "20240312000001", "20240312"),
              item("사업보고서 (2024.12)", "20250311000001", "20250311"),
              item("[기재정정]사업보고서 (2025.12)", "20260320000001", "20260320")]
    half = [item(f"반기보고서 ({y}.06)", f"{y}0814000001", f"{y}0814") for y in (2024, 2025, 2026)]
    quarterly = [item(f"분기보고서 ({y}.{m})", f"{y}{m}15000001", f"{y}{m}15") for y in (2024, 2025) for m in ("03", "09")]
    quarterly.append(item("분기보고서 (2026.03)", "20260515000001", "20260515"))
    return {"A001": annual, "A002": half, "A003": quarterly}


class SelectReportsTest(unittest.TestCase):
    def test_selects_by_period_not_filing_date(self):
        refs, missing = dart.select_reports("005930", "00126380", full_listing(), PERIODS)
        self.assertEqual(missing, [])
        self.assertEqual(len(refs), 10)
        periods = [r.period_end for r in refs]
        self.assertNotIn("2023-12-31", periods)  # 2024년 3월 제출 2023 사업보고서 제외
        self.assertIn("2025-12-31", periods)  # 2026년 3월 제출 2025 사업보고서 포함
        by_period = {r.period_end: r for r in refs}
        self.assertEqual(by_period["2024-03-31"].kind, "quarterly")
        self.assertEqual(by_period["2024-09-30"].kind, "quarterly")
        self.assertNotEqual(by_period["2024-03-31"].rcept_no, by_period["2024-09-30"].rcept_no)
        self.assertEqual(by_period["2025-12-31"].title, "[기재정정]사업보고서 (2025.12)")
        self.assertEqual(by_period["2025-12-31"].rcept_dt, "2026-03-20")

    def test_kind_mapping_and_source_url(self):
        refs, _ = dart.select_reports("005930", "c", full_listing(), PERIODS)
        kinds = {r.period_end[5:]: r.kind for r in refs}
        self.assertEqual(kinds, {"03-31": "quarterly", "06-30": "half", "09-30": "quarterly", "12-31": "annual"})
        self.assertEqual(refs[0].source_url, f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={refs[0].rcept_no}")

    def test_same_slot_candidates_are_sorted_latest_first(self):
        listing = full_listing()
        listing["A003"].extend([
            item("[기재정정]분기보고서 (2024.03)", "20240520000009", "20240520"),
            item("[기재정정]분기보고서 (2024.03)", "20240518000008", "20240518"),
        ])
        grouped, missing = dart.select_disclosure_candidates("005930", "c", listing, PERIODS)
        self.assertEqual(missing, [])
        self.assertEqual(
            [ref.rcept_no for ref in grouped[("quarterly", "2024-03-31")]],
            ["20240520000009", "20240518000008", "20240315000001"],
        )

    def test_missing_periods_reported(self):
        listing = full_listing()
        listing["A002"] = []
        refs, missing = dart.select_reports("005930", "c", listing, PERIODS)
        self.assertEqual(missing, ["2024-06-30", "2025-06-30", "2026-06-30"])
        self.assertEqual(len(refs), 7)

    def test_kind_comes_from_title_when_lists_are_mixed(self):
        # 실제 list.json: 상세 유형(A001)을 지정해도 반기·분기보고서가 섞여 온다 (2026-10-21 실호출에서 확인)
        everything = [entry for entries in full_listing().values() for entry in entries]
        listing = {"A001": list(everything), "A002": list(everything), "A003": list(everything)}
        refs, missing = dart.select_reports("005930", "c", listing, PERIODS)
        self.assertEqual(missing, [])
        self.assertEqual(len(refs), 10)
        kinds = {r.period_end[5:]: r.kind for r in refs}
        self.assertEqual(kinds, {"03-31": "quarterly", "06-30": "half", "09-30": "quarterly", "12-31": "annual"})
        self.assertEqual({r.period_end: r.kind for r in refs}["2026-06-30"], "half")

    def test_half_report_in_annual_list_is_half(self):
        refs, _ = dart.select_reports("005930", "c", {"A001": [item("반기보고서 (2026.06)", "20260814003699", "20260814")]}, PERIODS)
        self.assertEqual([(r.kind, r.period_end) for r in refs], [("half", "2026-06-30")])

    def test_non_periodic_title_is_skipped(self):
        with self.assertLogs("pipelines.disclosures.dart", level="WARNING"):
            refs, missing = dart.select_reports("005930", "c", {"A001": [item("주요사항보고서(자기주식취득결정)", "1")]}, PERIODS)
        self.assertEqual(refs, [])
        self.assertEqual(len(missing), 10)

    def test_kind_period_mismatch_is_not_a_candidate(self):
        with self.assertLogs("pipelines.disclosures.dart", level="WARNING"):
            refs, missing = dart.select_reports("005930", "c", {"A002": [item("반기보고서 (2024.09)", "1")]}, PERIODS)
        self.assertEqual(refs, [])
        self.assertEqual(len(missing), 10)

    def test_period_parse(self):
        self.assertEqual(dart.period_end_from_title("분기보고서 (2024.03)"), "2024-03-31")
        self.assertEqual(dart.period_end_from_title("[기재정정]반기보고서 (2025.06)"), "2025-06-30")
        for bad in ("사업보고서", "분기보고서 (2024.05)"):
            with self.assertRaises(dart_reports.DartError):
                dart.period_end_from_title(bad)


class XmlPeriodTest(unittest.TestCase):
    def test_xml_period_mismatch_is_error(self):
        ref = dart.ReportRef("005930", "1", "반기보고서 (2026.06)", "half", "2026-06-30", "2026-08-14")
        dart.check_xml_period(ref, "20260630")
        for bad in ("20260331", None, "2026-06-30"):
            with self.assertRaises(dart_reports.DartError):
                dart.check_xml_period(ref, bad)

    def test_ref_from_zip(self):
        ref = dart.ref_from_zip(Path("005930_20260814003699.zip"), "반기보고서", "20260630")
        self.assertEqual(
            (ref.symbol, ref.rcept_no, ref.title, ref.kind, ref.period_end, ref.rcept_dt),
            ("005930", "20260814003699", "반기보고서 (2026.06)", "half", "2026-06-30", "2026-08-14"),
        )
        with self.assertRaises(dart_reports.DartError):
            dart.ref_from_zip(Path("sample.zip"), "반기보고서", "20260630")
        with self.assertRaises(dart_reports.DartError):
            dart.ref_from_zip(Path("005930_20260814003699.zip"), "주요사항보고서", "20260630")


def candidate(rcept_no, title, period_end="2025-12-31", kind="annual", rcept_dt=None):
    return dart.ReportRef(
        "105560",
        rcept_no,
        title,
        kind,
        period_end,
        rcept_dt or f"{rcept_no[:4]}-{rcept_no[4:6]}-{rcept_no[6:8]}",
        "00688996",
    )


class CandidateFallbackTest(unittest.TestCase):
    def download(self, candidates, responses):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        return dart.download_first_available_candidate(
            candidates, API_KEY, Path(self.tmp.name), session=FakeSession(responses)
        )

    def test_latest_candidate_downloads_normally(self):
        latest = candidate("20260619000667", "[기재정정]사업보고서 (2025.12)", rcept_dt="2026-06-19")
        selected, path = self.download([latest], [FakeResponse(content=zip_bytes(f"{latest.rcept_no}.xml", "<DOCUMENT/>"))])
        self.assertEqual(selected, latest)
        self.assertTrue(path.exists())

    def test_014_falls_back_to_previous_candidate(self):
        latest = candidate("20260619000667", "[기재정정]사업보고서 (2025.12)", rcept_dt="2026-06-19")
        previous = candidate("20260317001234", "사업보고서 (2025.12)", rcept_dt="2026-03-17")
        responses = [
            FakeResponse(content="<result><status>014</status><message>파일이 존재하지 않습니다.</message></result>".encode()),
            FakeResponse(content=zip_bytes(f"{previous.rcept_no}.xml", "<DOCUMENT/>")),
        ]
        with self.assertLogs("pipelines.disclosures.dart", level="INFO") as logs:
            selected, _ = self.download([previous, latest], responses)
        self.assertEqual(selected, previous)
        self.assertTrue(any("20260619000667" in line and "014" in line for line in logs.output))
        self.assertTrue(any(previous.rcept_no in line and "성공" in line for line in logs.output))

    def test_multiple_014s_fall_back_to_original(self):
        candidates = [
            candidate("20260619000667", "[첨부정정]사업보고서 (2025.12)", rcept_dt="2026-06-19"),
            candidate("20260401000002", "[기재정정]사업보고서 (2025.12)", rcept_dt="2026-04-01"),
            candidate("20260317000001", "사업보고서 (2025.12)", rcept_dt="2026-03-17"),
        ]
        error = FakeResponse(content=b'{"status":"014","message":"missing"}')
        selected, _ = self.download(
            candidates,
            [error, error, FakeResponse(content=zip_bytes("20260317000001.xml", "<DOCUMENT/>"))],
        )
        self.assertEqual(selected.rcept_no, "20260317000001")

    def test_all_candidates_failed_error_has_slot_and_attempts(self):
        candidates = [
            candidate("20260619000667", "[기재정정]사업보고서 (2025.12)", rcept_dt="2026-06-19"),
            candidate("20260317000001", "사업보고서 (2025.12)", rcept_dt="2026-03-17"),
        ]
        with self.assertRaises(dart.AllCandidatesFailed) as caught:
            self.download(candidates, [
                FakeResponse(content=b'<result><status>014</status><message>missing newest</message></result>'),
                FakeResponse(content=b'{"status":"010","message":"missing original"}'),
            ])
        message = str(caught.exception)
        for expected in ("105560", "2025년", "2025-12-31", "사업보고서", "20260619000667", "014", "20260317000001", "010"):
            self.assertIn(expected, message)
        self.assertEqual([f.rcept_no for f in caught.exception.failures], [c.rcept_no for c in candidates])

    def test_different_period_or_kind_cannot_be_fallback(self):
        valid = candidate("20260619000667", "[기재정정]사업보고서 (2025.12)", rcept_dt="2026-06-19")
        wrong_period = candidate("20260515000001", "분기보고서 (2026.03)", "2026-03-31", "quarterly", "2026-05-15")
        with tempfile.TemporaryDirectory() as directory, self.assertRaises(ValueError) as caught:
            dart.download_first_available_candidate([valid, wrong_period], API_KEY, Path(directory), session=FakeSession([]))
        self.assertIn("서로 다른 보고서 슬롯", str(caught.exception))

        listing = {"A001": [
            item("[기재정정]사업보고서 (2025.12)", valid.rcept_no, "20260619"),
            item("분기보고서 (2026.03)", wrong_period.rcept_no, "20260515"),
        ]}
        grouped, _ = dart.select_disclosure_candidates("105560", "00688996", listing, ["2025-12-31", "2026-03-31"])
        self.assertEqual([r.rcept_no for r in grouped[("annual", "2025-12-31")]], [valid.rcept_no])
        self.assertEqual([r.rcept_no for r in grouped[("quarterly", "2026-03-31")]], [wrong_period.rcept_no])


class ListStatusTest(unittest.TestCase):
    def list_with(self, payload):
        session = FakeSession([FakeResponse(json_data=payload)])
        return dart_reports.list_reports("c", API_KEY, bgn_de="20240101", end_de="20261021", detail_type="A003", session=session), session

    def test_013_is_no_data(self):
        with self.assertRaises(dart_reports.DartNoDataError):
            self.list_with({"status": "013", "message": "조회된 데이타가 없습니다."})

    def test_020_is_rate_limit_without_key(self):
        with self.assertRaises(dart_reports.DartRateLimitError) as caught:
            self.list_with({"status": "020", "message": f"요청 제한 초과 {API_KEY}"})
        self.assertNotIn(API_KEY, str(caught.exception))

    def test_request_params(self):
        items, session = self.list_with({"status": "000", "total_page": 1, "list": [item("분기보고서 (2024.03)", "1")]})
        self.assertEqual(len(items), 1)
        params = session.calls[0][1]
        self.assertEqual((params["pblntf_detail_ty"], params["last_reprt_at"], params["pblntf_ty"]), ("A003", "Y", "A"))


class CollectTest(unittest.TestCase):
    def test_rate_limit_aborts_collect(self):
        session = FakeSession([
            FakeResponse(json_data={"status": "020", "message": "limit"}),
        ])
        with tempfile.TemporaryDirectory() as directory:
            raw = Path(directory)
            (raw / "corpCode.xml").write_bytes(corp_xml([("005930", "00126380")]))
            with self.assertRaises(dart_reports.DartRateLimitError):
                dart.collect(["005930"], PERIODS, API_KEY, raw, bgn_de="20240101", end_de="20261021", corp_cache_days=7, session=session)

    def test_no_data_becomes_missing_and_existing_zip_not_downloaded(self):
        listing = full_listing()
        responses = [
            FakeResponse(json_data={"status": "000", "total_page": 1, "list": listing["A001"]}),
            FakeResponse(json_data={"status": "013", "message": "없음"}),
            FakeResponse(json_data={"status": "000", "total_page": 1, "list": listing["A003"]}),
        ]
        session = FakeSession(responses)
        with tempfile.TemporaryDirectory() as directory:
            raw = Path(directory)
            (raw / "corpCode.xml").write_bytes(corp_xml([("005930", "00126380")]))
            refs, _ = dart.select_reports("005930", "00126380", {"A001": listing["A001"], "A003": listing["A003"]}, PERIODS)
            for ref in refs:
                (raw / ref.zip_name()).write_bytes(zip_bytes(f"{ref.rcept_no}.xml", "<DOCUMENT/>"))
            result = dart.collect(["005930"], PERIODS, API_KEY, raw, bgn_de="20240101", end_de="20261021", corp_cache_days=7, session=session)
        self.assertEqual(len(result.reports), 7)
        self.assertEqual(len(session.calls), 3)  # 목록 3회, 다운로드 0회
        self.assertEqual(len(result.failures), 3)
        self.assertEqual(result.corp_codes, {"005930": "00126380"})

    def test_download_failure_is_skipped_and_reported_without_key(self):
        listing = {"A001": [item("사업보고서 (2024.12)", "20250311000001", "20250311")]}
        responses = [
            FakeResponse(json_data={"status": "000", "total_page": 1, "list": listing["A001"]}),
            FakeResponse(json_data={"status": "013"}),
            FakeResponse(json_data={"status": "013"}),
            FakeResponse(content=f"<result><status>010</status><message>bad {API_KEY}</message></result>".encode()),
        ]
        with tempfile.TemporaryDirectory() as directory:
            raw = Path(directory)
            (raw / "corpCode.xml").write_bytes(corp_xml([("005930", "00126380")]))
            result = dart.collect(["005930"], ["2024-12-31"], API_KEY, raw, bgn_de="20240101", end_de="20261021", corp_cache_days=7, session=FakeSession(responses))
        self.assertEqual(result.reports, [])
        self.assertEqual(len(result.failures), 1)
        self.assertNotIn(API_KEY, result.failures[0])
        [failed] = result.failed_items
        self.assertEqual(
            {k: failed[k] for k in ("symbol", "stage", "period_end", "kind", "rcept_no")},
            {"symbol": "005930", "stage": "download", "period_end": "2024-12-31", "kind": "annual", "rcept_no": "20250311000001"},
        )
        self.assertIn("010", failed["reason"])
        self.assertNotIn(API_KEY, failed["reason"])


class DownloadSafetyTest(unittest.TestCase):
    def test_download_020_is_rate_limit_and_aborts_collect(self):
        listing = {"A001": [item("사업보고서 (2024.12)", "20250311000001", "20250311")]}
        responses = [
            FakeResponse(json_data={"status": "000", "total_page": 1, "list": listing["A001"]}),
            FakeResponse(json_data={"status": "013"}),
            FakeResponse(json_data={"status": "013"}),
            FakeResponse(content=b"<result><status>020</status><message>limit</message></result>"),
        ]
        with tempfile.TemporaryDirectory() as directory:
            raw = Path(directory)
            (raw / "corpCode.xml").write_bytes(corp_xml([("005930", "00126380")]))
            with self.assertRaises(dart_reports.DartRateLimitError):
                dart.collect(["005930"], ["2024-12-31"], API_KEY, raw, bgn_de="20240101", end_de="20261021", corp_cache_days=7, session=FakeSession(responses))

    def test_corrupt_existing_zip_is_downloaded_again(self):
        import zipfile

        listing = {"A001": [item("사업보고서 (2024.12)", "20250311000001", "20250311")]}
        good = io.BytesIO()
        with zipfile.ZipFile(good, "w") as archive:
            archive.writestr("20250311000001.xml", "<DOCUMENT/>")
        responses = [
            FakeResponse(json_data={"status": "000", "total_page": 1, "list": listing["A001"]}),
            FakeResponse(json_data={"status": "013"}),
            FakeResponse(json_data={"status": "013"}),
            FakeResponse(content=good.getvalue()),
        ]
        with tempfile.TemporaryDirectory() as directory:
            raw = Path(directory)
            (raw / "corpCode.xml").write_bytes(corp_xml([("005930", "00126380")]))
            (raw / "005930_20250311000001.zip").write_bytes(b"PK\x03\x04truncated")
            result = dart.collect(["005930"], ["2024-12-31"], API_KEY, raw, bgn_de="20240101", end_de="20261021", corp_cache_days=7, session=FakeSession(responses))
            self.assertEqual(len(result.reports), 1)
            self.assertTrue(zipfile.is_zipfile(raw / "005930_20250311000001.zip"))
            self.assertEqual(list(raw.glob("*.part")), [])


def dart_reports_zip():
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("CORPCODE.xml", corp_xml([("005930", "00126380")]))
    return buffer.getvalue()


class CorpCodeCacheTest(unittest.TestCase):
    def test_cache_used_when_fresh_and_refreshed_when_stale(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "corpCode.xml"
            session = FakeSession([FakeResponse(content=dart_reports_zip())])
            self.assertEqual(dart.load_corp_codes(API_KEY, cache, 7, session), {"005930": "00126380"})
            self.assertTrue(cache.exists())
            self.assertEqual(dart.load_corp_codes(API_KEY, cache, 7, FakeSession([])), {"005930": "00126380"})
            stale = time.time() + 8 * 86400
            session = FakeSession([FakeResponse(content=dart_reports_zip())])
            dart.load_corp_codes(API_KEY, cache, 7, session, now=stale)
            self.assertEqual(len(session.calls), 1)

    def test_no_cache_no_key(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(dart_reports.DartError):
                dart.load_corp_codes(None, Path(directory) / "corpCode.xml", 7)


class RetryThrottleTest(unittest.TestCase):
    def test_retry_backoff(self):
        sleeps, calls = [], []

        def flaky():
            calls.append(1)
            if len(calls) < 3:
                raise requests.ConnectionError("x")
            return "ok"

        self.assertEqual(retry_call(flaky, attempts=3, base_delay=1.0, sleep=sleeps.append), "ok")
        self.assertEqual(sleeps, [1.0, 2.0])

    def test_retry_gives_up(self):
        with self.assertRaises(ValueError):
            retry_call(lambda: (_ for _ in ()).throw(ValueError()), attempts=3, sleep=lambda s: None)

    def test_polite_session_retries_transient_only(self):
        class Flaky:
            def __init__(self):
                self.calls = 0

            def get(self, url, params, timeout):
                self.calls += 1
                if self.calls == 1:
                    raise requests.Timeout("t")
                return FakeResponse(json_data={"status": "000"})

        inner = Flaky()
        session = dart.PoliteSession(inner, interval=0, sleep=lambda s: None)
        self.assertEqual(session.get("u", params={}, timeout=1).json()["status"], "000")
        self.assertEqual(inner.calls, 2)

    def test_throttle_interval(self):
        now = [0.0]
        sleeps = []
        throttle = Throttle(0.2, clock=lambda: now[0], sleep=lambda s: (sleeps.append(round(s, 3)), now.__setitem__(0, now[0] + s)))
        throttle.wait()
        now[0] += 0.05
        throttle.wait()
        self.assertEqual(sleeps, [0.15])


class RedactTest(unittest.TestCase):
    def test_log_records_are_redacted(self):
        logger = logging.getLogger("pipelines.test_redact")
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.addFilter(RedactFilter([API_KEY]))
        logger.addHandler(handler)
        try:
            logger.error("url?crtfc_key=%s", API_KEY)
            try:
                raise RuntimeError(f"boom {API_KEY}")
            except RuntimeError:
                logger.exception("failed")
        finally:
            logger.removeHandler(handler)
        self.assertNotIn(API_KEY, stream.getvalue())
        self.assertIn("[REDACTED]", stream.getvalue())


if __name__ == "__main__":
    unittest.main()
