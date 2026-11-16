"""수정주가 이력 이상징후 진단 (읽기 전용).

prices_daily(KIS 원시)와 adjusted_prices_daily(KIS 수정)를 종목별 거래일 순으로 비교해
조정 기준이 섞였을 수 있는 지점을 찾는다. DB를 바꾸지 않고, 재수집하지 않는다.
탐지는 원인 확정이 아니라 검증 대상 목록이다. 공시 연결도 참고 근거일 뿐이다.

탐지 유형
- ADJUSTMENT_RATIO_JUMP: 수정/원시 비율이 직전 거래일 대비 급변 (정상 기업행동도 포함됨)
- ADJUSTED_ONLY_DISCONTINUITY: 원시는 거의 그대로인데 수정만 크게 움직임
- SUSPICIOUS_ZERO_VOLUME_CHANGE: 거래량 0인 날 원시 또는 수정 종가가 크게 움직임
- POTENTIAL_HISTORY_RESYNC: 과거 이력과 최근 일봉의 조정 기준이 다를 수 있는 재동기화 후보
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Callable, Iterable

RATIO_JUMP = "ADJUSTMENT_RATIO_JUMP"
ADJUSTED_ONLY = "ADJUSTED_ONLY_DISCONTINUITY"
ZERO_VOLUME = "SUSPICIOUS_ZERO_VOLUME_CHANGE"
HISTORY_RESYNC = "POTENTIAL_HISTORY_RESYNC"
TYPES = (RATIO_JUMP, ADJUSTED_ONLY, ZERO_VOLUME, HISTORY_RESYNC)

SEVERITY_ORDER = {"info": 0, "review": 1, "high": 2}

# 기업행동과 관련된 공시 종류 (configs/disclosure_events.yaml의 event_type)
CORPORATE_ACTION_EVENT_TYPES = (
    "share_count_change",
    "capital_reduction",
    "bonus_issue",
    "rights_offering",
    "restructuring",
    "trading_halt",
)

# pairs의 항목 경로(공백 제거)에서 날짜로 읽을 칸. 결정일과 조정 관련일을 구분해 둔다.
KEY_DATE_LABELS = (
    ("decision_date", re.compile(r"이사회결의일|결정일")),
    ("effective_date", re.compile(r"효력발생일")),
    ("record_date", re.compile(r"기준일")),
    ("halt_start", re.compile(r"매매거래정지(예정)?기간>시작일|매매거래정지일시$")),
    ("halt_end", re.compile(r"매매거래정지(예정)?기간>종료일|매매거래정지해제일시$")),
    ("listing_date", re.compile(r"상장예정일")),
    ("merger_date", re.compile(r"합병기일|분할기일|교환일|이전일")),
)
# pipelines.disclosures.events_fields.parse_date와 같은 규칙. 그 모듈은 lxml을 불러와서
# 시장 데이터 환경에 없을 수 있으므로 정규식만 같게 둔다 (DART 코드는 고치지 않는다).
DISCLOSURE_DATE_RE = re.compile(r"(\d{4})\s*[-./년]\s*(\d{1,2})\s*[-./월]\s*(\d{1,2})")
EMPTY_VALUES = {"", "-", "--", "—", "해당없음", "해당사항없음", "N/A"}  # events_fields.EMPTY_VALUES와 같다


def parse_disclosure_date(value: str) -> str | None:
    """'2027-01-12' · '2027.01.12' · '2027년 01월 12일' → '2027-01-12'. 빈 값은 None, 날짜가 아니면 ValueError."""
    text = (value or "").strip()
    if re.sub(r"\s+", "", text) in EMPTY_VALUES:
        return None
    match = DISCLOSURE_DATE_RE.search(text)
    if not match:
        raise ValueError(f"날짜가 아닙니다: {value!r}")
    year, month, day = (int(part) for part in match.groups())
    return date(year, month, day).isoformat()


SHARES_BEFORE = re.compile(r"발행주식총수>보통주식\(주\)>병합전$|발행주식총수>보통주식\(주\)>분할전$")
SHARES_AFTER = re.compile(r"발행주식총수>보통주식\(주\)>병합후$|발행주식총수>보통주식\(주\)>분할후$")


@dataclass(frozen=True)
class Thresholds:
    ratio_jump: float = 0.02            # A: 조정비율 변화율 절대값 초과
    adjusted_only_raw_max: float = 0.05  # B: 원시 수익률 절대값 이하
    adjusted_only_adj_min: float = 0.30  # B: 수정 수익률 절대값 이상
    zero_volume_return: float = 0.30     # C: 거래량 0일 때 수익률 절대값 초과
    price_limit: float = 0.305           # D: 원시가 이 이상 움직였는데 수정도 같이 움직이면 미조정 의심
    gap_sessions: int = 5                # 두 행 사이에 빠진 거래일이 이 이상이면 누락 구간으로 표시
    episode_rows: int = 5                # 같은 종목에서 이 행 수 안에 이어진 탐지는 한 묶음
    disclosure_lookback_days: int = 180  # 발생일 이전 공시 접수일 범위
    disclosure_lookahead_days: int = 7   # 발생일 이후 공시 접수일 범위
    key_date_window_days: int = 10       # 공시 안 날짜(효력발생일 등)와 발생일 거리


@dataclass
class PriceRow:
    symbol: str
    trade_date: date
    raw_close: Decimal | None
    adj_close: Decimal | None
    volume: int | None
    collected_at: datetime | None = None


@dataclass
class Observation:
    symbol: str
    trade_date: date
    prev_date: date
    raw_close: Decimal
    prev_raw_close: Decimal
    adj_close: Decimal
    prev_adj_close: Decimal
    raw_return: float
    adj_return: float
    ratio: float
    prev_ratio: float
    ratio_change: float
    return_gap: float
    volume: int | None
    zero_volume: bool | None
    missing_sessions: int
    collected_session: str | None
    prev_collected_session: str | None
    row_index: int


@dataclass
class Finding:
    symbol: str
    name: str | None
    trade_date: str
    prev_date: str
    types: list[str]
    severity: str
    assessment: str
    resync_reasons: list[str]
    raw_close: float
    prev_raw_close: float
    raw_return: float
    adj_close: float
    prev_adj_close: float
    adj_return: float
    prev_ratio: float
    ratio: float
    ratio_change: float
    volume: int | None
    zero_volume: bool | None
    missing_sessions: int
    collected_session: str | None
    prev_collected_session: str | None
    cause_status: str = "unverified"
    dart_coverage: str = "unknown"
    disclosures: list[dict] = field(default_factory=list)
    recommended_action: str = ""
    symbol_status: str | None = None  # configs/kis_symbol_status.json의 상장폐지·전환 상태 (정리매매 오탐 구분용)
    episode_id: str | None = None
    row_index: int = 0


# ---------------------------------------------------------------- 계산


def _valid_price(value) -> bool:
    return value is not None and Decimal(value).is_finite() and Decimal(value) > 0


def collection_session(value: datetime | None) -> str | None:
    """수정 일봉을 받은 날(KST). 같은 날 받은 행은 같은 조정 기준으로 본다."""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone(timedelta(hours=9))).date().isoformat()


def build_observations(
    rows: Iterable[PriceRow],
    session_counter: Callable[[date, date], int] | None = None,
) -> tuple[list[Observation], dict]:
    """한 종목의 행(거래일 오름차순)을 전 거래일과 비교한 관측치로 바꾼다.

    원시·수정 종가가 모두 양수인 날만 쓴다. 쓰지 못한 날은 issues에 남긴다.
    """
    issues = {"raw_missing": [], "adjusted_missing": [], "invalid_price": [], "gaps": []}
    observations: list[Observation] = []
    prev: PriceRow | None = None
    index = 0
    for row in rows:
        if row.raw_close is None and row.adj_close is None:
            continue
        if row.raw_close is None:
            issues["raw_missing"].append(row.trade_date.isoformat())
            continue
        if row.adj_close is None:
            issues["adjusted_missing"].append(row.trade_date.isoformat())
            continue
        if not (_valid_price(row.raw_close) and _valid_price(row.adj_close)):
            issues["invalid_price"].append(row.trade_date.isoformat())
            continue
        index += 1
        if prev is not None:
            raw, adj = Decimal(row.raw_close), Decimal(row.adj_close)
            praw, padj = Decimal(prev.raw_close), Decimal(prev.adj_close)
            ratio, pratio = adj / raw, padj / praw
            missing = session_counter(prev.trade_date, row.trade_date) if session_counter else 0
            if missing:
                issues["gaps"].append({
                    "from": prev.trade_date.isoformat(),
                    "to": row.trade_date.isoformat(),
                    "missing_sessions": missing,
                })
            observations.append(Observation(
                symbol=row.symbol,
                trade_date=row.trade_date,
                prev_date=prev.trade_date,
                raw_close=raw,
                prev_raw_close=praw,
                adj_close=adj,
                prev_adj_close=padj,
                raw_return=float(raw / praw - 1),
                adj_return=float(adj / padj - 1),
                ratio=float(ratio),
                prev_ratio=float(pratio),
                ratio_change=float(ratio / pratio - 1),
                return_gap=float(adj / padj - raw / praw),
                volume=row.volume,
                zero_volume=None if row.volume is None else row.volume == 0,
                missing_sessions=missing,
                collected_session=collection_session(row.collected_at),
                prev_collected_session=collection_session(prev.collected_at),
                row_index=index,
            ))
        prev = row
    return observations, issues


def classify(obs: Observation, t: Thresholds) -> tuple[list[str], list[str]]:
    """관측치 하나의 탐지 유형과 재동기화 후보 사유."""
    types: list[str] = []
    rr, ar = abs(obs.raw_return), abs(obs.adj_return)
    ratio_jump = abs(obs.ratio_change) > t.ratio_jump
    if ratio_jump:
        types.append(RATIO_JUMP)
    adjusted_only = rr <= t.adjusted_only_raw_max and ar >= t.adjusted_only_adj_min
    if adjusted_only:
        types.append(ADJUSTED_ONLY)
    if obs.zero_volume and (rr > t.zero_volume_return or ar > t.zero_volume_return):
        types.append(ZERO_VOLUME)

    reasons: list[str] = []
    crosses_session = (
        obs.collected_session is not None
        and obs.prev_collected_session is not None
        and obs.collected_session != obs.prev_collected_session
    )
    if (ratio_jump or adjusted_only) and crosses_session:
        # 서로 다른 날 받은 행 사이에서 조정 기준이 바뀌었다
        reasons.append("ratio_shift_across_collection_sessions")
    if rr > t.price_limit and ar > t.price_limit and obs.raw_return * obs.adj_return > 0:
        # 가격제한폭을 넘는 원시 단절을 수정주가가 그대로 따라갔다 (조정 미반영 의심)
        reasons.append("unadjusted_raw_break")
    if reasons:
        types.append(HISTORY_RESYNC)
    return types, reasons


def assess(types: list[str], reasons: list[str], obs: Observation, t: Thresholds) -> tuple[str, str, str]:
    """(severity, assessment, recommended_action). 어떤 경우에도 자동 수정하지 않는다."""
    if HISTORY_RESYNC in types:
        if "ratio_shift_across_collection_sessions" in reasons:
            return ("high", "adjustment_basis_mixed_across_sessions",
                    "KIS 수정주가 해당 종목 전체 이력을 재조회해 기존 이력과 비율 비교. 재수집·DB 갱신은 승인 후")
        return ("high", "raw_break_not_adjusted",
                "기업행동·거래정지 사유 확인 후 매매 재개 시점에 KIS 수정 이력 재조회 대조. 자동 수정 금지")
    if ADJUSTED_ONLY in types:
        return ("high", "adjusted_only_discontinuity",
                "기업행동 공시·KRX 안내 확인 후 KIS 수정 이력 재조회 대조. 자동 수정 금지")
    if ZERO_VOLUME in types:
        return ("review", "zero_volume_price_reset",
                "거래정지·기준가격 변경 사유 확인. 자동 수정 금지")
    if abs(obs.adj_return) <= t.price_limit:
        return ("info", "consistent_adjustment",
                "수정주가는 연속적. 공시와 대조해 정상 기업행동 조정인지 확인 (우선순위 낮음)")
    return ("review", "ratio_jump_with_adjusted_move",
            "공시와 대조해 조정 비율 확인")


def detect(
    observations: Iterable[Observation],
    thresholds: Thresholds,
    names: dict[str, str] | None = None,
) -> list[Finding]:
    """관측치를 탐지 결과로. 같은 종목·같은 날의 여러 유형은 한 건으로 합친다."""
    names = names or {}
    findings: list[Finding] = []
    for obs in observations:
        types, reasons = classify(obs, thresholds)
        if not types:
            continue
        severity, assessment, action = assess(types, reasons, obs, thresholds)
        findings.append(Finding(
            symbol=obs.symbol,
            name=names.get(obs.symbol),
            trade_date=obs.trade_date.isoformat(),
            prev_date=obs.prev_date.isoformat(),
            types=types,
            severity=severity,
            assessment=assessment,
            resync_reasons=reasons,
            raw_close=float(obs.raw_close),
            prev_raw_close=float(obs.prev_raw_close),
            raw_return=round(obs.raw_return, 6),
            adj_close=float(obs.adj_close),
            prev_adj_close=float(obs.prev_adj_close),
            adj_return=round(obs.adj_return, 6),
            prev_ratio=round(obs.prev_ratio, 6),
            ratio=round(obs.ratio, 6),
            ratio_change=round(obs.ratio_change, 6),
            volume=obs.volume,
            zero_volume=obs.zero_volume,
            missing_sessions=obs.missing_sessions,
            collected_session=obs.collected_session,
            prev_collected_session=obs.prev_collected_session,
            recommended_action=action,
            row_index=obs.row_index,
        ))
    return findings


def annotate_symbol_status(findings: list[Finding], statuses: dict) -> None:
    """상장폐지·전환 레지스트리에 있는 종목 표시. 정리매매는 가격제한폭이 없어 원시 단절이 정상일 수 있다."""
    for item in findings:
        status = statuses.get(item.symbol)
        if status is not None:
            item.symbol_status = status.status
            item.recommended_action += " / 레지스트리상 종료 종목: 정리매매 등 정상 사례 가능, 운영 대상 아님"


def group_episodes(findings: list[Finding], episode_rows: int) -> list[dict]:
    """같은 종목에서 episode_rows 행 안에 이어진 탐지를 한 묶음으로 만든다."""
    episodes: list[dict] = []
    current: dict | None = None
    last_index = None
    for item in sorted(findings, key=lambda f: (f.symbol, f.row_index)):
        if (
            current is None
            or current["symbol"] != item.symbol
            or item.row_index - last_index > episode_rows
        ):
            current = {
                "episode_id": f"{item.symbol}:{item.trade_date}",
                "symbol": item.symbol,
                "name": item.name,
                "start": item.trade_date,
                "end": item.trade_date,
                "finding_count": 0,
                "types": [],
                "severity": "info",
            }
            episodes.append(current)
        item.episode_id = current["episode_id"]
        current["end"] = item.trade_date
        current["finding_count"] += 1
        current["types"] = sorted(set(current["types"]) | set(item.types))
        if SEVERITY_ORDER[item.severity] > SEVERITY_ORDER[current["severity"]]:
            current["severity"] = item.severity
        last_index = item.row_index
    return episodes


# ---------------------------------------------------------------- 공시 연결


def _compact(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def extract_key_dates(pairs: list[dict], parse_date: Callable[[str], str | None]) -> dict[str, list[str]]:
    """공시 원문 표에서 결정일과 조정 관련 날짜를 따로 읽는다. 원문에 없는 날짜는 만들지 않는다."""
    found: dict[str, list[str]] = {}
    for pair in pairs or []:
        path = _compact(str(pair.get("path") or ""))
        value = str(pair.get("value") or "")
        for label, pattern in KEY_DATE_LABELS:
            if not pattern.search(path):
                continue
            try:
                parsed = parse_date(value)
            except ValueError:
                parsed = None
            if parsed and parsed not in found.setdefault(label, []):
                found[label].append(parsed)
            break
    return found


def share_count_ratio(pairs: list[dict]) -> float | None:
    """병합·분할 공시의 전후 보통주 수로 계산한 비율(전/후). 칸이 없으면 None."""
    before = after = None
    for pair in pairs or []:
        path = _compact(str(pair.get("path") or ""))
        digits = re.sub(r"[^\d]", "", str(pair.get("value") or ""))
        if not digits:
            continue
        if SHARES_BEFORE.search(path):
            before = int(digits)
        elif SHARES_AFTER.search(path):
            after = int(digits)
    if before and after:
        return round(before / after, 6)
    return None


def link_disclosures(
    findings: list[Finding],
    events: list[dict],
    thresholds: Thresholds,
    *,
    coverage_start: date | None,
    common_symbol: Callable[[str], str],
    parse_date: Callable[[str], str | None],
) -> None:
    """탐지 결과에 관련 공시를 참고 근거로 붙인다. 원인 확정은 하지 않는다.

    events: disclosures + disclosure_events 행 (is_latest = 다른 정정본이 가리키지 않음).
    정정본에 밀린 원본은 붙이지 않는다. 자회사 공시는 표시해서 구분한다.
    """
    by_symbol: dict[str, list[dict]] = {}
    for event in events:
        if not event.get("is_latest", True):
            continue
        prepared = dict(event)
        prepared["key_dates"] = extract_key_dates(event.get("pairs") or [], parse_date)
        prepared["share_ratio"] = share_count_ratio(event.get("pairs") or [])
        by_symbol.setdefault(event["symbol"], []).append(prepared)

    window = timedelta(days=thresholds.key_date_window_days)
    for item in findings:
        day = date.fromisoformat(item.trade_date)
        if coverage_start is None:
            item.dart_coverage = "unknown"
        elif day < coverage_start - timedelta(days=thresholds.disclosure_lookahead_days):
            item.dart_coverage = "before_coverage"
        else:
            item.dart_coverage = "covered"
        linked = []
        for event in by_symbol.get(common_symbol(item.symbol), []):
            rcept = event["rcept_dt"]
            if isinstance(rcept, str):
                rcept = date.fromisoformat(rcept)
            relations = []
            if day - timedelta(days=thresholds.disclosure_lookback_days) <= rcept <= day + timedelta(
                days=thresholds.disclosure_lookahead_days
            ):
                relations.append("filed_within_window")
            near = sorted({
                label
                for label, values in event["key_dates"].items()
                if label != "decision_date"
                for value in values
                if abs(date.fromisoformat(value) - day) <= window
            })
            if near:
                relations.append("key_date_near:" + ",".join(near))
            if not relations:
                continue
            linked.append({
                "rcept_no": event["rcept_no"],
                "symbol": event["symbol"],
                "title": event["title"],
                "rcept_dt": rcept.isoformat(),
                "event_type": event["event_type"],
                "is_subsidiary": bool(event.get("is_subsidiary")),
                "is_correction": bool(event.get("is_correction")),
                "parse_status": event.get("parse_status"),
                "key_dates": event["key_dates"],
                "share_ratio_before_after": event["share_ratio"],
                "relation": relations,
            })
        # 상장사 본인 공시를 앞에, 자회사 공시는 뒤에
        linked.sort(key=lambda e: (e["is_subsidiary"], e["rcept_dt"]), reverse=False)
        item.disclosures = linked
        own = [e for e in linked if not e["is_subsidiary"]]
        if own:
            item.cause_status = "unverified_disclosure_reference"
        elif linked:
            item.cause_status = "unverified_subsidiary_only"
        else:
            item.cause_status = "unverified_no_disclosure"


# ---------------------------------------------------------------- 출력


def summarize(findings: list[Finding], episodes: list[dict]) -> dict:
    by_type = {name: sum(name in f.types for f in findings) for name in TYPES}
    by_severity: dict[str, int] = {}
    for f in findings:
        by_severity[f.severity] = by_severity.get(f.severity, 0) + 1
    by_assessment: dict[str, int] = {}
    for f in findings:
        by_assessment[f.assessment] = by_assessment.get(f.assessment, 0) + 1
    return {
        "findings": len(findings),
        "episodes": len(episodes),
        "symbols": len({f.symbol for f in findings}),
        "by_type": by_type,
        "by_severity": by_severity,
        "by_assessment": by_assessment,
        "with_own_disclosure": sum(f.cause_status == "unverified_disclosure_reference" for f in findings),
        "terminal_symbol_findings": sum(f.symbol_status is not None for f in findings),
    }


def new_output_dir(root: Path, now: datetime | None = None) -> Path:
    """실행마다 새 폴더. 이미 있으면 덮어쓰지 않고 실패한다."""
    stamp = (now or datetime.now(timezone.utc)).astimezone(timezone(timedelta(hours=9))).strftime("%Y%m%dT%H%M%S")
    path = root / stamp
    path.mkdir(parents=True, exist_ok=False)
    return path


def _pct(value: float) -> str:
    return f"{value * 100:+.2f}%"


def render_markdown(report: dict, *, focus: Iterable[str] = (), top: int = 40) -> str:
    s = report["summary"]
    meta = report["meta"]
    lines = [
        "# 수정주가 이력 이상징후 진단",
        "",
        f"- 생성: {meta['generated_at']} · DB 읽기 전용 확인: {meta['read_only_verified']}",
        f"- 범위: 종목 {meta['symbols_analyzed']}개 · 행 {meta['rows_loaded']} · 기간 {meta['start'] or '전체'} ~ {meta['end'] or '전체'}",
        f"- 공시 데이터 시작일: {meta['dart_coverage_start']} (이전 구간은 공시 근거 없음)",
        "- 모든 탐지는 원인 미확인 상태의 검증 대상이다. 자동 수정·재수집은 하지 않는다.",
        "",
        "## 유형별 건수",
        "",
        "| 유형 | 건수 |",
        "|---|---:|",
    ]
    lines += [f"| {name} | {count} |" for name, count in s["by_type"].items()]
    lines += [
        "",
        f"- 탐지 {s['findings']}건 · 묶음 {s['episodes']}개 · 종목 {s['symbols']}개",
        f"- 심각도: {s['by_severity']}",
        f"- 판정: {s['by_assessment']}",
        f"- 상장사 본인 공시가 연결된 탐지: {s['with_own_disclosure']}건",
        f"- 상장폐지·전환 레지스트리 종목의 탐지: {s.get('terminal_symbol_findings', 0)}건 (정리매매 등 정상 사례 가능)",
        "",
    ]
    findings = report["findings"]

    def row(f: dict) -> str:
        disc = "; ".join(
            f"{d['rcept_no']} {d['title']}{' (자회사)' if d['is_subsidiary'] else ''}" for d in f["disclosures"][:2]
        ) or "-"
        return (
            f"| {f['symbol']} {f['name'] or ''} | {f['trade_date']} | {', '.join(f['types'])} | "
            f"{f['prev_raw_close']:,.0f}→{f['raw_close']:,.0f} ({_pct(f['raw_return'])}) | "
            f"{f['prev_adj_close']:,.0f}→{f['adj_close']:,.0f} ({_pct(f['adj_return'])}) | "
            f"{f['prev_ratio']:.4f}→{f['ratio']:.4f} | {f['volume']} | {disc} | {f['cause_status']}"
            f"{' · 종료종목(' + f['symbol_status'] + ')' if f.get('symbol_status') else ''} |"
        )

    header = [
        "| 종목 | 발생일 | 유형 | 원시 종가 | 수정 종가 | 조정비율 | 거래량 | 관련 공시 | 원인 |",
        "|---|---|---|---|---|---|---:|---|---|",
    ]
    focus = [s for s in focus]
    if focus:
        lines += ["## 지정 종목", ""] + header
        lines += [row(f) for f in findings if f["symbol"] in focus] or ["| (탐지 없음) |||||||||"]
        lines.append("")
    high = [f for f in findings if f["severity"] == "high"]
    lines += [f"## 우선 검증 대상 (high {len(high)}건 중 최근 {min(top, len(high))}건)", ""] + header
    lines += [row(f) for f in sorted(high, key=lambda f: f["trade_date"], reverse=True)[:top]]
    lines += [
        "",
        "## 해석 주의",
        "",
        "- ADJUSTMENT_RATIO_JUMP 중 consistent_adjustment는 수정주가가 연속적인 정상 조정 패턴일 수 있다.",
        "- SUSPICIOUS_ZERO_VOLUME_CHANGE는 거래정지 중 기준가격 변경 같은 정상 사례를 포함한다.",
        "- POTENTIAL_HISTORY_RESYNC는 재동기화 후보일 뿐, KIS 재조회로 확인하기 전까지 오류가 아니다.",
        "- 공시가 없다고 정상으로 보지 않는다. 공시가 있어도 원인으로 확정하지 않는다.",
        "",
    ]
    return "\n".join(lines)


def write_report(out_dir: Path, report: dict, *, focus: Iterable[str] = ()) -> tuple[Path, Path]:
    json_path = out_dir / "findings.json"
    md_path = out_dir / "summary.md"
    for path in (json_path, md_path):
        if path.exists():
            raise FileExistsError(f"진단 결과 파일이 이미 있습니다: {path}")
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(report, focus=focus), encoding="utf-8")
    return json_path, md_path


def finding_dicts(findings: list[Finding]) -> list[dict]:
    return [asdict(f) for f in findings]
