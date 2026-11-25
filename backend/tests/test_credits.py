"""크레딧 (2026-11-20, 0019). 실제 SQL이 핵심이라 로컬 테스트 DB(TEST_DATABASE_URL, 0019 이상)에서 돈다. 없으면 건너뛴다."""

from __future__ import annotations

import os
import re
from datetime import datetime

import pytest
from sqlalchemy import create_engine, text

from app.credits import ledger

SEOUL = ledger.SEOUL
EMAIL = "credits-test@example.test"
SYMBOL = "C00001"
NOV = datetime(2026, 11, 20, 12, 0, tzinfo=SEOUL)     # 첫 사용 → 시작점 11/20, 주기 11/20~12/19
MID = datetime(2026, 12, 2, 9, 0, tzinfo=SEOUL)       # 같은 주기 중간
DEC = datetime(2026, 12, 20, 9, 0, tzinfo=SEOUL)      # 다음 주기 (12/20 0시 시작)


def _url():
    url = os.getenv("TEST_DATABASE_URL", "")
    if not url or "test" not in url:
        pytest.skip("로컬 테스트 DB(TEST_DATABASE_URL)가 없습니다")
    return url


def _engine():
    return create_engine(re.sub(r"^postgres(ql)?(\+\w+)?://", "postgresql+psycopg://", _url()))


def _cleanup(c):
    c.execute(text("DELETE FROM memos WHERE symbol = :s"), {"s": SYMBOL})
    c.execute(text("DELETE FROM users WHERE email = :e"), {"e": EMAIL})
    c.execute(text("DELETE FROM stocks WHERE symbol = :s"), {"s": SYMBOL})


@pytest.fixture()
def db():
    engine = _engine()
    with engine.connect() as c:
        tx = c.begin()
        if c.execute(text("SELECT to_regclass('credit_grants')")).scalar() is None:
            pytest.skip("0019 전 DB")
        uid = c.execute(text("INSERT INTO users (email, display_name) VALUES (:e, '크레딧') RETURNING id"), {"e": EMAIL}).scalar()
        yield c, uid
        tx.rollback()
    engine.dispose()


def test_monthly_grant_once_and_usage(db):
    c, uid = db
    assert ledger.ensure_monthly(c, uid, NOV) == 20                 # free 기본량 (configs/credits.yaml)
    assert ledger.ensure_monthly(c, uid, NOV) == 0                  # 같은 주기 두 번 X
    assert ledger.ensure_monthly(c, uid, MID) == 0                  # 중간 접속도 다시 시작 X
    u = ledger.usage(c, uid, NOV)
    assert (u.balance, u.used, u.usage_percent, u.paused) == (20, 0, 0, False)
    assert u.to_dict()["renew_label"] == "12.19 갱신"                # 시작점 11/20 기준 (달력 월 아님)


def test_spend_monthly_first_then_purchase_and_never_negative(db):
    c, uid = db
    ledger.grant_purchase(c, uid, 10, "pay-1", NOV)
    assert ledger.spend(c, uid, 25, "card", "tracking_update", 1, NOV) == 25
    rows = dict(c.execute(text("SELECT source, remaining FROM credit_grants WHERE user_id = :u"), {"u": uid}).all())
    assert rows == {"monthly": 0, "purchase": 5}                    # 기본량(20) 먼저, 산 크레딧은 나중
    assert ledger.spend(c, uid, 100, "answer", "tracking_update", 2, NOV) == 5    # 잔액까지만
    assert ledger.balance(c, uid, NOV) == 0
    assert ledger.usage(c, uid, NOV).paused is True
    assert ledger.spend(c, uid, 1, "card", "tracking_update", 1, NOV) == 0        # 같은 카드는 한 번만


def test_month_change_expires_monthly_keeps_purchase(db):
    c, uid = db
    ledger.ensure_monthly(c, uid, NOV)
    ledger.grant_purchase(c, uid, 10, "pay-2", NOV)
    ledger.spend(c, uid, 4, "card", "tracking_update", 3, NOV)
    assert ledger.usage(c, uid, MID).balance == 26                   # 같은 주기 중간: 그대로
    u = ledger.usage(c, uid, DEC)                                    # 다음 주기: 앞 기본량 16 만료, 새 기본량 20, 산 크레딧 10 이월
    assert u.balance == 30 and u.used == 0
    assert c.execute(text("SELECT -sum(delta) FROM credit_ledger WHERE user_id = :u AND reason = 'expire'"), {"u": uid}).scalar() == 16
    assert ledger.grant_purchase(c, uid, 10, "pay-2", DEC) is None   # 같은 결제번호 두 번 X


def _seed_items(c):
    c.execute(text("INSERT INTO stocks (symbol, name, market) VALUES (:s, '크레딧전자', 'KOSPI') ON CONFLICT DO NOTHING"), {"s": SYMBOL})
    uid = c.execute(text("INSERT INTO users (email, display_name) VALUES (:e, '크레딧') RETURNING id"), {"e": EMAIL}).scalar()
    mid = c.execute(text("""INSERT INTO memos (user_id, symbol, kind, title, content, ai_linked)
        VALUES (:u, :s, 'note', 't', 'b', true) RETURNING id"""), {"u": uid, "s": SYMBOL}).scalar()
    ids = {}
    for typ, desc, price in (("topic", "소식", None), ("ask", "얼마야", None), ("price_below", "7만원", 70000)):
        ids[typ] = c.execute(text("""INSERT INTO tracking_items (memo_id, type, description, price_threshold)
            VALUES (:m, CAST(:t AS tracking_type), :d, :p) RETURNING id"""), {"m": mid, "t": typ, "d": desc, "p": price}).scalar()
    return uid, ids


def test_daily_skips_paused_users_and_charges_cards():
    from app.credits.daily import charge_run, eligible_item_ids
    engine = _engine()
    url = _url()
    try:
        with engine.begin() as c:
            if c.execute(text("SELECT to_regclass('credit_grants')")).scalar() is None:
                pytest.skip("0019 전 DB")
            _cleanup(c)
            uid, ids = _seed_items(c)
        keep, info = eligible_item_ids(url, (SYMBOL,))
        assert sorted(keep) == sorted(str(i) for i in ids.values()) and info["paused_users"] == []
        with engine.begin() as c:
            ups = [c.execute(text("""INSERT INTO tracking_updates (tracking_item_id, type, title, summary)
                VALUES (:i, CAST(:t AS update_type), 'x', 'y') RETURNING id"""), {"i": ids[k], "t": t}).scalar()
                   for k, t in (("topic", "news"), ("ask", "answer"))]
            c.execute(text("UPDATE credit_grants SET remaining = 1 WHERE user_id = :u"), {"u": uid})   # 잔액 1
        out = charge_run(url, ups)
        assert out == {"cards": 2, "charged": 1, "short": 1}       # 잔액까지만 빼고 모자란 양 기록
        assert charge_run(url, ups) == {"cards": 1, "charged": 0, "short": 1}   # 다시 돌려도 이미 뺀 카드는 안 뺌 (못 뺀 카드만 다시 시도)
        keep, info = eligible_item_ids(url, (SYMBOL,))
        assert keep == [] and info["paused_users"] == [uid]       # 2026-11-24: 잔액 0이면 가격 조건까지 전부 멈춘다
    finally:
        with engine.begin() as c:
            _cleanup(c)
        engine.dispose()


def test_usage_api():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import Session

    from app.auth.routes import get_current_user
    from app.credits.routes import router
    from app.db import get_db
    engine = _engine()
    try:
        with engine.begin() as c:
            if c.execute(text("SELECT to_regclass('credit_grants')")).scalar() is None:
                pytest.skip("0019 전 DB")
            _cleanup(c)
            uid = c.execute(text("INSERT INTO users (email, display_name) VALUES (:e, '크레딧') RETURNING id"), {"e": EMAIL}).scalar()

        def session():
            with Session(engine) as s:
                yield s
                s.commit()
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_db] = session
        app.dependency_overrides[get_current_user] = lambda: {"id": str(uid)}
        body = TestClient(app).get("/api/v1/me/usage").json()
        assert body["balance"] == 20 and body["usage_percent"] == 0 and body["paused"] is False and "갱신" in body["renew_label"]
        assert body["ai_memo_count"] == 0
        assert TestClient(app).post("/api/v1/me/ai-off").json() == {"turned_off": 0}
    finally:
        with engine.begin() as c:
            _cleanup(c)
        engine.dispose()


def test_turn_off_all_pauses_items_and_keeps_memo():
    """2026-11-24 선택 창 '모두 끄기': 메모는 남고 AI 연결만 꺼짐, 활성 항목은 멈춤(지우지 않음)."""
    from app.credits import ai_off
    engine = _engine()
    try:
        with engine.begin() as c:
            if c.execute(text("SELECT to_regclass('credit_grants')")).scalar() is None:
                pytest.skip("0019 전 DB")
            _cleanup(c)
            uid, ids = _seed_items(c)
            assert ai_off.active_ai_count(c, uid) == 1
            assert ai_off.turn_off_all(c, uid) == 1
            assert ai_off.active_ai_count(c, uid) == 0
            memo = c.execute(text("SELECT ai_linked, ai_linked_at, deleted_at FROM memos WHERE user_id = :u"), {"u": uid}).one()
            assert memo == (False, None, None)
            st = {r[0] for r in c.execute(text("SELECT status::text FROM tracking_items WHERE id = ANY(:i)"), {"i": list(ids.values())})}
            assert st == {"paused"}
            assert ai_off.turn_off_all(c, uid) == 0                  # 다시 불러도 그대로
    finally:
        with engine.begin() as c:
            _cleanup(c)
        engine.dispose()


def test_should_auto_off_rule():
    """갱신일 자동 끄기 조건 (2026-11-24): 새 기간을 처음 줬고 · 지난 기간이 있었고 · 지난 기간을 0으로 끝냄."""
    from app.credits.ai_off import should_auto_off
    assert should_auto_off(30, True, 0) is True
    assert should_auto_off(0, True, 0) is False          # 이미 이번 기간을 받음 (같은 기간 두 번째 호출)
    assert should_auto_off(30, False, 0) is False        # 첫 지급 (가입 직후)
    assert should_auto_off(30, True, 5) is False         # 월 크레딧이 남아 만료되거나 산 크레딧이 남음


def _seed_memo(c, uid):
    c.execute(text("INSERT INTO stocks (symbol, name, market) VALUES (:s, '크레딧전자', 'KOSPI') ON CONFLICT DO NOTHING"), {"s": SYMBOL})
    mid = c.execute(text("""INSERT INTO memos (user_id, symbol, kind, title, content, ai_linked)
        VALUES (:u, :s, 'note', 't', 'b', true) RETURNING id"""), {"u": uid, "s": SYMBOL}).scalar()
    c.execute(text("""INSERT INTO tracking_items (memo_id, type, description) VALUES (:m, 'topic', '소식')"""), {"m": mid})
    return mid


def test_renewal_turns_off_ai_when_period_ended_at_zero(db):
    """지난 기간을 0으로 끝낸 채 갱신 → AI 연결 메모 모두 끔 + ai_auto_off_at. 두 번 불러도 한 번만. 안내 확인하면 표시만 지움."""
    from app.credits import ai_off
    c, uid = db
    if c.execute(text("SELECT 1 FROM information_schema.columns WHERE table_name = 'memos' AND column_name = 'ai_auto_off_at'")).first() is None:
        pytest.skip("0026 전 DB")
    assert ledger.refresh(c, uid, NOV) == 0                           # 첫 지급: 끄지 않음
    mid = _seed_memo(c, uid)
    ledger.spend(c, uid, 20, "card", "tracking_update", 1, NOV)        # 다 씀
    assert ledger.refresh(c, uid, DEC) == 1                           # 갱신일: 자동으로 끔
    assert ledger.refresh(c, uid, DEC) == 0                           # 같은 기간 두 번째: 그대로
    linked, auto = c.execute(text("SELECT ai_linked, ai_auto_off_at FROM memos WHERE id = :m"), {"m": mid}).one()
    assert linked is False and auto is not None
    assert ai_off.auto_off_count(c, uid) == 1
    assert ai_off.clear_notice(c, uid) == 1 and ai_off.auto_off_count(c, uid) == 0
    assert c.execute(text("SELECT ai_linked FROM memos WHERE id = :m"), {"m": mid}).scalar() is False   # 메모는 꺼진 채


def test_renewal_keeps_ai_when_credits_left(db):
    c, uid = db
    ledger.refresh(c, uid, NOV)
    mid = _seed_memo(c, uid)
    ledger.spend(c, uid, 10, "card", "tracking_update", 1, NOV)        # 10 남은 채 끝남 → 만료돼도 다 쓴 게 아님
    assert ledger.refresh(c, uid, DEC) == 0
    assert c.execute(text("SELECT ai_linked FROM memos WHERE id = :m"), {"m": mid}).scalar() is True


def test_plan_catalog_matches_config():
    """2026-11-25 확정안 ⑧: 요금제 숫자는 configs/credits.yaml 한 곳."""
    from app.credits.plans import catalog
    c = catalog()
    by = {p["code"]: p for p in c["plans"]}
    assert [p["code"] for p in c["plans"]] == ["free", "plus", "pro"]
    assert (by["plus"]["price"], by["plus"]["first_month_price"], by["plus"]["monthly_credits"], by["plus"]["tracking_items"]) == (14900, 7450, 80, 30)
    assert (by["pro"]["price"], by["pro"]["monthly_credits"], by["pro"]["tracking_items"]) == (29900, 160, 100)
    assert (by["free"]["price"], by["free"]["first_month_price"], by["free"]["monthly_credits"], by["free"]["tracking_items"]) == (0, None, 20, 5)
    assert c["credit_packs"] == [{"credits": 50, "price": 9300}]
    assert c["costs"]["report"] == 3 and c["costs"]["lab"] == 1 and c["costs"]["answer_unverified"] == 0
    assert ledger.cost("answer_unverified") == 0
