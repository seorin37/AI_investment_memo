"""DART 재무 원본 JSON → financials / financials_fin 값 매핑 (WO-015 ②단계).

원칙: 확인되지 않은 수치는 추정해 저장하지 않는다 (NULL + 검토 사유).
- 계정은 account_id로만 매칭한다. 후보·허용 sj_div·값 종류는 `configs/financials_mapping.yaml`에 둔다.
- 손익(flow)·주당(per_share)은 연초부터 누적값: 분기·반기 `thstrm_add_amount`, 사업보고서 `thstrm_amount`.
- 잔액(balance)은 `thstrm_amount`이며 매핑에서 `sj_div: [BS]`로 제한한다 (SCE·CF 총계 행 사용 금지).
- BPS = 지배주주지분(BS) ÷ (발행주식총수 − 자기주식수), 주식 수는 `stockTotqySttus.json`.
- 기간 유형(q1·half·q3·annual)은 결산월 기준이다. 3월 결산이면 6월말이 1분기, 3월말이 사업보고서.
- 전기 비교값(prior): 같은 보고서의 `frmtrm_*`로 1년 전 기간을 채운다. 분기 보고서의 재무상태표 전기 값은
  전년 같은 분기가 아니라 직전 사업연도 말이므로 쓰지 않는다 (NULL, not_reported).
- NULL 사유 코드(`null_reasons`): not_applicable(업종상 해당 없음) · no_standard_id(표준 ID 없이 계정명만 있음)
  · not_reported(계정 없음) · needs_review(모호·통화·빈 값 등 검토 필요)
"""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path

import yaml


PERIOD_OFFSETS = {3: "q1", 6: "half", 9: "q3", 0: "annual"}  # (기간 말 월 − 결산월) % 12
FS_DIV_ORDER = ("CFS", "OFS")
FS_DIV_LABELS = {"CFS": "consolidated", "OFS": "separate"}
KINDS = {"flow", "balance", "per_share"}
CENT = Decimal("0.01")
FIN_TYPES = ("bank", "insurance", "securities", "holding", "other")
NULL_CODES = ("not_applicable", "no_standard_id", "not_reported", "needs_review")
NO_STANDARD_ID = "-표준계정코드 미사용-"


def period_type(period_end: str, fy_end_month: int = 12) -> str:
    offset = (int(period_end[5:7]) - fy_end_month) % 12
    if offset not in PERIOD_OFFSETS:
        raise ValueError(f"{period_end}는 결산월 {fy_end_month}월 기준 분기 말이 아닙니다.")
    return PERIOD_OFFSETS[offset]


def month_end(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}-{calendar.monthrange(year, month)[1]:02d}"


def prior_period_end(period_end: str) -> str:
    """1년 전 같은 기간 말 (2월 말 윤년 보정)."""
    return month_end(int(period_end[:4]) - 1, int(period_end[5:7]))


def parse_amount(value) -> Decimal | None:
    """DART 금액 문자열 → Decimal. 쉼표 제거, `(123)`은 음수, 빈 값·`-`·숫자가 아니면 None."""
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    negative = text.startswith("(") and text.endswith(")")
    if negative:
        text = text[1:-1].strip()
    if text in ("", "-"):
        return None
    try:
        amount = Decimal(text)
    except InvalidOperation:
        return None
    if not amount.is_finite():
        return None
    return -amount if negative else amount


def value_field(kind: str, ptype: str, prior: bool = False) -> str | None:
    """값을 읽을 응답 필드. 잔액은 항상 당기말, 손익·주당은 분기·반기면 누적 필드.

    prior=True면 1년 전 같은 기간 값: 사업보고서 frmtrm_amount, 분기·반기 손익 frmtrm_add_amount.
    분기·반기 잔액의 frmtrm_amount는 직전 사업연도 말이라 같은 기간이 아니므로 None.
    """
    if prior:
        if ptype == "annual":
            return "frmtrm_amount"
        return None if kind == "balance" else "frmtrm_add_amount"
    if kind == "balance" or ptype == "annual":
        return "thstrm_amount"
    return "thstrm_add_amount"


# ── 매핑 설정 ─────────────────────────────────────────
@dataclass(frozen=True)
class ColumnRule:
    column: str
    sj_divs: tuple[str, ...]
    kind: str
    ids: tuple[str, ...]
    sign: int = 1
    overrides: dict[str, tuple[str, ...]] = field(default_factory=dict)  # 종목별 후보 교체 (설정에 근거 주석 필수)
    null_symbols: dict[str, str] = field(default_factory=dict)  # 종목 → 항상 NULL인 사유
    null_periods: dict[str, str] = field(default_factory=dict)  # "종목 YYYY-MM-DD" → NULL 사유 (검토 결정)
    scale: Decimal = Decimal(1)  # 저장 자릿수 (numeric(20,0)=1, numeric(14,2)=0.01)
    fin_types: tuple[str, ...] | None = None  # 이 금융 세부 업종에만 값을 찾는다 (None이면 전부)
    not_for_fin_types: tuple[str, ...] = ()  # 이 금융 세부 업종이면 not_applicable
    ofs_ids: tuple[str, ...] = ()  # 별도재무제표(OFS)일 때만 뒤에 붙이는 후보 (비지배지분이 없어 총액 = 지배주주분)
    name_hint: str | None = None  # 후보 ID가 없을 때 표준 ID 없는 행을 검토 목록에 올릴 계정명 정규식
    # 후보 ID가 하나도 없을 때의 대체 (0017 작업, 2026-11-16):
    name_pattern: str | None = None  # 계정명이 이 정규식에 맞는 행이 하나의 값이면 그 값 (ID는 무엇이든)
    sum_ids: tuple[str, ...] = ()  # 첫 ID가 있으면, 있는 것끼리 합 (예: 주식발행초과금 + 기타자본잉여금)

    def applies_to(self, fin_type: str | None) -> bool:
        if fin_type in self.not_for_fin_types:
            return False
        return self.fin_types is None or fin_type in self.fin_types


@dataclass(frozen=True)
class Mapping:
    financials: tuple[ColumnRule, ...]
    fin_symbols: tuple[str, ...]
    financials_fin: tuple[ColumnRule, ...]
    owners_equity: ColumnRule
    continuing_fallback: dict
    accounting_identity_fallback: dict
    capital_note_fallback_periods: tuple[str, ...]
    fin_type_overrides: dict[str, str] = field(default_factory=dict)  # 기존 파이프라인(TARGET_SYMBOLS)용 고정 분류


def _rule(column: str, spec: dict) -> ColumnRule:
    kind = spec["kind"]
    if kind not in KINDS:
        raise ValueError(f"{column}: 알 수 없는 값 종류 {kind}")
    sj_divs = tuple(spec["sj_div"])
    if kind == "balance" and sj_divs != ("BS",):
        raise ValueError(f"{column}: 잔액 항목은 sj_div [BS]만 허용합니다: {sj_divs}")
    sign = int(spec.get("sign", 1))
    if sign not in (1, -1):
        raise ValueError(f"{column}: sign은 1 또는 -1이어야 합니다")
    fin_types = tuple(spec["fin_types"]) if "fin_types" in spec else None
    not_for = tuple(spec.get("not_for_fin_types") or ())
    unknown = sorted((set(fin_types or ()) | set(not_for)) - set(FIN_TYPES))
    if unknown:
        raise ValueError(f"{column}: 알 수 없는 금융 세부 업종 {unknown}")
    return ColumnRule(
        column=column,
        sj_divs=sj_divs,
        kind=kind,
        ids=tuple(spec["ids"]),
        sign=sign,
        overrides={str(k): tuple(v) for k, v in (spec.get("overrides") or {}).items()},
        null_symbols={str(k): str(v) for k, v in (spec.get("null_symbols") or {}).items()},
        null_periods={str(k): str(v) for k, v in (spec.get("null_periods") or {}).items()},
        scale=CENT if kind == "per_share" else Decimal(1),
        fin_types=fin_types,
        not_for_fin_types=not_for,
        ofs_ids=tuple(spec.get("ofs_ids") or ()),
        name_hint=spec.get("name_hint"),
        name_pattern=spec.get("name_pattern"),
        sum_ids=tuple(spec.get("sum_ids") or ()),
    )


def load_mapping(path: str | Path) -> Mapping:
    with Path(path).open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    fin = data["financials_fin"]
    overrides = {str(k): str(v) for k, v in (fin.get("fin_type_overrides") or {}).items()}
    if set(overrides.values()) - set(FIN_TYPES):
        raise ValueError(f"fin_type_overrides에 알 수 없는 업종: {sorted(set(overrides.values()) - set(FIN_TYPES))}")
    return Mapping(
        financials=tuple(_rule(c, s) for c, s in data["financials"].items()),
        fin_symbols=tuple(str(s) for s in fin["symbols"]),
        financials_fin=tuple(_rule(c, s) for c, s in fin["columns"].items()),
        owners_equity=_rule("owners_equity", data["bps"]["owners_equity"]),
        continuing_fallback=dict(data.get("continuing_operations_fallback") or {}),
        accounting_identity_fallback=dict(data.get("accounting_identity_fallback") or {}),
        capital_note_fallback_periods=tuple(str(v) for v in data["bps"].get("capital_note_fallback_periods", [])),
        fin_type_overrides=overrides,
    )


# ── 값 선택 ─────────────────────────────────────────
@dataclass
class Picked:
    value: Decimal | None
    source: dict  # provenance: account_id, sj_div, field, file (값이 있을 때) 또는 reason (NULL일 때)

    @property
    def reason(self) -> str | None:
        return self.source.get("reason")

    @property
    def null_code(self) -> str | None:
        return self.source.get("null_code")


def _quantize(value: Decimal, scale: Decimal) -> Decimal | None:
    quantized = value.quantize(scale, rounding=ROUND_HALF_UP)
    return quantized if quantized == value or scale != Decimal(1) else None


def _null(reason: str, code: str, *, expected: bool = False, **extra) -> Picked:
    source = {**extra, "reason": reason, "null_code": code}
    if expected:
        source["expected_null"] = True
    return Picked(None, source)


def _unmapped_rows(rows: list[dict], rule: ColumnRule, value_key: str) -> list[dict]:
    """표준 ID 없이 계정명만 있는 행 중 name_hint에 맞는 것 (값을 채우지 않고 검토 목록에만 올린다)."""
    if not rule.name_hint:
        return []
    pattern = re.compile(rule.name_hint)
    return [
        {"account_nm": str(r.get("account_nm", "")).strip(), "sj_div": r.get("sj_div"), "value": r.get(value_key)}
        for r in rows
        if r.get("account_id") == NO_STANDARD_ID and r.get("sj_div") in rule.sj_divs and pattern.search(str(r.get("account_nm", "")))
    ]


def _single_value(matches: list[dict], value_key: str) -> Decimal | None:
    values = {v for v in (parse_amount(r.get(value_key)) for r in matches) if v is not None}
    if len(values) != 1 or any((r.get("currency") or "KRW") != "KRW" for r in matches):
        return None
    return values.pop()


def _alternate_pick(rows: list[dict], rule: ColumnRule, value_key: str, source_file: str) -> Picked | None:
    """후보 ID가 없을 때: ① 계정명 정규식(name_pattern)에 맞는 행 하나 ② sum_ids 합. 못 고르면 None."""
    in_sj = [r for r in rows if r.get("sj_div") in rule.sj_divs]
    if rule.name_pattern:
        pattern = re.compile(rule.name_pattern)
        matches = [r for r in in_sj if pattern.search(str(r.get("account_nm", "")).strip())]
        if matches:
            value = _single_value(matches, value_key)
            if value is not None:
                value = _quantize(value * rule.sign, rule.scale)
                if value is not None:
                    return Picked(value, {"account_nm": str(matches[0].get("account_nm", "")).strip(),
                                          "account_id": matches[0].get("account_id"), "sj_div": matches[0].get("sj_div"),
                                          "field": value_key, "file": source_file, "fallback": "name_pattern"})
    if rule.sum_ids and any(r.get("account_id") == rule.sum_ids[0] for r in in_sj):
        total, used = Decimal(0), []
        for account_id in rule.sum_ids:
            matches = [r for r in in_sj if r.get("account_id") == account_id]
            if not matches:
                continue
            value = _single_value(matches, value_key)
            if value is None:
                return None  # 구성 계정 값이 모호하면 합을 만들지 않는다
            total += value
            used.append(account_id)
        value = _quantize(total * rule.sign, rule.scale)
        if value is not None:
            return Picked(value, {"account_id": "+".join(used), "sj_div": ",".join(rule.sj_divs), "field": value_key,
                                  "file": source_file, "fallback": "sum_ids"})
    return None


def pick(
    rows: list[dict], rule: ColumnRule, symbol: str, period_end: str, source_file: str,
    *, ptype: str | None = None, prior: bool = False, fs_div: str = "CFS",
) -> Picked:
    """후보 account_id를 우선순위대로 찾아 값 하나를 고른다. 못 고르면 None + 사유 + 사유 코드(null_code).

    ptype은 결산월 기준 기간 유형 (없으면 12월 결산으로 본다). prior=True면 전기(1년 전 같은 기간) 값.
    """
    if symbol in rule.null_symbols:
        return _null(rule.null_symbols[symbol], "not_applicable", expected=True)
    if f"{symbol} {period_end}" in rule.null_periods:
        return _null(rule.null_periods[f"{symbol} {period_end}"], "not_applicable", expected=True)
    ids = rule.overrides.get(symbol, rule.ids) + (rule.ofs_ids if fs_div == "OFS" else ())
    value_key = value_field(rule.kind, ptype or period_type(period_end), prior)
    if value_key is None:
        return _null("분기·반기 보고서의 재무상태표 전기 값은 직전 사업연도 말이라 같은 기간이 아님", "not_reported", expected=True)
    for account_id in ids:
        matches = [r for r in rows if r.get("account_id") == account_id and r.get("sj_div") in rule.sj_divs]
        if not matches:
            continue
        where = {"account_id": account_id, "sj_div": ",".join(sorted({r["sj_div"] for r in matches})), "field": value_key, "file": source_file}
        currencies = {r.get("currency") or "KRW" for r in matches}
        if currencies != {"KRW"}:
            return _null(f"{account_id} 통화가 KRW가 아님: {sorted(currencies)}", "needs_review", **where)
        values = {v for v in (parse_amount(r.get(value_key)) for r in matches) if v is not None}
        if not values:
            what = "누적값 미확인" if value_key == "thstrm_add_amount" else "값 없음"
            return _null(f"{account_id} {value_key} 비어 있음 ({what})", "needs_review", **where)
        if len(values) > 1:
            return _null(f"{account_id} 값이 여러 개로 모호함: {sorted(map(str, values))}", "needs_review", **where)
        value = _quantize(values.pop() * rule.sign, rule.scale)
        if value is None:
            return _null(f"{account_id} 원 단위 정수가 아님", "needs_review", **where)
        return Picked(value, where)
    alt = _alternate_pick(rows, rule, value_key, source_file)
    if alt is not None:
        return alt
    reason = f"후보 account_id 없음 ({', '.join(ids)}; sj_div {'/'.join(rule.sj_divs)})"
    unmapped = _unmapped_rows(rows, rule, value_key)
    if unmapped:
        return _null(reason + " — 표준 ID 없는 같은 성격 계정 있음", "no_standard_id", unmapped=unmapped, field=value_key, file=source_file)
    return _null(reason, "not_reported")


# ── 이자비용 (financial_metrics.interest_cost, 0017) ─────────────────
# 대부분의 일반 기업은 손익계산서 본문에 이자비용을 따로 적지 않고(금융비용 합계만) 주석에만 적는다.
# 금융비용 합계(ifrs-full_FinanceCosts)는 외환·파생 손실까지 섞여 쓰지 않는다(2026-10-22 결정).
# 순서: 손익계산서 이자비용 → 현금흐름표 조정 '이자비용'(발생액) → 현금흐름표 '이자의 지급'(현금, 근사). 2026-11-16 결정.
INTEREST_CHAIN = (
    ("income_statement", ("IS", "CIS"), ("ifrs-full_InterestExpense", "dart_InterestExpenseFinanceExpense"), False),
    ("cf_adjustment", ("CF",), ("dart_AdjustmentsForInterestExpenses", "ifrs-full_AdjustmentsForInterestExpense"), False),
    ("cf_paid", ("CF",), ("ifrs-full_InterestPaidClassifiedAsOperatingActivities", "ifrs-full_InterestPaidClassifiedAsFinancingActivities"), True),
)


def _cf_field(ptype: str, prior: bool) -> str | None:
    """현금흐름표는 분기·반기도 thstrm_amount가 누적값이다(누적 필드 add_amount 없음). 전기는 사업보고서만."""
    if prior:
        return "frmtrm_amount" if ptype == "annual" else None
    return "thstrm_amount"


def pick_interest_cost(rows: list[dict], ptype: str, *, prior: bool = False) -> tuple[Decimal | None, str | None, str | None]:
    """(이자비용 누적값, 근거, NULL 사유). 값은 양수(비용 크기)로 저장한다.

    한 단계 안에서 후보 ID가 여러 개면: 손익·조정은 앞 후보 하나, '이자의 지급'은 영업·재무활동 분류를 합한다.
    """
    for basis, sj_divs, ids, sum_all in INTEREST_CHAIN:
        key = value_field("flow", ptype, prior) if basis == "income_statement" else _cf_field(ptype, prior)
        if key is None:
            continue
        found: list[Decimal] = []
        for account_id in ids:
            matches = [r for r in rows if r.get("account_id") == account_id and r.get("sj_div") in sj_divs]
            if not matches:
                continue
            value = _single_value(matches, key)
            if value is None:
                return None, None, "needs_review"
            found.append(abs(value))
            if not sum_all:
                break
        if found:
            return sum(found, Decimal(0)), basis, None
    return None, None, "not_reported"


# ── 주식 수·BPS ─────────────────────────────────────
@dataclass(frozen=True)
class ShareCounts:
    issued: int | None  # 발행주식총수 istc_totqy
    treasury: int | None  # 자기주식수 tesstk_co
    outstanding: int | None  # 유통주식수 distb_stock_co
    basis: str  # "합계" | "보통주+우선주"


def _count(value, *, dash_is_zero: bool = False) -> int | None:
    """주식 수 문자열 (쉼표 제거). `-`는 기본적으로 미기재(None) — 분기보고서는 합계 행을 `-`로만 채우는 경우가 많다.
    우선주 행의 `-`만 '우선주 없음(0)'으로 본다 (dash_is_zero)."""
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if text == "-":
        return 0 if dash_is_zero else None
    return int(text) if text.isdigit() else None


def parse_share_counts(data: dict) -> ShareCounts | None:
    """stockTotqySttus 응답 → 주식 수. 013·행 없음이면 None. `합계` 행이 없으면 보통주+우선주."""
    if str(data.get("status")) != "000":
        return None
    by_se = {str(r.get("se", "")).strip(): r for r in data.get("list", [])}
    keys = ("istc_totqy", "tesstk_co", "distb_stock_co")
    if "합계" in by_se:
        issued, treasury, outstanding = (_count(by_se["합계"].get(k)) for k in keys)
        basis = "합계"
    elif "보통주" in by_se:
        common, preferred = by_se["보통주"], by_se.get("우선주")
        counts = []
        for key in keys:
            values = [_count(common.get(key)), _count(preferred.get(key), dash_is_zero=True) if preferred else 0]
            counts.append(None if None in values else sum(values))
        issued, treasury, outstanding = counts
        basis = "보통주+우선주"
    else:
        return None
    # 자기주식 `-`이고 유통주식수 = 발행주식총수이면 자기주식 0이 응답 안에서 확인된다 (유통 = 발행 − 자기)
    if treasury is None and issued is not None and issued == outstanding:
        treasury = 0
    return ShareCounts(issued, treasury, outstanding, basis=basis)


def compute_bps(owners_equity: Decimal | None, shares: ShareCounts | None) -> Decimal | None:
    """값이 하나라도 없거나 분모(발행주식총수 − 자기주식수)가 0 이하이면 None. 원 단위 소수 2자리."""
    if owners_equity is None or shares is None or shares.issued is None or shares.treasury is None:
        return None
    denominator = shares.issued - shares.treasury
    if denominator <= 0:
        return None
    return (owners_equity / Decimal(denominator)).quantize(CENT, rounding=ROUND_HALF_UP)


def _fallback_pick(rows: list[dict], account_id: str, period_end: str, source_file: str, *, per_share: bool = False) -> Picked:
    return pick(
        rows,
        ColumnRule("fallback", ("IS", "CIS"), "per_share" if per_share else "flow", (account_id,), scale=CENT if per_share else Decimal(1)),
        "", period_end, source_file,
    )


def continuing_operations_fallback(rows: list[dict], symbol: str, period_end: str, source_file: str, mapping: Mapping) -> dict | None:
    """허용된 슬롯에서 중단영업 0을 검증해 net_income·eps 대체값과 조건 provenance를 반환한다."""
    spec = mapping.continuing_fallback
    if f"{symbol} {period_end}" not in {str(v) for v in spec.get("targets", [])}:
        return None
    picks = {
        "profit_loss": _fallback_pick(rows, spec["profit_loss"], period_end, source_file),
        "continuing_profit_loss": _fallback_pick(rows, spec["continuing_profit_loss"], period_end, source_file),
        "owners_profit_loss": _fallback_pick(rows, spec["owners_profit_loss"], period_end, source_file),
        "noncontrolling_profit_loss": _fallback_pick(rows, spec["noncontrolling_profit_loss"], period_end, source_file),
        "basic_eps": _fallback_pick(rows, spec["basic_eps"], period_end, source_file, per_share=True),
    }
    values = {name: picked.value for name, picked in picks.items()}
    missing = [name for name in ("profit_loss", "continuing_profit_loss", "owners_profit_loss", "basic_eps") if values[name] is None]
    condition_ok = not missing and values["profit_loss"] == values["continuing_profit_loss"]
    source = {
        "fallback_rule": "continuing_operations_when_no_discontinued_operations",
        "condition": "ProfitLoss == ProfitLossFromContinuingOperations",
        "condition_ok": condition_ok,
        "condition_values": {name: None if value is None else str(value) for name, value in values.items()},
        "accounts": {name: picked.source for name, picked in picks.items()},
    }
    if not condition_ok:
        source["reason"] = "계속영업 대체 조건 불충족: " + (f"필수 계정 없음 {missing}" if missing else "ProfitLoss와 계속영업손익 불일치")
        return {"net_income": None, "eps": None, "source": source}
    source["component_sum_ok"] = (
        values["noncontrolling_profit_loss"] is not None
        and values["owners_profit_loss"] + values["noncontrolling_profit_loss"] == values["profit_loss"]
    )
    return {"net_income": values["owners_profit_loss"], "eps": values["basic_eps"], "source": source}


def apply_accounting_identity_fallback(
    rows: list[dict], symbol: str, period_end: str, source_file: str, mapping: Mapping,
    values: dict[str, Decimal | None], provenance: list[dict], *, prior: bool = False,
) -> bool:
    """Repair explicitly approved DART total-account defects with auditable provenance.

    Some filings expose stale ``Assets``/``Liabilities`` values in the structured API
    while ``EquityAndLiabilities`` and ``Equity`` match the filed statement.  The
    fallback is deliberately restricted to configured symbol/period/receipt triples.
    """
    spec = mapping.accounting_identity_fallback
    targets = {str(k): str(v) for k, v in (spec.get("targets") or {}).items()}
    expected_rcept = targets.get(f"{symbol} {period_end}")
    if prior or expected_rcept is None:
        return False
    rcept_nos = {str(row["rcept_no"]) for row in rows if row.get("rcept_no")}
    if rcept_nos != {expected_rcept}:
        return False
    assets, liabilities, equity = (values.get(c) for c in ("total_assets", "total_liabilities", "total_equity"))
    if None in (assets, liabilities, equity) or assets == liabilities + equity:
        return False

    account_id = str(spec.get("account_id") or "ifrs-full_EquityAndLiabilities")
    combined = pick(
        rows, ColumnRule("total_assets", ("BS",), "balance", (account_id,)),
        symbol, period_end, source_file, ptype=period_type(period_end), fs_div="CFS",
    )
    if combined.value is None:
        return False
    corrected = {
        "total_assets": combined.value,
        "total_liabilities": combined.value - equity,
    }
    equity_source = next(p for p in provenance if p["table"] == "financials" and p["column"] == "total_equity")
    for column, value in corrected.items():
        source = next(p for p in provenance if p["table"] == "financials" and p["column"] == column)
        original = {k: source.get(k) for k in ("value", "account_id", "sj_div", "field", "file") if k in source}
        replacement = {
            "symbol": symbol,
            "period_end": period_end,
            "table": "financials",
            "column": column,
            "value": value,
            "fallback_rule": "filed_accounting_identity",
            "verified_rcept_no": expected_rcept,
            "replaced_source": original,
            "file": source_file,
        }
        if column == "total_assets":
            replacement.update(combined.source)
            replacement["formula"] = account_id
        else:
            replacement.update({
                "formula": f"{account_id} - ifrs-full_Equity",
                "components": {
                    "equity_and_liabilities": str(combined.value),
                    "equity": str(equity),
                    "equity_account_id": equity_source.get("account_id"),
                },
            })
        source.clear()
        source.update(replacement)
        values[column] = value
    return corrected["total_assets"] == corrected["total_liabilities"] + equity


# ── 기간 1건 매핑 ───────────────────────────────────
FROM_MAPPING = object()  # map_period(fin_type=...) 기본값: 설정의 fin_type_overrides를 쓴다 (기존 4개사 파이프라인)


@dataclass
class MappedPeriod:
    symbol: str
    period_end: str
    period_type: str
    fs_div: str  # consolidated | separate
    rcept_no: str | None  # 재무 API 응답의 접수번호
    values: dict[str, Decimal | None]
    fin_values: dict[str, Decimal | None] | None  # 금융사만 (fin_type이 있을 때)
    provenance: list[dict]
    review: list[str]  # 예상하지 못한 NULL (사유 포함)
    shares: ShareCounts | None
    null_reasons: dict[str, str] = field(default_factory=dict)  # financials 컬럼 → 사유 코드
    fin_null_reasons: dict[str, str] = field(default_factory=dict)  # financials_fin 컬럼 → 사유 코드
    fin_type: str | None = None
    prior: bool = False  # 다음 해 보고서의 전기 값으로 채운 기간
    review_items: list[dict] = field(default_factory=list)  # 검토 CSV용 (review와 같은 항목, 구조화)
    # 이자비용 누적값·근거·NULL 사유 (financial_metrics.interest_cost, 0017). 기본값은 '계산 안 함'
    interest_cost: tuple[Decimal | None, str | None, str | None] = (None, None, "not_reported")


def map_period(
    symbol: str, period_end: str, fs_div: str, statement: dict, statement_file: str, shares_data: dict | None, shares_file: str | None, mapping: Mapping,
    *, fallback_shares: ShareCounts | None = None, fallback_shares_source: dict | None = None,
    fin_type=FROM_MAPPING, fy_end_month: int = 12, prior: bool = False,
) -> MappedPeriod:
    """재무제표 원본 1건 → 한 기간의 값.

    prior=True면 `period_end`는 보고서 기간이고, 결과는 1년 전 같은 기간(전기 값)이다. 전기 BPS는
    그 시점 주식 수가 없어 계산하지 않는다 (NULL, not_reported).
    """
    if fin_type is FROM_MAPPING:
        fin_type = mapping.fin_type_overrides.get(symbol)
    ptype = period_type(period_end, fy_end_month)
    out_end = prior_period_end(period_end) if prior else period_end
    rows = statement.get("list", [])
    provenance: list[dict] = []
    review: list[str] = []
    review_items: list[dict] = []
    reasons: dict[str, dict[str, str]] = {"financials": {}, "financials_fin": {}}

    def record(table: str, column: str, value, source: dict) -> None:
        provenance.append({"symbol": symbol, "period_end": out_end, "table": table, "column": column, "value": value, **source})
        if value is None:
            reasons[table][column] = source.get("null_code") or "needs_review"
            if not source.get("expected_null"):
                review.append(f"{symbol} {out_end} {table}.{column}: {source.get('reason')}")
                review_items.append({"symbol": symbol, "period_end": out_end, "table": table, "column": column,
                                     "null_code": reasons[table][column], "reason": source.get("reason"),
                                     "unmapped": source.get("unmapped", []), "file": statement_file})
        else:
            reasons[table].pop(column, None)

    def take(rule: ColumnRule, table: str) -> Decimal | None:
        if not rule.applies_to(fin_type):
            picked = _null(f"{fin_type or '일반'} 업종에는 해당 없음", "not_applicable", expected=True)
        else:
            picked = pick(rows, rule, symbol, period_end, statement_file, ptype=ptype, prior=prior, fs_div=fs_div)
        record(table, rule.column, picked.value, picked.source)
        return picked.value

    values = {rule.column: take(rule, "financials") for rule in mapping.financials}
    apply_accounting_identity_fallback(
        rows, symbol, period_end, statement_file, mapping, values, provenance, prior=prior,
    )
    net_source = next(p for p in provenance if p["table"] == "financials" and p["column"] == "net_income")
    eps_source = next(p for p in provenance if p["table"] == "financials" and p["column"] == "eps")
    base_missing = all(str(source.get("reason", "")).startswith("후보 account_id 없음") for source in (net_source, eps_source))
    fallback = continuing_operations_fallback(rows, symbol, period_end, statement_file, mapping) if base_missing and not prior else None
    if fallback is not None:
        drop = {("financials", "net_income"), ("financials", "eps")}
        review[:] = [line for line in review if not ("financials.net_income:" in line or "financials.eps:" in line)]
        review_items[:] = [item for item in review_items if (item["table"], item["column"]) not in drop]
        values["net_income"], values["eps"] = fallback["net_income"], fallback["eps"]
        for column, source in (("net_income", net_source), ("eps", eps_source)):
            source.clear()
            source.update({"symbol": symbol, "period_end": out_end, "table": "financials", "column": column,
                           "value": values[column], **fallback["source"]})
            source["fallback_account"] = (mapping.continuing_fallback["owners_profit_loss"] if column == "net_income"
                                          else mapping.continuing_fallback["basic_eps"])
            if values[column] is None:
                reasons["financials"][column] = "needs_review"
                review.append(f"{symbol} {out_end} financials.{column}: {fallback['source']['reason']}")
                review_items.append({"symbol": symbol, "period_end": out_end, "table": "financials", "column": column,
                                     "null_code": "needs_review", "reason": fallback["source"]["reason"], "unmapped": [], "file": statement_file})
            else:
                reasons["financials"].pop(column, None)

    if prior:
        values["bps"] = None
        provenance.append({"symbol": symbol, "period_end": out_end, "table": "financials", "column": "bps", "value": None,
                           "reason": "전기 BPS: 그 시점 주식 수 자료 없음", "null_code": "not_reported"})
        reasons["financials"]["bps"] = "not_reported"
        shares = None
    else:
        owners = pick(rows, mapping.owners_equity, symbol, period_end, statement_file, ptype=ptype, fs_div=fs_div)
        api_shares = parse_share_counts(shares_data) if shares_data is not None else None
        api_usable = api_shares is not None and api_shares.issued is not None and api_shares.treasury is not None
        shares = api_shares if api_usable else fallback_shares
        values["bps"] = compute_bps(owners.value, shares)
        if values["bps"] is not None:
            bps_source = {"formula": "owners_equity / (issued - treasury)", "owners_equity": owners.source, "shares_file": shares_file,
                          "shares_basis": shares.basis, "issued": shares.issued, "treasury": shares.treasury}
            if not api_usable and fallback_shares_source:
                bps_source["shares_fallback"] = fallback_shares_source
        else:
            reason = (owners.reason if owners.value is None
                      else "주식 총수 데이터 없음(013 또는 원본 없음, 공시 fallback 실패)" if shares is None
                      else f"주식 수 미기재({shares.basis} 행 '-' 또는 빈 값)" if shares.issued is None or shares.treasury is None
                      else f"분모 0 이하 (발행 {shares.issued}, 자기 {shares.treasury})")
            code = owners.null_code if owners.value is None else "not_reported" if shares is None else "needs_review"
            bps_source = {"reason": f"BPS 계산 불가: {reason}", "null_code": code, "shares_file": shares_file}
            if not api_usable and fallback_shares_source:
                bps_source["shares_fallback"] = fallback_shares_source
        record("financials", "bps", values["bps"], bps_source)

    fin_values = {rule.column: take(rule, "financials_fin") for rule in mapping.financials_fin} if fin_type is not None else None
    rcept_nos = sorted({str(r["rcept_no"]) for r in rows if r.get("rcept_no")})
    return MappedPeriod(
        symbol=symbol,
        period_end=out_end,
        period_type=ptype,
        fs_div=FS_DIV_LABELS[fs_div],
        rcept_no=rcept_nos[0] if len(rcept_nos) == 1 else None,
        values=values,
        fin_values=fin_values,
        provenance=provenance,
        review=review,
        shares=shares,
        null_reasons=reasons["financials"],
        fin_null_reasons=reasons["financials_fin"],
        fin_type=fin_type,
        prior=prior,
        review_items=review_items,
        interest_cost=pick_interest_cost(rows, ptype, prior=prior),
    )
