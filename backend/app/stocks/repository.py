"""PostgreSQL access for stock master and user-owned stock rows."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


# 종목별 메모 수 · AI 연결 수 (2026-11-22). 사용자 메모를 종목별로 한 번에 묶어 붙인다 (종목마다 따로 조회하지 않음)
# - memo_count: 휴지통 제외(deleted_at IS NULL) + 일반 메모(kind = 'note'). 체크리스트 · 참고자료는 세지 않음
# - ai_count: GET /ai/stats 의 linked_memos 와 같은 조건(deleted_at IS NULL AND ai_linked)을 종목별로.
#   ck_memos_ai_only_note 로 ai_linked 는 note 에만 있어 memo_count 범위 안에 든다
MEMO_COUNTS_COLUMNS = """,
                       COALESCE(mc.memo_count, 0)::integer AS memo_count,
                       COALESCE(mc.ai_count, 0)::integer AS ai_count"""
MEMO_COUNTS_JOIN = """
                LEFT JOIN (
                  SELECT symbol,
                         count(*) FILTER (WHERE kind = 'note') AS memo_count,
                         count(*) FILTER (WHERE ai_linked) AS ai_count
                  FROM memos
                  WHERE user_id = :user_id AND deleted_at IS NULL
                  GROUP BY symbol
                ) mc ON mc.symbol = us.symbol"""


class StockRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def search_kospi(self, query: str, limit: int = 8) -> list[dict[str, Any]]:
        rows = self.db.execute(
            text(
                """
                SELECT btrim(symbol) AS code, name, market::text AS market
                FROM stocks
                WHERE market = 'KOSPI'
                  AND (name ILIKE :pattern OR btrim(symbol) ILIKE :pattern)
                ORDER BY
                  CASE
                    WHEN btrim(symbol) = :query THEN 0
                    WHEN name = :query THEN 1
                    WHEN btrim(symbol) ILIKE :prefix THEN 2
                    WHEN name ILIKE :prefix THEN 3
                    ELSE 4
                  END,
                  name, symbol
                LIMIT :limit
                """
            ),
            {
                "query": query,
                "pattern": f"%{query}%",
                "prefix": f"{query}%",
                "limit": limit,
            },
        ).mappings().all()
        return [dict(row) for row in rows]

    def get_kospi(self, code: str) -> dict[str, Any] | None:
        row = self.db.execute(
            text(
                """
                SELECT btrim(symbol) AS code, name, market::text AS market
                FROM stocks
                WHERE symbol = :code AND market = 'KOSPI'
                """
            ),
            {"code": code},
        ).mappings().first()
        return dict(row) if row else None

    # ─── 많이 찾는 종목 (GET /stocks/popular, 2026-11-22)
    def popular_by_users(self, *, min_users: int, limit: int) -> list[dict[str, Any]]:
        """담은 사람이 min_users 명 이상인 KOSPI 종목, 많은 순. 인원 수는 정렬에만 쓰고 돌려주지 않는다."""
        rows = self.db.execute(
            text(
                """
                SELECT btrim(s.symbol) AS code, s.name, s.market::text AS market
                FROM user_stocks us
                JOIN stocks s ON s.symbol = us.symbol
                JOIN users u ON u.id = us.user_id AND u.deleted_at IS NULL
                WHERE us.deleted_at IS NULL
                  AND s.market = 'KOSPI'
                GROUP BY s.symbol, s.name, s.market
                HAVING count(DISTINCT us.user_id) >= :min_users
                ORDER BY count(DISTINCT us.user_id) DESC, s.symbol
                LIMIT :limit
                """
            ),
            {"min_users": min_users, "limit": limit},
        ).mappings().all()
        return [dict(row) for row in rows]

    def top_market_cap(self, *, limit: int, exclude: list[str]) -> list[dict[str, Any]]:
        """시총 큰 KOSPI 종목. 기준일 = KOSPI 종목에 market_cap 이 있는 가장 최근 거래일. exclude 코드는 뺀다."""
        rows = self.db.execute(
            text(
                """
                WITH latest AS (
                  SELECT max(p.trade_date) AS d
                  FROM prices_daily p
                  JOIN stocks s ON s.symbol = p.symbol
                  WHERE s.market = 'KOSPI' AND p.market_cap IS NOT NULL
                )
                SELECT btrim(s.symbol) AS code, s.name, s.market::text AS market
                FROM prices_daily p
                JOIN latest ON p.trade_date = latest.d
                JOIN stocks s ON s.symbol = p.symbol
                WHERE s.market = 'KOSPI'
                  AND p.market_cap IS NOT NULL
                  AND NOT (btrim(s.symbol) = ANY(:exclude))
                ORDER BY p.market_cap DESC, s.symbol
                LIMIT :limit
                """
            ),
            {"limit": limit, "exclude": list(exclude)},
        ).mappings().all()
        return [dict(row) for row in rows]

    def list_user_stocks(self, user_id: int) -> list[dict[str, Any]]:
        rows = self.db.execute(
            text(
                f"""
                SELECT btrim(s.symbol) AS code,
                       s.name,
                       s.market::text AS market,
                       us.status::text AS status,
                       us.created_at AS added_at,
                       COALESCE((
                         SELECT count(DISTINCT tu.id)
                         FROM memos m
                         JOIN tracking_items ti ON ti.memo_id = m.id
                         JOIN tracking_updates tu ON tu.tracking_item_id = ti.id
                         WHERE m.user_id = us.user_id
                           AND m.symbol = us.symbol
                           AND m.deleted_at IS NULL
                           AND tu.created_at > COALESCE(
                             us.last_checked_at,
                             CAST('-infinity' AS timestamptz)
                           )
                       ), 0)::integer AS unread_updates{MEMO_COUNTS_COLUMNS}
                FROM user_stocks us
                JOIN stocks s ON s.symbol = us.symbol{MEMO_COUNTS_JOIN}
                WHERE us.user_id = :user_id
                  AND us.deleted_at IS NULL
                ORDER BY us.position NULLS LAST, us.created_at, s.symbol
                """
            ),
            {"user_id": user_id},
        ).mappings().all()
        return [{**dict(row), "position": index} for index, row in enumerate(rows)]   # 사이드바 자리 (0021, 0부터)

    def stock_order(self, user_id: int, *, lock: bool = False) -> list[str]:
        """내 종목 순서 (지우지 않은 것). lock=True면 순서를 다시 쓰는 동안 동시 변경을 막는다."""
        rows = self.db.execute(
            text(
                f"""
                SELECT btrim(symbol) FROM user_stocks
                WHERE user_id = :user_id AND deleted_at IS NULL
                ORDER BY position NULLS LAST, created_at, symbol
                {"FOR UPDATE" if lock else ""}
                """
            ),
            {"user_id": user_id},
        ).scalars().all()
        return list(rows)

    def write_stock_order(self, user_id: int, codes: list[str]) -> None:
        """내 종목 순서를 0부터 다시 매긴다. codes는 지우지 않은 내 종목 전체."""
        if not codes:
            return
        self.db.execute(
            text(
                """
                UPDATE user_stocks us SET position = o.pos - 1
                FROM unnest(CAST(:codes AS text[])) WITH ORDINALITY AS o(code, pos)
                WHERE us.user_id = :user_id AND btrim(us.symbol) = o.code AND us.deleted_at IS NULL
                  AND us.position IS DISTINCT FROM o.pos - 1
                """
            ),
            {"user_id": user_id, "codes": codes},
        )

    def get_user_stock(self, user_id: int, code: str) -> dict[str, Any] | None:
        row = self.db.execute(
            text(
                f"""
                SELECT btrim(s.symbol) AS code,
                       s.name,
                       s.market::text AS market,
                       us.status::text AS status,
                       us.created_at AS added_at,
                       COALESCE((
                         SELECT count(DISTINCT tu.id)
                         FROM memos m
                         JOIN tracking_items ti ON ti.memo_id = m.id
                         JOIN tracking_updates tu ON tu.tracking_item_id = ti.id
                         WHERE m.user_id = us.user_id
                           AND m.symbol = us.symbol
                           AND m.deleted_at IS NULL
                           AND tu.created_at > COALESCE(
                             us.last_checked_at,
                             CAST('-infinity' AS timestamptz)
                           )
                       ), 0)::integer AS unread_updates{MEMO_COUNTS_COLUMNS}
                FROM user_stocks us
                JOIN stocks s ON s.symbol = us.symbol{MEMO_COUNTS_JOIN}
                WHERE us.user_id = :user_id
                  AND us.symbol = :code
                  AND us.deleted_at IS NULL
                """
            ),
            {"user_id": user_id, "code": code},
        ).mappings().first()
        return dict(row) if row else None

    def upsert_user_stock(
        self, user_id: int, code: str, status: str
    ) -> dict[str, Any]:
        self.db.execute(
            text(
                """
                INSERT INTO user_stocks (user_id, symbol, status, position)
                VALUES (:user_id, :code, CAST(:status AS stock_status),
                        (SELECT COALESCE(max(position) + 1, 0) FROM user_stocks
                         WHERE user_id = :user_id AND deleted_at IS NULL))
                ON CONFLICT (user_id, symbol) DO UPDATE
                SET status = EXCLUDED.status,
                    position = CASE WHEN user_stocks.deleted_at IS NULL THEN user_stocks.position
                                    ELSE EXCLUDED.position END,     -- 새로·다시 추가하면 맨 뒤 (0021)
                    deleted_at = NULL
                """
            ),
            {"user_id": user_id, "code": code, "status": status},
        )
        return self.get_user_stock(user_id, code)  # type: ignore[return-value]

    def update_status(
        self, user_id: int, code: str, status: str
    ) -> dict[str, Any] | None:
        changed = self.db.execute(
            text(
                """
                UPDATE user_stocks
                SET status = CAST(:status AS stock_status)
                WHERE user_id = :user_id
                  AND symbol = :code
                  AND deleted_at IS NULL
                RETURNING symbol
                """
            ),
            {"user_id": user_id, "code": code, "status": status},
        ).first()
        return self.get_user_stock(user_id, code) if changed else None

    def soft_delete(self, user_id: int, code: str) -> bool:
        changed = self.db.execute(
            text(
                """
                UPDATE user_stocks
                SET deleted_at = now()
                WHERE user_id = :user_id
                  AND symbol = :code
                  AND deleted_at IS NULL
                RETURNING symbol
                """
            ),
            {"user_id": user_id, "code": code},
        ).first()
        return changed is not None
