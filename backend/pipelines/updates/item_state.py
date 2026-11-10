"""추적 항목 상태 — 마지막 확인 시각(last_checked_at)과 마지막 응답 유형(status) (2026-11-10).

no_new_info는 알림을 보내지 않고 이 상태만 남긴다. DB의 tracking_items.status는 active·paused·done만 받아
응답 유형을 둘 칸이 없어서, 스키마를 바꾸지 않고 저장소 인터페이스 + 파일 구현으로 둔다 (used_refs와 같은 방식).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Protocol

from .models import Response

FILE_VERSION = 1


class ItemStateStore(Protocol):
    def get(self, item_id: str) -> dict | None:
        """{"last_checked_at", "status", "reason"} 또는 None."""

    def record(self, response: Response) -> None:
        """항목 응답의 상태를 덮어쓴다 (항목 범위 응답만)."""


class MemoryItemStateStore:
    def __init__(self, data: dict[str, dict] | None = None):
        self.data = {k: dict(v) for k, v in (data or {}).items()}

    def get(self, item_id: str) -> dict | None:
        return self.data.get(item_id)

    def record(self, response: Response) -> None:
        if response.scope != "item" or not response.item_id:
            return
        self.data[response.item_id] = {"last_checked_at": response.checked_at, "status": response.type,
                                       "reason": response.reason}


def last_checked(store: ItemStateStore | None, item_id: str):
    """마지막 확인 시각(timezone 있는 datetime). 기록이 없으면 None (첫 확인: 조회 기간 전체를 쓴다)."""
    from datetime import datetime

    rec = store.get(item_id) if store is not None else None
    if not rec or not rec.get("last_checked_at"):
        return None
    ts = datetime.fromisoformat(rec["last_checked_at"])
    if ts.tzinfo is None:
        raise ValueError(f"last_checked_at에 시간대가 없습니다: {rec['last_checked_at']}")
    return ts


class FileItemStateStore(MemoryItemStateStore):
    """JSON 파일 하나: {"version": 1, "items": {항목 ID: {last_checked_at, status, reason}}}. 쓸 때 임시 파일 후 교체."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        data = {}
        if self.path.is_file():
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if raw.get("version") != FILE_VERSION:
                raise ValueError(f"item_state 파일 버전이 다릅니다: {raw.get('version')} (기대 {FILE_VERSION})")
            data = raw.get("items") or {}
        super().__init__(data)

    def record(self, response: Response) -> None:
        before = dict(self.data)
        super().record(response)
        if self.data == before:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + ".tmp")
        tmp.write_text(json.dumps({"version": FILE_VERSION, "items": self.data}, ensure_ascii=False, indent=1),
                       encoding="utf-8")
        os.replace(tmp, self.path)
