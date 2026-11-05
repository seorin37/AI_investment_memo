from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


MemoColor = Literal["yellow", "blue", "pink", "green", "purple"]
ReferenceType = Literal["ir", "news", "report", "disclosure", "etc"]


def _clean_tags(values: list[str]) -> list[str]:
    cleaned = [value.strip() for value in values if value.strip()]
    if any(len(value) > 80 for value in cleaned):
        raise ValueError("태그는 80자 이하여야 합니다.")
    return list(dict.fromkeys(cleaned))


class ChecklistItemInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str | None = None
    text: str = Field(min_length=1, max_length=500)
    done: bool = False

    @field_validator("text")
    @classmethod
    def clean_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("체크리스트 내용은 비어 있을 수 없습니다.")
        return cleaned


class ChecklistItemResponse(BaseModel):
    id: str
    text: str
    done: bool


class ReferenceLinkInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str | None = None
    title: str = Field(min_length=1, max_length=500)
    url: HttpUrl
    ref_type: ReferenceType = "etc"
    source: Literal["link", "file"] = "link"

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("링크 제목은 비어 있을 수 없습니다.")
        return cleaned


class ReferenceLinkResponse(BaseModel):
    id: str
    title: str
    url: str
    ref_type: ReferenceType
    source: Literal["link", "file"]


class MemoCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=500)
    body: str = Field(max_length=100_000)
    tags: list[str] = Field(default_factory=list, max_length=50)
    color: MemoColor = "yellow"
    ai_linked: bool = False
    pinned: bool = False

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("메모 제목은 비어 있을 수 없습니다.")
        return cleaned

    @field_validator("tags")
    @classmethod
    def clean_tags(cls, values: list[str]) -> list[str]:
        return _clean_tags(values)


class ChecklistCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=500)
    items: list[ChecklistItemInput] = Field(default_factory=list, max_length=200)

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("체크리스트 제목은 비어 있을 수 없습니다.")
        return cleaned


class ReferenceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=500)
    links: list[ReferenceLinkInput] = Field(default_factory=list, max_length=100)

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("참고자료 제목은 비어 있을 수 없습니다.")
        return cleaned


class BoardItemPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = Field(default=None, min_length=1, max_length=500)
    body: str | None = Field(default=None, max_length=100_000)
    tags: list[str] | None = Field(default=None, max_length=50)
    color: MemoColor | None = None
    pinned: bool | None = None
    position: int | None = Field(default=None, ge=0)
    items: list[ChecklistItemInput] | None = Field(default=None, max_length=200)
    links: list[ReferenceLinkInput] | None = Field(default=None, max_length=100)

    @field_validator("title")
    @classmethod
    def clean_optional_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("제목은 비어 있을 수 없습니다.")
        return cleaned

    @field_validator("tags")
    @classmethod
    def clean_optional_tags(cls, values: list[str] | None) -> list[str] | None:
        return _clean_tags(values) if values is not None else None


class ChecklistItemPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str | None = Field(default=None, min_length=1, max_length=500)
    done: bool | None = None

    @field_validator("text")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("체크리스트 내용은 비어 있을 수 없습니다.")
        return cleaned


class AiLinkPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool


class BoardBase(BaseModel):
    id: str
    stock_code: str
    title: str
    position: int
    created_at: datetime
    updated_at: datetime


class MemoResponse(BoardBase):
    kind: Literal["memo"]
    body: str
    tags: list[str]
    color: MemoColor
    pinned: bool
    ai_linked: bool
    ai_linked_at: datetime | None
    price_conditions: list = Field(default_factory=list)
    unread_updates: int = 0


class ChecklistResponse(BoardBase):
    kind: Literal["checklist"]
    items: list[ChecklistItemResponse]


class ReferenceResponse(BoardBase):
    kind: Literal["reference"]
    links: list[ReferenceLinkResponse]


BoardResponse = MemoResponse | ChecklistResponse | ReferenceResponse
