"""Transactional PostgreSQL repository for identities and auth sessions."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from .providers import ProviderProfile


class AuthRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_oauth_transaction(self, values: dict[str, Any]) -> None:
        self.db.execute(
            text(
                """
                INSERT INTO oauth_transactions
                  (state_hash, provider, client_type, return_to, provider_redirect_uri,
                   provider_code_verifier, oidc_nonce, app_code_challenge, expires_at)
                VALUES
                  (:state_hash, :provider, :client_type, :return_to, :provider_redirect_uri,
                   :provider_code_verifier, :oidc_nonce, :app_code_challenge, :expires_at)
                """
            ),
            values,
        )

    def consume_oauth_transaction(self, state_hash: str) -> dict[str, Any] | None:
        row = self.db.execute(
            text(
                """
                SELECT * FROM oauth_transactions
                WHERE state_hash = :state_hash
                FOR UPDATE
                """
            ),
            {"state_hash": state_hash},
        ).mappings().first()
        if not row or row["consumed_at"] is not None or row["expires_at"] <= datetime.now(timezone.utc):
            return None
        self.db.execute(
            text("UPDATE oauth_transactions SET consumed_at = now() WHERE state_hash = :state_hash"),
            {"state_hash": state_hash},
        )
        return dict(row)

    def get_or_create_user(self, profile: ProviderProfile) -> dict[str, Any]:
        lock_key = f"oauth:{profile.provider}:{profile.provider_user_id}"
        self.db.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:lock_key, 0))"),
            {"lock_key": lock_key},
        )
        existing = self._identity_user(profile.provider, profile.provider_user_id)
        if existing:
            return existing
        user_email = profile.email
        if user_email:
            # Different providers can return the same email. Serialize only the
            # email decision, but never use it to merge identities.
            self.db.execute(
                text(
                    "SELECT pg_advisory_xact_lock(hashtextextended(:lock_key, 0))"
                ),
                {"lock_key": f"oauth-email:{user_email.casefold()}"},
            )
            email_taken = self.db.execute(
                text("SELECT 1 FROM users WHERE lower(email) = lower(:email) LIMIT 1"),
                {"email": user_email},
            ).first()
            if email_taken:
                user_email = None
        user = self.db.execute(
            text(
                """
                INSERT INTO users (email, display_name, avatar_url)
                VALUES (:email, :display_name, :avatar_url)
                RETURNING id, email, display_name, bio, avatar_url, plan, deleted_at
                """
            ),
            {
                "email": user_email,
                "display_name": profile.display_name,
                "avatar_url": profile.avatar_url,
            },
        ).mappings().one()
        self.db.execute(
            text("INSERT INTO user_settings (user_id) VALUES (:user_id) ON CONFLICT DO NOTHING"),
            {"user_id": user["id"]},
        )
        self.db.execute(
            text(
                """
                INSERT INTO auth_identities (user_id, provider, provider_uid, email)
                VALUES (:user_id, :provider, :provider_uid, :email)
                """
            ),
            {
                "user_id": user["id"],
                "provider": profile.provider,
                "provider_uid": profile.provider_user_id,
                "email": profile.email,
            },
        )
        result = dict(user)
        result["providers"] = [
            {"provider": profile.provider, "email": profile.email, "connected": True, "current": True}
        ]
        return result

    def _identity_user(self, provider: str, provider_uid: str) -> dict[str, Any] | None:
        row = self.db.execute(
            text(
                """
                SELECT u.id, u.email, u.display_name, u.bio, u.avatar_url, u.plan, u.deleted_at
                FROM auth_identities ai
                JOIN users u ON u.id = ai.user_id
                WHERE ai.provider = :provider AND ai.provider_uid = :provider_uid
                """
            ),
            {"provider": provider, "provider_uid": provider_uid},
        ).mappings().first()
        if not row:
            return None
        result = dict(row)
        result["providers"] = self.list_identities(row["id"], current_provider=provider)
        return result

    def list_identities(self, user_id: int, current_provider: str | None = None) -> list[dict[str, Any]]:
        rows = self.db.execute(
            text(
                """
                SELECT provider, email FROM auth_identities
                WHERE user_id = :user_id ORDER BY id
                """
            ),
            {"user_id": user_id},
        ).mappings().all()
        return [
            {
                "provider": row["provider"],
                "email": row["email"],
                "connected": True,
                "current": row["provider"] == current_provider if current_provider else False,
            }
            for row in rows
        ]

    def get_user(self, user_id: int) -> dict[str, Any] | None:
        row = self.db.execute(
            text(
                """
                SELECT id, email, display_name, bio, avatar_url, plan, deleted_at
                FROM users WHERE id = :id
                """
            ),
            {"id": user_id},
        ).mappings().first()
        if not row:
            return None
        result = dict(row)
        result["providers"] = self.list_identities(user_id)
        return result

    def get_active_user_for_session(self, user_id: int, session_id: UUID) -> dict[str, Any] | None:
        row = self.db.execute(
            text(
                """
                SELECT u.id, u.email, u.display_name, u.bio, u.avatar_url, u.plan, u.deleted_at
                FROM auth_sessions s
                JOIN users u ON u.id = s.user_id
                WHERE s.id = :session_id AND s.user_id = :user_id
                  AND s.revoked_at IS NULL AND s.expires_at > now()
                  AND u.deleted_at IS NULL
                """
            ),
            {"session_id": session_id, "user_id": user_id},
        ).mappings().first()
        if not row:
            return None
        result = dict(row)
        result["providers"] = self.list_identities(user_id)
        return result

    def insert_session(self, values: dict[str, Any]) -> None:
        self.db.execute(
            text(
                """
                INSERT INTO auth_sessions
                  (id, family_id, user_id, refresh_token_hash, user_agent_hash, expires_at)
                VALUES
                  (:id, :family_id, :user_id, :refresh_token_hash, :user_agent_hash, :expires_at)
                """
            ),
            values,
        )

    def lock_session_by_refresh_hash(self, refresh_hash: str) -> dict[str, Any] | None:
        row = self.db.execute(
            text("SELECT * FROM auth_sessions WHERE refresh_token_hash = :value FOR UPDATE"),
            {"value": refresh_hash},
        ).mappings().first()
        return dict(row) if row else None

    def rotate_session(self, old_id: UUID, new_values: dict[str, Any]) -> None:
        self.insert_session(new_values)
        self.db.execute(
            text(
                """
                UPDATE auth_sessions
                SET revoked_at = now(), revoke_reason = 'rotated', replaced_by = :new_id, last_used_at = now()
                WHERE id = :old_id
                """
            ),
            {"old_id": old_id, "new_id": new_values["id"]},
        )

    def revoke_family(self, family_id: UUID, reason: str) -> None:
        self.db.execute(
            text(
                """
                UPDATE auth_sessions
                SET revoked_at = COALESCE(revoked_at, now()), revoke_reason = COALESCE(revoke_reason, :reason)
                WHERE family_id = :family_id
                """
            ),
            {"family_id": family_id, "reason": reason},
        )

    def revoke_session(self, session_id: UUID, reason: str = "logout") -> None:
        self.db.execute(
            text(
                """
                UPDATE auth_sessions
                SET revoked_at = COALESCE(revoked_at, now()), revoke_reason = COALESCE(revoke_reason, :reason)
                WHERE id = :session_id
                """
            ),
            {"session_id": session_id, "reason": reason},
        )

    def create_exchange_code(self, values: dict[str, Any]) -> None:
        self.db.execute(
            text(
                """
                INSERT INTO auth_exchange_codes (code_hash, user_id, code_challenge, expires_at)
                VALUES (:code_hash, :user_id, :code_challenge, :expires_at)
                """
            ),
            values,
        )

    def consume_exchange_code(self, code_hash: str) -> dict[str, Any] | None:
        row = self.db.execute(
            text("SELECT * FROM auth_exchange_codes WHERE code_hash = :value FOR UPDATE"),
            {"value": code_hash},
        ).mappings().first()
        if not row or row["used_at"] is not None or row["expires_at"] <= datetime.now(timezone.utc):
            return None
        self.db.execute(
            text("UPDATE auth_exchange_codes SET used_at = now() WHERE code_hash = :value"),
            {"value": code_hash},
        )
        return dict(row)
