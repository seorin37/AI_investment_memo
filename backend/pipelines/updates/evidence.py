"""근거 준비 — 후보를 골라 E1, E2… 번호를 붙인다. 공시 → 뉴스 순으로 믿는다 (지침서 Ⅱ-2·3).

뉴스는 같은 사건 기사를 하나로 묶고(제목 유사도), 근거는 최대 max_news개. 뉴스 본문은 저장하지 않으므로 제목+제공 요약만 쓴다.
"""

from __future__ import annotations

from .models import Candidate, Evidence


def _bigrams(text: str) -> set[str]:
    t = "".join(text.split())
    return {t[i:i + 2] for i in range(len(t) - 1)}


def title_similarity(a: str, b: str) -> float:
    x, y = _bigrams(a), _bigrams(b)
    return len(x & y) / len(x | y) if x and y else 0.0


def shown_text(c: Candidate, max_chars: int) -> str:
    return (c.text or "")[:max_chars]


def build_evidence(candidates: list[Candidate], max_disclosure: int = 2, max_news: int = 3,
                   news_dup_similarity: float = 0.7, max_chars_news: int = 600,
                   max_chars_disclosure: int = 800) -> list[Evidence]:
    ordered = sorted(candidates, key=lambda c: -c.similarity)
    disclosures = [c for c in ordered if c.kind == "disclosure"][:max_disclosure]
    news: list[Candidate] = []
    for c in (c for c in ordered if c.kind == "news"):
        if any(title_similarity(c.title, n.title) >= news_dup_similarity for n in news):
            continue                                  # 같은 사건 기사: 가장 유사한 하나만
        if len(news) < max_news:
            news.append(c)
    out = []
    for i, c in enumerate(disclosures + news, 1):
        limit = max_chars_disclosure if c.kind == "disclosure" else max_chars_news
        out.append(Evidence(f"E{i}", c, shown_text(c, limit)))
    return out


def related_news(evidence: list[Evidence], used_refs: set[str], min_similarity: float) -> list[tuple[str, str]]:
    """공시 중심 카드에 덧붙일 관련 기사. 이미 근거로 쓴 기사는 빼고, 유사도가 min_similarity 이상인 것만.

    LLM이 문장으로 쓴 근거가 아니라 '이 기사도 있어요' 링크다 (제목·매체만 보여 주고 사실 문장은 만들지 않는다).
    """
    return [(e.candidate.ref, e.candidate.title) for e in evidence
            if e.candidate.kind == "news" and e.candidate.ref not in used_refs and e.candidate.similarity >= min_similarity]
