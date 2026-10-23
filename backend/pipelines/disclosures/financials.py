"""DART 재무 원본 JSON → financials / financials_fin 값 매핑 (WO-015 ②단계).

원칙: 확인되지 않은 수치는 추정해 저장하지 않는다 (NULL + 검토 사유).
- 계정은 account_id로만 매칭한다. 후보·허용 sj_div·값 종류는 `configs/financials_mapping.yaml`에 둔다.
- 손익(flow)·주당(per_share)은 연초부터 누적값: 분기·반기 `thstrm_add_amount`, 사업보고서 `thstrm_amount`.
- 잔액(balance)은 `thstrm_amount`이며 매핑에서 `sj_div: [BS]`로 제한한다 (SCE·CF 총계 행 사용 금지).
- BPS = 지배주주지분(BS) ÷ (발행주식총수 − 자기주식수), 주식 수는 `stockTotqySttus.json`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path

import yaml


PERIOD_TYPES = {"03": "q1", "06": "half", "09": "q3", "12": "annual"}
FS_DIV_ORDER = ("CFS", "OFS")
FS_DIV_LABELS = {"CFS": "consolidated", "OFS": "separate"}
KINDS = {"flow", "balance", "per_share"}
CENT = Decimal("0.01")


def period_type(period_end: str) -> str:
    return PERIOD_TYPES[period_end[5:7]]


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


def value_field(kind: str, period_end: str) -> str:
    """값을 읽을 응답 필드. 잔액은 항상 당기말, 손익·주당은 분기·반기면 누적 필드."""
    if kind == "balance" or period_type(period_end) == "annual":
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


@dataclass(frozen=True)
class Mapping:
    financials: tuple[ColumnRule, ...]
    fin_symbols: tuple[str, ...]
    financials_fin: tuple[ColumnRule, ...]
    owners_equity: ColumnRule
    continuing_fallback: dict
    capital_note_fallback_periods: tuple[str, ...]


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
    )


def load_mapping(path: str | Path) -> Mapping:
    with Path(path).open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    fin = data["financials_fin"]
    return Mapping(
        financials=tuple(_rule(c, s) for c, s in data["financials"].items()),
        fin_symbols=tuple(str(s) for s in fin["symbols"]),
        financials_fin=tuple(_rule(c, s) for c, s in fin["columns"].items()),
        owners_equity=_rule("owners_equity", data["bps"]["owners_equity"]),
        continuing_fallback=dict(data.get("continuing_operations_fallback") or {}),
        capital_note_fallback_periods=tuple(str(v) for v in data["bps"].get("capital_note_fallback_periods", [])),
    )


# ── 값 선택 ─────────────────────────────────────────
@dataclass
class Picked:
    value: Decimal | None
    source: dict  # provenance: account_id, sj_div, field, file (값이 있을 때) 또는 reason (NULL일 때)

    @property
    def reason(self) -> str | None:
        return self.source.get("reason")


def _quantize(value: Decimal, scale: Decimal) -> Decimal | None:
    quantized = value.quantize(scale, rounding=ROUND_HALF_UP)
    return quantized if quantized == value or scale != Decimal(1) else None


def pick(rows: list[dict], rule: ColumnRule, symbol: str, period_end: str, source_file: str) -> Picked:
    """후보 account_id를 우선순위대로 찾아 값 하나를 고른다. 못 고르면 None + 사유."""
    if symbol in rule.null_symbols:
        return Picked(None, {"reason": rule.null_symbols[symbol], "expected_null": True})
    if f"{symbol} {period_end}" in rule.null_periods:
        return Picked(None, {"reason": rule.null_periods[f"{symbol} {period_end}"], "expected_null": True})
    ids = rule.overrides.get(symbol, rule.ids)
    value_key = value_field(rule.kind, period_end)
    for account_id in ids:
        matches = [r for r in rows if r.get("account_id") == account_id and r.get("sj_div") in rule.sj_divs]
        if not matches:
            continue
        where = {"account_id": account_id, "sj_div": ",".join(sorted({r["sj_div"] for r in matches})), "field": value_key, "file": source_file}
        currencies = {r.get("currency") or "KRW" for r in matches}
        if currencies != {"KRW"}:
            return Picked(None, {**where, "reason": f"{account_id} 통화가 KRW가 아님: {sorted(currencies)}"})
        values = {v for v in (parse_amount(r.get(value_key)) for r in matches) if v is not None}
        if not values:
            what = "누적값 미확인" if value_key == "thstrm_add_amount" else "값 없음"
            return Picked(None, {**where, "reason": f"{account_id} {value_key} 비어 있음 ({what})"})
        if len(values) > 1:
            return Picked(None, {**where, "reason": f"{account_id} 값이 여러 개로 모호함: {sorted(map(str, values))}"})
        value = _quantize(values.pop() * rule.sign, rule.scale)
        if value is None:
            return Picked(None, {**where, "reason": f"{account_id} 원 단위 정수가 아님"})
        return Picked(value, where)
    return Picked(None, {"reason": f"후보 account_id 없음 ({', '.join(ids)}; sj_div {'/'.join(rule.sj_divs)})"})


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


# ── 기간 1건 매핑 ───────────────────────────────────
@dataclass
class MappedPeriod:
    symbol: str
    period_end: str
    period_type: str
    fs_div: str  # consolidated | separate
    rcept_no: str | None  # 재무 API 응답의 접수번호
    values: dict[str, Decimal | None]
    fin_values: dict[str, Decimal | None] | None  # financials_fin 대상 종목만
    provenance: list[dict]
    review: list[str]  # 예상하지 못한 NULL (사유 포함)
    shares: ShareCounts | None


def map_period(
    symbol: str, period_end: str, fs_div: str, statement: dict, statement_file: str, shares_data: dict | None, shares_file: str | None, mapping: Mapping,
    *, fallback_shares: ShareCounts | None = None, fallback_shares_source: dict | None = None,
) -> MappedPeriod:
    rows = statement.get("list", [])
    provenance: list[dict] = []
    review: list[str] = []

    def take(rule: ColumnRule, table: str) -> Decimal | None:
        picked = pick(rows, rule, symbol, period_end, statement_file)
        provenance.append({"symbol": symbol, "period_end": period_end, "table": table, "column": rule.column, "value": picked.value, **picked.source})
        if picked.value is None and not picked.source.get("expected_null"):
            review.append(f"{symbol} {period_end} {table}.{rule.column}: {picked.reason}")
        return picked.value

    values = {rule.column: take(rule, "financials") for rule in mapping.financials}
    net_source = next(p for p in provenance if p["table"] == "financials" and p["column"] == "net_income")
    eps_source = next(p for p in provenance if p["table"] == "financials" and p["column"] == "eps")
    base_missing = all(str(source.get("reason", "")).startswith("후보 account_id 없음") for source in (net_source, eps_source))
    fallback = continuing_operations_fallback(rows, symbol, period_end, statement_file, mapping) if base_missing else None
    if fallback is not None:
        review[:] = [line for line in review if not ("financials.net_income:" in line or "financials.eps:" in line)]
        values["net_income"], values["eps"] = fallback["net_income"], fallback["eps"]
        for column, source in (("net_income", net_source), ("eps", eps_source)):
            source.clear()
            source.update({"symbol": symbol, "period_end": period_end, "table": "financials", "column": column,
                           "value": values[column], **fallback["source"]})
            source["fallback_account"] = (mapping.continuing_fallback["owners_profit_loss"] if column == "net_income"
                                          else mapping.continuing_fallback["basic_eps"])
            if values[column] is None:
                review.append(f"{symbol} {period_end} financials.{column}: {fallback['source']['reason']}")
    owners = pick(rows, mapping.owners_equity, symbol, period_end, statement_file)
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
        bps_source = {"reason": f"BPS 계산 불가: {reason}", "shares_file": shares_file}
        if not api_usable and fallback_shares_source:
            bps_source["shares_fallback"] = fallback_shares_source
        review.append(f"{symbol} {period_end} financials.bps: {bps_source['reason']}")
    provenance.append({"symbol": symbol, "period_end": period_end, "table": "financials", "column": "bps", "value": values["bps"], **bps_source})

    fin_values = {rule.column: take(rule, "financials_fin") for rule in mapping.financials_fin} if symbol in mapping.fin_symbols else None
    rcept_nos = sorted({str(r["rcept_no"]) for r in rows if r.get("rcept_no")})
    return MappedPeriod(
        symbol=symbol,
        period_end=period_end,
        period_type=period_type(period_end),
        fs_div=FS_DIV_LABELS[fs_div],
        rcept_no=rcept_nos[0] if len(rcept_nos) == 1 else None,
        values=values,
        fin_values=fin_values,
        provenance=provenance,
        review=review,
        shares=shares,
    )
