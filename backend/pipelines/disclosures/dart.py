"""OpenDART 정기보고서 수집: 대상 기간 목록 확정 · 원문 ZIP 다운로드 · corpCode 캐시.

- 보고서는 제출일이 아니라 대상 기간(period_end, report_nm의 `(YYYY.MM)`)으로 고른다.
- 같은 (기업, 사업연도, 유형, 대상 기간)의 모든 제출본을 최신순 후보로 두고 유효한 첫 원문을 쓴다.
- 상태 020(요청 한도 초과)은 전체 수집 중단, 013(데이터 없음)은 빈 목록.
"""

from __future__ import annotations

import calendar
import json
import re
import time
from dataclasses import asdict, dataclass, field, replace
from datetime import date, datetime
from pathlib import Path

import requests

from app.dart_reports import (
    REPORT_TYPES,
    DartDownloadError,
    DartError,
    DartNoDataError,
    DartRateLimitError,
    _safe_message,
    download_document,
    fetch_corp_code_xml,
    list_reports,
    parse_corp_codes,
    parse_dart_error,
    validate_document_zip,
)

from ..common.logging import get_logger
from ..common.retry import Throttle, retry_call


log = get_logger("disclosures.dart")

PERIOD_RE = re.compile(r"\((\d{4})\.(\d{2})\)")
MONTH_END = {3: 31, 6: 30, 9: 30, 12: 31}
KIND_MONTHS = {"annual": {12}, "half": {6}, "quarterly": {3, 9}}
KIND_DOCUMENT_NAMES = {"사업보고서": "annual", "반기보고서": "half", "분기보고서": "quarterly"}
KIND_LABELS = {"annual": "사업보고서", "half": "반기보고서", "quarterly": "분기보고서"}


@dataclass(frozen=True)
class ReportRef:
    symbol: str
    rcept_no: str
    title: str
    kind: str
    period_end: str  # YYYY-MM-DD
    rcept_dt: str  # YYYY-MM-DD (KST)
    corp_code: str = ""
    period_label: str = ""  # 청크 헤더용 (1분기·반기·3분기·사업보고서). 비어 있으면 period_end 월로 정한다.

    @property
    def source_url(self) -> str:
        return source_url(self.rcept_no)

    def zip_name(self) -> str:
        return f"{self.symbol}_{self.rcept_no}.zip"

    @property
    def is_amendment(self) -> bool:
        return "정정" in self.title

    def to_dict(self) -> dict:
        return asdict(self)


def source_url(rcept_no: str) -> str:
    return f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}"


def period_end_from_title(report_nm: str) -> str:
    """report_nm의 `(YYYY.MM)`에서 period_end(월말)를 구한다."""
    matches = PERIOD_RE.findall(report_nm)
    if not matches:
        raise DartError(f"보고서명에서 기간을 찾을 수 없습니다: {report_nm}")
    year, month = int(matches[-1][0]), int(matches[-1][1])
    if month not in MONTH_END:
        raise DartError(f"정기보고서 기간 월이 올바르지 않습니다: {report_nm}")
    return date(year, month, MONTH_END[month]).isoformat()


def check_kind_period(kind: str, period_end: str, label: str) -> None:
    if int(period_end[5:7]) not in KIND_MONTHS[kind]:
        raise DartError(f"보고서 유형({kind})과 기간({period_end})이 맞지 않습니다: {label}")


def check_xml_period(ref: ReportRef, period_to: str | None) -> None:
    """XML 표지의 AUNIT=PERIODTO 값과 period_end가 다르면 오류."""
    xml_period = None
    if period_to and re.fullmatch(r"\d{8}", period_to):
        xml_period = f"{period_to[:4]}-{period_to[4:6]}-{period_to[6:]}"
    if xml_period != ref.period_end:
        raise DartError(f"{ref.rcept_no}: 보고서명 기간 {ref.period_end}와 XML 기간 {period_to}이 다릅니다.")


def _iso(yyyymmdd: str) -> str:
    return datetime.strptime(yyyymmdd, "%Y%m%d").date().isoformat()


def kind_from_title(report_nm: str) -> str | None:
    """보고서명(사업·반기·분기보고서)으로 disclosures.kind를 정한다. 정기보고서가 아니면 None."""
    compact = report_nm.replace(" ", "")
    return next((kind for name, kind in KIND_DOCUMENT_NAMES.items() if name in compact), None)


CandidateKey = tuple[str, str]  # (kind, period_end)


def _expected_kind(period_end: str) -> str:
    month = int(period_end[5:7])
    matches = [kind for kind, months in KIND_MONTHS.items() if month in months]
    if len(matches) != 1:
        raise DartError(f"대상 기간의 보고서 유형을 결정할 수 없습니다: {period_end}")
    return matches[0]


def select_disclosure_candidates(
    symbol: str,
    corp_code: str,
    items_by_type: dict[str, list[dict]],
    periods: list[str],
) -> tuple[dict[CandidateKey, list[ReportRef]], list[CandidateKey]]:
    """정확히 같은 보고서 슬롯의 제출 이력을 묶어 접수일·접수번호 최신순으로 반환한다.

    보고서 종류는 요청한 상세 유형(A001~A003)이 아니라 보고서명으로 정한다. 실제 list.json은 상세 유형을
    지정해도 다른 정기보고서를 섞어 돌려주므로, 같은 접수번호가 여러 목록에 나와도 한 번만 센다.
    """
    targets = set(periods)
    target_keys = {(_expected_kind(period), period) for period in targets}
    grouped: dict[CandidateKey, list[ReportRef]] = {key: [] for key in target_keys}
    seen: set[str] = set()
    for _, items in sorted(items_by_type.items()):
        for item in items:
            title = str(item.get("report_nm", "")).strip()
            rcept_no = str(item["rcept_no"])
            if rcept_no in seen:
                continue
            kind = kind_from_title(title)
            if kind is None or not PERIOD_RE.search(title):
                log.warning("정기보고서 형식이 아닌 항목 건너뜀: %s %s", rcept_no, title)
                continue
            period_end = period_end_from_title(title)
            if period_end not in targets:
                continue
            key = (kind, period_end)
            if key not in target_keys:
                log.warning("대상 슬롯과 유형이 다른 항목 건너뜀: %s %s", rcept_no, title)
                continue
            check_kind_period(kind, period_end, title)
            seen.add(rcept_no)
            grouped[key].append(ReportRef(
                symbol=symbol,
                rcept_no=rcept_no,
                title=title,
                kind=kind,
                period_end=period_end,
                rcept_dt=_iso(str(item["rcept_dt"])),
                corp_code=corp_code,
            ))
    for candidates in grouped.values():
        candidates.sort(key=lambda ref: (ref.rcept_dt, ref.rcept_no), reverse=True)
    missing = sorted(key for key, candidates in grouped.items() if not candidates)
    return {key: candidates for key, candidates in grouped.items() if candidates}, missing


def fiscal_period_label(kind: str, period_end: str, fy_end_month: int) -> str | None:
    """결산월 기준으로 몇 번째 분기인지 정한다. 12월 결산이면 월 기준 라벨과 같다. 유형과 안 맞으면 None."""
    offset = (int(period_end[5:7]) - fy_end_month) % 12
    label = {3: "1분기", 6: "반기", 9: "3분기", 0: "사업보고서"}.get(offset)
    expected = {"1분기": "quarterly", "3분기": "quarterly", "반기": "half", "사업보고서": "annual"}.get(label or "")
    return label if expected == kind else None


def _any_period_end(report_nm: str) -> str:
    """report_nm의 `(YYYY.MM)`에서 그 달 말일을 구한다 (결산월 제한 없음)."""
    matches = PERIOD_RE.findall(report_nm)
    if not matches:
        raise DartError(f"보고서명에서 기간을 찾을 수 없습니다: {report_nm}")
    year, month = int(matches[-1][0]), int(matches[-1][1])
    if not 1 <= month <= 12:
        raise DartError(f"보고서명의 기간 월이 올바르지 않습니다: {report_nm}")
    return date(year, month, calendar.monthrange(year, month)[1]).isoformat()


def select_window_candidates(
    symbol: str,
    corp_code: str,
    items_by_type: dict[str, list[dict]],
    start: str,
    end: str,
    max_slots: int,
) -> tuple[dict[CandidateKey, list[ReportRef]], list[CandidateKey]]:
    """결산월과 무관하게 대상 기간(start~end) 안의 정기보고서 슬롯을 최근 max_slots개까지 고른다.

    결산월은 목록에 있는 가장 최근 사업보고서의 기간 월로 정한다 (없으면 반기보고서 월 + 6, 그것도 없으면 12월).
    누락 슬롯 개념이 없으므로 두 번째 반환값은 항상 빈 목록이다.
    """
    entries: list[tuple[str, str, dict]] = []  # (kind, period_end, item)
    seen: set[str] = set()
    for _, items in sorted(items_by_type.items()):
        for item in items:
            title = str(item.get("report_nm", "")).strip()
            rcept_no = str(item["rcept_no"])
            if rcept_no in seen:
                continue
            seen.add(rcept_no)
            kind = kind_from_title(title)
            if kind is None or not PERIOD_RE.search(title):
                log.warning("정기보고서 형식이 아닌 항목 건너뜀: %s %s", rcept_no, title)
                continue
            try:
                entries.append((kind, _any_period_end(title), item))
            except DartError as exc:
                log.warning("기간을 읽을 수 없는 항목 건너뜀: %s %s (%s)", rcept_no, title, exc)

    annual = sorted(period for kind, period, _ in entries if kind == "annual")
    half = sorted(period for kind, period, _ in entries if kind == "half")
    if annual:
        fy_end_month = int(annual[-1][5:7])
    elif half:
        fy_end_month = (int(half[-1][5:7]) + 6 - 1) % 12 + 1
    else:
        fy_end_month = 12

    grouped: dict[CandidateKey, list[ReportRef]] = {}
    for kind, period_end, item in entries:
        if not start <= period_end <= end:
            continue
        title = str(item.get("report_nm", "")).strip()
        label = fiscal_period_label(kind, period_end, fy_end_month)
        if label is None:
            log.warning("결산월(%d월)과 유형이 맞지 않는 항목 건너뜀: %s %s %s", fy_end_month, symbol, item["rcept_no"], title)
            continue
        grouped.setdefault((kind, period_end), []).append(ReportRef(
            symbol=symbol,
            rcept_no=str(item["rcept_no"]),
            title=title,
            kind=kind,
            period_end=period_end,
            rcept_dt=_iso(str(item["rcept_dt"])),
            corp_code=corp_code,
            period_label=label,
        ))
    for candidates in grouped.values():
        candidates.sort(key=lambda ref: (ref.rcept_dt, ref.rcept_no), reverse=True)
    keep = sorted(grouped, key=lambda key: key[1])[-max_slots:] if max_slots > 0 else []
    return {key: grouped[key] for key in keep}, []


def select_reports(symbol: str, corp_code: str, items_by_type: dict[str, list[dict]], periods: list[str]) -> tuple[list[ReportRef], list[str]]:
    """호환용: 각 슬롯의 최신 후보와 누락 기간을 반환한다."""
    grouped, missing = select_disclosure_candidates(symbol, corp_code, items_by_type, periods)
    selected = [candidates[0] for _, candidates in sorted(grouped.items(), key=lambda entry: entry[0][1])]
    return selected, [period for _, period in missing]


@dataclass(frozen=True)
class CandidateFailure:
    rcept_no: str
    code: str
    message: str


class AllCandidatesFailed(DartError):
    def __init__(self, candidate: ReportRef, failures: list[CandidateFailure]):
        self.symbol = candidate.symbol
        self.business_year = candidate.period_end[:4]
        self.period_end = candidate.period_end
        self.kind = candidate.kind
        self.failures = failures
        attempts = "; ".join(f"{f.rcept_no} [{f.code}: {f.message}]" for f in failures)
        super().__init__(
            f"{self.symbol} {self.business_year}년 {self.period_end} {KIND_LABELS[self.kind]}: "
            f"모든 원문 후보 다운로드 실패. 시도: {attempts}"
        )


def _failure(exc: DartError) -> tuple[str, str]:
    if isinstance(exc, DartDownloadError):
        return exc.code, exc.message
    return "request_error", str(exc)


def download_first_available_candidate(
    candidates: list[ReportRef], api_key: str, raw_dir: Path, *, session=None
) -> tuple[ReportRef, Path]:
    """동일 슬롯 후보를 최신순으로 시도하고 유효한 첫 ZIP만 반환한다."""
    if not candidates:
        raise ValueError("다운로드 후보가 없습니다.")
    slot = {(ref.symbol, ref.period_end[:4], ref.kind, ref.period_end) for ref in candidates}
    if len(slot) != 1:
        raise ValueError(f"서로 다른 보고서 슬롯의 후보가 섞였습니다: {sorted(slot)}")

    ordered = sorted(candidates, key=lambda ref: (ref.rcept_dt, ref.rcept_no), reverse=True)
    failures: list[CandidateFailure] = []
    for ref in ordered:
        correction = "정정" if ref.is_amendment else "최초"
        log.info(
            "원문 후보 시도: 종목=%s 기간=%s 유형=%s 접수번호=%s 보고서명=%s 접수일=%s 정정여부=%s",
            ref.symbol, ref.period_end, ref.kind, ref.rcept_no, ref.title, ref.rcept_dt, correction,
        )
        path = raw_dir / ref.zip_name()
        if path.exists():
            try:
                validate_document_zip(path.read_bytes(), f"{ref.rcept_no}.xml")
                log.info("원문 후보 성공(기존 ZIP): 접수번호=%s 경로=%s", ref.rcept_no, path)
                return ref, path
            except DartDownloadError as exc:
                log.warning("기존 ZIP 무효, 재다운로드: 접수번호=%s 사유=%s", ref.rcept_no, exc)
        try:
            download_document(ref.rcept_no, api_key, path, session=session)
            log.info("원문 후보 성공: 접수번호=%s 경로=%s", ref.rcept_no, path)
            return ref, path
        except DartRateLimitError:
            log.error("원문 후보 실패: 접수번호=%s 코드=020 메시지=요청 한도 초과", ref.rcept_no)
            raise
        except DartError as exc:
            code, message = _failure(exc)
            failures.append(CandidateFailure(ref.rcept_no, code, message))
            log.warning("원문 후보 실패: 접수번호=%s 코드=%s 메시지=%s", ref.rcept_no, code, message)
    raise AllCandidatesFailed(ordered[0], failures)


class PoliteSession:
    """DART 호출 간격 유지 + 일시적 오류(연결·타임아웃·5xx) 지수 백오프 재시도."""

    def __init__(self, session=None, *, interval: float = 0.2, attempts: int = 3, base_delay: float = 1.0, sleep=time.sleep):
        self.session = session if session is not None else requests.Session()
        self.throttle = Throttle(interval, sleep=sleep)
        self.attempts = attempts
        self.base_delay = base_delay
        self.sleep = sleep

    def get(self, url, *, params, timeout):
        def call():
            self.throttle.wait()
            response = self.session.get(url, params=params, timeout=timeout)
            status = getattr(response, "status_code", 200)
            if isinstance(status, int) and status >= 500:
                response.raise_for_status()
            return response

        def transient(exc):
            if isinstance(exc, requests.HTTPError):
                return getattr(exc.response, "status_code", 500) >= 500
            return isinstance(exc, (requests.ConnectionError, requests.Timeout))

        return retry_call(
            call,
            attempts=self.attempts,
            base_delay=self.base_delay,
            retry_on=(requests.RequestException,),
            should_retry=transient,
            sleep=self.sleep,
        )


def load_corp_codes(api_key: str | None, cache_path: Path, max_age_days: float, session=None, now: float | None = None) -> dict[str, str]:
    """corpCode.xml을 캐시에서 읽고, 없거나 오래됐으면 한 번 받아 캐시한다."""
    now = time.time() if now is None else now
    if cache_path.exists() and now - cache_path.stat().st_mtime < max_age_days * 86400:
        return parse_corp_codes(cache_path.read_bytes())
    if not api_key:
        raise DartError("corpCode 캐시가 없고 DART_API_KEY도 없습니다.")
    content = fetch_corp_code_xml(api_key, session)
    mapping = parse_corp_codes(content)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_bytes(content)
    return mapping


@dataclass
class CollectResult:
    reports: list[ReportRef]
    corp_codes: dict[str, str]
    failures: list[str]
    failed_items: list[dict] = field(default_factory=list)  # failure_item() 형식, 실패 목록 파일용


def failure_item(symbol: str, stage: str, reason: str, *, period_end: str = "", kind: str = "", rcept_no: str = "", title: str = "") -> dict:
    """실패 1건을 한 행으로. stage: corp_code·list·missing·download·parse·chunk·load·embed·validate·run"""
    return {
        "symbol": symbol,
        "period_end": period_end,
        "kind": kind,
        "stage": stage,
        "rcept_no": rcept_no,
        "title": title,
        "reason": reason,
    }


def collect(
    symbols: list[str],
    periods: list[str],
    api_key: str,
    raw_dir: Path,
    *,
    bgn_de: str,
    end_de: str,
    corp_cache_days: float,
    session=None,
    download: bool = True,
    selector=None,
) -> CollectResult:
    """대상 기업별 보고서 후보를 확정하고 슬롯마다 유효한 첫 원문 ZIP을 받는다.

    selector(symbol, corp_code, items_by_type)를 주면 고정 periods 대신 그 함수로 슬롯을 고른다.
    DartRateLimitError(020)는 잡지 않고 그대로 올려 전체 수집을 중단시킨다.
    """
    corp_codes_all = load_corp_codes(api_key, raw_dir / "corpCode.xml", corp_cache_days, session)
    reports: list[ReportRef] = []
    corp_codes: dict[str, str] = {}
    failures: list[str] = []
    failed_items: list[dict] = []
    for symbol in symbols:
        corp_code = corp_codes_all.get(symbol)
        if not corp_code:
            failures.append(f"{symbol}: corpCode에 고유번호가 없습니다.")
            failed_items.append(failure_item(symbol, "corp_code", "corpCode에 고유번호가 없습니다."))
            continue
        corp_codes[symbol] = corp_code
        try:
            items_by_type = {}
            for detail_type in REPORT_TYPES:
                try:
                    items_by_type[detail_type] = list_reports(
                        corp_code,
                        api_key,
                        bgn_de=bgn_de,
                        end_de=end_de,
                        detail_type=detail_type,
                        last_reprt_at="N",
                        session=session,
                    )
                except DartNoDataError:
                    items_by_type[detail_type] = []
            if selector is not None:
                grouped, missing = selector(symbol, corp_code, items_by_type)
            else:
                grouped, missing = select_disclosure_candidates(symbol, corp_code, items_by_type, periods)
        except DartRateLimitError:
            raise
        except DartError as exc:
            failures.append(f"{symbol}: {_safe_message(exc, api_key)}")
            failed_items.append(failure_item(symbol, "list", _safe_message(exc, api_key)))
            continue
        failures.extend(
            f"{symbol} {period[:4]}년 {period} {KIND_LABELS[kind]}: 대상 보고서 후보가 목록에 없습니다."
            for kind, period in missing
        )
        failed_items.extend(
            failure_item(symbol, "missing", "대상 보고서 후보가 목록에 없습니다.", period_end=period, kind=kind)
            for kind, period in missing
        )
        for _, candidates in sorted(grouped.items(), key=lambda entry: entry[0][1]):
            if download:
                try:
                    ref, _ = download_first_available_candidate(candidates, api_key, raw_dir, session=session)
                except DartRateLimitError:
                    raise
                except AllCandidatesFailed as exc:
                    failures.append(_safe_message(exc, api_key))
                    failed_items.append(failure_item(
                        symbol,
                        "download",
                        _safe_message("; ".join(f"{f.rcept_no} [{f.code}: {f.message}]" for f in exc.failures), api_key),
                        period_end=exc.period_end,
                        kind=exc.kind,
                        rcept_no=",".join(f.rcept_no for f in exc.failures),
                        title=candidates[0].title,
                    ))
                    continue
            else:
                ref = candidates[0]
                for candidate in candidates:
                    log.info(
                        "원문 후보(다운로드 안 함): 종목=%s 기간=%s 유형=%s 접수번호=%s 보고서명=%s 접수일=%s 정정여부=%s",
                        candidate.symbol,
                        candidate.period_end,
                        candidate.kind,
                        candidate.rcept_no,
                        candidate.title,
                        candidate.rcept_dt,
                        "정정" if candidate.is_amendment else "최초",
                    )
            reports.append(ref)
            log.info("선택: %s %s %s %s", symbol, ref.period_end, ref.rcept_no, ref.title)
    return CollectResult(reports=reports, corp_codes=corp_codes, failures=failures, failed_items=failed_items)


def ref_from_zip(zip_path: Path, document_name: str, period_to: str | None) -> ReportRef:
    """`{symbol}_{rcept_no}.zip` 파일과 XML 표지만으로 ReportRef를 만든다 (DART 호출 없음).

    title은 `{문서명} (YYYY.MM)`, rcept_dt는 접수번호 앞 8자리(접수일).
    """
    match = re.fullmatch(r"(\d{6})_(\d{14})\.zip", zip_path.name)
    if not match:
        raise DartError(f"ZIP 파일명은 {{종목코드}}_{{접수번호}}.zip 형식이어야 합니다: {zip_path.name}")
    symbol, rcept_no = match.groups()
    kind = kind_from_title(document_name)
    if kind is None:
        raise DartError(f"정기보고서가 아닙니다: {document_name}")
    if not period_to or not re.fullmatch(r"\d{8}", period_to):
        raise DartError(f"{zip_path.name}: XML에서 PERIODTO를 찾을 수 없습니다.")
    title = f"{document_name} ({period_to[:4]}.{period_to[4:6]})"
    period_end = period_end_from_title(title)
    check_kind_period(kind, period_end, title)
    return ReportRef(symbol=symbol, rcept_no=rcept_no, title=title, kind=kind, period_end=period_end, rcept_dt=_iso(rcept_no[:8]))


def save_reports(path: Path, reports: list[ReportRef]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = sorted((ref.to_dict() for ref in reports), key=lambda row: (row["symbol"], row["period_end"]))
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(rows, handle, ensure_ascii=False, indent=1)
        handle.write("\n")


def load_reports(path: Path) -> list[ReportRef]:
    with path.open(encoding="utf-8") as handle:
        return [ReportRef(**row) for row in json.load(handle)]
