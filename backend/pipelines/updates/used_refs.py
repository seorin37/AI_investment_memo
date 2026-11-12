"""이미 카드에 쓴 근거(ref) 기록 — 다음 실행에서 같은 항목의 후보에서 뺀다 (2026-11-09).

- 저장소는 인터페이스(UsedRefStore)만 파이프라인이 안다. 지금은 파일 구현(FileUsedRefStore)만 있고,
  나중에 DB 테이블로 옮길 때는 같은 두 메서드(used·record)를 가진 클래스를 하나 더 만들면 된다. DB 테이블은 만들지 않았다.
- 기록 단위: (항목 ID, ref). ref는 후보의 ref 그대로다 (news:<기사 id>, disc:<접수번호>#<청크 번호>).
  카드의 sources(카드 문장이 실제로 쓴 근거)만 기록한다. 관련 기사(related_news)·같은 사건 기사(supporting_news)는
  링크로만 붙어 문장에 쓰이지 않아 기록하지 않는다. 가격 카드는 근거 ref가 없어 기록할 것이 없다.
- 빼는 기준(match): "ref"(기본)면 같은 ref만, "doc"이면 같은 공시의 다른 청크도 뺀다 (뉴스는 ref가 이미 기사 단위).
- 기존 already_shown_ids(근거가 '모두' 보여 준 출처면 LLM을 부르지 않음)와 다르다: 여기는 보여 준 근거를 후보에서 미리 뺀다.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Protocol

from .models import Candidate, UpdateDraft

FILE_VERSION = 1


class UsedRefStore(Protocol):
    def used(self, item_id: str) -> set[str]:
        """이 항목의 카드에 이미 쓴 ref."""

    def record(self, item_id: str, refs: Iterable[str], at: str | None = None) -> None:
        """카드에 쓴 ref를 더한다 (이미 있는 ref는 처음 쓴 시각을 그대로 둔다)."""


class MemoryUsedRefStore:
    """테스트·한 번 실행용 (프로세스가 끝나면 사라진다)."""

    def __init__(self, data: dict[str, dict[str, str]] | None = None):
        self.data = {k: dict(v) for k, v in (data or {}).items()}

    def used(self, item_id: str) -> set[str]:
        return set(self.data.get(item_id, {}))

    def record(self, item_id: str, refs: Iterable[str], at: str | None = None) -> None:
        stamp = at or datetime.now().astimezone().isoformat(timespec="seconds")
        bucket = self.data.setdefault(item_id, {})
        for ref in refs:
            bucket.setdefault(ref, stamp)


class FileUsedRefStore(MemoryUsedRefStore):
    """JSON 파일 하나: {"version": 1, "items": {항목 ID: {ref: 처음 쓴 시각}}}.
    record 때마다 임시 파일에 쓰고 바꿔 끼운다 (중간에 끊겨도 파일이 반쯤 쓰이지 않게). 동시 실행은 고려하지 않는다."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        data = {}
        if self.path.is_file():
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if raw.get("version") != FILE_VERSION:
                raise ValueError(f"used_refs 파일 버전이 다릅니다: {raw.get('version')} (기대 {FILE_VERSION})")
            data = raw.get("items") or {}
        super().__init__(data)

    def record(self, item_id: str, refs: Iterable[str], at: str | None = None) -> None:
        refs = list(refs)
        if not refs:
            return
        super().record(item_id, refs, at)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + ".tmp")
        tmp.write_text(json.dumps({"version": FILE_VERSION, "items": self.data}, ensure_ascii=False, indent=1),
                       encoding="utf-8")
        os.replace(tmp, self.path)


def _doc_key(ref: str) -> str:
    return ref.split("#", 1)[0]


def drop_used(cands: list[Candidate], used: set[str], match: str = "ref") -> tuple[list[Candidate], list[Candidate]]:
    """(남은 후보, 뺀 후보). match="doc"이면 공시는 접수번호가 같으면 뺀다."""
    if match not in ("ref", "doc"):
        raise ValueError(f"match는 ref 또는 doc: {match}")
    if not used:
        return list(cands), []
    keys = {_doc_key(r) for r in used} if match == "doc" else used
    kept, dropped = [], []
    for c in cands:
        key = _doc_key(c.ref) if match == "doc" else c.ref
        (dropped if key in keys else kept).append(c)
    return kept, dropped


def card_refs(draft: UpdateDraft | None) -> list[str]:
    """카드 문장이 쓴 근거 ref (중복 없이 순서대로). 카드가 없거나 가격 카드면 빈 목록."""
    if draft is None or draft.type == "price_condition":
        return []
    # cmp:<접수번호>는 코드가 DB에서 만든 비교용 근거 (compare_prior)라 기록하지 않는다
    return list(dict.fromkeys(ref for ref, _ in draft.sources if ref and not ref.startswith("cmp:")))
