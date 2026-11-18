"""금융 세부 업종 판별: DART 기업개황 업종코드(KSIC) + 연결재무제표 계정 (docs/financials-kospi-plan.md 5절).

업종코드만으로는 안 된다. 지주회사 64992에 KB금융·메리츠금융지주(금융)와 LG·SK(일반)가 함께 있다.
  641          → bank        (은행)
  651·652·653  → insurance   (보험·재보험·연금)
  6612         → securities  (증권 중개 등)
  64992·649    → holding     예수부채나 보험수익 계정이 있을 때만. 없으면 일반 지주
                             (649는 DART가 세분류 없이 3자리로 준 지주회사 코드: 효성·HDC·오리온홀딩스 등)
  그 밖의 64~66 → other      (카드·캐피탈·자산운용 등)
업종과 계정이 어긋나면 결과는 그대로 두고 검토 사유를 남긴다 (예: 은행 코드인데 예수부채 없음).
코드만으로 판별이 틀리는 종목은 SYMBOL_OVERRIDES에 근거와 함께 고정한다.
"""

from __future__ import annotations

from dataclasses import dataclass


HOLDING_CODES = ("64992", "649")
DEPOSITS = "ifrs-full_DepositsFromCustomers"
INSURANCE_REVENUE = "ifrs-full_InsuranceRevenue"

# 종목코드 → (fin_type, 근거). fin_type None = 일반 기업
SYMBOL_OVERRIDES: dict[str, tuple[str | None, str]] = {
    "030210": ("securities", "다올투자증권: 업종코드가 661(3자리)로만 와서 증권 규칙(6612)에 안 걸림"),
    "487570": (None, "HS효성: 업종코드 64999지만 금융 계정 없는 사업 지주회사"),
}


@dataclass(frozen=True)
class Classification:
    fin_type: str | None  # None = 일반 기업
    basis: str
    review: str | None = None  # 검토 CSV에 남길 사유


def classify(induty_code: str, rows: list[dict], symbol: str = "") -> Classification:
    code = str(induty_code or "").strip()
    if symbol in SYMBOL_OVERRIDES:
        fin_type, reason = SYMBOL_OVERRIDES[symbol]
        return Classification(fin_type, f"종목 고정 (업종코드 {code or '없음'}): {reason}")
    ids = {r.get("account_id") for r in rows}
    has_deposits, has_insurance = DEPOSITS in ids, INSURANCE_REVENUE in ids
    evidence = ", ".join(name for name, ok in (("예수부채", has_deposits), ("보험수익", has_insurance)) if ok) or "금융 계정 없음"

    if code in HOLDING_CODES:
        if has_deposits or has_insurance:
            return Classification("holding", f"지주회사 {code} + {evidence}")
        return Classification(None, f"지주회사 {code}, {evidence} → 일반 지주")
    if code.startswith("641"):
        review = None if has_deposits else "은행 업종코드인데 예수부채 계정이 없음"
        return Classification("bank", f"업종코드 {code}", review)
    if code[:3] in ("651", "652", "653"):
        review = None if has_insurance else "보험 업종코드인데 보험수익 계정이 없음"
        return Classification("insurance", f"업종코드 {code}", review)
    if code.startswith("6612"):
        return Classification("securities", f"업종코드 {code}")
    if code[:2] in ("64", "65", "66"):
        return Classification("other", f"업종코드 {code}")
    if has_deposits or has_insurance:
        return Classification(None, f"업종코드 {code or '없음'}", f"일반 업종코드인데 {evidence} 계정이 있음")
    return Classification(None, f"업종코드 {code or '없음'}")
