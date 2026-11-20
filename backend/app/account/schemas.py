"""요청 검증 모델. 응답 모양은 frontend/src/types/models.ts 와 같다."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

WidgetType = Literal[
    "market",
    "updates",
    "calendar",
    "news",
    "pinned_memos",
    "checklist",
    "quick_memo",
    "price_conditions",
    "recent_journal",
    "memo_updates",
    "memo_backtest",
    "compare_memo",
    "conclude_memo",
]

_HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


class WidgetInstance(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=64)
    type: WidgetType
    span: Literal[1, 2, 3, 4]


class HomeLayout(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["unset", "template", "custom"]
    widgets: list[WidgetInstance] = Field(max_length=40)


# ─── 설정 PATCH (DeepPartial<Settings>) ─────────────────────────


class _Patch(BaseModel):
    # 화면이 받은 값을 그대로 되돌려 보내도 실패하지 않게 모르는 키는 무시한다.
    model_config = ConfigDict(extra="ignore")


class ChannelsPatch(_Patch):
    in_app: bool | None = None
    email: bool | None = None
    push: bool | None = None


class QuietHoursPatch(_Patch):
    enabled: bool | None = None
    from_: str | None = Field(default=None, alias="from")
    to: str | None = None

    @field_validator("from_", "to")
    @classmethod
    def hhmm(cls, value: str | None) -> str | None:
        if value is not None and not _HHMM.match(value):
            raise ValueError("시간은 HH:MM 형식이어야 합니다.")
        return value


class NotificationsPatch(_Patch):
    disclosure: bool | None = None
    news: bool | None = None
    price_condition: bool | None = None
    price_spike: bool | None = None
    price_spike_threshold: Literal[3, 5, 10] | None = None
    channels: ChannelsPatch | None = None
    frequency: Literal["realtime", "hourly", "daily"] | None = None
    quiet_hours: QuietHoursPatch | None = None


class AiSourcesPatch(_Patch):
    disclosure: bool | None = None
    news: bool | None = None
    price: bool | None = None


class AiPatch(_Patch):
    default_link_new_memo: bool | None = None
    sources: AiSourcesPatch | None = None
    sensitivity: Literal["strict", "balanced", "broad"] | None = None


class McpScopesPatch(_Patch):
    memo: bool | None = None
    journal: bool | None = None
    stock: bool | None = None


class McpPatch(_Patch):
    # server_url, apps 는 읽기 전용이라 받지 않는다(무시).
    enabled: bool | None = None
    scopes: McpScopesPatch | None = None
    access: Literal["read", "read_write"] | None = None
    only_ai_linked: bool | None = None


class SettingsPatch(_Patch):
    theme: Literal["system", "light", "dark"] | None = None
    language: Literal["ko"] | None = None
    updown_color: Literal["red_up", "green_up"] | None = None
    notifications: NotificationsPatch | None = None
    ai: AiPatch | None = None
    mcp: McpPatch | None = None


class ProfilePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, max_length=40)
    bio: str | None = Field(default=None, max_length=100)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("이름은 비어 있을 수 없습니다.")
        return cleaned

    @field_validator("bio")
    @classmethod
    def clean_bio(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None
