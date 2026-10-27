"""즉시 답변 (LLM 프롬프트 지침 v1.0, 2장).

호출 전 분기는 규칙으로 한다 (LLM 없음):
  advice          사야 하나/팔까/손절할까   → 고정 거절 문구
  forecast        어디까지 오를까/목표가     → 고정 거절 문구
  price_now       현재가·수익률              → 코드가 가격 DB를 조회해 거래일과 함께 답한다
  financial_value 매출·영업이익 등 단순 수치 → 코드가 재무 DB를 조회해 기간·연결/별도와 함께 답한다 (DB 조회는 아직 없음)
  recent          공시·뉴스 정리, 원인 질문  → 근거를 모아 LLM(answer_question)
LLM 답변은 코드 검사를 통과해야 하고, 실패하거나 cannot_answer면 reason_code에 맞는 고정 문구를 쓴다.
저장 위치(즉시 답변 테이블, 근거 연결)는 팀에서 아직 정하지 않았다 (지침서 5). 이 모듈은 저장하지 않는다.
"""

from __future__ import annotations

import re
from typing import Callable

from .checks import check_answer
from .fixed import DECLINE_ADVICE, DECLINE_FORECAST, FIXED_BY_REASON, NO_DATA
from .judge import build_instant_prompt, parse_answer
from .models import CreditsExhausted, Evidence

_ADVICE = re.compile(r"(사야|살까|사도 (돼|되|될까)|팔아야|팔까|팔 때|매수|매도|손절|물타|추매|들어가도|담아도|홀딩)")
_FORECAST = re.compile(r"(오를까|내릴까|떨어질까|올라갈까|내려갈까|반등|전망|목표가|목표 주가|얼마까지|예상 주가|앞으로.*(주가|가격))")
_PRICE_NOW = re.compile(r"(지금|현재|오늘|어제).{0,6}(얼마|가격|주가|시세|종가)|(주가|가격|종가)가? 얼마|수익률")
_FINANCIAL = re.compile(r"(매출|영업이익|순이익|당기순이익)(이|은|는|이?가)? ?(얼마|몇)")


def classify(question: str) -> str:
    q = (question or "").strip()
    if _ADVICE.search(q):
        return "advice"
    if _FORECAST.search(q):
        return "forecast"
    if _PRICE_NOW.search(q):
        return "price_now"
    if _FINANCIAL.search(q):
        return "financial_value"
    return "recent"


def answer_fixed(kind: str) -> str | None:
    return {"advice": DECLINE_ADVICE, "forecast": DECLINE_FORECAST}.get(kind)


def answer_price_now(close: float | None, trade_date: str | None) -> str:
    if close is None or not trade_date:
        return NO_DATA
    return f"{trade_date} 종가는 {close:,.0f}원이에요. 실시간 가격은 아니에요."


def answer_question(question: str, evidence: list[Evidence], call: Callable[[str], str], banned: list[str],
                    cfg: dict | None = None, *, company_name: str, stock_code: str, question_type: str, as_of: str,
                    memo_revision_id: str = "") -> dict:
    """근거를 받아 LLM으로 답한다. 반환: {"status": answer|fixed, "text": [...], "sources": [(eid, fact)], "reason_code", "fail_codes"}.
    CreditsExhausted는 그대로 올린다. 근거가 없으면 LLM을 부르지 않고 자료 부족 문구를 쓴다."""
    if not evidence:
        return {"status": "fixed", "text": [NO_DATA], "sources": [], "reason_code": "insufficient_evidence", "fail_codes": []}
    prompt = build_instant_prompt(question, evidence, company_name=company_name, stock_code=stock_code,
                                  question_type=question_type, as_of=as_of, memo_revision_id=memo_revision_id)
    try:
        raw = call(prompt)
    except CreditsExhausted:
        raise
    except Exception as exc:
        return {"status": "fixed", "text": [NO_DATA], "sources": [], "reason_code": "insufficient_evidence",
                "fail_codes": [f"CALL_FAILED:{type(exc).__name__}"]}
    ans = parse_answer(raw)
    if ans is None:
        return {"status": "fixed", "text": [NO_DATA], "sources": [], "reason_code": "insufficient_evidence",
                "fail_codes": ["FORMAT_PARSE"]}
    codes = check_answer(ans, evidence, banned, cfg)
    if ans.status == "cannot_answer" and not codes:
        return {"status": "fixed", "text": [FIXED_BY_REASON.get(ans.reason_code, NO_DATA)], "sources": [],
                "reason_code": ans.reason_code, "fail_codes": []}
    if codes:
        return {"status": "fixed", "text": [NO_DATA], "sources": [], "reason_code": "insufficient_evidence", "fail_codes": codes}
    return {"status": "answer", "text": [_TAGS.sub("", s).strip() for s in ans.answer], "sources": ans.evidence,
            "reason_code": "none", "fail_codes": []}


_TAGS = re.compile(r"\s*\[E\d+\]")
