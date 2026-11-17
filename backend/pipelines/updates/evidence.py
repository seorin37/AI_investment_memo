"""근거 준비 — 후보를 골라 E1, E2… 번호를 붙인다. 번호는 날짜 최신순(같은 날이면 유사도순)이다.

1) pick_recent: 최신 날짜부터 하루씩 거슬러 올라가며(오늘 → 전날 → 전전날) 어디까지 볼지 정한다. 강한 후보가 나온 날에서 멈추고,
   그날부터 window_days일 전까지는 함께 본다 (공시가 나오고 하루이틀 뒤에 기사가 나오면 기사에서 멈춰 원본 공시가 빠지지 않게).
2) build_evidence: 그 범위 안에서 종류별로 유사도가 높은 것을 고르고, 날짜 최신순으로 번호를 붙인다.
   mode=legacy(기본): 공시 max_disclosure개(청크 단위), 뉴스 max_news개.
   mode=all(2026-11-09): 임계값을 넘은 건 다 넣고 안전 상한만 둔다. 공시는 접수번호 단위로 세어 공시당 최고 청크
   max_chunks_per_disclosure개, 공시 max_disclosure_docs건까지. 뉴스는 중복을 뺀 나머지 전부. 합이 max_total을 넘으면
   뉴스부터(유사도 낮은 것부터) 자른다. 공시는 자르지 않는다.
   (최신순으로 자르면 더 최신인 약한 기사들에 밀려 강한 후보가 빠질 수 있어서, 고르기는 유사도로 한다)
   공시 자리는 정기보고서와 수시공시가 나눠 쓰므로 유사도 대신 '자기 최소 기준보다 얼마나 높은가'로 비교한다
   (정기보고서는 유사도가 원래 높게 나와서 그대로 비교하면 형식적인 정기보고서 문구가 수시공시를 밀어낸다).
뉴스는 같은 사건 기사를 하나로 묶고(제목 유사도), 근거는 최대 max_news개. 뉴스 본문은 저장하지 않으므로 제목+제공 요약만 쓴다.
3) split_same_event(설정 same_event, 기본 꺼짐): 근거로 뽑힐 공시와 같은 사건으로 묶인 기사(same_event.link_same_event)는
   근거에서 빼서 그 공시 카드의 보조 기사로 넘긴다. 남는 뉴스 자리에는 묶이지 않은 다른 사건 기사가 들어간다.
"""

from __future__ import annotations

from datetime import date, timedelta

from .models import Candidate, Evidence


def _bigrams(text: str) -> set[str]:
    t = "".join(text.split())
    return {t[i:i + 2] for i in range(len(t) - 1)}


def title_similarity(a: str, b: str) -> float:
    x, y = _bigrams(a), _bigrams(b)
    return len(x & y) / len(x | y) if x and y else 0.0


def shown_text(c: Candidate, max_chars: int) -> str:
    return (c.text or "")[:max_chars]


def candidate_score(c: Candidate) -> float:
    """검색 방식이 제공한 순위 점수. 기존 후보는 dense similarity와 같다."""
    return c.retrieval_score if c.retrieval_score is not None else c.similarity


def bypasses_floor(c: Candidate) -> bool:
    """하이브리드 상위 공시는 관련성 LLM을 통과한 뒤이므로 dense 기준으로 다시 버리지 않는다."""
    return c.kind == "disclosure" and c.retrieval == "hybrid"


def _recent_first(c: Candidate) -> tuple[str, float]:
    return c.date, candidate_score(c)


def threshold_key(c: Candidate) -> str:
    """임계값을 고르는 기준: news(제목+요약) | news_chunks(원문 청크) | disclosure(정기보고서) | event(수시공시)."""
    return {"event": "event", "chunk": "news_chunks"}.get(c.doc, c.kind)


def _limit(table: dict[str, float], c: Candidate) -> float:
    return table.get(threshold_key(c), table[c.kind])         # event·news_chunks 값이 없으면 공시·뉴스 값을 쓴다


def pick_recent(candidates: list[Candidate], floor: dict[str, float], strong: dict[str, float],
                window_days: int = 0) -> list[Candidate]:
    """최신 날짜부터 하루씩 거슬러 올라가며 종류별 임계값(floor)을 넘은 후보를 모은다.
    강한 후보(종류별 strong 이상)가 처음 나온 날에서 멈춘다. 그날까지 모은 더 최신의 약한 후보도 함께 돌려주고,
    멈춘 날부터 window_days일 전까지의 후보도 더한다. 끝까지 강한 후보가 없으면 모은 것을 모두 돌려준다 (없으면 빈 목록)."""
    passed = [c for c in candidates if bypasses_floor(c) or candidate_score(c) >= _limit(floor, c)]
    picked: list[Candidate] = []
    for day in sorted({c.date for c in passed}, reverse=True):
        picked += [c for c in passed if c.date == day]
        if any(candidate_score(c) >= _limit(strong, c) for c in picked):
            edge = (date.fromisoformat(day) - timedelta(days=window_days)).isoformat()
            picked += [c for c in passed if edge <= c.date < day]
            break
    return picked


def rcept_of(ref: str) -> str:
    """disc:<접수번호>#<청크> → 접수번호 (같은 공시의 다른 청크는 같은 공시)."""
    return ref.split(":", 1)[1].split("#", 1)[0]


MODES = ("legacy", "all")


def pick_disclosures(candidates: list[Candidate], max_disclosure: int = 2,
                     floor: dict[str, float] | None = None, mode: str = "legacy", max_disclosure_docs: int = 5,
                     max_chunks_per_disclosure: int = 2) -> list[Candidate]:
    """근거로 쓸 공시. floor가 있으면 '유사도 - 자기 최소 기준'이 큰 순으로 고른다 (없으면 유사도순).
    legacy: 청크 max_disclosure개. all: 접수번호마다 최고 청크 max_chunks_per_disclosure개, 공시 max_disclosure_docs건."""
    if mode not in MODES:
        raise ValueError(f"evidence_mode는 {MODES} 중 하나여야 합니다: {mode}")
    ordered = sorted(candidates, key=lambda c: -candidate_score(c))
    margin = (lambda c: candidate_score(c) - _limit(floor, c)) if floor else candidate_score
    discs = sorted((c for c in ordered if c.kind == "disclosure"), key=margin, reverse=True)
    if mode == "legacy":
        return discs[:max_disclosure]
    by_doc: dict[str, list[Candidate]] = {}
    for c in discs:                                             # margin 순이라 접수번호마다 처음 나온 게 가장 높은 청크
        chunks = by_doc.setdefault(rcept_of(c.ref), [])
        if len(chunks) < max_chunks_per_disclosure:
            chunks.append(c)
    return [c for chunks in list(by_doc.values())[:max_disclosure_docs] for c in chunks]


def evidence_options(cfg: dict) -> dict:
    """topic 설정 → pick_disclosures·build_evidence에 넘기는 근거 고르기 값."""
    return {"mode": cfg.get("evidence_mode", "legacy"), "max_disclosure_docs": cfg.get("max_disclosure_docs", 5),
            "max_chunks_per_disclosure": cfg.get("max_chunks_per_disclosure", 2), "max_total": cfg.get("max_total", 15)}


def split_same_event(candidates: list[Candidate], links: dict[str, str], max_disclosure: int = 2,
                     floor: dict[str, float] | None = None, **options) -> tuple[list[Candidate], list[tuple[Candidate, str]]]:
    """(남길 후보, [(같은 사건으로 묶여 근거에서 뺀 기사, 공시 접수번호)]). links: 기사 ref → 공시 접수번호.
    그 공시가 근거로 뽑힐 때만 뺀다 (공시가 근거에 못 들면 기사는 그대로 근거 후보로 남는다). options는 evidence_options."""
    options.pop("max_total", None)
    chosen = {rcept_of(c.ref) for c in pick_disclosures(candidates, max_disclosure, floor, **options)}
    keep, grouped = [], []
    for c in candidates:
        rcept = links.get(c.ref) if c.kind == "news" else None
        if rcept is not None and rcept in chosen:
            grouped.append((c, rcept))
        else:
            keep.append(c)
    return keep, grouped


def build_evidence(candidates: list[Candidate], max_disclosure: int = 2, max_news: int = 3,
                   news_dup_similarity: float = 0.7, max_chars_news: int = 600,
                   max_chars_disclosure: int = 800, floor: dict[str, float] | None = None, mode: str = "legacy",
                   max_disclosure_docs: int = 5, max_chunks_per_disclosure: int = 2, max_total: int = 15) -> list[Evidence]:
    """floor가 있으면 공시는 '유사도 - 자기 최소 기준'이 큰 순으로 고른다 (없으면 유사도순). mode는 모듈 설명 2)."""
    ordered = sorted(candidates, key=lambda c: -candidate_score(c))
    disclosures = pick_disclosures(candidates, max_disclosure, floor, mode, max_disclosure_docs, max_chunks_per_disclosure)
    news: list[Candidate] = []
    news_cap = max_news if mode == "legacy" else max(0, max_total - len(disclosures))   # all: 공시는 자르지 않고 뉴스부터
    for c in (c for c in ordered if c.kind == "news"):
        if any(title_similarity(c.title, n.title) >= news_dup_similarity for n in news):
            continue                                  # 같은 사건 기사: 가장 유사한 하나만
        if len(news) < news_cap:
            news.append(c)
    out = []
    for i, c in enumerate(sorted(disclosures + news, key=_recent_first, reverse=True), 1):
        limit = max_chars_disclosure if c.kind == "disclosure" else max_chars_news
        out.append(Evidence(f"E{i}", c, shown_text(c, limit)))
    return out


def related_news(evidence: list[Evidence], used_refs: set[str], min_similarity: float) -> list[tuple[str, str]]:
    """공시 중심 카드에 덧붙일 관련 기사. 이미 근거로 쓴 기사는 빼고, 유사도가 min_similarity 이상인 것만.

    LLM이 문장으로 쓴 근거가 아니라 '이 기사도 있어요' 링크다 (제목·매체만 보여 주고 사실 문장은 만들지 않는다).
    """
    return [(e.candidate.ref, e.candidate.title) for e in evidence
            if e.candidate.kind == "news" and e.candidate.ref not in used_refs and e.candidate.similarity >= min_similarity]
