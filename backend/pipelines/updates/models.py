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
    time_hint: str = ""               # 메모 분석이 뽑은 시점·기한 원문 ("다음 주", "이번 분기 실적 발표"). 2026-11-09 전달만
                                      # (DB 열 없음, 기한 날짜 계산·카드 반영은 아직 안 함. 검색어 query_text에도 넣지 않는다)

    @property
    def query_text(self) -> str:
        if self.category == "ask" and self.memo_text:
            # 실험(2026-11-17): 질문은 메모 원문 + 종목명으로 검색한다. 메모 분석이 질문을 실행마다 다르게 정리해
            # ("실적에 회계상…" / "연결 재무제표와 실적에…") 검색 후보가 바뀌고 답이 나왔다 안 나왔다 했다 (N09)
            return " ".join(x for x in (self.company_name, self.memo_text) if x).strip()
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
    retrieval_score: float | None = None  # 하이브리드 검색 점수. 없으면 similarity를 순위·기준값에 쓴다
    retrieval: str = ""                  # "hybrid": dense 기준 대신 관련성 판정이 통과 여부를 정한다


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
class CardV2:
    """v2 카드 (2026-11-10, topic.card_schema: v2). 사건 하나 · 문장마다 근거 하나.
    title·summary·reason·evidence는 v1 Card를 읽던 코드(보고서·검수 호출)가 그대로 쓰게 맞춘 별칭이다."""
    status: str                       # update | no_update
    headline: str = ""
    when: str = ""                    # 사건 날짜 YYYY-MM-DD
    facts: list[tuple[str, str]] = field(default_factory=list)      # (문장, evidence_id). "비교 자료 없음"은 evidence_id ""
    memo_link: str = ""
    sources: list[str] = field(default_factory=list)                 # facts에서 쓴 evidence_id
    confidence: float = 0.0
    explanation: str = ""            # 설명 문단 (topic.explanation.enabled일 때만, 2026-11-12 시험)
    calc: list[dict] = field(default_factory=list)   # 실험(2026-11-17) ask: 코드가 계산할 두 값·근거 번호 (calc.py)

    @property
    def title(self) -> str:
        return self.headline

    @property
    def summary(self) -> list[str]:
        return [t for t, _ in self.facts]

    @property
    def reason(self) -> str:
        return self.memo_link

    @property
    def evidence(self) -> list[tuple[str, str]]:
        return [(eid, t) for t, eid in self.facts if eid]


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
    # 같은 사건 기사 (same_event): 공시와 같은 사건으로 묶여 근거에서 뺀 기사. {ref, title, source, date, url}만, 기사 문장은 쓰지 않는다
    supporting_news: list[dict] = field(default_factory=list)
    # v2 카드 (card_schema="v2"일 때만 채운다. v1 카드의 cards.jsonl 모양은 그대로)
    card_schema: str = "v1"
    when: str = ""
    facts: list[dict] = field(default_factory=list)          # {text, ref}. ref ""는 코드가 붙인 "비교 자료 없음"
    merged_items: list[dict] = field(default_factory=list)   # 같은 메모·같은 근거라 이 카드로 합친 다른 항목 {item_id, description}
    explanation: str = ""                                     # 설명 문단 (topic.explanation 켰을 때만)
    coverage: str = ""                                        # 자료 범위 문구 ("10월 28일 이후 기사 기준", 뉴스를 쓴 v2 카드만)
    calculations: list[dict] = field(default_factory=list)   # 실험(2026-11-17) ask: 코드가 검증·계산한 값 (calc.compute)
    source_list: list[dict] = field(default_factory=list)    # 실험(2026-11-18) ask: 답 아래에 모아 보일 출처 (topic.source_list)


@dataclass
class Response:
    """사용자 응답 한 건 (response.py가 정한다, 2026-11-10). LLM이 아니라 코드가 유형을 정한다.
    type: update_card | price_card | no_new_info | no_data | needs_confirmation | out_of_scope
    scope: item(추적 항목) | sentence(메모 문장) | memo(메모 전체)"""
    type: str
    scope: str
    memo_id: str = ""
    item_id: str = ""
    sentence_index: int | None = None
    user_visible: bool = True          # False면 내부 기록(responses.jsonl)에만 남고 사용자에게 보이지 않는다
    reason: str = ""                   # 왜 이 유형인지 (check_failed, call_failed, parse_failed, no_candidates …)
    message: str = ""                  # 사용자에게 보일 문구 (카드면 카드 제목)
    question: str = ""                 # needs_confirmation: 질문 문장
    options: list[dict] = field(default_factory=list)   # needs_confirmation: 선택지 (없으면 빈 목록)
    card: dict | None = None           # update_card·price_card: results.draft_to_dict 모양
    fail_codes: list[str] = field(default_factory=list)
    checked_at: str = ""               # 확인한 시각 (no_new_info는 이 값과 status만 남긴다)
    text: str = ""                     # sentence 범위: 메모 문장
    relevance: dict | None = None      # 관련성 판정 (relevance.Relevance.to_dict, 2026-11-10): 범위·판정 수·이유 코드·후보별 O/X


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
    grouped: list = field(default_factory=list)              # (기사 Candidate, 공시 접수번호): 같은 사건으로 묶여 근거에서 뺀 기사
    checks: list[dict] = field(default_factory=list)         # v2 검사 기록 {stage: card|format_retry|verify, card, codes}
                                                             # (topic._judge_v2, 2026-11-17. 실행 결과 outcomes.jsonl에만 쓴다)
