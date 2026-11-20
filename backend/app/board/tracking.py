"""메모의 추적 항목 저장 (2026-11-11): tracking_items · tracking_item_revisions. 분석은 analysis.py.

- 항목 맞추기 (결정): 같은 항목(종류·설명·조건가)은 그대로 둔다, 새 분석에 없는 항목은 done, 새 항목은 만든다 (버전 1번).
  확인 질문 답변으로 만든 가격 항목은 그 문장이 다시 확인 질문으로 남아 있고 같은 선택지가 있으면 그대로 둔다.
- AI 끄기: active → paused. AI 켜기: 마지막 분석 뒤 메모가 바뀌었으면 다시 분석(호출자), 아니면 paused → active.
- 메모 응답의 price_conditions·unread_updates도 여기서 읽는다 (가격 항목 · 읽지 않은 카드 수).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

PRICE_WINDOW_SQL = """SELECT trade_date, high, low, close FROM prices_daily
WHERE symbol = :symbol ORDER BY trade_date DESC LIMIT 260"""         # pipelines.updates.confirm.PRICE_WINDOW_SQL과 같다


def item_key(item: dict) -> tuple:
    threshold = item.get("price_threshold")
    return (item["type"], " ".join((item.get("description") or "").split()),
            None if threshold is None else int(float(threshold)))


class TrackingRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ---------------------------------------------------------------- 읽기
    def items(self, memo_id: int, statuses=("active", "paused")) -> list[dict[str, Any]]:
        rows = self.db.execute(text("""
            SELECT ti.id, ti.status::text AS status, COALESCE(r.type, ti.type)::text AS type,
                   COALESCE(r.description, ti.description) AS description, COALESCE(r.keywords, ti.keywords) AS keywords,
                   COALESCE(r.price_threshold, ti.price_threshold) AS price_threshold, ti.last_checked_at, r.created_at AS revised_at
            FROM tracking_items ti
            LEFT JOIN LATERAL (SELECT type, description, keywords, price_threshold, created_at FROM tracking_item_revisions
                               WHERE tracking_item_id = ti.id ORDER BY revision_no DESC LIMIT 1) r ON true
            WHERE ti.memo_id = :memo_id AND ti.status::text = ANY(:statuses)
            ORDER BY ti.id"""), {"memo_id": memo_id, "statuses": list(statuses)}).mappings().all()
        return [dict(r) for r in rows]

    def latest_revision(self, memo_id: int) -> dict[str, Any] | None:
        row = self.db.execute(text("""SELECT id, revision_no, title, content, created_at FROM memo_revisions
            WHERE memo_id = :memo_id ORDER BY revision_no DESC LIMIT 1"""), {"memo_id": memo_id}).mappings().first()
        return dict(row) if row else None

    def changed_since_analysis(self, memo_id: int) -> bool:
        """마지막 분석(그 메모 항목 버전 중 가장 늦은 것) 뒤 메모 버전이 새로 생겼는가. 항목이 하나도 없으면 True(판단할 수 없음)."""
        row = self.db.execute(text("""
            SELECT (SELECT max(mr.created_at) FROM memo_revisions mr WHERE mr.memo_id = :memo_id),
                   (SELECT max(r.created_at) FROM tracking_item_revisions r JOIN tracking_items ti ON ti.id = r.tracking_item_id
                    WHERE ti.memo_id = :memo_id)"""), {"memo_id": memo_id}).first()
        memo_at, analyzed_at = row
        return analyzed_at is None or (memo_at is not None and memo_at > analyzed_at)

    def stock_name(self, symbol: str) -> str:
        row = self.db.execute(text("SELECT name FROM stocks WHERE symbol = :symbol"), {"symbol": symbol}).first()
        return row[0] if row else symbol

    def price_window(self, symbol: str) -> list[tuple]:
        rows = self.db.execute(text(PRICE_WINDOW_SQL), {"symbol": symbol}).all()
        return [(d, float(h), float(lo), float(c)) for d, h, lo, c in rows]

    def price_conditions(self, memo_id: int) -> list[dict[str, Any]]:
        """계약의 Memo.price_conditions: 가격 항목마다 {id, direction, price, tracking, status(waiting|reached|paused), reached_at}."""
        rows = self.db.execute(text("""
            SELECT ti.id, ti.status::text AS status, COALESCE(r.type, ti.type)::text AS type,
                   COALESCE(r.price_threshold, ti.price_threshold) AS price,
                   (SELECT max(tu.created_at) FROM tracking_updates tu WHERE tu.tracking_item_id = ti.id
                      AND tu.type = 'price_condition' AND tu.price_state = 'reached'
                      AND tu.tracking_revision_id IS NOT DISTINCT FROM r.id) AS reached_at
            FROM tracking_items ti
            LEFT JOIN LATERAL (SELECT id, type, price_threshold FROM tracking_item_revisions
                               WHERE tracking_item_id = ti.id ORDER BY revision_no DESC LIMIT 1) r ON true
            WHERE ti.memo_id = :memo_id AND ti.status::text IN ('active', 'paused')
              AND COALESCE(r.type, ti.type)::text IN ('price_below', 'price_above')
            ORDER BY ti.id"""), {"memo_id": memo_id}).mappings().all()
        out = []
        for r in rows:
            status = "paused" if r["status"] == "paused" else ("reached" if r["reached_at"] else "waiting")
            out.append({"id": str(r["id"]), "direction": "below" if r["type"] == "price_below" else "above",
                        "price": int(r["price"]) if r["price"] is not None else None, "tracking": r["status"] == "active",
                        "status": status, "reached_at": r["reached_at"]})
        return out

    def unread_updates(self, memo_id: int) -> int:
        return int(self.db.execute(text("""SELECT count(*) FROM tracking_updates tu JOIN tracking_items ti ON ti.id = tu.tracking_item_id
            WHERE ti.memo_id = :memo_id AND NOT tu.is_read"""), {"memo_id": memo_id}).scalar() or 0)

    # ---------------------------------------------------------------- 쓰기 (호출자가 트랜잭션을 잡는다)
    def create_item(self, memo_id: int, item: dict, status: str = "active") -> dict[str, Any]:
        keywords = ", ".join(item.get("keywords") or []) or None
        iid = self.db.execute(text("""INSERT INTO tracking_items (memo_id, type, description, keywords, price_threshold, status)
            VALUES (:memo_id, CAST(:type AS tracking_type), :description, :keywords, :threshold, CAST(:status AS tracking_status))
            RETURNING id"""), {"memo_id": memo_id, "type": item["type"], "description": item["description"],
                               "keywords": keywords, "threshold": item.get("price_threshold"), "status": status}).scalar()
        self.db.execute(text("""INSERT INTO tracking_item_revisions (tracking_item_id, revision_no, type, description, keywords,
            price_threshold) VALUES (:iid, 1, CAST(:type AS tracking_type), :description, :keywords, :threshold)"""),
                        {"iid": iid, "type": item["type"], "description": item["description"], "keywords": keywords,
                         "threshold": item.get("price_threshold")})
        return {"id": iid, "status": status, **{k: item.get(k) for k in ("type", "description", "price_threshold")}}

    def set_status(self, ids: list[int], status: str) -> int:
        if not ids:
            return 0
        return self.db.execute(text("""UPDATE tracking_items SET status = CAST(:status AS tracking_status), updated_at = now()
            WHERE id = ANY(:ids)"""), {"ids": ids, "status": status}).rowcount

    def set_memo_status(self, memo_id: int, from_status: str, to_status: str) -> int:
        return self.db.execute(text("""UPDATE tracking_items SET status = CAST(:to AS tracking_status), updated_at = now()
            WHERE memo_id = :memo_id AND status = CAST(:frm AS tracking_status)"""),
                               {"memo_id": memo_id, "frm": from_status, "to": to_status}).rowcount

    def sync(self, memo_id: int, new_items: list[dict], confirmations: list[dict],
             questions: list[dict] | None = None) -> dict[str, list]:
        """항목 맞추기. 반환 {kept, created, done} (항목 dict 목록).

        questions(2026-11-20, 0019): 메모 분석이 찾은 '한 번 답하면 끝나는 질문'을 type='ask' 항목으로 둔다.
        매일 실행이 한 번 답하면 done이 된다. 이미 답한(done) 같은 질문은 메모를 다시 저장해도 새로 만들지 않는다."""
        existing = self.items(memo_id)
        by_key = {item_key(e): e for e in existing}
        answered = {item_key(e) for e in self.items(memo_id, ("done",)) if e["type"] == "ask"}
        option_keys = {item_key({**o["item"]}) for c in confirmations for o in c["options"] if o.get("item", {}).get("type")}
        asks = [{"type": "ask", "description": " ".join(str(q.get("question") or "").split()), "keywords": []}
                for q in (questions or [])]
        wanted, created, kept = set(), [], []
        for it in [*new_items, *(a for a in asks if a["description"])]:
            key = item_key(it)
            if key in wanted:
                continue
            wanted.add(key)
            if key in by_key:
                kept.append(by_key[key])
            elif it["type"] == "ask" and key in answered:
                continue                                        # 이미 답한 질문
            else:
                created.append(self.create_item(memo_id, it))
        done = [e for e in existing if item_key(e) not in wanted and item_key(e) not in option_keys]
        kept += [e for e in existing if item_key(e) not in wanted and item_key(e) in option_keys]   # 확인 답변으로 만든 가격 항목
        self.set_status([e["id"] for e in done], "done")
        self.set_status([e["id"] for e in kept if e["status"] == "paused"], "active")
        return {"kept": kept, "created": created, "done": done}
