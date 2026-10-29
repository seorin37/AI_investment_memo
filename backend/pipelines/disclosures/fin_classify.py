"""금융 세부 업종 판별: DART 기업개황 업종코드(KSIC) + 연결재무제표 계정 (docs/financials-kospi-plan.md 5절).

업종코드만으로는 안 된다. 지주회사 64992에 KB금융·메리츠금융지주(금융)와 LG·SK(일반)가 함께 있다.
  641          → bank        (은행)
  651·652·653  → insurance   (보험·재보험·연금)
  6612         → securities  (증권 중개 등)
  64992        → holding     예수부채나 보험수익 계정이 있을 때만. 없으면 일반 지주
  그 밖의 64~66 → other      (카드·캐피탈·자산운용 등)
업종과 계정이 어긋나면 결과는 그대로 두고 검토 사유를 남긴다 (예: 은행 코드인데 예수부채 없음).
"""

from __future__ import annotations

from dataclasses import dataclass


HOLDING_CODE = "64992"
DEPOSITS = "ifrs-full_DepositsFromCustomers"
INSURANCE_REVENUE = "ifrs-full_InsuranceRevenue"


@dataclass(frozen=True)
class Classification:
    fin_type: str | None  # None = 일반 기업
    basis: str
    review: str | None = None  # 검토 CSV에 남길 사유


def classify(induty_code: str, rows: list[dict]) -> Classification:
    code = str(induty_code or "").strip()
    ids = {r.get("account_id") for r in rows}
    has_deposits, has_insurance = DEPOSITS in ids, INSURANCE_REVENUE in ids
    evidence = ", ".join(name for name, ok in (("예수부채", has_deposits), ("보험수익", has_insurance)) if ok) or "금융 계정 없음"

    if code == HOLDING_CODE:
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
