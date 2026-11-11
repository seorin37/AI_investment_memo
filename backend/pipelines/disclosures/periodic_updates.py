"""정기보고서 증분 업데이트의 목록·판단·상태 (run_periodic_updates 1~2단계, docs/periodic-updates.md).

- 목록: DART list.json을 회사 지정 없이 날짜·정기공시(A)·코스피로 받는다 (events_list.fetch_day 재사용).
- 판단: 보고서명에서 (종류, 기준일)을 읽고, DB·상태 파일에 없는 접수번호만 남겨 기업별 슬롯으로 묶는다.
  · DB에 그 슬롯이 없으면 신규, 있으면 정정본(교체는 loader.upsert_disclosure 현행 규칙).
- 상태(data/periodic_updates/state.json): 처리한 접수번호, 재시도 횟수, 재무 대기 목록, 마지막 목록 종료일.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

from .dart import PERIOD_RE, DartError, _any_period_end, kind_from_title, select_window_candidates
from .events_list import normalize_title


LIST_CONFIG = {"pblntf_types": ["A"], "corp_cls": "Y", "last_reprt_at": "N", "page_count": 100}
FIRST_SINCE = "2026-07-01"  # 첫 실행: run_all 대상 기간(~2026-06-30) 이후 제출분과 그 사이 정정본을 따라잡는다
LOOKBACK_DAYS = 3  # 지난 실행 종료일보다 며칠 앞부터 다시 본다 (늦게 목록에 잡히는 공시 대비)
MAX_BODY_ATTEMPTS = 3  # 본문 처리 실패 시 다시 시도하는 실행 횟수 (넘으면 gave_up)
FINANCIALS_WAIT_DAYS = 14  # 재무 API에 자료가 아직 없을 때(013) 기다리는 날 수
ATTACHMENT_ONLY_PREFIXES = ("첨부추가", "첨부정정")  # 첨부(감사보고서 등)만 바뀐 제출본 — 본문은 같다

Slot = tuple[str, str]  # (kind, period_end)


@dataclass(frozen=True)
class PeriodicFiling:
    rcept_no: str
    symbol: str
    corp_code: str
    corp_name: str
    title: str
    kind: str  # annual | half | quarterly
    period_end: str  # YYYY-MM-DD (보고서명의 (YYYY.MM) 말일)
    rcept_dt: str  # YYYY-MM-DD
    prefix: str  # [기재정정] 등 앞 꼬리표 ("" = 최초)

    @property
    def slot(self) -> Slot:
        return (self.kind, self.period_end)

    def to_dict(self) -> dict:
        return asdict(self)


def parse_filings(
    items: list[dict], universe: set[str] | None = None, min_period: str | None = None
) -> tuple[list[PeriodicFiling], dict]:
    """목록 항목 → 정기보고서(사업·반기·분기) 목록. 건너뛴 것은 사유별 건수만 센다.

    - [첨부추가]·[첨부정정]: 첨부만 바뀐 제출본이라 본문이 같다. 받으면 접수번호만 바뀐 같은 본문을 통째로
      다시 임베딩하게 되므로 받지 않는다 (본문을 고친 [기재정정]은 받는다).
    - min_period보다 앞선 기간(대상 기간 시작 전 보고서의 정정본)은 받지 않는다.
    """
    filings: list[PeriodicFiling] = []
    skipped = {"not_periodic": 0, "no_period": 0, "attachment_only": 0, "before_window": 0,
               "no_stock_code": 0, "not_in_universe": 0, "duplicates": 0}
    seen: set[str] = set()
    for item in items:
        rcept_no = str(item["rcept_no"])
        if rcept_no in seen:
            skipped["duplicates"] += 1
            continue
        seen.add(rcept_no)
        title = str(item.get("report_nm", "")).strip()
        base, prefix = normalize_title(title)
        kind = kind_from_title(base)
        if kind is None or not base.startswith(("사업보고서", "반기보고서", "분기보고서")):
            skipped["not_periodic"] += 1
            continue
        if not PERIOD_RE.search(title):
            skipped["no_period"] += 1
            continue
        try:
            period_end = _any_period_end(title)
        except DartError:
            skipped["no_period"] += 1
            continue
        if any(marker in prefix for marker in ATTACHMENT_ONLY_PREFIXES):
            skipped["attachment_only"] += 1
            continue
        if min_period and period_end < min_period:
            skipped["before_window"] += 1
            continue
        symbol =str(item.get("stock_code") or "").strip()
        if not symbol:
            skipped["no_stock_code"] += 1
            continue
        if universe is not None and symbol not in universe:
            skipped["not_in_universe"] += 1
            continue
        rcept_dt = str(item["rcept_dt"])
        filings.append(PeriodicFiling(
            rcept_no=rcept_no,
            symbol=symbol,
            corp_code=str(item.get("corp_code", "")),
            corp_name=str(item.get("corp_name", "")),
            title=title,
            kind=kind,
            period_end=period_end,
            rcept_dt=f"{rcept_dt[:4]}-{rcept_dt[4:6]}-{rcept_dt[6:8]}",
            prefix=prefix,
        ))
    filings.sort(key=lambda f: (f.rcept_dt, f.rcept_no))
    return filings, skipped


@dataclass
class Plan:
    """기업별로 이번에 처리할 슬롯. amended는 DB에 같은 슬롯이 이미 있던 것 (정정본 교체·재무 다시 받기)."""

    slots: dict[str, set[Slot]] = field(default_factory=dict)
    filings: dict[tuple[str, str, str], list[PeriodicFiling]] = field(default_factory=dict)  # (symbol, kind, period_end)
    amended: set[tuple[str, str, str]] = field(default_factory=set)
    known: int = 0

    @property
    def symbols(self) -> list[str]:
        return sorted(self.slots)

    def to_dict(self) -> dict:
        return {
            "companies": len(self.slots),
            "slots": sum(len(v) for v in self.slots.values()),
            "new_slots": sum(len(v) for v in self.slots.values()) - len(self.amended),
            "amended_slots": len(self.amended),
            "already_known_filings": self.known,
            "by_period": _count_by_period(self.filings),
            "items": [
                {"symbol": s, "kind": k, "period_end": p, "amended": (s, k, p) in self.amended,
                 "rcept_nos": [f.rcept_no for f in fs], "titles": [f.title for f in fs]}
                for (s, k, p), fs in sorted(self.filings.items())
            ],
        }


def _count_by_period(filings: dict) -> dict[str, int]:
    counts: dict[str, int] = {}
    for (_, _, period_end) in filings:
        counts[period_end] = counts.get(period_end, 0) + 1
    return dict(sorted(counts.items()))


def build_plan(
    filings: list[PeriodicFiling], known_rcept_nos: set[str], existing_slots: dict[tuple[str, str, str], str]
) -> Plan:
    """DB·상태에 없는 접수번호만 슬롯으로 묶는다.

    existing_slots: DB에 있는 (symbol, kind, period_end) → 그 슬롯의 접수번호. DB 쪽이 같거나 더 새 접수번호면
    (DB에 정정본이 있고 목록에 원본이 나온 경우 등) 이미 반영된 것으로 본다.
    """
    plan = Plan()
    for filing in filings:
        key = (filing.symbol, filing.kind, filing.period_end)
        if filing.rcept_no in known_rcept_nos or (key in existing_slots and filing.rcept_no <= existing_slots[key]):
            plan.known += 1
            continue
        plan.slots.setdefault(filing.symbol, set()).add(filing.slot)
        plan.filings.setdefault(key, []).append(filing)
        if key in existing_slots:
            plan.amended.add(key)
    return plan


def make_selector(plan: Plan):
    """run_all의 BatchRun용 슬롯 선택 함수: 기업 목록(회사별 list.json)에서 계획한 슬롯만 남긴다.

    결산월·헤더 라벨은 run_all과 같은 select_window_candidates 규칙으로 정한다.
    """

    def selector(symbol: str, corp_code: str, items_by_type: dict[str, list[dict]]):
        wanted = plan.slots.get(symbol, set())
        if not wanted:
            return {}, []
        periods = sorted(p for _, p in wanted)
        grouped, _ = select_window_candidates(symbol, corp_code, items_by_type, periods[0], periods[-1], 10_000)
        return {key: refs for key, refs in grouped.items() if key in wanted}, []

    return selector


# ── 상태 파일 ────────────────────────────────────────
class UpdateState:
    """처리한 접수번호·재시도·재무 대기. 실행 중 단계마다 원자적으로 저장한다."""

    def __init__(self, path: Path):
        self.path = path
        if path.exists():
            self.data = json.loads(path.read_text(encoding="utf-8"))
        else:
            self.data = {}
        self.data.setdefault("last_until", None)
        self.data.setdefault("handled", {})  # rcept_no → {status, slot, at, note}
        self.data.setdefault("attempts", {})  # "symbol|kind|period_end" → 실패한 실행 수
        self.data.setdefault("pending_financials", {})  # "symbol|period_end" → {first_seen, attempts, refresh}

    @property
    def handled(self) -> dict[str, dict]:
        return self.data["handled"]

    @property
    def attempts(self) -> dict[str, int]:
        return self.data["attempts"]

    @property
    def pending_financials(self) -> dict[str, dict]:
        return self.data["pending_financials"]

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps(self.data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        os.replace(temp, self.path)

    def default_since(self) -> date:
        if self.data["last_until"]:
            return date.fromisoformat(self.data["last_until"]) - timedelta(days=LOOKBACK_DAYS)
        return date.fromisoformat(FIRST_SINCE)

    def mark(self, filings: list[PeriodicFiling], status: str, now: str, note: str = "") -> None:
        for filing in filings:
            self.handled[filing.rcept_no] = {
                "status": status, "symbol": filing.symbol, "kind": filing.kind, "period_end": filing.period_end,
                "at": now, **({"note": note} if note else {}),
            }

    def record_failure(self, key: tuple[str, str, str], filings: list[PeriodicFiling], now: str, note: str) -> bool:
        """실패 1회를 센다. MAX_BODY_ATTEMPTS에 닿으면 gave_up으로 표시하고 True."""
        name = "|".join(key)
        self.attempts[name] = self.attempts.get(name, 0) + 1
        if self.attempts[name] >= MAX_BODY_ATTEMPTS:
            self.mark(filings, "gave_up", now, note)
            self.attempts.pop(name, None)
            return True
        return False

    def clear_failure(self, key: tuple[str, str, str]) -> None:
        self.attempts.pop("|".join(key), None)

    def add_financials(self, symbol: str, period_end: str, today: str) -> None:
        name = f"{symbol}|{period_end}"
        entry = self.pending_financials.setdefault(name, {"first_seen": today, "attempts": 0})
        entry["refresh"] = True  # 신규면 013 저장본, 정정이면 예전 값일 수 있어 그 기간은 늘 다시 받는다

    def expired_financials(self, today: date) -> list[str]:
        return [
            name for name, entry in self.pending_financials.items()
            if (today - date.fromisoformat(entry["first_seen"])).days > FINANCIALS_WAIT_DAYS
        ]


def now_kst_iso(tz) -> str:
    return datetime.now(tz).isoformat(timespec="seconds")
