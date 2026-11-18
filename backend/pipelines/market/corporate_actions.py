"""DART 공시로 수정주가 조정 가능성이 있는 기업행동을 미리 찾는다 (읽기 전용).

- disclosures·disclosure_events를 읽기만 한다. DART 수집 코드와 테이블은 바꾸지 않는다.
- 원문 표(pairs)와 이미 뽑힌 fields에 실제로 있는 값만 쓴다. 없는 값은 None으로 두고 추정하지 않는다.
- 공시일(rcept_dt)·결정일·기준일·효력발생일·매매거래정지·신주상장예정일은 서로 다른 칸으로 둔다.
  권리락일은 원문에 칸이 있을 때만 읽고, 기준일에서 계산하지 않는다(없으면 "unconfirmed").
- 정정공시는 corrects만 믿지 않고 종목·base_title·원 제출일·결정일로 같은 기업행동을 묶는다.
  최신 유효본을 고를 수 없으면 날짜·비율을 확정하지 않고 검토 대상으로 남긴다.
- 자회사 공시(is_subsidiary)는 상장사 본인 기업행동과 따로 둔다.
- 우선주는 보통주 기업행동의 파생 후보로만 올린다. 같은 조정비율을 가정하지 않는다.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from typing import Callable, Iterable

from pipelines.market.adjusted_history_diagnostics import parse_disclosure_date

ACTION_EVENT_TYPES = (
    "share_count_change",
    "capital_reduction",
    "bonus_issue",
    "rights_offering",
    "restructuring",
)
AUXILIARY_EVENT_TYPES = ("trading_halt",)

# 관리 상태 (가격·공시 탐지 단계). 재조회로 확정하는 상태는 adjusted_recheck에 있다.
NORMAL_ADJUSTMENT = "NORMAL_ADJUSTMENT"
REVIEW_REQUIRED = "REVIEW_REQUIRED"
HISTORY_RESYNC_CANDIDATE = "HISTORY_RESYNC_CANDIDATE"
SOURCE_DISCONTINUITY = "SOURCE_DISCONTINUITY"
NO_ACTION = "NO_ACTION"
TERMINAL_EXCLUDED = "TERMINAL_EXCLUDED"

# pairs 경로(공백 제거)별 날짜 칸. 위에서부터 처음 맞는 칸 하나에만 넣는다.
DATE_FIELDS = (
    ("ex_rights_date", re.compile(r"권리락")),
    ("decision_date", re.compile(r"이사회결의일|결정일")),
    ("shareholder_meeting_date", re.compile(r"주주총회")),
    ("effective_date", re.compile(r"효력발생일")),
    ("record_date", re.compile(r"(감자|신주배정|주주확정|배정)기준일|^(\d+\.)?기준일$")),
    ("halt_start", re.compile(r"매매거래정지(예정)?기간>시작일$|매매거래정지일시$")),
    ("halt_end", re.compile(r"매매거래정지(예정)?기간>종료일$|매매거래정지해제일시$")),
    ("listing_date", re.compile(r"(신주권?|신주의)?상장예정일")),
    ("merger_date", re.compile(r"합병기일|분할기일|교환일|이전일")),
    ("payment_date", re.compile(r"납입일")),
)
# 주가 조정과 직접 관련될 수 있는 날짜 (결정일·주주총회·납입일은 제외)
ADJUSTMENT_DATE_FIELDS = ("ex_rights_date", "effective_date", "record_date", "halt_start", "halt_end",
                          "listing_date", "merger_date")
# 재조회를 권할 기준 날짜 (지나면 KIS 수정주가가 바뀌었을 수 있는 날). 주주총회·결정일·주주확정기준일만으로는 권하지 않는다.
TRIGGER_FIELDS = {
    "share_count_change": ("halt_start", "effective_date", "listing_date"),
    "capital_reduction": ("halt_start", "record_date", "listing_date"),
    "bonus_issue": ("ex_rights_date", "record_date", "listing_date"),
    "rights_offering": ("ex_rights_date", "record_date", "listing_date"),
    "restructuring": ("halt_start", "merger_date", "listing_date"),
    "trading_halt": ("halt_start", "halt_end"),
}
THIRD_PARTY_ALLOTMENT = re.compile(r"제3자배정")

SHARES_BEFORE = re.compile(r"발행주식총수>보통주식\(주\)>(병합|분할)전$")
SHARES_AFTER = re.compile(r"발행주식총수>보통주식\(주\)>(병합|분할)후$")
REDUCTION_PCT = re.compile(r"감자비율>보통주식?\(%\)$")
BONUS_PER_SHARE = re.compile(r"1주당신주배정주식수>보통주식?\(주\)$")
MERGER_RATIO = re.compile(r"^(\d+\.)?(합병|분할|교환|이전|분할합병)비율$")
HALT_REASON = re.compile(r"매매거래정지사유$")
# 매매거래정지 사유 중 주가 조정과 관련될 수 있는 것 (보조 신호)
ACTION_HALT_REASON = re.compile(r"병합|분할|감자|무상증자|합병|교환|이전|액면")
EMPTY = {"", "-", "--", "—", "해당없음", "해당사항없음", "N/A"}


def _compact(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def _number(value: str) -> float | None:
    text = _compact(value).replace(",", "")
    if text in EMPTY:
        return None
    try:
        return float(text)
    except ValueError:
        return None


@dataclass
class ActionEvent:
    rcept_no: str
    symbol: str
    title: str
    base_title: str
    event_type: str
    rcept_dt: str
    is_correction: bool
    is_subsidiary: bool
    corrects: str | None
    correction_original_date: str | None
    parse_status: str
    dates: dict[str, list[str]]
    ratios: dict[str, object]
    ex_rights_status: str
    value_issues: list[str] = field(default_factory=list)


def extract_event(row: dict) -> ActionEvent:
    """disclosures + disclosure_events 한 행 → 기업행동 이벤트. 원문에 없는 값은 비워 둔다."""
    pairs = row.get("pairs") or []
    fields = row.get("fields") or {}
    dates: dict[str, list[str]] = {}
    issues: list[str] = []
    shares_before = shares_after = None
    ratios: dict[str, object] = {}
    for pair in pairs:
        path = _compact(str(pair.get("path") or ""))
        value = str(pair.get("value") or "")
        for name, pattern in DATE_FIELDS:
            if not pattern.search(path):
                continue
            try:
                parsed = parse_disclosure_date(value)
            except ValueError:
                parsed = None
                if _compact(value) not in EMPTY:
                    issues.append(f"{name}:not_a_date:{value[:30]}")
            if parsed and parsed not in dates.setdefault(name, []):
                dates[name].append(parsed)
            break
        if SHARES_BEFORE.search(path):
            shares_before = _number(value)
        elif SHARES_AFTER.search(path):
            shares_after = _number(value)
        elif REDUCTION_PCT.search(path):
            ratios["reduction_pct_common"] = _number(value)
        elif BONUS_PER_SHARE.search(path):
            ratios["bonus_shares_per_share_common"] = _number(value)
        elif MERGER_RATIO.search(path) and _compact(value) not in EMPTY:
            ratios["ratio_text"] = value.strip()[:300]  # 여러 회사 비율이 섞인 서술형이라 숫자로 확정하지 않는다
        elif HALT_REASON.search(path) and _compact(value) not in EMPTY:
            ratios["halt_reason"] = value.strip()[:200]
    if shares_before and shares_after:
        ratios["shares_before_common"] = int(shares_before)
        ratios["shares_after_common"] = int(shares_after)
        ratios["share_count_ratio_before_after"] = round(shares_before / shares_after, 6)
    # 유상증자는 DART 팀이 이미 뽑은 fields를 그대로 쓴다
    if row.get("event_type") == "rights_offering":
        for key in ("method", "new_shares_common", "shares_before_common", "issue_price_common", "discount_pct"):
            if fields.get(key) is not None:
                ratios[key] = fields[key]
        for key, target in (("pay_date", "payment_date"), ("listing_date", "listing_date")):
            value = fields.get(key)
            if value and value not in dates.setdefault(target, []):
                dates[target].append(value)
    dates = {k: sorted(v) for k, v in dates.items() if v}
    for name, values in dates.items():
        if len(values) > 1:
            issues.append(f"{name}:multiple_values")
    correction = row.get("correction") or {}
    rcept = row.get("rcept_dt")
    return ActionEvent(
        rcept_no=str(row["rcept_no"]),
        symbol=str(row["symbol"]).strip(),
        title=str(row.get("title") or ""),
        base_title=str(row.get("base_title") or ""),
        event_type=str(row.get("event_type") or ""),
        rcept_dt=rcept.isoformat() if isinstance(rcept, date) else str(rcept),
        is_correction=bool(row.get("is_correction")),
        is_subsidiary=bool(row.get("is_subsidiary")),
        corrects=row.get("corrects"),
        correction_original_date=correction.get("original_date") if isinstance(correction, dict) else None,
        parse_status=str(row.get("parse_status") or ""),
        dates=dates,
        ratios=ratios,
        ex_rights_status="from_disclosure" if dates.get("ex_rights_date") else "unconfirmed",
        value_issues=issues,
    )


# ---------------------------------------------------------------- 정정공시 묶기


class _UnionFind:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def find(self, key: str) -> str:
        self.parent.setdefault(key, key)
        while self.parent[key] != key:
            self.parent[key] = self.parent[self.parent[key]]
            key = self.parent[key]
        return key

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)


@dataclass
class ActionGroup:
    group_id: str
    symbol: str
    event_type: str
    base_title: str
    is_subsidiary: bool
    members: list[str]
    latest_rcept_no: str | None
    latest: dict | None
    resolution: str            # resolved | ambiguous_original | latest_failed | conflicting_decision_dates
    schedule_changed: bool
    changed_fields: list[str]
    original_missing: bool
    issues: list[str]


def group_events(events: Iterable[ActionEvent]) -> list[ActionGroup]:
    """같은 기업행동의 원본·정정본을 묶는다.

    연결 근거: corrects, (종목·base_title·원 제출일 = 원본 접수일), (종목·base_title·결정일).
    원 제출일이 같은 원본 후보가 둘 이상이면 연결하지 않고 ambiguous로 남긴다.
    """
    events = list(events)
    by_no = {e.rcept_no: e for e in events}
    uf = _UnionFind()
    ambiguous: set[str] = set()
    for e in events:
        uf.find(e.rcept_no)
    key = lambda e: (e.symbol, e.base_title, e.is_subsidiary)
    by_key: dict[tuple, list[ActionEvent]] = {}
    for e in events:
        by_key.setdefault(key(e), []).append(e)
    for e in events:
        if e.corrects and e.corrects in by_no:
            uf.union(e.rcept_no, e.corrects)
            continue
        if not e.is_correction:
            continue
        same = [o for o in by_key[key(e)] if o.rcept_no < e.rcept_no]
        if e.correction_original_date:
            originals = [o for o in same if o.rcept_dt == e.correction_original_date]
            if len(originals) == 1:
                uf.union(e.rcept_no, originals[0].rcept_no)
            elif len(originals) > 1:
                ambiguous.add(e.rcept_no)
    # 결정일이 같은 같은 종류의 공시도 같은 기업행동으로 본다 (원본이 수집 기간 밖이어도 정정본끼리 묶인다)
    for group in by_key.values():
        by_decision: dict[str, list[ActionEvent]] = {}
        for e in group:
            for d in e.dates.get("decision_date", [])[:1]:
                by_decision.setdefault(d, []).append(e)
        for members in by_decision.values():
            for other in members[1:]:
                uf.union(members[0].rcept_no, other.rcept_no)

    clusters: dict[str, list[ActionEvent]] = {}
    for e in events:
        clusters.setdefault(uf.find(e.rcept_no), []).append(e)
    groups = []
    for root, members in clusters.items():
        members.sort(key=lambda e: e.rcept_no)
        usable = [e for e in members if e.parse_status != "failed"]
        latest = usable[-1] if usable else None
        issues: list[str] = []
        resolution = "resolved"
        if any(m.rcept_no in ambiguous for m in members):
            resolution = "ambiguous_original"
            issues.append("원 제출일이 같은 원본 후보가 여럿이라 연결하지 않음")
        if latest is None:
            resolution = "latest_failed"
            issues.append("파싱에 성공한 공시가 없음")
        decisions = {d for m in usable for d in m.dates.get("decision_date", [])[:1]}
        if len(decisions) > 1:
            resolution = "conflicting_decision_dates"
            issues.append(f"결정일이 서로 다름: {sorted(decisions)}")
        changed: list[str] = []
        if latest is not None and len(usable) > 1:
            previous = usable[-2]
            for name in sorted(set(latest.dates) | set(previous.dates)):
                if latest.dates.get(name) != previous.dates.get(name):
                    changed.append(name)
        original_missing = bool(
            members[0].is_correction and (members[0].corrects is None)
        )
        if original_missing:
            issues.append("원본 공시가 DB에 없음 (수집 기간 밖이거나 연결 실패)")
        if latest is not None and latest.value_issues:
            issues += latest.value_issues
        first = members[0]
        groups.append(ActionGroup(
            group_id=f"{first.symbol}:{first.event_type}:{min(m.rcept_no for m in members)}",
            symbol=first.symbol,
            event_type=first.event_type,
            base_title=first.base_title,
            is_subsidiary=first.is_subsidiary,
            members=[m.rcept_no for m in members],
            latest_rcept_no=latest.rcept_no if latest else None,
            latest=asdict(latest) if latest else None,
            resolution=resolution,
            schedule_changed=bool(set(changed) & set(ADJUSTMENT_DATE_FIELDS)),
            changed_fields=changed,
            original_missing=original_missing,
            issues=issues,
        ))
    groups.sort(key=lambda g: g.group_id)
    return groups


# ---------------------------------------------------------------- 일정 판정·후보


@dataclass
class ActionCandidate:
    symbol: str
    name: str | None
    source: str                    # disclosure | disclosure_preferred
    group_id: str
    event_type: str
    is_subsidiary: bool
    latest_rcept_no: str | None
    latest_title: str | None
    rcept_dt: str | None
    dates: dict[str, list[str]]
    ratios: dict[str, object]
    ex_rights_status: str
    schedule_phase: str            # upcoming | in_progress | passed | no_adjustment_date
    nearest_adjustment_date: str | None
    schedule_changed: bool
    resolution: str
    status: str
    recheck_recommended: bool
    recheck_after: str | None
    recheck_window: list[str] | None
    derived_from: str | None = None
    terminal_status: str | None = None
    triggered_dates: list[str] = field(default_factory=list)  # 이미 지난 재조회 기준 날짜 (중복 억제 키에 쓴다)
    notes: list[str] = field(default_factory=list)


def schedule_phase(dates: dict[str, list[str]], as_of: date, horizon_days: int) -> tuple[str, str | None]:
    values = sorted({date.fromisoformat(v) for k in ADJUSTMENT_DATE_FIELDS for v in dates.get(k, [])})
    if not values:
        return "no_adjustment_date", None
    future = [d for d in values if d > as_of]
    past = [d for d in values if d <= as_of]
    if past and future:
        return "in_progress", future[0].isoformat()
    if future:
        return ("upcoming" if future[0] <= as_of + timedelta(days=horizon_days) else "scheduled_later"), future[0].isoformat()
    return "passed", past[-1].isoformat()


def build_candidates(
    groups: Iterable[ActionGroup],
    *,
    as_of: date,
    names: dict[str, str],
    preferred_of_common: dict[str, list[str]],
    terminal: dict,
    horizon_days: int = 30,
    window_days: int = 10,
) -> list[ActionCandidate]:
    """공시 묶음 → 재검증 후보. 가격 이상이 없어도 후보로 관리한다."""
    out: list[ActionCandidate] = []
    for g in groups:
        latest = g.latest or {}
        dates = latest.get("dates") or {}
        phase, nearest = schedule_phase(dates, as_of, horizon_days)
        notes: list[str] = list(g.issues)
        triggers = sorted({v for k in TRIGGER_FIELDS.get(g.event_type, ()) for v in dates.get(k, [])})
        triggered = [v for v in triggers if date.fromisoformat(v) <= as_of]
        third_party = bool(THIRD_PARTY_ALLOTMENT.search(str((latest.get("ratios") or {}).get("method") or "")))
        if g.is_subsidiary:
            status, recommend = NO_ACTION, False
            notes.append("자회사·종속회사 공시: 상장사 본인 주가 조정 근거로 쓰지 않음")
        elif g.event_type in AUXILIARY_EVENT_TYPES:
            reason = str((latest.get("ratios") or {}).get("halt_reason") or "")
            related = bool(ACTION_HALT_REASON.search(_compact(reason)))
            status = REVIEW_REQUIRED if related else NO_ACTION
            recommend = related and bool(triggered)
            notes.append(f"보조 신호(매매거래정지): {reason or '사유 없음'}")
        elif g.resolution != "resolved":
            status, recommend = REVIEW_REQUIRED, False
            notes.append("최신 유효 공시를 확정할 수 없어 날짜·비율을 확정하지 않음")
        elif g.event_type == "rights_offering" and third_party:
            status, recommend = REVIEW_REQUIRED, False
            notes.append("제3자배정 유상증자: 권리락이 없는 경우가 일반적이라 재조회는 권하지 않음(추정, 검토는 유지)")
        else:
            status = REVIEW_REQUIRED
            recommend = bool(triggered)
            if not triggers:
                notes.append("재조회 기준 날짜(효력발생·정지·상장·기준일)가 원문에 없음")
        if g.schedule_changed:
            notes.append(f"정정으로 일정 변경: {g.changed_fields}")
        window = None
        recheck_after = next((v for v in triggers if date.fromisoformat(v) > as_of), None)
        if triggered:
            lo = date.fromisoformat(triggered[0]) - timedelta(days=window_days)
            hi = min(date.fromisoformat(triggered[-1]) + timedelta(days=window_days), as_of)
            if lo <= hi:
                window = [lo.isoformat(), hi.isoformat()]
        base = dict(
            group_id=g.group_id, event_type=g.event_type, is_subsidiary=g.is_subsidiary,
            latest_rcept_no=g.latest_rcept_no, latest_title=latest.get("title"), rcept_dt=latest.get("rcept_dt"),
            dates=dates, ratios=latest.get("ratios") or {}, ex_rights_status=latest.get("ex_rights_status", "unconfirmed"),
            schedule_phase=phase, nearest_adjustment_date=nearest, schedule_changed=g.schedule_changed,
            resolution=g.resolution, recheck_after=recheck_after, recheck_window=window,
            triggered_dates=triggered,
        )
        term = terminal.get(g.symbol)
        out.append(ActionCandidate(
            symbol=g.symbol, name=names.get(g.symbol), source="disclosure", status=status,
            recheck_recommended=recommend and term is None,
            terminal_status=getattr(term, "status", None), notes=notes, **base,
        ))
        if g.is_subsidiary:
            continue
        for pref in preferred_of_common.get(g.symbol, []):
            pterm = terminal.get(pref)
            out.append(ActionCandidate(
                symbol=pref, name=names.get(pref), source="disclosure_preferred", status=REVIEW_REQUIRED,
                recheck_recommended=recommend and pterm is None and g.resolution == "resolved",
                derived_from=g.symbol, terminal_status=getattr(pterm, "status", None),
                notes=notes + ["보통주 공시에서 파생된 우선주 후보: 조정비율이 같다고 가정하지 않음"],
                **{**base, "ratios": {}},
            ))
    return out


def preferred_of_common(pref_map: dict[str, str]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for pref, common in pref_map.items():
        out.setdefault(common, []).append(pref)
    return {k: sorted(v) for k, v in out.items()}


# ---------------------------------------------------------------- 가격 탐지와 통합


def price_status(finding: dict) -> tuple[str, bool]:
    """가격 이상징후 1건의 관리 상태와 재조회 권장 여부. KIS 재조회 전에는 확정 상태를 주지 않는다."""
    if finding.get("assessment") == "consistent_adjustment":
        return NORMAL_ADJUSTMENT, False
    return REVIEW_REQUIRED, finding.get("severity") == "high"


def integrate(
    price_findings: list[dict],
    candidates: list[ActionCandidate],
    *,
    terminal: dict,
    verified: dict[str, dict] | None = None,
    window_days: int = 10,
) -> list[dict]:
    """종목별 관리 항목. 가격 탐지와 공시 탐지는 서로 독립이고, 둘 다 있으면 한 항목에 함께 둔다.

    verified: 재조회 상태(adjusted_recheck state)의 종목별 확정 결과. 있으면 그 상태를 쓴다.
    """
    verified = verified or {}
    items: dict[str, dict] = {}

    def item(symbol: str, name: str | None) -> dict:
        if symbol not in items:
            term = terminal.get(symbol)
            items[symbol] = {
                "symbol": symbol, "name": name, "terminal_status": getattr(term, "status", None),
                "price_findings": [], "disclosure_candidates": [], "status": NORMAL_ADJUSTMENT,
                "recheck_recommended": False, "recheck_windows": [], "reasons": [],
            }
        return items[symbol]

    for f in price_findings:
        status, recommend = price_status(f)
        it = item(f["symbol"], f.get("name"))
        it["price_findings"].append({k: f.get(k) for k in (
            "trade_date", "prev_date", "types", "severity", "assessment", "resync_reasons",
            "prev_ratio", "ratio", "raw_return", "adj_return", "volume", "episode_id")})
        if status == REVIEW_REQUIRED:
            it["status"] = REVIEW_REQUIRED
            it["reasons"].append(f"price:{f['trade_date']}:{f.get('assessment')}")
        if recommend:
            it["recheck_recommended"] = True
            day = date.fromisoformat(f["trade_date"])
            prev = date.fromisoformat(f.get("prev_date") or f["trade_date"])
            it["recheck_windows"].append([(prev - timedelta(days=window_days)).isoformat(),
                                          (day + timedelta(days=window_days)).isoformat()])
    for c in candidates:
        it = item(c.symbol, c.name)
        it["disclosure_candidates"].append(asdict(c))
        if c.status == REVIEW_REQUIRED:
            it["status"] = REVIEW_REQUIRED
            it["reasons"].append(f"disclosure:{c.group_id}:{c.schedule_phase}")
        if c.recheck_recommended:
            it["recheck_recommended"] = True
            if c.recheck_window:
                it["recheck_windows"].append(c.recheck_window)
    for symbol, it in items.items():
        if it["terminal_status"]:
            it["status"] = TERMINAL_EXCLUDED
            it["recheck_recommended"] = False
            it["reasons"].append(f"terminal:{it['terminal_status']} (정리매매 등 정상 사례 가능, 운영 대상 아님)")
        v = verified.get(symbol)
        if v:
            it["verified"] = v
            it["status"] = v["status"]
        it["recheck_windows"] = merge_windows(it["recheck_windows"])
    return sorted(items.values(), key=lambda x: x["symbol"])


def merge_windows(windows: list[list[str]], gap_days: int = 5) -> list[list[str]]:
    spans = sorted((date.fromisoformat(a), date.fromisoformat(b)) for a, b in windows)
    merged: list[list[date]] = []
    for a, b in spans:
        if merged and a <= merged[-1][1] + timedelta(days=gap_days):
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    return [[a.isoformat(), b.isoformat()] for a, b in merged]
