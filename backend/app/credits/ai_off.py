"""크레딧을 다 썼을 때 AI 연결 끄기 (2026-11-24 서린 님 결정).

- 잔액이 0이 되면 화면이 '충전하거나 플랜을 업그레이드하지 않으면 AI 연결 메모 N개가 모두 꺼져요' 선택 창을 띄운다.
  그동안(끄기 대기)은 매일 실행이 그 사용자 항목을 가격 조건까지 전부 건너뛴다 (app/credits/daily.py).
- 사용자가 '모두 끄기'를 고르면 turn_off_all: 사용자가 메모 하나씩 끌 때(BoardService.set_ai_link False)와 같게
  memos.ai_linked=false · ai_linked_at=NULL, 그 메모의 활성 추적 항목은 paused (지우지 않음). 다시 켤 때는 메모마다 켠다.
- 호출자의 연결·트랜잭션 안에서 돈다. commit은 호출자가 한다 (ledger와 같음).
"""

from __future__ import annotations

from sqlalchemy import text

ACTIVE_SQL = """SELECT count(*) FROM memos
WHERE user_id = :u AND ai_linked AND kind = 'note' AND deleted_at IS NULL"""


def active_ai_count(db, user_id: int) -> int:
    """지금 AI 연결이 켜진 메모 수 (선택 창의 N)."""
    return int(db.execute(text(ACTIVE_SQL), {"u": user_id}).scalar() or 0)


def turn_off_all(db, user_id: int) -> int:
    """이 사용자의 AI 연결 메모를 모두 끈다. 끈 메모 수."""
    ids = [int(r[0]) for r in db.execute(text("""UPDATE memos
        SET ai_linked = false, ai_linked_at = NULL, updated_at = now()
        WHERE user_id = :u AND ai_linked AND kind = 'note' AND deleted_at IS NULL
        RETURNING id"""), {"u": user_id}).all()]
    if ids:
        db.execute(text("""UPDATE tracking_items SET status = 'paused', updated_at = now()
            WHERE memo_id = ANY(:ids) AND status = 'active'"""), {"ids": ids})
    return len(ids)
