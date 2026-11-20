"""즉석 비교 계산 (실험, 2026-11-17): 한 번 답하기(ask) 질문의 "몇 배·몇 %"를 LLM이 아니라 코드가 계산한다.

LLM은 계산하지 않는다(지침 원칙). 대신 카드 JSON의 calc에 비교할 두 값과 각각의 근거 번호만 적는다:
    "calc": [{"label": "유상증자 규모 ÷ 2025년 연간 영업이익", "op": "div",
              "a": {"value": "4조 2,087억원", "evidence_id": "E1"},
              "b": {"value": "3조 893억 2,018만 1,000원", "evidence_id": "E4"}}]
코드는 (1) 두 근거 번호가 실제 입력 근거인지, (2) 각 값의 숫자가 그 근거 글에 그대로 있는지(checks.evidence_numbers)
확인한 뒤에만 계산한다. 하나라도 어긋나면 그 계산은 버리고 이유를 남긴다 (화면에 계산값을 보이지 않는다).
op: div(a ÷ b, "약 1.36배") | pct(a ÷ b × 100, "136.2%") | change(b 대비 a 증감률, "+36.2%").
"""

from __future__ import annotations


from .checks import _ev_text, evidence_numbers, numbers

OPS = ("div", "pct", "change")
MAX_CALCS = 3


# 같은 원 단위 금액끼리 나눴는데 이 범위를 벗어나면 단위가 어긋났을 가능성이 커서 계산하지 않는다 (2026-11-17 "약 0.00배")
RATIO_RANGE = (1e-3, 1e4)


def _value(text: str) -> tuple[float, float] | None:
    """값 글 → (근거와 대조할 숫자, 계산에 쓸 원 단위 숫자). "3조 893억 2,018만 1,000원"처럼 나눠 쓴 금액은 합친 값(가장 큰 값).
    checks.numbers가 '백만원·십억원'도 원 단위로 바꿔 읽고("60,512,857백만원" → 60,512,857,000,000),
    근거 쪽 evidence_numbers도 표 머리 "(단위 : 백만원)"을 환산한 값을 넣으므로 두 값이 같다 (2026-11-19 서린님 숫자 검사 변경에 맞춤)."""
    vals = numbers(text or "")
    if not vals:
        return None
    raw = max(vals)
    return raw, raw


def _is_won(text: str) -> bool:
    return "원" in (text or "")


def _fmt(op: str, a: float, b: float) -> str:
    r = a / b
    if op == "div":
        return f"약 {r:,.2f}배"
    if op == "pct":
        return f"{r * 100:,.1f}%"
    return f"{(r - 1) * 100:+,.1f}%"


def compute(calcs: list[dict], evidence: list) -> list[dict]:
    """검증된 계산만 결과를 채운다. 각 행: {label, op, a, b, a_ref, b_ref, result, ok, reason}."""
    by_id = {e.eid: e for e in evidence}
    out = []
    for c in (calcs or [])[:MAX_CALCS]:
        row = {"label": str(c.get("label") or "").strip(), "op": c.get("op"), "ok": False, "result": "", "reason": ""}
        a, b = c.get("a") or {}, c.get("b") or {}
        row["a"], row["b"] = str(a.get("value") or ""), str(b.get("value") or "")
        ea, eb = by_id.get(str(a.get("evidence_id") or "")), by_id.get(str(b.get("evidence_id") or ""))
        if row["op"] not in OPS:
            row["reason"] = "op"
        elif ea is None or eb is None:
            row["reason"] = "evidence_id"
        else:
            row["a_ref"], row["b_ref"] = ea.candidate.ref, eb.candidate.ref
            pa, pb = _value(row["a"]), _value(row["b"])
            if pa is None or pb is None:
                row["reason"] = "no_number"
            elif round(pa[0], 6) not in evidence_numbers(_ev_text(ea)) or round(pb[0], 6) not in evidence_numbers(_ev_text(eb)):
                row["reason"] = "not_in_evidence"          # 근거에 없는 숫자로 계산하지 않는다
            elif pb[1] == 0 or (row["op"] == "change" and pb[1] < 0):
                row["reason"] = "zero_or_negative_base"
            elif _is_won(row["a"]) and _is_won(row["b"]) and not (RATIO_RANGE[0] <= abs(pa[1] / pb[1]) <= RATIO_RANGE[1]):
                row["reason"] = "unit_suspect"
            else:
                row["result"], row["ok"] = _fmt(row["op"], pa[1], pb[1]), True
        out.append(row)
    return out
