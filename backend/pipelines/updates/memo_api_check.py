"""메모 저장 시 분석 점검 (2026-11-11): 로컬 테스트 DB에서 BoardService를 실제 LLM으로 돌려 흐름 전체를 본다.

    PYTHONPATH=backend python -m pipelines.updates.memo_api_check            # LLM 약 3~4회 (메모당 약 $0.0075)

1) AI 켠 메모 생성 → 분석·항목·확인 질문  2) 확인 질문 답변 → 가격 항목  3) 색만 바꾸기 → 다시 분석 안 함
4) 본문 바꾸기 → 다시 분석(같은 항목 유지·없어진 항목 done·새 항목)  5) AI 끄기 → paused  6) AI 켜기(안 바뀜) → active
7) AI 끈 메모 생성 → 분석 안 함  8) LLM 실패 → 메모는 저장, analysis.status=failed
쓰기 대상은 TEST_DATABASE_URL의 로컬 테스트 DB만 (db_store.check_test_target). 공용 DB는 쓰지 않는다.
"""

from __future__ import annotations

import json
import os


def main() -> int:
    import psycopg
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.board.repository import BoardRepository
    from app.board.schemas import MemoCreate
    from app.board.service import BoardService, StaleConfirmationError
    from app.board.tracking import TrackingRepository

    from .db_store import check_test_target, finish, seed_user_stocks

    from ..common.db import load_env
    load_env()                                                  # 앱과 같이 .env를 읽는다 (서명 키·LLM 키, 값은 출력하지 않음)
    if not (os.environ.get("MEMO_CONFIRM_SECRET") or os.environ.get("AUTH_JWT_SECRET")):
        import secrets
        os.environ["MEMO_CONFIRM_SECRET"] = secrets.token_hex(32)   # 점검 실행에서만 쓰는 임의 키 (서버는 AUTH_JWT_SECRET)
        print("서명 키가 없어 이 점검 실행에서만 임의 키를 씁니다")
    dsn = os.environ.get("TEST_DATABASE_URL", "")
    target = check_test_target(dsn)
    print(f"테스트 DB: {target}")
    pg = psycopg.connect(dsn)
    uid = seed_user_stocks(pg, ["005930", "000660", "035420", "105560"])
    finish(pg)
    url = dsn.replace("postgresql://", "postgresql+psycopg://", 1) if dsn.startswith("postgresql://") else dsn
    session = sessionmaker(bind=create_engine(url), expire_on_commit=False)()
    calls = {"n": 0}

    from app.board.analysis import default_llm
    real = default_llm()

    def counting(prompt: str) -> str:
        calls["n"] += 1
        return real(prompt)

    svc = BoardService(BoardRepository(session), TrackingRepository(session), llm_factory=lambda: counting)
    show = lambda tag, out: print(f"\n[{tag}] memo {out['id']} · analysis " + json.dumps(
        {k: v for k, v in (out.get("analysis") or {}).items() if k != "confirmations"}, ensure_ascii=False, default=str)
        + f" · 확인 질문 {len((out.get('analysis') or {}).get('confirmations') or [])}개 · price_conditions {out['price_conditions']}")

    body = "HBM 관련 소식 나오면 알려줘.\n고점에서 20% 빠지면 알려줘.\n배당 언제 나오는지도 궁금함."
    m = svc.create_memo(uid, "005930", MemoCreate(title="점검 메모", body=body, ai_linked=True))
    show("1 생성 AI 켬", m)
    mid = int(m["id"])
    for c in m["analysis"]["confirmations"]:
        print(f"  확인 질문 #{c['sentence_index']} {c['question']} · 선택지 " +
              ", ".join(f"{o['item']['description']}({o.get('status')})" for o in c["options"]))
    opts = [o for c in m["analysis"]["confirmations"] for o in c["options"]]
    if opts:
        out = svc.confirm(uid, mid, opts[0]["option_id"])
        show("2 확인 답변", out)
        try:
            svc.confirm(uid, mid, opts[0]["option_id"][:-2] + "00")
        except Exception as exc:
            print(f"  변조한 선택지 → {type(exc).__name__}")
    before = calls["n"]
    show("3 색만 바꿈", svc.update(uid, mid, {"color": "blue"}))
    print(f"  LLM 호출 {calls['n'] - before}회")
    out = svc.update(uid, mid, {"body": "HBM 관련 소식 나오면 알려줘.\n고점에서 20% 빠지면 알려줘.\n파운드리 수주 소식도 보고 싶어."})
    show("4 본문 바꿈", out)
    if opts:
        try:
            svc.confirm(uid, mid, opts[0]["option_id"])
        except StaleConfirmationError as exc:
            print(f"  옛 버전 선택지 → 409 ({exc})")
    show("5 AI 끔", svc.set_ai_link(uid, mid, False))
    before = calls["n"]
    show("6 AI 켬(안 바뀜)", svc.set_ai_link(uid, mid, True))
    print(f"  LLM 호출 {calls['n'] - before}회")
    show("7 AI 끈 메모 생성", svc.create_memo(uid, "000660", MemoCreate(title="AI 끔", body="하닉 실적 발표 보기", ai_linked=False)))

    def broken(prompt: str) -> str:
        raise TimeoutError("시험용 실패")
    bad = BoardService(BoardRepository(session), TrackingRepository(session), llm_factory=lambda: broken)
    out = bad.create_memo(uid, "035420", MemoCreate(title="실패 시험", body="네이버 웹툰 실적 영향이 궁금하다", ai_linked=True))
    show("8 LLM 실패", out)
    print(f"  메모는 저장됨: {svc.get(uid, int(out['id']))['id'] == out['id']}")
    print(f"\nLLM 호출 합계 {calls['n']}회 (실패 시험 제외)")
    session.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
