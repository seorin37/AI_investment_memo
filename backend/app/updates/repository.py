"""AI 업데이트 카드 조회 (2026-11-11): tracking_updates + update_sources를 읽는다. 쓰기는 읽음 처리(is_read)만."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

CARD_SQL = """
SELECT tu.id, tu.type::text AS type, tu.title, tu.summary, tu.reason, tu.details, tu.is_read, tu.created_at,
       tu.price_state, tu.observed_value, tu.observed_trade_date,
       ti.id AS item_id, ti.type::text AS item_type, ti.description AS item_description, ti.status::text AS item_status,
       ti.last_checked_at, ti.price_threshold,
       m.id AS memo_id, m.title AS memo_title, m.color, btrim(m.symbol) AS symbol, s.name AS stock_name,
       mr.revision_no AS memo_version, mr.title AS snapshot_title, mr.content AS snapshot_body, mr.created_at AS snapshot_at
FROM tracking_updates tu
JOIN tracking_items ti ON ti.id = tu.tracking_item_id
JOIN memos m ON m.id = ti.memo_id
LEFT JOIN stocks s ON s.symbol = m.symbol
LEFT JOIN memo_revisions mr ON mr.id = tu.memo_revision_id
WHERE m.user_id = :user_id AND m.deleted_at IS NULL {where}
ORDER BY tu.created_at DESC, tu.id DESC
LIMIT :limit"""

SOURCES_SQL = """
SELECT us.update_id, us.news_id, us.disclosure_rcept_no, us.quote,
       a.title AS news_title, a.url AS news_url, a.published_at, ns.name AS news_source,
       d.title AS disclosure_title, d.rcept_dt
FROM update_sources us
LEFT JOIN news_articles a ON a.id = us.news_id
LEFT JOIN news_sources ns ON ns.id = a.source_id
LEFT JOIN disclosures d ON d.rcept_no = us.disclosure_rcept_no
WHERE us.update_id = ANY(:ids)
ORDER BY us.update_id, us.id"""

MATCH_SQL = """SELECT tracking_item_id, news_id, similarity FROM tracking_matches
WHERE tracking_item_id = ANY(:items) AND news_id = ANY(:news)"""


class UpdatesRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def cards(self, user_id: int, *, symbol: str | None = None, memo_id: int | None = None,
              unread_only: bool = False, ai_linked_only: bool = True, limit: int = 100,
              active_stocks_only: bool = False, recent_days: int | None = None) -> list[dict[str, Any]]:
        where, params = [], {"user_id": user_id, "limit": limit}
        if ai_linked_only:
            where.append("m.ai_linked")
        if active_stocks_only:                                  # 2026-11-20 /updates: 지금 내 종목만
            where.append("EXISTS (SELECT 1 FROM user_stocks us WHERE us.user_id = m.user_id AND us.symbol = m.symbol"
                         " AND us.deleted_at IS NULL)")
        if recent_days is not None:
            where.append("tu.created_at >= now() - make_interval(days => :recent_days)")
            params["recent_days"] = recent_days
        if symbol is not None:
            where.append("btrim(m.symbol) = :symbol")
            params["symbol"] = symbol
        if memo_id is not None:
            where.append("m.id = :memo_id")
            params["memo_id"] = memo_id
        if unread_only:
            where.append("NOT tu.is_read")
        sql = CARD_SQL.format(where="".join(f" AND {w}" for w in where))
        return [dict(r) for r in self.db.execute(text(sql), params).mappings().all()]

    def sources(self, update_ids: list[int]) -> dict[int, list[dict[str, Any]]]:
        out: dict[int, list[dict[str, Any]]] = {}
        if not update_ids:
            return out
        for r in self.db.execute(text(SOURCES_SQL), {"ids": update_ids}).mappings().all():
            out.setdefault(int(r["update_id"]), []).append(dict(r))
        return out

    def similarities(self, pairs: list[tuple[int, int]]) -> dict[tuple[int, int], float]:
        if not pairs:
            return {}
        rows = self.db.execute(text(MATCH_SQL), {"items": sorted({i for i, _ in pairs}),
                                                 "news": sorted({n for _, n in pairs})}).all()
        return {(int(i), int(n)): float(s) for i, n, s in rows}

    def recent_closes(self, symbol: str, until: Any, n: int = 10) -> list[tuple[Any, float]]:
        """가격 카드 작은 차트: until(관측 거래일)까지 최근 n거래일 (거래일, 종가), 오래된 → 최근."""
        rows = self.db.execute(text("""SELECT trade_date, close FROM prices_daily WHERE symbol = :symbol AND trade_date <= :until
            AND close IS NOT NULL ORDER BY trade_date DESC LIMIT :n"""), {"symbol": symbol, "until": until, "n": n}).all()
        return [(r[0], float(r[1])) for r in reversed(rows)]

    def memo(self, user_id: int, memo_id: int) -> dict[str, Any] | None:
        row = self.db.execute(text("""SELECT id, title, ai_linked, ai_linked_at, btrim(symbol) AS symbol FROM memos
            WHERE id = :memo_id AND user_id = :user_id AND deleted_at IS NULL"""),
                              {"memo_id": memo_id, "user_id": user_id}).mappings().first()
        return dict(row) if row else None

    def revisions(self, memo_id: int) -> list[dict[str, Any]]:
        return [dict(r) for r in self.db.execute(text("""SELECT revision_no, title, content, created_at FROM memo_revisions
            WHERE memo_id = :memo_id ORDER BY revision_no"""), {"memo_id": memo_id}).mappings().all()]

    def items(self, memo_id: int) -> list[dict[str, Any]]:
        return [dict(r) for r in self.db.execute(text("""SELECT id, type::text AS type, description, status::text AS status,
            price_threshold, last_checked_at FROM tracking_items WHERE memo_id = :memo_id AND status::text <> 'done'
            ORDER BY id"""), {"memo_id": memo_id}).mappings().all()]

    def mark_read(self, user_id: int, update_id: int) -> bool:
        row = self.db.execute(text("""UPDATE tracking_updates tu SET is_read = true
            FROM tracking_items ti JOIN memos m ON m.id = ti.memo_id
            WHERE tu.id = :update_id AND ti.id = tu.tracking_item_id AND m.user_id = :user_id AND m.deleted_at IS NULL
            RETURNING tu.id"""), {"update_id": update_id, "user_id": user_id}).first()
        return row is not None

    def mark_memo_read(self, user_id: int, memo_id: int) -> int | None:
        """메모 하나에 붙은 안 읽은 카드를 모두 읽음으로 (2026-11-23). 내 메모가 아니거나 지운 메모면 None, 아니면 바꾼 수."""
        if self.memo(user_id, memo_id) is None:
            return None
        rows = self.db.execute(text("""UPDATE tracking_updates tu SET is_read = true
            FROM tracking_items ti
            WHERE ti.id = tu.tracking_item_id AND ti.memo_id = :memo_id AND NOT tu.is_read
            RETURNING tu.id"""), {"memo_id": memo_id}).all()
        return len(rows)
