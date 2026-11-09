"""모듈 간에 주고받는 데이터. 파이프라인 전체가 이 모양만 안다."""

from __future__ import annotations

from dataclasses import dataclass, field


class CreditsExhausted(RuntimeError):
    """LLM 호출 함수가 크레딧 소진을 알릴 때 던진다. 고정 문구 카드로 대체하지 않고 그대로 위로 올린다."""


@dataclass(frozen=True)
class TrackingItem:
    item_id: str
    symbol: str                       # 항목이 가리키는 종목 (지금은 메모 종목)
    type: str                         # topic | price_below | price_above
    description: str
    keywords: tuple[str, ...] = ()
    price_threshold: int | None = None
    category: str = ""                # 폴백 분류 코드 (A1~C4). 답변 방식이 코드마다 다르다
    memo_text: str = ""               # 항목이 나온 메모 문장 (정제본, 참고용)
    company_name: str = ""            # 프롬프트에 넣는 종목명 (stocks.name)
    previous_checked_at: str = ""     # 이전 확인 시점 (없으면 빈 문자열)
    already_shown_ids: tuple[str, ...] = ()   # 이미 사용자에게 보여 준 출처 ref (news:123, disc:…)
    previous_summary: str = ""        # 직전 카드 요약
    fingerprint: str = ""             # 직전 카드 식별값

    @property
    def query_text(self) -> str:
        return " ".join([self.description, *self.keywords]).strip()


@dataclass(frozen=True)
class Candidate:
    ref: str                          # "news:123" | "disc:<rcept_no>#<chunk_index>"
    kind: str                         # news | disclosure
    symbol: str
    date: str                         # YYYY-MM-DD
    title: str
    text: str                         # 뉴스: 제공 요약(본문 저장 금지), 공시: 청크 원문
    url: str | None
    source: str                       # 매체명 또는 "DART"
    similarity: float
    doc: str = ""                     # 공시: periodic(정기보고서) | event(수시공시), 뉴스: chunk(원문 청크 검색) | ""(제목+요약). 임계값을 따로 쓴다


@dataclass(frozen=True)
class Evidence:
    """LLM에 넣는 근거. 실제 출처 번호 대신 E1, E2… 임시 번호만 LLM에 보이고 코드가 되돌린다."""
    eid: str
    candidate: Candidate
    shown_text: str                   # LLM이 실제로 본 글 (검사는 이 글 기준)


@dataclass
class Card:
    status: str                       # update | no_update
    title: str = ""
    summary: list[str] = field(default_factory=list)
    reason: str = ""
    evidence: list[tuple[str, str]] = field(default_factory=list)   # (source_id, fact)
    confidence: float = 0.0


@dataclass
class Answer:
    """즉시 답변 (지침서 2). status는 answer | cannot_answer."""
    status: str
    reason_code: str = "none"
    answer: list[str] = field(default_factory=list)
    evidence: list[tuple[str, str]] = field(default_factory=list)
    confidence: float = 0.0


@dataclass
class UpdateDraft:
    item: TrackingItem
    type: str                         # news | disclosure | price_condition
    title: str
    summary: str
    reason: str
    sources: list[tuple[str, str | None]] = field(default_factory=list)   # (ref, quote=LLM이 쓴 사실 한 줄)
    price_state: str | None = None
    details: dict | None = None
    observed_trade_date: str | None = None
    origin: str = "llm"               # llm | fixed
    related_news: list[tuple[str, str]] = field(default_factory=list)   # (ref, 기사 제목): 공시 카드에 덧붙는 관련 기사 (링크만, LLM 문장 없음)


@dataclass
class TopicOutcome:
    kind: str                         # no_candidates | not_called | no_update | update | fixed_card
    evidence: list[Evidence] = field(default_factory=list)
    card: Card | None = None
    fail_codes: list[str] = field(default_factory=list)   # 코드 검사에 걸린 이유 (LLM 원본 기준)
    draft: UpdateDraft | None = None
    raw: str = ""                    # LLM 원문 (형식 오류 원인을 보려고 보고서에 남긴다)
    retried: bool = False            # 형식 오류로 한 번 다시 요청했는지
    verify_notes: list[str] = field(default_factory=list)   # 검수 호출이 막은 문장과 이유 (보고서용)