"""투자 기록 요청 검증. 블록 모양은 frontend/src/types/models.ts 의 JournalBlock 과 같다."""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field

_ID = Field(min_length=1, max_length=64)
_TEXT = Field(default="", max_length=20_000)


class _Block(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = _ID


class TextBlock(_Block):
    type: Literal["paragraph", "heading"]
    text: str = _TEXT
    highlight: bool | None = None


class ChecklistBlock(_Block):
    type: Literal["checklist"]
    text: str = _TEXT
    checked: bool = False


class TableBlock(_Block):
    type: Literal["table"]
    rows: list[list[Annotated[str, Field(max_length=2_000)]]] = Field(default_factory=list, max_length=100)


class AttachmentBlock(_Block):
    type: Literal["attachment"]
    name: str = Field(min_length=1, max_length=500)
    url: str = Field(min_length=1, max_length=2_000)


JournalBlock = Annotated[Union[TextBlock, ChecklistBlock, TableBlock, AttachmentBlock], Field(discriminator="type")]

StockCode = Annotated[str, Field(pattern=r"^[0-9A-Z]{6}$")]


class JournalCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(default="", max_length=500)
    stock_code: StockCode | None = None
    blocks: list[JournalBlock] = Field(default_factory=list, max_length=500)


class JournalPatch(BaseModel):
    """보낸 필드만 바꾼다. stock_code 를 null 로 보내면 종목 연결을 지운다 (model_fields_set 으로 구분)."""

    model_config = ConfigDict(extra="forbid")
    title: str | None = Field(default=None, max_length=500)
    stock_code: StockCode | None = None
    blocks: list[JournalBlock] | None = Field(default=None, max_length=500)
