"""Business rules for authenticated memo-board management.

2026-11-11 메모 저장 시 분석: AI가 켜진 일반 메모(note)는 저장(커밋) 뒤 메모 분석 → 추적 항목 저장 (analysis.py · tracking.py).
분석이 실패해도 메모 저장은 성공이고, 응답의 analysis.status=failed·error와 로그에 남는다. 재시도는 메모를 다시 저장할 때만.
첫 카드는 매일 실행 때 만든다 (analysis.next_update_at).
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from pipelines.updates.db_store import memo_full_text

from .analysis import AnalysisError, analyze_memo, default_llm, next_update_at, read_option
from .repository import BoardRepository
from .schemas import ChecklistCreate, MemoCreate, ReferenceCreate
from .tracking import TrackingRepository

log = logging.getLogger(__name__)


class BoardItemNotFoundError(LookupError):
    pass


class StockBoardNotFoundError(LookupError):
    pass


class InvalidBoardPatchError(ValueError):
    pass


class StaleConfirmationError(ValueError):
    """확인 질문 선택지가 지금 메모 버전의 것이 아님 (메모가 바뀜). 화면은 메모를 다시 불러 새 질문을 보여 준다."""


class BoardService:
    _COLORS = {"yellow", "blue", "pink", "green", "purple"}

    def __init__(self, repository: BoardRepository, tracking: TrackingRepository | None = None,
                 llm_factory: Callable[[], Callable[[str], str] | None] = default_llm) -> None:
        self.repository = repository
        self.tracking = tracking or TrackingRepository(repository.db)
        self._llm_factory, self._llm = llm_factory, None

    def list_board(self, user_id: int, symbol: str) -> list[dict[str, Any]]:
        self._require_stock(user_id, symbol)
        return [self._response(row) for row in self.repository.list_board(user_id, symbol)]

    def get(self, user_id: int, memo_id: int) -> dict[str, Any]:
        return self._response(self._require_item(user_id, memo_id))

    def create_memo(self, user_id: int, symbol: str, payload: MemoCreate) -> dict[str, Any]:
        self._require_stock(user_id, symbol)
        row = self.repository.create(
            user_id=user_id,
            symbol=symbol,
            kind="note",
            title=payload.title,
            content=payload.body,
            color=payload.color,
            pinned=payload.pinned,
            ai_linked=payload.ai_linked,
        )
        self.repository.replace_tags(user_id, int(row["id"]), payload.tags)
        self._commit()                                          # 메모 저장을 먼저 확정한다 (분석 실패와 무관하게)
        analysis = self._analyze(row) if payload.ai_linked else self._skipped("ai_off")
        return {**self._response(row), "analysis": analysis}

    def create_checklist(
        self, user_id: int, symbol: str, payload: ChecklistCreate
    ) -> dict[str, Any]:
        self._require_stock(user_id, symbol)
        row = self.repository.create(
            user_id=user_id,
            symbol=symbol,
            kind="checklist",
            title=payload.title,
            content="",
        )
        self.repository.replace_checklist(
            int(row["id"]), [item.model_dump(exclude={"id"}) for item in payload.items]
        )
        return self._response(row)

    def create_reference(
        self, user_id: int, symbol: str, payload: ReferenceCreate
    ) -> dict[str, Any]:
        self._require_stock(user_id, symbol)
        row = self.repository.create(
            user_id=user_id,
            symbol=symbol,
            kind="reference",
            title=payload.title,
            content="",
        )
        self.repository.replace_links(
            int(row["id"]), [link.model_dump(exclude={"id"}) for link in payload.links]
        )
        return self._response(row)

    def update(self, user_id: int, memo_id: int, values: dict[str, Any]) -> dict[str, Any]:
        row = self._require_item(user_id, memo_id)
        if "position" in values:
            raise InvalidBoardPatchError(
                "현재 DB 스키마에는 메모 순서 저장 컬럼이 없어 position 변경을 지원하지 않습니다."
            )
        kind = str(row["kind"])
        allowed = {
            "note": {"title", "body", "tags", "color", "pinned"},
            "checklist": {"title", "items"},
            "reference": {"title", "links"},
        }[kind]
        unsupported = set(values) - allowed
        if unsupported:
            raise InvalidBoardPatchError(
                f"{kind} 유형에서 수정할 수 없는 필드입니다: {', '.join(sorted(unsupported))}"
            )

        base = {key: value for key, value in values.items() if key in {"title", "body", "color", "pinned"}}
        # 분석 입력(제목 + 본문)이 실제로 바뀐 경우만 다시 분석. 제목만 바뀌어도 입력이 바뀌면 다시 분석한다 (2026-11-18)
        text_changed = kind == "note" and ("title" in values or "body" in values) and memo_full_text(
            values.get("title", row.get("title")), values.get("body", row.get("content"))
        ) != memo_full_text(row.get("title"), row.get("content"))
        if base and not self.repository.update_base(user_id, memo_id, base):
            raise BoardItemNotFoundError(memo_id)
        children_changed = False
        if "tags" in values:
            self.repository.replace_tags(user_id, memo_id, values["tags"])
            children_changed = True
        if "items" in values:
            self.repository.replace_checklist(memo_id, values["items"])
            children_changed = True
        if "links" in values:
            self.repository.replace_links(memo_id, values["links"])
            children_changed = True
        if children_changed:
            self.repository.touch(user_id, memo_id)
        if kind != "note":
            return self.get(user_id, memo_id)
        self._commit()
        fresh = self._require_item(user_id, memo_id)
        if not fresh.get("ai_linked"):
            analysis = self._skipped("ai_off")
        elif text_changed:                                      # 제목 + 본문이 실제로 바뀐 경우만 다시 분석
            analysis = self._analyze(fresh)
        else:
            analysis = self._unchanged(memo_id)
        return {**self._response(fresh), "analysis": analysis}

    def update_checklist_item(
        self, user_id: int, memo_id: int, item_id: int, values: dict[str, Any]
    ) -> dict[str, Any]:
        if not values:
            raise InvalidBoardPatchError("수정할 체크리스트 필드가 없습니다.")
        row = self._require_item(user_id, memo_id)
        if str(row["kind"]) != "checklist":
            raise InvalidBoardPatchError("체크리스트 항목은 체크리스트 메모에서만 수정할 수 있습니다.")
        if not self.repository.update_checklist_item(user_id, memo_id, item_id, values):
            raise BoardItemNotFoundError(item_id)
        return self.get(user_id, memo_id)

    def set_ai_link(self, user_id: int, memo_id: int, enabled: bool) -> dict[str, Any]:
        row = self._require_item(user_id, memo_id)
        if str(row["kind"]) != "note":
            raise InvalidBoardPatchError("일반 메모만 AI 추적 대상으로 설정할 수 있습니다.")
        if not self.repository.set_ai_link(user_id, memo_id, enabled):
            raise BoardItemNotFoundError(memo_id)
        if not enabled:                                         # AI 끄기: 항목을 멈춘다 (지우지 않음)
            paused = self.tracking.set_memo_status(memo_id, "active", "paused")
            self._commit()
            return {**self.get(user_id, memo_id), "analysis": {**self._skipped("ai_off"), "paused": paused}}
        self._commit()
        fresh = self._require_item(user_id, memo_id)
        if self.tracking.changed_since_analysis(memo_id):       # 마지막 분석 뒤 메모가 바뀌었으면(또는 항목이 없으면) 다시 분석
            return {**self._response(fresh), "analysis": self._analyze(fresh)}
        resumed = self.tracking.set_memo_status(memo_id, "paused", "active")
        self._commit()
        return {**self._response(fresh), "analysis": {**self._unchanged(memo_id), "resumed": resumed}}

    def confirm(self, user_id: int, memo_id: int, option_id: str) -> dict[str, Any]:
        """확인 질문 답변: 서명한 선택지의 가격 항목(price_below/price_above)을 만든다."""
        row = self._require_item(user_id, memo_id)
        if str(row["kind"]) != "note" or not row.get("ai_linked"):
            raise InvalidBoardPatchError("AI가 켜진 일반 메모에서만 확인 질문에 답할 수 있습니다.")
        option = read_option(option_id)
        if option is None or option.get("m") != memo_id:
            raise InvalidBoardPatchError("올바르지 않은 선택지입니다.")
        rev = self.tracking.latest_revision(memo_id)
        if rev is None or rev["revision_no"] != option.get("r"):
            raise StaleConfirmationError("메모가 바뀌어 이 질문은 더 이상 유효하지 않습니다.")
        item = option["i"]
        if item.get("type") not in ("price_below", "price_above") or item.get("price_threshold") is None:
            raise InvalidBoardPatchError("가격 조건 선택지가 아닙니다.")
        from .tracking import item_key
        same = [e for e in self.tracking.items(memo_id) if item_key(e) == item_key(item)]
        created = same[0] if same else self.tracking.create_item(memo_id, item)
        self._commit()
        return {**self._response(row), "analysis": {"status": "confirmed", "items": [self._item_out(created)],
                                                    "confirmations": [], "out_of_scope": False, "error": None,
                                                    "next_update_at": next_update_at()}}

    # ---------------------------------------------------------------- 분석 (2026-11-11)
    def _commit(self) -> None:
        self.repository.db.commit()

    def _llm_call(self):
        if self._llm is None:
            self._llm = self._llm_factory()
        return self._llm

    @staticmethod
    def _item_out(e: dict[str, Any]) -> dict[str, Any]:
        threshold = e.get("price_threshold")
        return {"id": str(e["id"]), "type": str(e["type"]), "description": e["description"],
                "price_threshold": None if threshold is None else int(float(threshold)), "status": str(e.get("status") or "active")}

    def _skipped(self, reason: str) -> dict[str, Any]:
        return {"status": "skipped", "reason": reason, "items": [], "confirmations": [], "out_of_scope": False,
                "error": None, "next_update_at": None}

    def _unchanged(self, memo_id: int) -> dict[str, Any]:
        return {"status": "unchanged", "items": [self._item_out(e) for e in self.tracking.items(memo_id, ("active",))],
                "confirmations": [], "out_of_scope": False, "error": None, "next_update_at": next_update_at()}

    def _analyze(self, row: dict[str, Any]) -> dict[str, Any]:
        """메모가 이미 커밋된 뒤에 부른다. 실패해도 예외를 올리지 않고 status=failed로 돌려준다."""
        memo_id, symbol = int(row["id"]), str(row["symbol"]).strip()
        current = [self._item_out(e) for e in self.tracking.items(memo_id, ("active",))]
        failed = lambda code: {"status": "failed", "error": code, "items": current, "confirmations": [],
                               "out_of_scope": False, "next_update_at": None}
        try:
            rev = self.tracking.latest_revision(memo_id)
            result = analyze_memo(memo_id, rev["revision_no"] if rev else 1, memo_full_text(row.get("title"), row.get("content")), symbol,
                                  self.tracking.stock_name(symbol), self._llm_call(), self.tracking.price_window(symbol))
        except AnalysisError as exc:
            log.warning("memo analysis failed memo=%s code=%s detail=%s", memo_id, exc.code, exc)
            return failed(exc.code)
        except Exception as exc:                                # 예상하지 못한 오류도 메모 저장은 그대로
            log.exception("memo analysis error memo=%s", memo_id)
            return failed(f"internal_error:{type(exc).__name__}")
        try:
            changes = self.tracking.sync(memo_id, result.items, result.confirmations)
            self._commit()
        except Exception as exc:
            self.repository.db.rollback()                       # 메모는 이미 커밋돼 있다
            log.exception("memo analysis save failed memo=%s", memo_id)
            return failed(f"save_failed:{type(exc).__name__}")
        log.info("memo analysis memo=%s items=%s created=%s done=%s confirmations=%s llm_calls=%s", memo_id,
                 len(result.items), len(changes["created"]), len(changes["done"]), len(result.confirmations), result.llm_calls)
        return {"status": "done", "error": None,
                "items": [self._item_out(e) for e in self.tracking.items(memo_id, ("active",))],
                "created": len(changes["created"]), "done": len(changes["done"]),
                "confirmations": result.confirmations, "out_of_scope": result.out_of_scope,
                "next_update_at": next_update_at()}

    def delete(self, user_id: int, memo_id: int) -> None:
        self._require_item(user_id, memo_id)
        if not self.repository.soft_delete(user_id, memo_id):
            raise BoardItemNotFoundError(memo_id)

    def _require_stock(self, user_id: int, symbol: str) -> None:
        if not self.repository.owns_stock(user_id, symbol):
            raise StockBoardNotFoundError(symbol)

    def _require_item(self, user_id: int, memo_id: int) -> dict[str, Any]:
        row = self.repository.get_owned(user_id, memo_id)
        if row is None or not self.repository.owns_stock(user_id, str(row["symbol"]).strip()):
            raise BoardItemNotFoundError(memo_id)
        return row

    def _response(self, row: dict[str, Any]) -> dict[str, Any]:
        memo_id = int(row["id"])
        common = {
            "id": str(memo_id),
            "stock_code": str(row["symbol"]).strip(),
            "title": row["title"] or "",
            "position": int(row.get("position") or 0),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
        kind = str(row["kind"])
        if kind == "note":
            color = row.get("color")
            return {
                **common,
                "kind": "memo",
                "body": row["content"],
                "tags": self.repository.tags(memo_id),
                "color": color if color in self._COLORS else "yellow",
                "pinned": bool(row.get("is_pinned")),
                "ai_linked": bool(row.get("ai_linked")),
                "ai_linked_at": row.get("ai_linked_at"),
                "price_conditions": self.tracking.price_conditions(memo_id),
                "unread_updates": self.tracking.unread_updates(memo_id),
            }
        if kind == "checklist":
            return {**common, "kind": "checklist", "items": self.repository.checklist_items(memo_id)}
        if kind == "reference":
            return {**common, "kind": "reference", "links": self.repository.links(memo_id)}
        raise InvalidBoardPatchError(f"지원하지 않는 메모 유형입니다: {kind}")
