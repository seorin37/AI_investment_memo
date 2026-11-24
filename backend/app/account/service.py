"""DB 행 ↔ 프론트 Settings / HomeLayout / User 모양 변환."""

from __future__ import annotations

from datetime import time
from decimal import Decimal
from typing import Any, Callable

from pydantic import ValidationError

from app.auth.repository import AuthRepository
from app.auth.service import _public_user

from .defaults import REQUIRED_TERMS, TERMS_VERSION, default_home_layout, default_settings
from .repository import AccountRepository
from .schemas import HomeLayout, ProfilePatch, SettingsPatch, TermsAgree


class UserNotFoundError(LookupError):
    pass


class TermsError(ValueError):
    """약관 동의 요청이 현재 약관과 맞지 않음 (422)."""


def _to_hhmm(value: Any) -> str:
    if isinstance(value, time):
        return value.strftime("%H:%M")
    return str(value)[:5]


def _to_time(value: str) -> time:
    hour, minute = value.split(":")
    return time(int(hour), int(minute))


def _to_threshold(value: Any) -> int | None:
    number = int(Decimal(str(value)))
    return number if number in (3, 5, 10) else None


_same: Callable[[Any], Any] = lambda value: value

# (Settings 안의 경로, 테이블, 컬럼, DB→API, API→DB)
FIELD_MAP: list[tuple[tuple[str, ...], str, str, Callable, Callable]] = [
    (("theme",), "user", "theme", _same, _same),
    (("language",), "user", "language", _same, _same),
    (("updown_color",), "user", "price_color", _same, _same),
    (("notifications", "disclosure"), "user", "notify_disclosure", _same, _same),
    (("notifications", "news"), "user", "notify_news", _same, _same),
    (("notifications", "price_condition"), "user", "notify_price_condition", _same, _same),
    (("notifications", "price_spike"), "user", "notify_surge", _same, _same),
    (("notifications", "price_spike_threshold"), "user", "surge_threshold_pct", _to_threshold, _same),
    (("notifications", "channels", "in_app"), "user", "notify_in_app", _same, _same),
    (("notifications", "channels", "email"), "user", "notify_email", _same, _same),
    (("notifications", "channels", "push"), "user", "notify_push", _same, _same),
    (("notifications", "frequency"), "user", "notify_frequency", _same, _same),
    (("notifications", "quiet_hours", "enabled"), "user", "quiet_hours_enabled", _same, _same),
    (("notifications", "quiet_hours", "from"), "user", "quiet_start", _to_hhmm, _to_time),
    (("notifications", "quiet_hours", "to"), "user", "quiet_end", _to_hhmm, _to_time),
    (("ai", "default_link_new_memo"), "user", "ai_default_on", _same, _same),
    (("ai", "sources", "disclosure"), "user", "ai_source_disclosure", _same, _same),
    (("ai", "sources", "news"), "user", "ai_source_news", _same, _same),
    (("ai", "sources", "price"), "user", "ai_source_price", _same, _same),
    (("ai", "sensitivity"), "user", "ai_sensitivity", _same, _same),
    (("mcp", "enabled"), "mcp", "enabled", _same, _same),
    (("mcp", "scopes", "memo"), "mcp", "scope_memos", _same, _same),
    (("mcp", "scopes", "journal"), "mcp", "scope_journal", _same, _same),
    (("mcp", "scopes", "stock"), "mcp", "scope_stocks", _same, _same),
    (("mcp", "access"), "mcp", "access", _same, _same),
    (("mcp", "only_ai_linked"), "mcp", "ai_linked_only", _same, _same),
]


def _get_path(data: dict[str, Any], path: tuple[str, ...]) -> tuple[bool, Any]:
    cur: Any = data
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return False, None
        cur = cur[key]
    return True, cur


def _set_path(data: dict[str, Any], path: tuple[str, ...], value: Any) -> None:
    cur = data
    for key in path[:-1]:
        cur = cur[key]
    cur[path[-1]] = value


def _iso(value: Any) -> Any:
    return value.isoformat() if hasattr(value, "isoformat") else value


class AccountService:
    def __init__(self, repo: AccountRepository, auth_repo: AuthRepository) -> None:
        self.repo = repo
        self.auth_repo = auth_repo

    # ─── 설정
    def get_settings(self, user_id: int) -> dict[str, Any]:
        rows = {
            "user": self.repo.get_user_settings(user_id) or {},
            "mcp": self.repo.get_mcp_settings(user_id) or {},
        }
        settings = default_settings()
        for path, table, column, to_api, _to_db in FIELD_MAP:
            value = rows[table].get(column)
            if value is None:
                continue
            converted = to_api(value)
            if converted is not None:
                _set_path(settings, path, converted)
        settings["mcp"]["apps"] = [
            {
                "id": str(app["id"]),
                "name": app["app_name"],
                "access": app["access"] if app["access"] in ("read", "read_write") else "read",
                "last_used_at": _iso(app["last_used_at"]),
            }
            for app in self.repo.list_mcp_apps(user_id)
        ]
        return settings

    def update_settings(self, user_id: int, patch: SettingsPatch) -> dict[str, Any]:
        data = patch.model_dump(by_alias=True, exclude_none=True)
        columns: dict[str, dict[str, Any]] = {"user": {}, "mcp": {}}
        for path, table, column, _to_api, to_db in FIELD_MAP:
            found, value = _get_path(data, path)
            if found:
                columns[table][column] = to_db(value)
        if columns["user"]:
            self.repo.upsert_user_settings(user_id, columns["user"])
        if columns["mcp"]:
            self.repo.upsert_mcp_settings(user_id, columns["mcp"])
        return self.get_settings(user_id)

    # ─── 홈 배치
    def get_home_layout(self, user_id: int) -> dict[str, Any]:
        stored = self.repo.get_home_layout(user_id)
        if stored is None:
            return default_home_layout()
        try:
            return HomeLayout.model_validate(stored).model_dump()
        except ValidationError:
            # 예전 형식이나 깨진 값이면 화면이 멈추지 않게 기본 배치를 준다.
            return default_home_layout()

    def save_home_layout(self, user_id: int, layout: HomeLayout) -> dict[str, Any]:
        data = layout.model_dump()
        self.repo.save_home_layout(user_id, data)
        return data

    # ─── 약관 동의
    def get_terms(self, user_id: int) -> dict[str, Any]:
        """{required: 현재 필수 약관, agreed: 철회 안 한 동의(옛 버전 포함), complete: 현재 버전 필수 전부 동의}."""
        rows = self.repo.list_terms_consents(user_id)
        agreed = [
            {"kind": row["kind"], "version": row["version"], "agreed_at": _iso(row["agreed_at"])}
            for row in rows
        ]
        have = {(row["kind"], row["version"]) for row in rows}
        return {
            "required": [{"kind": kind, "version": TERMS_VERSION} for kind in REQUIRED_TERMS],
            "agreed": agreed,
            "complete": all((kind, TERMS_VERSION) in have for kind in REQUIRED_TERMS),
        }

    def agree_terms(self, user_id: int, payload: TermsAgree) -> dict[str, Any]:
        """현재 버전 필수 약관 전부를 한 번에 받는다. 모르는 종류 · 옛 버전 · 빠진 필수 → TermsError."""
        kinds: list[str] = []
        for item in payload.items:
            if item.kind not in REQUIRED_TERMS:
                raise TermsError(f"알 수 없는 약관입니다: {item.kind}")
            if item.version != TERMS_VERSION:
                raise TermsError(f"현재 약관 버전이 아닙니다: {item.kind} {item.version}")
            kinds.append(item.kind)
        missing = [kind for kind in REQUIRED_TERMS if kind not in kinds]
        if missing:
            raise TermsError(f"필수 약관 동의가 빠졌습니다: {', '.join(missing)}")
        self.repo.insert_terms_consents(user_id, [(kind, TERMS_VERSION) for kind in dict.fromkeys(kinds)])
        return self.get_terms(user_id)

    # ─── 프로필
    def get_me(self, user_id: int) -> dict[str, Any]:
        user = self.auth_repo.get_user(user_id)
        if not user or user.get("deleted_at") is not None:
            raise UserNotFoundError(user_id)
        return _public_user(user)

    def update_me(self, user_id: int, patch: ProfilePatch) -> dict[str, Any]:
        self.repo.update_profile(user_id, display_name=patch.name, bio=patch.bio)
        return self.get_me(user_id)
