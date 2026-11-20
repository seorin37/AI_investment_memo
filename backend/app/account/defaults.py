"""DB에 값이 없을 때 쓰는 기본값.

frontend/src/api/mock/seed.ts 의 settings 와 mock/index.ts 의 layout 기본값을 그대로 옮겼다.
(mcp.apps 는 예외: 가짜 연결 앱을 보여주지 않도록 mcp_connections 행만 돌려준다.)
"""

from __future__ import annotations

import copy
from typing import Any

DEFAULT_HOME_LAYOUT: dict[str, Any] = {"mode": "unset", "widgets": []}

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
