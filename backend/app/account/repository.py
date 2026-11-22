"""user_settings / mcp_settings / mcp_connections / users 읽기·쓰기."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

USER_SETTINGS_COLUMNS = frozenset(
    {
        "theme",
        "language",
        "price_color",
        "notify_disclosure",
        "notify_news",
        "notify_price_condition",
        "notify_surge",
        "surge_threshold_pct",
        "notify_in_app",
        "notify_email",
        "notify_push",
        "notify_frequency",
        "quiet_hours_enabled",
        "quiet_start",
        "quiet_end",
        "ai_default_on",
        "ai_source_disclosure",
        "ai_source_news",
        "ai_source_price",
        "ai_sensitivity",
    }
)

MCP_SETTINGS_COLUMNS = frozenset(
    {"enabled", "scope_memos", "scope_journal", "scope_stocks", "access", "ai_linked_only"}
)


def _checked(columns: dict[str, Any], allowed: frozenset[str]) -> dict[str, Any]:
    unknown = set(columns) - allowed
    if unknown:
        raise ValueError(f"허용되지 않은 컬럼: {sorted(unknown)}")
    return columns


class AccountRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ─── 설정
    def get_user_settings(self, user_id: int) -> dict[str, Any] | None:
        row = self.db.execute(
            text("SELECT * FROM user_settings WHERE user_id = :user_id"),
            {"user_id": user_id},
        ).mappings().first()
        return dict(row) if row else None

    def get_mcp_settings(self, user_id: int) -> dict[str, Any] | None:
        row = self.db.execute(
            text("SELECT * FROM mcp_settings WHERE user_id = :user_id"),
            {"user_id": user_id},
        ).mappings().first()
        return dict(row) if row else None

    def list_mcp_apps(self, user_id: int) -> list[dict[str, Any]]:
        rows = self.db.execute(
            text(
                """
                SELECT id, app_name, access, last_used_at
                FROM mcp_connections
                WHERE user_id = :user_id AND revoked_at IS NULL
                ORDER BY last_used_at DESC NULLS LAST, id
                """
            ),
            {"user_id": user_id},
        ).mappings().all()
        return [dict(row) for row in rows]

    def upsert_user_settings(self, user_id: int, columns: dict[str, Any]) -> None:
        if not _checked(columns, USER_SETTINGS_COLUMNS):
            return
        names = sorted(columns)
        self.db.execute(
            text(
                f"""
                INSERT INTO user_settings (user_id, {", ".join(names)})
                VALUES (:user_id, {", ".join(f":{n}" for n in names)})
                ON CONFLICT (user_id) DO UPDATE SET
                  {", ".join(f"{n} = EXCLUDED.{n}" for n in names)},
                  updated_at = now()
                """
            ),
            {"user_id": user_id, **columns},
        )

    def upsert_mcp_settings(self, user_id: int, columns: dict[str, Any]) -> None:
        if not _checked(columns, MCP_SETTINGS_COLUMNS):
            return
        names = sorted(columns)
        self.db.execute(
            text(
                f"""
                INSERT INTO mcp_settings (user_id, {", ".join(names)})
                VALUES (:user_id, {", ".join(f":{n}" for n in names)})
                ON CONFLICT (user_id) DO UPDATE SET
                  {", ".join(f"{n} = EXCLUDED.{n}" for n in names)}
                """
            ),
            {"user_id": user_id, **columns},
        )

    # ─── 홈 배치
    def get_home_layout(self, user_id: int) -> Any | None:
        row = self.db.execute(
            text("SELECT home_layout FROM user_settings WHERE user_id = :user_id"),
            {"user_id": user_id},
        ).first()
        return row[0] if row else None

    def save_home_layout(self, user_id: int, layout: dict[str, Any]) -> None:
        self.db.execute(
            text(
                """
                INSERT INTO user_settings (user_id, home_layout)
                VALUES (:user_id, CAST(:layout AS jsonb))
                ON CONFLICT (user_id) DO UPDATE SET
                  home_layout = EXCLUDED.home_layout,
                  updated_at = now()
                """
            ),
            {"user_id": user_id, "layout": json.dumps(layout, ensure_ascii=False)},
        )

    # ─── 약관 동의 (0022 user_terms_consents)
    def list_terms_consents(self, user_id: int) -> list[dict[str, Any]]:
        """철회하지 않은 동의 (옛 버전 포함)."""
        rows = self.db.execute(
            text(
                """
                SELECT kind, version, agreed_at
                FROM user_terms_consents
                WHERE user_id = :user_id AND withdrawn_at IS NULL
                ORDER BY agreed_at, kind, version
                """
            ),
            {"user_id": user_id},
        ).mappings().all()
        return [dict(row) for row in rows]

    def insert_terms_consents(self, user_id: int, items: list[tuple[str, str]]) -> None:
        """같은 사용자·종류·버전은 한 행 (UNIQUE) — 다시 보내도 그대로."""
        if not items:
            return
        self.db.execute(
            text(
                """
                INSERT INTO user_terms_consents (user_id, kind, version, is_required)
                VALUES (:user_id, :kind, :version, true)
                ON CONFLICT (user_id, kind, version) DO NOTHING
                """
            ),
            [{"user_id": user_id, "kind": kind, "version": version} for kind, version in items],
        )

    # ─── 프로필
    def update_profile(
        self, user_id: int, *, display_name: str | None, bio: str | None
    ) -> None:
        sets: list[str] = []
        params: dict[str, Any] = {"user_id": user_id}
        if display_name is not None:
            sets.append("display_name = :display_name")
            params["display_name"] = display_name
        if bio is not None:
            sets.append("bio = :bio")
            params["bio"] = bio
        if not sets:
            return
        self.db.execute(
            text(
                f"UPDATE users SET {', '.join(sets)} "
                "WHERE id = :user_id AND deleted_at IS NULL"
            ),
            params,
        )
