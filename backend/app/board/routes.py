"""Authenticated memo, checklist, and reference-board API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.auth.routes import get_current_user
from app.db import get_db, get_read_db

from .repository import BoardRepository
from .schemas import (
    AiLinkPatch,
    BoardItemPatch,
    BoardOrderPut,
    BoardResponse,
    ChecklistCreate,
    ConfirmationAnswer,
    ChecklistItemPatch,
    MemoCreate,
    ReferenceCreate,
)
from .service import (
    BoardItemNotFoundError,
    BoardService,
    InvalidBoardPatchError,
    StaleConfirmationError,
    StockBoardNotFoundError,
)


router = APIRouter(prefix="/api/v1", tags=["memo-board"])


def get_query_service(db: Session = Depends(get_read_db)) -> BoardService:
    return BoardService(BoardRepository(db))


def get_command_service(db: Session = Depends(get_db)) -> BoardService:
    return BoardService(BoardRepository(db))


def _user_id(current_user: dict) -> int:
    try:
        return int(current_user["id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(401, detail="유효하지 않은 인증 사용자입니다.") from exc


def _not_found() -> HTTPException:
    return HTTPException(404, detail="메모 또는 종목 보드를 찾을 수 없습니다.")


def _handle_error(exc: Exception) -> None:
    if isinstance(exc, (BoardItemNotFoundError, StockBoardNotFoundError)):
        raise _not_found() from exc
    if isinstance(exc, StaleConfirmationError):
        raise HTTPException(409, detail=str(exc)) from exc
    if isinstance(exc, InvalidBoardPatchError):
        raise HTTPException(422, detail=str(exc)) from exc
    raise exc


@router.get("/memos/pinned")
def list_pinned_memos(
    current: dict = Depends(get_current_user),
    service: BoardService = Depends(get_query_service),
):
    return service.list_pinned(_user_id(current))


@router.get("/stocks/{code}/board", response_model=list[BoardResponse])
def list_board(
    code: str,
    current: dict = Depends(get_current_user),
    service: BoardService = Depends(get_query_service),
):
    try:
        return service.list_board(_user_id(current), code)
    except (StockBoardNotFoundError, InvalidBoardPatchError) as exc:
        _handle_error(exc)


@router.put("/stocks/{code}/board-order", response_model=list[BoardResponse])
def put_board_order(
    code: str,
    payload: BoardOrderPut,
    current: dict = Depends(get_current_user),
    service: BoardService = Depends(get_command_service),
):
    """끌어서 옮긴 뒤 보드 카드 전체 순서를 저장하고, 새 순서의 보드를 돌려준다."""
    try:
        return service.reorder(_user_id(current), code, payload.ids)
    except (StockBoardNotFoundError, InvalidBoardPatchError) as exc:
        _handle_error(exc)


@router.post("/stocks/{code}/memos", response_model=BoardResponse, status_code=201)
def create_memo(
    code: str,
    payload: MemoCreate,
    current: dict = Depends(get_current_user),
    service: BoardService = Depends(get_command_service),
):
    try:
        return service.create_memo(_user_id(current), code, payload)
    except StockBoardNotFoundError as exc:
        _handle_error(exc)


@router.post("/stocks/{code}/checklists", response_model=BoardResponse, status_code=201)
def create_checklist(
    code: str,
    payload: ChecklistCreate,
    current: dict = Depends(get_current_user),
    service: BoardService = Depends(get_command_service),
):
    try:
        return service.create_checklist(_user_id(current), code, payload)
    except StockBoardNotFoundError as exc:
        _handle_error(exc)


@router.post("/stocks/{code}/references", response_model=BoardResponse, status_code=201)
def create_reference(
    code: str,
    payload: ReferenceCreate,
    current: dict = Depends(get_current_user),
    service: BoardService = Depends(get_command_service),
):
    try:
        return service.create_reference(_user_id(current), code, payload)
    except StockBoardNotFoundError as exc:
        _handle_error(exc)


@router.get("/board-items/{memo_id}", response_model=BoardResponse)
def get_board_item(
    memo_id: int,
    current: dict = Depends(get_current_user),
    service: BoardService = Depends(get_query_service),
):
    try:
        return service.get(_user_id(current), memo_id)
    except BoardItemNotFoundError as exc:
        _handle_error(exc)


@router.patch("/board-items/{memo_id}", response_model=BoardResponse)
def update_board_item(
    memo_id: int,
    payload: BoardItemPatch,
    current: dict = Depends(get_current_user),
    service: BoardService = Depends(get_command_service),
):
    try:
        values = payload.model_dump(exclude_unset=True)
        if payload.items is not None:
            values["items"] = [item.model_dump(exclude={"id"}) for item in payload.items]
        if payload.links is not None:
            values["links"] = [link.model_dump(exclude={"id"}) for link in payload.links]
        if not values:
            raise InvalidBoardPatchError("수정할 필드가 없습니다.")
        return service.update(_user_id(current), memo_id, values)
    except (BoardItemNotFoundError, InvalidBoardPatchError) as exc:
        _handle_error(exc)


@router.patch("/checklists/{memo_id}/items/{item_id}", response_model=BoardResponse)
def update_checklist_item(
    memo_id: int,
    item_id: int,
    payload: ChecklistItemPatch,
    current: dict = Depends(get_current_user),
    service: BoardService = Depends(get_command_service),
):
    try:
        return service.update_checklist_item(
            _user_id(current), memo_id, item_id, payload.model_dump(exclude_unset=True)
        )
    except (BoardItemNotFoundError, InvalidBoardPatchError) as exc:
        _handle_error(exc)


@router.put("/memos/{memo_id}/ai-link", response_model=BoardResponse)
def set_ai_link(
    memo_id: int,
    payload: AiLinkPatch,
    current: dict = Depends(get_current_user),
    service: BoardService = Depends(get_command_service),
):
    try:
        return service.set_ai_link(_user_id(current), memo_id, payload.enabled)
    except (BoardItemNotFoundError, InvalidBoardPatchError) as exc:
        _handle_error(exc)


@router.post("/memos/{memo_id}/confirmations", response_model=BoardResponse)
def answer_confirmation(
    memo_id: int,
    payload: ConfirmationAnswer,
    current: dict = Depends(get_current_user),
    service: BoardService = Depends(get_command_service),
):
    """메모 분석의 확인 질문에서 고른 선택지(option_id)로 가격 항목을 만든다. 메모가 바뀌었으면 409."""
    try:
        return service.confirm(_user_id(current), memo_id, payload.option_id)
    except (BoardItemNotFoundError, InvalidBoardPatchError, StaleConfirmationError) as exc:
        _handle_error(exc)


@router.delete("/board-items/{memo_id}", status_code=204)
def delete_board_item(
    memo_id: int,
    current: dict = Depends(get_current_user),
    service: BoardService = Depends(get_command_service),
):
    try:
        service.delete(_user_id(current), memo_id)
    except BoardItemNotFoundError as exc:
        _handle_error(exc)
    return Response(status_code=204)
