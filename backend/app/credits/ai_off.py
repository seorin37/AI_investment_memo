"""크레딧을 다 썼을 때 AI 연결 끄기 (2026-11-24 서린 님 결정).

- 잔액이 0이 되면 화면이 '충전하거나 플랜을 업그레이드하지 않으면 AI 연결 메모 N개가 모두 꺼져요' 선택 창을 띄운다.
  그동안(끄기 대기)은 매일 실행이 그 사용자 항목을 가격 조건까지 전부 건너뛴다 (app/credits/daily.py).
- 사용자가 '모두 끄기'를 고르면 turn_off_all: 사용자가 메모 하나씩 끌 때(BoardService.set_ai_link False)와 같게
  memos.ai_linked=false · ai_linked_at=NULL, 그 메모의 활성 추적 항목은 paused (지우지 않음). 다시 켤 때는 메모마다 켠다.
- 고르지 않은 채 사용자별 갱신일이 지나면 ledger.refresh가 turn_off_all(auto=True): 같은 방식으로 끄고 memos.ai_auto_off_at(0026)에
  끈 시각을 적는다 → 화면이 '지난 기간 AI 사용량을 다 써서 AI 연결 메모 N개가 꺼졌어요' 안내를 한 번 띄운다 (auto_off_count · clear_notice).
- 호출자의 연결·트랜잭션 안에서 돈다. commit은 호출자가 한다 (ledger와 같음).
"""

from __future__ import annotations

from sqlalchemy import text

ACTIVE_SQL = """SELECT count(*) FROM memos
WHERE user_id = :u AND ai_linked AND kind = 'note' AND deleted_at IS NULL"""


def active_ai_count(db, user_id: int) -> int:
    """지금 AI 연결이 켜진 메모 수 (선택 창의 N)."""
    return int(db.execute(text(ACTIVE_SQL), {"u": user_id}).scalar() or 0)


def turn_off_all(db, user_id: int, auto: bool = False) -> int:
    """이 사용자의 AI 연결 메모를 모두 끈다. 끈 메모 수. auto=True(갱신일 자동 끄기)면 ai_auto_off_at에 끈 시각을 적는다."""
    ids = [int(r[0]) for r in db.execute(text("""UPDATE memos
        SET ai_linked = false, ai_linked_at = NULL, updated_at = now(),
            ai_auto_off_at = CASE WHEN :auto THEN now() ELSE ai_auto_off_at END
        WHERE user_id = :u AND ai_linked AND kind = 'note' AND deleted_at IS NULL
        RETURNING id"""), {"u": user_id, "auto": auto}).all()]
    if ids:
        db.execute(text("""UPDATE tracking_items SET status = 'paused', updated_at = now()
            WHERE memo_id = ANY(:ids) AND status = 'active'"""), {"ids": ids})
    return len(ids)


def auto_off_count(db, user_id: int) -> int:
    """갱신일에 자동으로 꺼졌고 아직 안내를 확인하지 않은(다시 켜지도 않은) 메모 수."""
    return int(db.execute(text("""SELECT count(*) FROM memos WHERE user_id = :u AND ai_auto_off_at IS NOT NULL
        AND NOT ai_linked AND deleted_at IS NULL"""), {"u": user_id}).scalar() or 0)


def clear_notice(db, user_id: int) -> int:
    """자동 꺼짐 안내 확인: 표시만 지운다 (메모는 꺼진 채)."""
    return db.execute(text("UPDATE memos SET ai_auto_off_at = NULL WHERE user_id = :u AND ai_auto_off_at IS NOT NULL"),
                      {"u": user_id}).rowcount


def should_auto_off(granted: int, had_prior_period: bool, left_before: int) -> bool:
    """갱신일 자동 끄기 조건: 이번 호출에서 새 기간 기본량을 처음 줬고(기간마다 한 번), 지난 기간이 있었고(첫 지급 X),
    만료 처리 전 남은 크레딧이 0 = 지난 기간을 다 쓴 채 끝남 (월 크레딧이 남아 만료되거나 산 크레딧이 남았으면 X)."""
    return granted > 0 and had_prior_period and left_before <= 0
