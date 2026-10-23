"""OpenDART 재무 API 수집: 원본 응답 JSON을 그대로 저장한다 (WO-015 ①단계).

- `fnlttSinglAcntAll.json`(단일회사 전체 재무제표): CFS 우선, 상태 013이면 OFS
  → `{financials_raw_dir}/{symbol}_{bsns_year}_{reprt_code}_{fs_div}.json`
- `stockTotqySttus.json`(주식의 총수 현황): 013이면 빈 결과
  → `{shares_raw_dir}/{symbol}_{bsns_year}_{reprt_code}.json`

상태 000·013 응답만 저장하고, 파일이 이미 있으면 다시 호출하지 않는다 (refresh=True일 때만 다시 받음).
상태 020(요청 한도)과 인증키 오류는 수집 전체를 중단한다. 매핑·적재는 이 모듈에서 하지 않는다.
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from app.dart_reports import DartError, DartRateLimitError, _get, _safe_message

from ..common.logging import get_logger
from .financials import FS_DIV_ORDER


log = get_logger("disclosures.financials_dart")

STATEMENTS_ENDPOINT = "fnlttSinglAcntAll.json"
SHARES_ENDPOINT = "stockTotqySttus.json"
REPRT_CODES = {"03": "11013", "06": "11012", "09": "11014", "12": "11011"}
OK, NO_DATA, RATE_LIMIT = "000", "013", "020"
# 키가 틀리거나 막힌 경우: 남은 호출도 모두 같은 오류이므로 전체를 중단한다.
AUTH_ERRORS = {"010", "011", "012", "901"}


class DartAuthError(DartError):
    """인증키 오류(010·011·012·901). 수집을 중단해야 한다."""


@dataclass(frozen=True)
class Target:
    symbol: str
    corp_code: str
    period_end: str  # YYYY-MM-DD

    @property
    def bsns_year(self) -> str:
        return self.period_end[:4]

    @property
    def reprt_code(self) -> str:
        return REPRT_CODES[self.period_end[5:7]]


def statement_path(raw_dir: Path, target: Target, fs_div: str) -> Path:
    return raw_dir / f"{target.symbol}_{target.bsns_year}_{target.reprt_code}_{fs_div}.json"


def shares_path(raw_dir: Path, target: Target) -> Path:
    return raw_dir / f"{target.symbol}_{target.bsns_year}_{target.reprt_code}.json"


def response_status(content: bytes, label: str) -> tuple[str, str]:
    """DART JSON 응답의 (status, message). JSON이 아니면 DartError."""
    try:
        data = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise DartError(f"{label}: JSON 응답이 아닙니다.") from None
    if not isinstance(data, dict) or "status" not in data:
        raise DartError(f"{label}: status가 없는 응답입니다.")
    return str(data["status"]), str(data.get("message", ""))


def _write_atomic(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".part")
    temp.write_bytes(content)
    os.replace(temp, path)


def fetch_json(endpoint: str, params: dict, api_key: str, session=None) -> bytes:
    """DART JSON API 1회 호출. 000·013 응답 본문(bytes)을 그대로 반환한다."""
    response = _get(session, endpoint, params={"crtfc_key": api_key, **params}, timeout=30)
    content = response.content
    status, message = response_status(content, endpoint)
    message = _safe_message(message, api_key)
    if status == RATE_LIMIT:
        raise DartRateLimitError(f"{endpoint} 요청 한도 초과 ({status}): {message}")
    if status in AUTH_ERRORS:
        raise DartAuthError(f"{endpoint} 인증키 오류 ({status}): {message}")
    if status not in (OK, NO_DATA):
        raise DartError(f"{endpoint} 오류 ({status}): {message}")
    return content


@dataclass
class Fetched:
    status: str
    path: Path
    called: bool


def get_or_fetch(path: Path, endpoint: str, params: dict, api_key: str, *, session=None, refresh: bool = False) -> Fetched:
    """저장된 원본이 있으면 그대로 쓰고, 없거나 refresh거나 저장본이 손상(JSON 아님·000/013 아님)이면 호출해 저장한다."""
    if path.exists() and not refresh:
        try:
            status, _ = response_status(path.read_bytes(), path.name)
        except DartError as exc:
            status = None
            log.warning("저장된 원본 손상 → 다시 받음: %s (%s)", path.name, exc)
        if status in (OK, NO_DATA):
            return Fetched(status, path, called=False)
        if status is not None:
            log.warning("저장된 원본 상태가 %s → 다시 받음: %s", status, path.name)
    content = fetch_json(endpoint, params, api_key, session)
    _write_atomic(path, content)
    status, _ = response_status(content, endpoint)
    return Fetched(status, path, called=True)


@dataclass
class CollectReport:
    statements: dict[tuple[str, str], Fetched] = field(default_factory=dict)  # (symbol, period_end) → 사용할 재무제표 원본
    shares: dict[tuple[str, str], Fetched] = field(default_factory=dict)
    calls: int = 0
    failures: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        def files(entries):
            return {f"{s} {p}": {"status": f.status, "file": f.path.name, "called": f.called} for (s, p), f in sorted(entries.items())}

        return {"calls": self.calls, "statements": files(self.statements), "shares": files(self.shares), "failures": self.failures, "notes": self.notes}


def collect_statements(target: Target, api_key: str, raw_dir: Path, report: CollectReport, *, session=None, refresh: bool = False) -> None:
    """CFS부터 시도해 상태 000인 첫 재무제표를 고른다. 모두 013이면 실패로 기록."""
    label = f"{target.symbol} {target.period_end}"
    for fs_div in FS_DIV_ORDER:
        params = {"corp_code": target.corp_code, "bsns_year": target.bsns_year, "reprt_code": target.reprt_code, "fs_div": fs_div}
        fetched = get_or_fetch(statement_path(raw_dir, target, fs_div), STATEMENTS_ENDPOINT, params, api_key, session=session, refresh=refresh)
        report.calls += fetched.called
        if fetched.status == OK:
            report.statements[(target.symbol, target.period_end)] = fetched
            if fs_div != FS_DIV_ORDER[0]:
                report.notes.append(f"{label}: 연결(CFS) 없음(013) → 별도(OFS) 사용")
            return
        log.info("%s %s 재무제표 없음(013)", label, fs_div)
    report.failures.append(f"{label}: 재무제표 CFS·OFS 모두 데이터 없음(013)")


def collect_shares(target: Target, api_key: str, raw_dir: Path, report: CollectReport, *, session=None, refresh: bool = False) -> None:
    params = {"corp_code": target.corp_code, "bsns_year": target.bsns_year, "reprt_code": target.reprt_code}
    fetched = get_or_fetch(shares_path(raw_dir, target), SHARES_ENDPOINT, params, api_key, session=session, refresh=refresh)
    report.calls += fetched.called
    report.shares[(target.symbol, target.period_end)] = fetched
    if fetched.status == NO_DATA:
        report.notes.append(f"{target.symbol} {target.period_end}: 주식 총수 데이터 없음(013) → BPS NULL 예정")


def collect(
    targets: list[Target],
    api_key: str,
    statements_dir: Path,
    shares_dir: Path,
    *,
    session=None,
    refresh: bool = False,
) -> CollectReport:
    """대상마다 재무제표·주식 총수 원본을 확보한다. 020·인증키 오류는 그대로 올려 전체를 중단한다."""
    report = CollectReport()
    for target in targets:
        for step in (collect_statements, collect_shares):
            try:
                step(target, api_key, statements_dir if step is collect_statements else shares_dir, report, session=session, refresh=refresh)
            except (DartRateLimitError, DartAuthError):
                raise
            except DartError as exc:
                report.failures.append(f"{target.symbol} {target.period_end}: {_safe_message(exc, api_key)}")
    return report


def cached_statement(statements_dir: Path, target: Target) -> tuple[str, Path] | None:
    """저장된 원본에서 사용할 재무제표를 고른다 (collect와 같은 규칙: CFS가 000이면 CFS, 013이면 OFS). 호출 없음."""
    for fs_div in FS_DIV_ORDER:
        path = statement_path(statements_dir, target, fs_div)
        if not path.exists():
            return None
        try:
            status, _ = response_status(path.read_bytes(), path.name)
        except DartError:
            return None  # 손상된 원본 → 대상 실패로 보고 (collect가 다시 받는다)
        if status == OK:
            return fs_div, path
        if status != NO_DATA:
            return None
    return None


def plan_calls(targets: list[Target], statements_dir: Path, shares_dir: Path, *, refresh: bool = False) -> dict:
    """호출 없이 필요한 최소 호출 수를 센다. 저장된 CFS가 013이면 OFS 1회를 최소 호출에 넣는다.

    아직 CFS를 받지 않은 대상은 CFS가 013일 때 OFS가 1회 더 필요할 수 있다 (`possible_ofs_retries`).
    """

    def cached_status(path: Path) -> str | None:
        if refresh or not path.exists():
            return None
        try:
            status, _ = response_status(path.read_bytes(), path.name)
        except DartError:
            return None
        return status if status in (OK, NO_DATA) else None

    statements = shares = possible_ofs = 0
    for target in targets:
        cfs = cached_status(statement_path(statements_dir, target, "CFS"))
        if cfs is None:
            statements += 1
            possible_ofs += 1
        elif cfs == NO_DATA and cached_status(statement_path(statements_dir, target, "OFS")) is None:
            statements += 1
        if cached_status(shares_path(shares_dir, target)) is None:
            shares += 1
    return {
        "targets": len(targets),
        STATEMENTS_ENDPOINT: statements,
        SHARES_ENDPOINT: shares,
        "min_calls": statements + shares,
        "possible_ofs_retries": possible_ofs,
    }


def account_inventory(statements_dir: Path, symbols: list[str]) -> dict[str, list[dict]]:
    """저장된 재무제표 원본에서 기업별 (sj_div, account_id, account_nm) 목록과 등장 파일 수를 뽑는다.

    여러 원본에 같은 회사가 있으면(CFS·OFS) 각 파일을 모두 센다. ①단계 계정 확인 보고용.
    """
    result: dict[str, list[dict]] = {}
    for symbol in symbols:
        counts: dict[tuple[str, str, str], set[str]] = defaultdict(set)
        for path in sorted(statements_dir.glob(f"{symbol}_*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            if str(data.get("status")) != OK:
                continue
            for row in data.get("list", []):
                key = (str(row.get("sj_div", "")), str(row.get("account_id", "")), str(row.get("account_nm", "")).strip())
                counts[key].add(path.stem)
        result[symbol] = [
            {"sj_div": sj, "account_id": aid, "account_nm": nm, "files": len(files)}
            for (sj, aid, nm), files in sorted(counts.items())
        ]
    return result
