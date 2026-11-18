"""수시공시 목록 받기 · 종류 거르기 (run_events 1단계).

- DART list.json을 회사 지정 없이 날짜·공시유형(B 주요사항, I 거래소, E 기타)·법인구분(코스피)으로 받는다.
- 보고서명을 정규화한 뒤 configs/disclosure_events.yaml의 exclude → events 순서로 종류를 정한다.
- 어느 규칙에도 안 맞는 보고서명은 unclassified로 수집하지 않고 보고서에만 남긴다.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from app.dart_reports import DartNoDataError, list_disclosures

from ..common.logging import get_logger


log = get_logger("disclosures.events_list")

PREFIX_RE = re.compile(r"^(\[[^\]]*\])+")
MAJOR_WRAPPER_RE = re.compile(r"^주요사항보고서\(([^()]*)\)")


@dataclass(frozen=True)
class EventRef:
    rcept_no: str
    symbol: str
    corp_code: str
    corp_name: str
    title: str  # DART 원래 보고서명
    base_title: str  # 정규화한 보고서명 (규칙 판정용)
    rcept_dt: str  # YYYY-MM-DD
    pblntf_ty: str  # B·I·E
    kind: str  # disclosures.kind: major | other
    event_type: str
    topic: str
    is_correction: bool  # [기재정정]·[첨부정정] 등 정정 제출본
    is_subsidiary: bool  # 자회사·종속회사의 주요경영사항
    rm: str = ""  # DART 비고 (유: 유가증권시장, 정: 이후 정정됨 …)

    @property
    def source_url(self) -> str:
        return f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={self.rcept_no}"

    def to_dict(self) -> dict:
        return asdict(self)


def normalize_title(report_nm: str) -> tuple[str, str]:
    """(정규화한 보고서명, 앞 꼬리표)를 반환한다. 공백 제거, [..] 꼬리표 분리, 주요사항보고서(X) → X."""
    compact = re.sub(r"\s+", "", report_nm or "")
    match = PREFIX_RE.match(compact)
    prefix = match.group(0) if match else ""
    base = compact[len(prefix):]
    base = MAJOR_WRAPPER_RE.sub(lambda m: m.group(1), base, count=1)
    return base, prefix


@dataclass
class EventRules:
    exclude: list[re.Pattern]
    events: list[tuple[str, str, list[re.Pattern]]]  # (type, topic, patterns)
    subsidiary_markers: list[str]
    include_subsidiary: bool = True
    skip_prefixes: list[str] = field(default_factory=list)

    @classmethod
    def from_config(cls, config: dict) -> "EventRules":
        events = []
        seen: set[str] = set()
        for entry in config.get("events", []):
            event_type, topic = entry["type"], entry["topic"]
            if event_type in seen:
                raise ValueError(f"공시 종류가 중복됩니다: {event_type}")
            seen.add(event_type)
            events.append((event_type, topic, [re.compile(p) for p in entry["patterns"]]))
        return cls(
            exclude=[re.compile(p) for p in config.get("exclude", [])],
            events=events,
            subsidiary_markers=list(config.get("subsidiary_markers", [])),
            include_subsidiary=bool(config.get("include_subsidiary", True)),
            skip_prefixes=list(config.get("skip_prefixes", [])),
        )

    def classify(self, base_title: str) -> tuple[str, str | None]:
        """("excluded", None) | ("unclassified", None) | (event_type, topic)."""
        if any(p.match(base_title) for p in self.exclude):
            return "excluded", None
        for event_type, topic, patterns in self.events:
            if any(p.match(base_title) for p in patterns):
                return event_type, topic
        return "unclassified", None

    def is_subsidiary(self, base_title: str) -> bool:
        return any(marker in base_title for marker in self.subsidiary_markers)


@dataclass
class SelectReport:
    """종류 거르기 결과 집계 (dry-run 보고서용)."""

    total: int = 0
    by_event_type: Counter = field(default_factory=Counter)
    by_day: dict[str, Counter] = field(default_factory=dict)
    excluded_titles: Counter = field(default_factory=Counter)
    unclassified_titles: Counter = field(default_factory=Counter)
    skipped_subsidiary: int = 0
    skipped_prefix: Counter = field(default_factory=Counter)  # 꼬리표 → 건수 ([첨부정정] 등)
    not_in_universe: Counter = field(default_factory=Counter)  # 종목코드 → 건수
    no_stock_code: int = 0
    corrections: int = 0
    duplicates: int = 0

    def to_dict(self) -> dict:
        return {
            "total_listed": self.total,
            "selected": sum(self.by_event_type.values()),
            "corrections_selected": self.corrections,
            "by_event_type": dict(self.by_event_type.most_common()),
            "by_day": {day: dict(counter.most_common()) for day, counter in sorted(self.by_day.items())},
            "excluded_titles": dict(self.excluded_titles.most_common()),
            "unclassified_titles": dict(self.unclassified_titles.most_common()),
            "skipped_subsidiary": self.skipped_subsidiary,
            "skipped_prefix": dict(self.skipped_prefix.most_common()),
            "not_in_universe": dict(self.not_in_universe.most_common()),
            "no_stock_code": self.no_stock_code,
            "duplicates": self.duplicates,
        }


def _iso(yyyymmdd: str) -> str:
    return datetime.strptime(yyyymmdd, "%Y%m%d").date().isoformat()


def select_events(
    items: list[dict],
    rules: EventRules,
    kind_by_type: dict[str, str],
    universe: set[str] | None = None,
    report: SelectReport | None = None,
) -> tuple[list[EventRef], SelectReport]:
    """목록 항목(각각 `_pblntf_ty` 키 포함)을 종류 규칙으로 걸러 EventRef 목록을 만든다.

    universe를 주면 그 종목코드만 남긴다 (stocks 테이블에 있는 코스피 종목, FK 대비).
    """
    report = report or SelectReport()
    refs: list[EventRef] = []
    seen: set[str] = set()
    for item in items:
        rcept_no = str(item["rcept_no"])
        if rcept_no in seen:
            report.duplicates += 1
            continue
        seen.add(rcept_no)
        report.total += 1
        title = str(item.get("report_nm", "")).strip()
        base, prefix = normalize_title(title)
        if any(marker in prefix for marker in rules.skip_prefixes):
            report.skipped_prefix[prefix] += 1
            continue
        event_type, topic = rules.classify(base)
        if topic is None:
            target = report.excluded_titles if event_type == "excluded" else report.unclassified_titles
            target[base] += 1
            continue
        subsidiary = rules.is_subsidiary(base)
        if subsidiary and not rules.include_subsidiary:
            report.skipped_subsidiary += 1
            continue
        symbol = str(item.get("stock_code") or "").strip()
        if not symbol:
            report.no_stock_code += 1
            continue
        if universe is not None and symbol not in universe:
            report.not_in_universe[symbol] += 1
            continue
        pblntf_ty = str(item["_pblntf_ty"])
        ref = EventRef(
            rcept_no=rcept_no,
            symbol=symbol,
            corp_code=str(item.get("corp_code", "")),
            corp_name=str(item.get("corp_name", "")),
            title=title,
            base_title=base,
            rcept_dt=_iso(str(item["rcept_dt"])),
            pblntf_ty=pblntf_ty,
            kind=kind_by_type[pblntf_ty],
            event_type=event_type,
            topic=topic,
            is_correction="정정" in prefix,
            is_subsidiary=subsidiary,
            rm=str(item.get("rm", "") or ""),
        )
        refs.append(ref)
        report.by_event_type[event_type] += 1
        report.by_day.setdefault(ref.rcept_dt, Counter())[event_type] += 1
        report.corrections += int(ref.is_correction)
    refs.sort(key=lambda ref: (ref.rcept_dt, ref.rcept_no))
    return refs, report


KST = ZoneInfo("Asia/Seoul")


def _cache_is_final(cache: Path, day: date) -> bool:
    """그날이 끝난 뒤(다음 날 이후, KST)에 쓴 캐시만 완성본으로 본다.

    예전 코드는 오늘 목록도 캐시에 썼다. 그날 마지막 실행 뒤에 나온 공시가 빠진 파일이라 믿지 않고 다시 받는다.
    """
    written = datetime.fromtimestamp(cache.stat().st_mtime, KST).date()
    return written > day


def fetch_day(
    api_key: str,
    day: date,
    list_config: dict,
    raw_dir: Path,
    *,
    session=None,
    use_cache: bool = True,
    now: datetime | None = None,
) -> list[dict]:
    """하루치 목록을 공시유형별로 받아 `_pblntf_ty`를 붙여 반환한다.

    지난 날짜(오늘 이전, KST)는 data/raw/dart/events/lists/YYYYMMDD.json에 캐시해 다시 받지 않는다.
    오늘 목록은 하루 중에도 늘어나므로 캐시를 읽지도 쓰지도 않는다. 쓰면 다음 날 그 파일을 완성본으로 믿어
    그날 마지막 실행 뒤에 나온 공시를 영영 놓친다. 그래서 자동 실행은 어제~오늘을 받는다.
    DartRateLimitError(020)는 그대로 올린다.
    """
    today = (now or datetime.now(KST)).astimezone(KST).date()
    is_past = day < today
    yyyymmdd = day.strftime("%Y%m%d")
    cache = raw_dir / "lists" / f"{yyyymmdd}.json"
    if use_cache and is_past and cache.exists() and _cache_is_final(cache, day):
        with cache.open(encoding="utf-8") as handle:
            return json.load(handle)
    items: list[dict] = []
    for pblntf_ty in list_config["pblntf_types"]:
        try:
            listed = list_disclosures(
                api_key,
                bgn_de=yyyymmdd,
                end_de=yyyymmdd,
                pblntf_ty=pblntf_ty,
                corp_cls=list_config.get("corp_cls"),
                last_reprt_at=list_config.get("last_reprt_at", "N"),
                page_count=int(list_config.get("page_count", 100)),
                session=session,
            )
        except DartNoDataError:
            listed = []
        items.extend({**entry, "_pblntf_ty": pblntf_ty} for entry in listed)
        log.info("목록: %s 유형=%s %d건", day.isoformat(), pblntf_ty, len(listed))
    if is_past:
        cache.parent.mkdir(parents=True, exist_ok=True)
        with cache.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(items, handle, ensure_ascii=False, indent=0)
            handle.write("\n")
    return items


def days_between(since: date, until: date) -> list[date]:
    if since > until:
        raise ValueError(f"시작일({since})이 종료일({until})보다 늦습니다.")
    return [since + timedelta(days=offset) for offset in range((until - since).days + 1)]
