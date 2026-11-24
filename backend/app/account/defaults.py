"""DB에 값이 없을 때 쓰는 기본값.

frontend/src/api/mock/seed.ts 의 settings 와 mock/index.ts 의 layout 기본값을 그대로 옮겼다.
(mcp.apps 는 예외: 가짜 연결 앱을 보여주지 않도록 mcp_connections 행만 돌려준다.)
"""

from __future__ import annotations

import copy
from typing import Any

DEFAULT_HOME_LAYOUT: dict[str, Any] = {"mode": "unset", "widgets": []}

# 약관 동의 (2026-11-22, 0022 user_terms_consents). 현재 약관 버전과 필수 항목은 여기 한 곳에만 둔다.
# 프론트는 GET /me/terms 의 required 를 그대로 쓴다. 약관을 바꾸면 버전을 바꾸고 → 모든 사용자가 다시 동의한다.
TERMS_VERSION = "2026-11-22"
REQUIRED_TERMS: tuple[str, ...] = ("age", "service", "invest")

DEFAULT_MCP_SERVER_URL = "https://mcp.memostock.example/mcp"

DEFAULT_SETTINGS: dict[str, Any] = {
    "theme": "system",
    "language": "ko",
    "updown_color": "red_up",
    "notifications": {
        "disclosure": True,
        "news": True,
        "price_condition": True,
        "price_spike": False,
        "price_spike_threshold": 5,
        "channels": {"in_app": True, "email": True, "push": False},
        "frequency": "realtime",
        "quiet_hours": {"enabled": True, "from": "22:00", "to": "07:00"},
    },
    "ai": {
        "default_link_new_memo": False,
        "sources": {"disclosure": True, "news": True, "price": True},
        "sensitivity": "balanced",
    },
    "mcp": {
        "enabled": True,
        "server_url": DEFAULT_MCP_SERVER_URL,
        "scopes": {"memo": True, "journal": True, "stock": True},
        "access": "read",
        "only_ai_linked": True,
        "apps": [],
    },
}


def default_settings() -> dict[str, Any]:
    return copy.deepcopy(DEFAULT_SETTINGS)


def default_home_layout() -> dict[str, Any]:
    return copy.deepcopy(DEFAULT_HOME_LAYOUT)
