"""후보 검색 — 항목 임베딩과 가까운 뉴스·공시를 DB에서 찾는다 (읽기 전용, 종목 필터 + 코사인 유사도).

뉴스는 news_embedding_variants(dense 벡터), 공시는 disclosure_chunks.dense_embedding을 쓴다.
뉴스 본문은 저장하지 않으므로 text는 제공 요약이다.

- news_candidates / disclosure_candidates: 유사도 상위 k건 (noise_floor가 쓴다)
- recent_news_candidates / recent_disclosure_candidates: 임계값(floor) 이상인 후보를 날짜 최신순으로 k건.
  날짜를 하루씩 거슬러 가며 고르는 건 evidence.pick_recent가 한다.
"""

from __future__ import annotations

from datetime import date

from .models import Candidate

NEWS_SQL = """
SELECT a.id, a.title, a.summary, a.url, a.published_at::date, s.name,
       1 - (v.dense <=> %(q)s::vector) AS sim
FROM news_embedding_variants v
JOIN news_articles a ON a.id = v.news_id
JOIN news_stocks ns ON ns.news_id = a.id AND ns.symbol = %(symbol)s
JOIN news_sources s ON s.id = a.source_id
WHERE v.variant = %(variant)s AND a.published_at >= %(since)s
ORDER BY v.dense <=> %(q)s::vector
LIMIT %(k)s
"""

DISCLOSURE_SQL = """
SELECT c.rcept_no, c.chunk_index, c.section, c.chunk_text, d.title, d.rcept_dt, d.source_url,
       1 - (c.dense_embedding <=> %(q)s::vector) AS sim
FROM disclosure_chunks c
JOIN disclosures d ON d.rcept_no = c.rcept_no
WHERE d.symbol = %(symbol)s AND c.dense_embedding IS NOT NULL AND d.rcept_dt >= %(since)s
ORDER BY c.dense_embedding <=> %(q)s::vector
LIMIT %(k)s
"""


RECENT_NEWS_SQL = """
SELECT a.id, a.title, a.summary, a.url, a.published_at::date, s.name,
       1 - (v.dense <=> %(q)s::vector) AS sim
FROM news_embedding_variants v
JOIN news_articles a ON a.id = v.news_id
JOIN news_stocks ns ON ns.news_id = a.id AND ns.symbol = %(symbol)s
JOIN news_sources s ON s.id = a.source_id
WHERE v.variant = %(variant)s AND a.published_at >= %(since)s
  AND 1 - (v.dense <=> %(q)s::vector) >= %(floor)s
ORDER BY a.published_at DESC, v.dense <=> %(q)s::vector
LIMIT %(k)s
"""

RECENT_DISCLOSURE_SQL = """
SELECT c.rcept_no, c.chunk_index, c.section, c.chunk_text, d.title, d.rcept_dt, d.source_url,
       1 - (c.dense_embedding <=> %(q)s::vector) AS sim
FROM disclosure_chunks c
JOIN disclosures d ON d.rcept_no = c.rcept_no
WHERE d.symbol = %(symbol)s AND c.dense_embedding IS NOT NULL AND d.rcept_dt >= %(since)s
  AND 1 - (c.dense_embedding <=> %(q)s::vector) >= %(floor)s
ORDER BY d.rcept_dt DESC, c.dense_embedding <=> %(q)s::vector
LIMIT %(k)s
"""


def vector_literal(vec) -> str:
    return "[" + ",".join(f"{float(x):.8g}" for x in vec) + "]"


def _news_rows(conn, sql: str, params: dict, symbol: str) -> list[Candidate]:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    return [Candidate(ref=f"news:{nid}", kind="news", symbol=symbol, date=str(day), title=title,
                      text=summary or "", url=url, source=source or "", similarity=float(sim))
            for nid, title, summary, url, day, source, sim in rows]


def _disclosure_rows(conn, sql: str, params: dict, symbol: str) -> list[Candidate]:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    return [Candidate(ref=f"disc:{rcept}#{idx}", kind="disclosure", symbol=symbol, date=str(day),
                      title=f"{title} · {section}" if section else title, text=text or "", url=url,
                      source="DART", similarity=float(sim))
            for rcept, idx, section, text, title, day, url, sim in rows]


def news_candidates(conn, symbol: str, query_vec, since: date, k: int, variant: str = "hybrid") -> list[Candidate]:
    return _news_rows(conn, NEWS_SQL, {"q": vector_literal(query_vec), "symbol": symbol, "variant": variant,
                                       "since": since, "k": k}, symbol)


def disclosure_candidates(conn, symbol: str, query_vec, since: date, k: int) -> list[Candidate]:
    return _disclosure_rows(conn, DISCLOSURE_SQL, {"q": vector_literal(query_vec), "symbol": symbol,
                                                   "since": since, "k": k}, symbol)


def recent_news_candidates(conn, symbol: str, query_vec, since: date, k: int, floor: float,
                           variant: str = "hybrid") -> list[Candidate]:
    return _news_rows(conn, RECENT_NEWS_SQL, {"q": vector_literal(query_vec), "symbol": symbol, "variant": variant,
                                              "since": since, "k": k, "floor": floor}, symbol)


def recent_disclosure_candidates(conn, symbol: str, query_vec, since: date, k: int, floor: float) -> list[Candidate]:
    return _disclosure_rows(conn, RECENT_DISCLOSURE_SQL, {"q": vector_literal(query_vec), "symbol": symbol,
                                                          "since": since, "k": k, "floor": floor}, symbol)
