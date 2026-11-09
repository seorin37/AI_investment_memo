"""근거 준비 — 후보를 골라 E1, E2… 번호를 붙인다. 번호는 날짜 최신순(같은 날이면 유사도순)이다.

1) pick_recent: 최신 날짜부터 하루씩 거슬러 올라가며(오늘 → 전날 → 전전날) 어디까지 볼지 정한다. 강한 후보가 나온 날에서 멈추고,
   그날부터 window_days일 전까지는 함께 본다 (공시가 나오고 하루이틀 뒤에 기사가 나오면 기사에서 멈춰 원본 공시가 빠지지 않게).
2) build_evidence: 그 범위 안에서 종류별로 유사도가 높은 것을 개수 상한만큼 고르고, 날짜 최신순으로 번호를 붙인다.
   (최신순으로 자르면 더 최신인 약한 기사들에 밀려 강한 후보가 빠질 수 있어서, 고르기는 유사도로 한다)
   공시 자리는 정기보고서와 수시공시가 나눠 쓰므로 유사도 대신 '자기 최소 기준보다 얼마나 높은가'로 비교한다
   (정기보고서는 유사도가 원래 높게 나와서 그대로 비교하면 형식적인 정기보고서 문구가 수시공시를 밀어낸다).
뉴스는 같은 사건 기사를 하나로 묶고(제목 유사도), 근거는 최대 max_news개. 뉴스 본문은 저장하지 않으므로 제목+제공 요약만 쓴다.
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


def _recent_first(c: Candidate) -> tuple[str, float]:
    return c.date, c.similarity


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
    passed = [c for c in candidates if c.similarity >= _limit(floor, c)]
    picked: list[Candidate] = []
    for day in sorted({c.date for c in passed}, reverse=True):
        picked += [c for c in passed if c.date == day]
        if any(c.similarity >= _limit(strong, c) for c in picked):
            edge = (date.fromisoformat(day) - timedelta(days=window_days)).isoformat()
            picked += [c for c in passed if edge <= c.date < day]
            break
    return picked


def build_evidence(candidates: list[Candidate], max_disclosure: int = 2, max_news: int = 3,
                   news_dup_similarity: float = 0.7, max_chars_news: int = 600,
                   max_chars_disclosure: int = 800, floor: dict[str, float] | None = None) -> list[Evidence]:
    """floor가 있으면 공시는 '유사도 - 자기 최소 기준'이 큰 순으로 고른다 (없으면 유사도순)."""
    ordered = sorted(candidates, key=lambda c: -c.similarity)
    margin = (lambda c: c.similarity - _limit(floor, c)) if floor else (lambda c: c.similarity)
    disclosures = sorted((c for c in ordered if c.kind == "disclosure"), key=margin, reverse=True)[:max_disclosure]
    news: list[Candidate] = []
    for c in (c for c in ordered if c.kind == "news"):
        if any(title_similarity(c.title, n.title) >= news_dup_similarity for n in news):
            continue                                  # 같은 사건 기사: 가장 유사한 하나만
        if len(news) < max_news:
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
