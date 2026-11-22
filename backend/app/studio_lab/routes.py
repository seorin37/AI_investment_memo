"""POST /api/v1/studio/lab: 투자 실험 실행 (LLM 답이 나왔을 때만 크레딧 lab 차감)."""
from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth.routes import get_current_user
from app.credits import ledger
from app.db import get_read_db, get_session
from app.marketdata.repository import MarketDataRepository
from app.marketdata.service import MarketDataService

from .lab import run_lab
from .llm import openai_call
from .prompt import StockCtx

log = logging.getLogger("studio_lab")
router = APIRouter(prefix="/api/v1/studio", tags=["studio-lab"])

MACRO_TEXT = {
    "USD_KRW": ("원/달러 환율", lambda v: f"{v:,.2f}원"),
    "WTI_SPOT": ("국제유가(WTI)", lambda v: f"{v:.1f}달러"),
    "KR_POLICY_RATE": ("한국 기준금리", lambda v: f"{v:.2f}%"),
    "US_TREASURY_10Y": ("미국 10년물 국채금리", lambda v: f"{v:.2f}%"),
}


class LabRequest(BaseModel):
    stock_code: str = Field(pattern=r"^[0-9A-Z]{6}$")
    dirs: list[Literal["상승", "유지", "하락"]] = Field(min_length=4, max_length=4)


def _stock(db: Session, code: str) -> StockCtx | None:
    row = db.execute(text("""SELECT btrim(symbol) AS code, name, sector::text AS sector, description
        FROM stocks WHERE symbol = :code"""), {"code": code}).mappings().first()
    if row is None:
        return None
    return StockCtx(row["code"], row["name"], row["sector"] == "financial", row["description"] or "")


def _macro(db: Session) -> tuple[list[tuple[str, str]], str]:
    """지표가 없어도 실험은 돌아가야 하므로 실패하면 빈 값으로 둔다."""
    try:
        overview = MarketDataService(MarketDataRepository(db)).macro()
    except Exception as exc:
        db.rollback()
        log.warning("lab macro unavailable: %s", type(exc).__name__)
        return [], ""
    values = []
    for item in overview["indicators"]:
        if item["key"] in MACRO_TEXT:
            label, render = MACRO_TEXT[item["key"]]
            values.append((label, render(float(item["value"]))))
    return values, overview.get("as_of") or ""


@router.post("/lab")
def post_lab(body: LabRequest, current: dict = Depends(get_current_user), db: Session = Depends(get_read_db)):
    if all(direction == "유지" for direction in body.dirs):
        raise HTTPException(422, detail="바꿀 조건을 하나 이상 골라 주세요.")
    try:
        user_id = int(current["id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(401, detail="유효하지 않은 인증 사용자입니다.") from exc
    stock = _stock(db, body.stock_code)
    if stock is None:
        raise HTTPException(404, detail="종목을 찾을 수 없습니다.")
    macro, as_of = _macro(db)
    db.rollback()  # LLM을 기다리는 동안 DB 트랜잭션을 잡고 있지 않는다

    cost = ledger.cost("lab")
    with get_session() as credit_db:
        ledger.refresh(credit_db, user_id)
        balance = ledger.balance(credit_db, user_id)
    if balance < cost:
        raise HTTPException(402, detail="크레딧이 부족해요. 충전하거나 다음 달에 다시 실험해 주세요.")

    result = run_lab(stock, list(body.dirs), openai_call, macro=macro, as_of=as_of)
    meta = result.pop("_meta")
    log.info("lab %s source=%s tries=%s usage=%s", stock.stock_code, result["source"], meta["tries"], meta["usage"])
    charged = 0
    if result["source"] == "llm":
        try:
            with get_session() as credit_db:
                charged = ledger.spend(credit_db, user_id, cost, "lab")
        except Exception:  # 이미 만든 답은 사용자에게 돌려주고 차감 실패만 기록한다
            log.exception("lab credit charge failed user=%s", user_id)
    return {**result, "credits_used": charged}
