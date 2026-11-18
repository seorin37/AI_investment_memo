"""OpenDART 정기보고서(사업·반기·분기) 목록 조회와 원문 ZIP 다운로드.

CLI는 최근 반기보고서 1건을 내려받는다. 여러 기간·보고서 유형 수집은 pipelines.disclosures.dart가 이 모듈을 쓴다.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import zipfile
from datetime import date, timedelta
from pathlib import Path
from xml.etree import ElementTree

import requests


API_BASE = "https://opendart.fss.or.kr/api"
DEFAULT_OUT_DIR = Path(__file__).resolve().parents[2] / "data" / "raw" / "dart"


class DartError(Exception):
    """OpenDART 요청 또는 응답 처리 실패."""


class DartNoDataError(DartError):
    """상태 013: 조회된 데이터 없음."""


class DartRateLimitError(DartError):
    """상태 020: 요청 한도 초과. 수집을 중단해야 한다."""


class DartDownloadError(DartError):
    """document.xml이 DART 오류 또는 유효하지 않은 ZIP을 반환했다."""

    def __init__(self, code: str, message: str):
        self.code = str(code)
        self.message = str(message)
        super().__init__(f"원문 다운로드 오류: {self.code}: {self.message}")


# 정기보고서 상세 유형 → disclosures.kind
REPORT_TYPES = {"A001": "annual", "A002": "half", "A003": "quarterly"}


def _session(session=None):
    return session if session is not None else requests


def _safe_message(message: object, api_key: str) -> str:
    return str(message).replace(api_key, "[REDACTED]") if api_key else str(message)


def _get(session, endpoint: str, *, params: dict, timeout: int):
    try:
        response = _session(session).get(
            f"{API_BASE}/{endpoint}", params=params, timeout=timeout
        )
        response.raise_for_status()
        return response
    except requests.RequestException as exc:
        raise DartError(f"{endpoint} 요청 실패 ({type(exc).__name__})") from None


def parse_dart_error(content: bytes) -> tuple[str, str] | None:
    """응답 본문이 DART 오류 XML/JSON이면 (코드, 메시지)를 반환한다."""
    try:
        root = ElementTree.fromstring(content)
        status = root.findtext(".//status")
        message = root.findtext(".//message")
        if status or message:
            return str(status or "unknown"), str(message or "알 수 없는 오류")
    except ElementTree.ParseError:
        pass

    try:
        data = json.loads(content.decode("utf-8"))
        status = data.get("status")
        message = data.get("message")
        if status or message:
            return str(status or "unknown"), str(message or "알 수 없는 오류")
    except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
        pass
    return None


def validate_document_zip(content: bytes, expected_xml: str | None = None) -> None:
    """실제 ZIP 구조·CRC·XML 포함 여부를 검사한다. Content-Type과 접두 바이트는 신뢰하지 않는다."""
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            if archive.testzip() is not None:
                raise zipfile.BadZipFile("CRC 오류")
            names = archive.namelist()
            if not any(name.lower().endswith(".xml") and not name.endswith("/") for name in names):
                raise zipfile.BadZipFile("XML 파일 없음")
            if expected_xml is not None and expected_xml not in names:
                raise zipfile.BadZipFile(f"본문 {expected_xml} 없음")
    except (zipfile.BadZipFile, OSError) as exc:
        raise DartDownloadError("invalid_zip", f"유효한 원문 ZIP이 아닙니다 ({exc})") from None


def fetch_corp_code_xml(api_key: str, session=None) -> bytes:
    """corpCode.xml(ZIP)을 받아 CORPCODE.xml 원문 바이트를 반환한다."""
    response = _get(
        session,
        "corpCode.xml",
        params={"crtfc_key": api_key},
        timeout=60,
    )
    try:
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            return archive.read("CORPCODE.xml")
    except (zipfile.BadZipFile, KeyError) as exc:
        raise DartError(f"corpCode.xml 응답 처리 실패 ({type(exc).__name__})") from None


def parse_corp_codes(xml_bytes: bytes) -> dict[str, str]:
    """CORPCODE.xml에서 {종목코드: 고유번호}를 만든다 (상장사만)."""
    try:
        root = ElementTree.fromstring(xml_bytes)
    except ElementTree.ParseError as exc:
        raise DartError(f"corpCode.xml 응답 처리 실패 ({type(exc).__name__})") from None
    mapping: dict[str, str] = {}
    for item in root.findall("list"):
        stock_code = (item.findtext("stock_code") or "").strip()
        corp_code = (item.findtext("corp_code") or "").strip()
        if stock_code and corp_code:
            mapping.setdefault(stock_code, corp_code)
    return mapping


def resolve_corp_code(stock_code: str, api_key: str, session=None) -> str:
    """종목코드에 대응하는 DART 고유번호를 반환한다."""
    corp_code = parse_corp_codes(fetch_corp_code_xml(api_key, session)).get(stock_code)
    if corp_code:
        return corp_code
    raise DartError(f"종목코드 {stock_code}에 해당하는 고유번호가 없습니다.")


def list_reports(
    corp_code: str,
    api_key: str,
    *,
    bgn_de: str,
    end_de: str,
    detail_type: str,
    last_reprt_at: str = "Y",
    session=None,
) -> list[dict]:
    """정기보고서 목록을 모든 페이지에서 모은다.

    상태 013은 DartNoDataError, 020은 DartRateLimitError, 그 밖의 오류는 DartError.
    `last_reprt_at="Y"`는 최종 정정본만, `"N"`은 최초 제출본을 포함한 전체 이력이다.
    """
    return list_disclosures(
        api_key,
        bgn_de=bgn_de,
        end_de=end_de,
        pblntf_ty="A",
        pblntf_detail_ty=detail_type,
        corp_code=corp_code,
        last_reprt_at=last_reprt_at,
        session=session,
    )


def list_disclosures(
    api_key: str,
    *,
    bgn_de: str,
    end_de: str,
    pblntf_ty: str,
    pblntf_detail_ty: str | None = None,
    corp_code: str | None = None,
    corp_cls: str | None = None,
    last_reprt_at: str = "Y",
    page_count: int = 100,
    session=None,
) -> list[dict]:
    """공시 목록(list.json)을 모든 페이지에서 모은다. 정기보고서·수시공시 공용.

    corp_code 없이 부르면 DART 규칙상 조회 기간이 3개월 이내여야 한다.
    상태 013은 DartNoDataError, 020은 DartRateLimitError, 그 밖의 오류는 DartError.
    """
    common_params = {
        "crtfc_key": api_key,
        "bgn_de": bgn_de,
        "end_de": end_de,
        "pblntf_ty": pblntf_ty,
        "last_reprt_at": last_reprt_at,
        "page_count": page_count,
    }
    if corp_code:
        common_params["corp_code"] = corp_code
    if pblntf_detail_ty:
        common_params["pblntf_detail_ty"] = pblntf_detail_ty
    if corp_cls:
        common_params["corp_cls"] = corp_cls
    items: list[dict] = []
    page_no = 1
    total_page = 1

    while page_no <= total_page:
        params = {**common_params, "page_no": page_no}
        response = _get(session, "list.json", params=params, timeout=10)
        try:
            data = response.json()
        except (ValueError, AttributeError):
            raise DartError("list.json 응답을 해석할 수 없습니다.") from None

        status = str(data.get("status", ""))
        if status == "013":
            raise DartNoDataError("조회 기간에 공시 데이터가 없습니다.")
        if status != "000":
            message = _safe_message(data.get("message") or "알 수 없는 오류", api_key)
            error = DartRateLimitError if status == "020" else DartError
            raise error(f"DART 목록 조회 오류 ({status}): {message}")

        items.extend(data.get("list", []))
        try:
            total_page = max(1, int(data.get("total_page", 1)))
        except (TypeError, ValueError):
            raise DartError("list.json의 total_page 값이 올바르지 않습니다.") from None
        page_no += 1
    return items


def find_latest_half_year_report(
    corp_code: str,
    api_key: str,
    session=None,
    today: date | None = None,
    lookback_days: int = 730,
) -> dict:
    """조회 기간 내 가장 최근 반기보고서의 메타데이터를 반환한다."""
    end = today or date.today()
    candidates = [
        item
        for item in list_reports(
            corp_code,
            api_key,
            bgn_de=(end - timedelta(days=lookback_days)).strftime("%Y%m%d"),
            end_de=end.strftime("%Y%m%d"),
            detail_type="A002",
            session=session,
        )
        if "반기보고서" in str(item.get("report_nm", ""))
    ]

    if not candidates:
        raise DartError("조회 기간에 반기보고서가 없습니다.")
    return max(
        candidates,
        key=lambda item: (str(item.get("rcept_dt", "")), str(item.get("rcept_no", ""))),
    )


def download_document(
    rcept_no: str, api_key: str, out_path: Path, session=None
) -> Path:
    """공시 원문 ZIP을 지정 경로에 저장한다."""
    response = _get(
        session,
        "document.xml",
        params={"crtfc_key": api_key, "rcept_no": rcept_no},
        timeout=60,
    )
    content = response.content
    dart_error = parse_dart_error(content)
    if dart_error is not None:
        code, message = dart_error
        message = _safe_message(message, api_key)
        if code == "020":
            raise DartRateLimitError(f"원문 다운로드 오류: {code}: {message}")
        raise DartDownloadError(code, message)
    validate_document_zip(content, f"{rcept_no}.xml")

    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # 중간에 끊겨도 잘린 ZIP이 최종 경로에 남지 않게 임시 파일에 쓰고 바꾼다.
    temp = path.with_name(path.name + ".part")
    temp.write_bytes(content)
    os.replace(temp, path)
    return path


def download_latest_half_year_report(
    stock_code: str,
    api_key: str,
    out_dir: Path,
    session=None,
    today: date | None = None,
) -> tuple[dict, Path]:
    """종목의 최신 반기보고서를 찾고 원문 ZIP을 저장한다."""
    corp_code = resolve_corp_code(stock_code, api_key, session=session)
    report = find_latest_half_year_report(
        corp_code, api_key, session=session, today=today
    )
    path = Path(out_dir) / f"{stock_code}_{report['rcept_no']}.zip"
    return report, download_document(
        str(report["rcept_no"]), api_key, path, session=session
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="OpenDART 최근 반기보고서 다운로드")
    parser.add_argument("--stock-code", default="005930")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args(argv)

    from dotenv import load_dotenv

    load_dotenv()
    api_key = os.getenv("DART_API_KEY")
    if not api_key:
        print("DART_API_KEY가 설정되지 않았습니다.", file=sys.stderr)
        return 2

    try:
        report, path = download_latest_half_year_report(
            args.stock_code, api_key, args.out_dir
        )
    except DartError as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 1

    print(f"보고서명: {report.get('report_nm', '')}")
    print(f"접수일: {report.get('rcept_dt', '')}")
    print(f"접수번호: {report.get('rcept_no', '')}")
    print(f"저장 경로: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
