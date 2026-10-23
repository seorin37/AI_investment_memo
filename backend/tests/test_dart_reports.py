import io
import os
import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path
from unittest import mock

import requests

from app import dart_reports


API_KEY = "test-secret-key"


class FakeResponse:
    def __init__(self, *, content=b"", json_data=None, status_error=None):
        self.content = content
        self._json_data = json_data
        self._status_error = status_error

    def raise_for_status(self):
        if self._status_error:
            raise self._status_error

    def json(self):
        if isinstance(self._json_data, Exception):
            raise self._json_data
        return self._json_data


class FakeSession:
    def __init__(self, responses=None, error=None):
        self.responses = list(responses or [])
        self.error = error
        self.calls = []

    def get(self, url, *, params, timeout):
        self.calls.append((url, params, timeout))
        if self.error:
            raise self.error
        return self.responses.pop(0)


def corp_code_zip(entries):
    body = "<result>" + "".join(
        f"<list><corp_code>{corp}</corp_code><stock_code>{stock}</stock_code></list>"
        for stock, corp in entries
    ) + "</result>"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("CORPCODE.xml", body)
    return buffer.getvalue()


def document_zip(rcept_no):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(f"{rcept_no}.xml", "<DOCUMENT/>")
    return buffer.getvalue()


class DartReportsTest(unittest.TestCase):
    def test_default_out_dir_is_absolute_repo_data_directory(self):
        self.assertTrue(dart_reports.DEFAULT_OUT_DIR.is_absolute())
        self.assertEqual(
            dart_reports.DEFAULT_OUT_DIR.parts[-3:], ("data", "raw", "dart")
        )
        self.assertTrue(
            (
                dart_reports.DEFAULT_OUT_DIR.parents[2]
                / "backend"
                / "app"
                / "dart_reports.py"
            ).is_file()
        )

    def test_resolve_corp_code(self):
        session = FakeSession([FakeResponse(content=corp_code_zip([("005930", "00126380")]))])
        self.assertEqual(dart_reports.resolve_corp_code("005930", API_KEY, session), "00126380")
        self.assertTrue(session.calls[0][0].endswith("/corpCode.xml"))
        self.assertEqual(session.calls[0][2], 60)

    def test_resolve_corp_code_missing_stock(self):
        session = FakeSession([FakeResponse(content=corp_code_zip([("000000", "12345678")]))])
        with self.assertRaises(dart_reports.DartError):
            dart_reports.resolve_corp_code("005930", API_KEY, session)

    def test_find_latest_report_and_request_params(self):
        reports = [
            {"report_nm": "반기보고서", "rcept_dt": "20240814", "rcept_no": "1"},
            {"report_nm": "반기보고서 (2025.06)", "rcept_dt": "20250814", "rcept_no": "2"},
            {"report_nm": "사업보고서", "rcept_dt": "20250901", "rcept_no": "3"},
        ]
        session = FakeSession([FakeResponse(json_data={"status": "000", "total_page": 1, "list": reports})])
        result = dart_reports.find_latest_half_year_report(
            "00126380", API_KEY, session, today=date(2025, 8, 20)
        )
        self.assertEqual(result["rcept_no"], "2")
        params = session.calls[0][1]
        self.assertEqual(params["corp_code"], "00126380")
        self.assertEqual(params["pblntf_ty"], "A")
        self.assertEqual(params["pblntf_detail_ty"], "A002")
        self.assertEqual(params["last_reprt_at"], "Y")
        self.assertEqual(params["bgn_de"], "20230821")
        self.assertEqual(params["end_de"], "20250820")
        self.assertEqual(session.calls[0][2], 10)

    def test_find_latest_report_reads_all_pages(self):
        session = FakeSession([
            FakeResponse(json_data={"status": "000", "total_page": 2, "list": [{"report_nm": "반기보고서", "rcept_dt": "20240814", "rcept_no": "1"}]}),
            FakeResponse(json_data={"status": "000", "total_page": 2, "list": [{"report_nm": "반기보고서", "rcept_dt": "20250814", "rcept_no": "2"}]}),
        ])
        result = dart_reports.find_latest_half_year_report("00126380", API_KEY, session)
        self.assertEqual(result["rcept_no"], "2")
        self.assertEqual([call[1]["page_no"] for call in session.calls], [1, 2])

    def test_find_latest_report_no_data_status(self):
        session = FakeSession([FakeResponse(json_data={"status": "013", "message": "조회된 데이터가 없습니다."})])
        with self.assertRaises(dart_reports.DartError) as caught:
            dart_reports.find_latest_half_year_report("00126380", API_KEY, session)
        self.assertIn("조회 기간에 공시 데이터가 없습니다", str(caught.exception))
        self.assertNotIn("목록 조회 오류", str(caught.exception))

    def test_find_latest_report_error_includes_message_not_key(self):
        session = FakeSession([FakeResponse(json_data={"status": "010", "message": f"등록되지 않은 키 {API_KEY}"})])
        with self.assertRaises(dart_reports.DartError) as caught:
            dart_reports.find_latest_half_year_report("00126380", API_KEY, session)
        self.assertIn("등록되지 않은 키", str(caught.exception))
        self.assertNotIn(API_KEY, str(caught.exception))

    def test_download_document_writes_zip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nested" / "report.zip"
            content = document_zip("123")
            session = FakeSession([FakeResponse(content=content)])
            self.assertEqual(dart_reports.download_document("123", API_KEY, path, session), path)
            self.assertEqual(path.read_bytes(), content)
            self.assertEqual(session.calls[0][2], 60)

    def test_download_document_rejects_error_xml_without_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.zip"
            content = b"<result><status>010</status><message>error</message></result>"
            session = FakeSession([FakeResponse(content=content)])
            with self.assertRaises(dart_reports.DartError) as caught:
                dart_reports.download_document("123", API_KEY, path, session)
            self.assertIn("error", str(caught.exception))
            self.assertFalse(path.exists())

    def test_download_document_rejects_error_json_and_fake_pk(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.zip"
            for content, code in ((b'{"status":"014","message":"missing"}', "014"), (b"PK\x03\x04not-a-zip", "invalid_zip")):
                with self.subTest(code=code), self.assertRaises(dart_reports.DartDownloadError) as caught:
                    dart_reports.download_document("123", API_KEY, path, FakeSession([FakeResponse(content=content)]))
                self.assertEqual(caught.exception.code, code)
                self.assertFalse(path.exists())

    def test_download_latest_half_year_report_full_flow(self):
        report = {"report_nm": "반기보고서", "rcept_dt": "20250814", "rcept_no": "202508140001"}
        session = FakeSession([
            FakeResponse(content=corp_code_zip([("005930", "00126380")])),
            FakeResponse(json_data={"status": "000", "total_page": 1, "list": [report]}),
            FakeResponse(content=document_zip("202508140001")),
        ])
        with tempfile.TemporaryDirectory() as directory:
            result, path = dart_reports.download_latest_half_year_report(
                "005930", API_KEY, Path(directory), session, today=date(2025, 8, 20)
            )
            self.assertEqual(result, report)
            self.assertEqual(path.name, "005930_202508140001.zip")
            self.assertTrue(path.exists())
        self.assertEqual([call[0].rsplit("/", 1)[-1] for call in session.calls], ["corpCode.xml", "list.json", "document.xml"])

    def test_request_exception_does_not_leak_key(self):
        error = requests.ConnectionError(f"failed URL?crtfc_key={API_KEY}")
        with self.assertRaises(dart_reports.DartError) as caught:
            dart_reports.resolve_corp_code("005930", API_KEY, FakeSession(error=error))
        self.assertNotIn(API_KEY, str(caught.exception))
        self.assertIn("ConnectionError", str(caught.exception))

    def test_http_error_does_not_leak_key(self):
        error = requests.HTTPError(f"401 URL?crtfc_key={API_KEY}")
        session = FakeSession([FakeResponse(status_error=error)])
        with self.assertRaises(dart_reports.DartError) as caught:
            dart_reports.resolve_corp_code("005930", API_KEY, session)
        self.assertNotIn(API_KEY, str(caught.exception))

    def test_cli_without_api_key_returns_two_without_network(self):
        with (
            mock.patch.dict(os.environ, {}, clear=True),
            mock.patch("dotenv.load_dotenv") as load_dotenv,
            mock.patch.object(dart_reports, "download_latest_half_year_report") as download,
            mock.patch("sys.stderr", new_callable=io.StringIO) as stderr,
        ):
            result = dart_reports.main([])
        self.assertEqual(result, 2)
        load_dotenv.assert_called_once_with()
        download.assert_not_called()
        self.assertIn("DART_API_KEY", stderr.getvalue())

    def test_cli_default_out_dir_is_independent_of_current_directory(self):
        report = {"report_nm": "반기보고서", "rcept_dt": "20250814", "rcept_no": "12345"}
        path = dart_reports.DEFAULT_OUT_DIR / "005930_12345.zip"
        with tempfile.TemporaryDirectory() as directory:
            original_directory = Path.cwd()
            try:
                os.chdir(directory)
                with (
                    mock.patch.dict(os.environ, {"DART_API_KEY": API_KEY}, clear=True),
                    mock.patch("dotenv.load_dotenv"),
                    mock.patch.object(
                        dart_reports,
                        "download_latest_half_year_report",
                        return_value=(report, path),
                    ) as download,
                    mock.patch("sys.stdout", new_callable=io.StringIO),
                ):
                    result = dart_reports.main([])
            finally:
                os.chdir(original_directory)
        self.assertEqual(result, 0)
        self.assertEqual(download.call_args.args[2], dart_reports.DEFAULT_OUT_DIR)

    def test_cli_preserves_custom_out_dir(self):
        report = {"report_nm": "반기보고서", "rcept_dt": "20250814", "rcept_no": "12345"}
        path = Path("custom/path/005930_12345.zip")
        with (
            mock.patch.dict(os.environ, {"DART_API_KEY": API_KEY}, clear=True),
            mock.patch("dotenv.load_dotenv"),
            mock.patch.object(
                dart_reports,
                "download_latest_half_year_report",
                return_value=(report, path),
            ) as download,
            mock.patch("sys.stdout", new_callable=io.StringIO),
        ):
            result = dart_reports.main(["--out-dir", "custom/path"])
        self.assertEqual(result, 0)
        self.assertEqual(download.call_args.args[2], Path("custom/path"))

    def test_cli_success(self):
        report = {"report_nm": "반기보고서", "rcept_dt": "20250814", "rcept_no": "12345"}
        path = Path("data/raw/dart/005930_12345.zip")
        with (
            mock.patch.dict(os.environ, {"DART_API_KEY": API_KEY}, clear=True),
            mock.patch("dotenv.load_dotenv"),
            mock.patch.object(dart_reports, "download_latest_half_year_report", return_value=(report, path)),
            mock.patch("sys.stdout", new_callable=io.StringIO) as stdout,
        ):
            result = dart_reports.main([])
        output = stdout.getvalue()
        self.assertEqual(result, 0)
        self.assertIn("12345", output)
        self.assertIn(str(path), output)
        self.assertNotIn(API_KEY, output)


if __name__ == "__main__":
    unittest.main()
