"""후보 검색 — 항목 임베딩과 가까운 뉴스·공시를 DB에서 찾는다 (읽기 전용, 종목 필터 + 코사인 유사도).

뉴스는 news_embedding_variants(dense 벡터), 공시는 disclosure_chunks.dense_embedding을 쓴다.
뉴스 본문은 저장하지 않으므로 text는 제공 요약이다.

- news_candidates / disclosure_candidates: 유사도 상위 k건 (noise_floor가 쓴다)
- recent_news_candidates / recent_disclosure_candidates: 임계값(floor) 이상인 후보를 날짜 최신순으로 k건.
  날짜를 하루씩 거슬러 가며 고르는 건 evidence.pick_recent가 한다.
- drop_other_company_news: 제목이 다른 상장사 이름으로 시작하고 추적 종목 이름이 없는 기사를 뺀다 (DB 조회 없음, 이름 목록은 호출자가 준다)

공시는 정기보고서와 수시공시(disclosures.kind = major/other)가 같은 테이블에 있다. 수시공시는 doc="event"로 표시하고
임계값을 따로 쓴다(event_floor). 정정공시가 고친 원본(disclosure_events.corrects가 가리키는 공시)은 후보에서 뺀다.
자회사 공시("자회사의 주요경영사항", disclosure_events.is_subsidiary)는 기본으로 뺀다: 자회사 실적을 모회사 실적처럼 쓰지 않게.
"""

from __future__ import annotations

import re
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

EVENT_KINDS = ("major", "other")   # 수시공시 (주요사항보고서 / 거래소·기타 공시)

# 정정공시가 가리키는 원본은 뺀다 (정정 전 숫자와 정정 후 숫자가 함께 근거로 들어가지 않게)
NOT_CORRECTED = "NOT EXISTS (SELECT 1 FROM disclosure_events e WHERE e.corrects = d.rcept_no)"
# 자회사 공시는 subsidiary=true일 때만 넣는다
SUBSIDIARY = ("(%(subsidiary)s OR NOT EXISTS "
              "(SELECT 1 FROM disclosure_events s WHERE s.rcept_no = d.rcept_no AND s.is_subsidiary))")

# 수시공시 표의 단위("단위 : 억원, %")는 한 청크에만 있다. 단위가 없는 청크에 붙일 수 있게 같은 공시에서 읽어 온다
# (2026-11-05 삼성 잠정실적 #1의 순이익 712,695(억원)를 LLM이 백만원으로 읽었다). %%는 psycopg 자리표시자와 구분
# 2026-11-06: 금액 단위만 읽는다 (NAVER 유상증자 금액 표에 첫 표의 "주"가 붙었다). 첫 청크로 고정하지 않고
# 금액 단위가 적힌 가장 앞 청크에서 읽는다 (삼성 기재정정은 정정전·후 숫자가 #0, "단위 : 조원"이 #1에 있었다)
_MONEY_UNIT = r"단위\s*:\s*(천원|백만원|억원|조원)"
UNIT = (rf"(SELECT substring(c0.chunk_text from '{_MONEY_UNIT}') FROM disclosure_chunks c0 "
        rf"WHERE c0.rcept_no = c.rcept_no AND c0.chunk_text ~ '{_MONEY_UNIT}' ORDER BY c0.chunk_index LIMIT 1)")

DISCLOSURE_SQL = f"""
SELECT c.rcept_no, c.chunk_index, c.section, c.chunk_text, d.title, d.rcept_dt, d.source_url, d.kind::text, {UNIT},
       1 - (c.dense_embedding <=> %(q)s::vector) AS sim
FROM disclosure_chunks c
JOIN disclosures d ON d.rcept_no = c.rcept_no
WHERE d.symbol = %(symbol)s AND c.dense_embedding IS NOT NULL AND d.rcept_dt >= %(since)s
  AND {NOT_CORRECTED} AND {SUBSIDIARY}
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

RECENT_DISCLOSURE_SQL = f"""
SELECT c.rcept_no, c.chunk_index, c.section, c.chunk_text, d.title, d.rcept_dt, d.source_url, d.kind::text, {UNIT},
       1 - (c.dense_embedding <=> %(q)s::vector) AS sim
FROM disclosure_chunks c
JOIN disclosures d ON d.rcept_no = c.rcept_no
WHERE d.symbol = %(symbol)s AND c.dense_embedding IS NOT NULL AND d.rcept_dt >= %(since)s
  AND {NOT_CORRECTED} AND {SUBSIDIARY}
  AND 1 - (c.dense_embedding <=> %(q)s::vector) >=
      CASE WHEN d.kind::text IN {EVENT_KINDS} THEN %(event_floor)s ELSE %(floor)s END
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
    out = []
    for rcept, idx, section, text, title, day, url, dkind, unit, sim in rows:
        event = dkind in EVENT_KINDS
        if event:
            title = f"[수시공시] {title}"
            if unit and "단위" not in (text or ""):
                text = f"(단위: {unit}) {text or ''}"
        elif section:
            title = f"{title} · {section}"
        out.append(Candidate(ref=f"disc:{rcept}#{idx}", kind="disclosure", symbol=symbol, date=str(day), title=title,
                             text=text or "", url=url, source="DART", similarity=float(sim),
                             doc="event" if event else "periodic"))
    return out


def news_candidates(conn, symbol: str, query_vec, since: date, k: int, variant: str = "hybrid") -> list[Candidate]:
    return _news_rows(conn, NEWS_SQL, {"q": vector_literal(query_vec), "symbol": symbol, "variant": variant,
                                       "since": since, "k": k}, symbol)


def disclosure_candidates(conn, symbol: str, query_vec, since: date, k: int,
                          include_subsidiary: bool = False) -> list[Candidate]:
    return _disclosure_rows(conn, DISCLOSURE_SQL, {"q": vector_literal(query_vec), "symbol": symbol,
                                                   "since": since, "k": k, "subsidiary": include_subsidiary}, symbol)


def recent_news_candidates(conn, symbol: str, query_vec, since: date, k: int, floor: float,
                           variant: str = "hybrid") -> list[Candidate]:
    return _news_rows(conn, RECENT_NEWS_SQL, {"q": vector_literal(query_vec), "symbol": symbol, "variant": variant,
                                              "since": since, "k": k, "floor": floor}, symbol)


def recent_disclosure_candidates(conn, symbol: str, query_vec, since: date, k: int, floor: float,
                                 event_floor: float | None = None, include_subsidiary: bool = False) -> list[Candidate]:
    """floor는 정기보고서, event_floor는 수시공시 임계값 (없으면 floor를 같이 쓴다)."""
    return _disclosure_rows(conn, RECENT_DISCLOSURE_SQL, {
        "q": vector_literal(query_vec), "symbol": symbol, "since": since, "k": k, "floor": floor,
        "event_floor": floor if event_floor is None else event_floor, "subsidiary": include_subsidiary}, symbol)


# 제목 맨 앞의 [단독]·따옴표·괄호는 건너뛰고 회사 이름을 본다. 이름 뒤는 구분 기호나 조사+공백이어야 한다 ("대상자"를 "대상"으로 읽지 않게)
_LEAD = re.compile(r"^(?:\s*\[[^\]]*\]|\s*【[^】]*】)*[\s“”\"'‘’「『(]*")
_AFTER = re.compile(r"(?:[,·…:\s'\"’”]|(?:가|이|는|은|의|도|와|과|에)[\s,])")


# 3글자 미만 이름("SK", "대상", "한화")은 시장 기사 제목과 잘못 겹칠 수 있어 빼는 근거로 쓰지 않는다
MIN_NAME_CHARS = 3


def lead_company(title: str, names: list[str], presorted: bool = False) -> str:
    """제목이 회사 이름으로 시작하면 그 이름 ("파트론, 내년 …" → 파트론). names는 긴 이름부터 본다. 없으면 빈 문자열."""
    head = title[_LEAD.match(title).end():]
    for name in (names if presorted else sorted(names, key=len, reverse=True)):
        if len(name) >= MIN_NAME_CHARS and head.startswith(name) and _AFTER.match(head, len(name)):
            return name
    return ""


def drop_other_company_news(cands: list[Candidate], company: str, names: list[str],
                            aliases: list[str] = ()) -> tuple[list[Candidate], list[Candidate]]:
    """다른 상장사 이름으로 시작하고 추적 종목 이름이 제목에 없는 기사를 뺀다. (남긴 후보, 뺀 기사).
    2026-11-06 "파트론, 내년 스마트폰 수요 부진에 실적 역성장 전망" 기사의 파트론 순이익(-44억9000만원)을 삼성전자 것처럼 쓴
    카드가 검수 호출을 통과했다 (검수는 실행마다 결과가 달라 이 유형을 꾸준히 막지 못한다). 환율·업황 기사는 제목에 회사명이 없어 남는다.
    aliases(네이버, 삼전 …)는 남기는 쪽으로만 쓴다: 제목에 있으면 추적 종목 기사로 본다. 맨 앞 회사 이름 안에 든 별칭은 세지 않는다
    ("삼성전기, …"의 "삼성"은 삼성전자 기사라는 뜻이 아니다)."""
    if not company:
        return list(cands), []
    own = [company, *aliases]
    ordered = sorted({n for n in names if len(n) >= MIN_NAME_CHARS}, key=len, reverse=True)
    kept, dropped = [], []
    for c in cands:
        lead = lead_company(c.title, ordered, presorted=True) if c.kind == "news" else ""
        rest = c.title.replace(lead, " ") if lead else c.title
        (dropped if lead and lead not in own and not any(n in rest for n in own) else kept).append(c)
    return kept, dropped


def listed_names(path) -> list[str]:
    """DART corpCode.xml에서 종목코드가 있는 회사 이름 (코스피·코스닥·코넥스, 상장폐지 회사도 섞여 있다). 파일이 없으면 빈 목록.
    disclosures.dart.load_corp_codes는 {종목코드: 고유번호}만 돌려줘 이름을 따로 읽는다."""
    import xml.etree.ElementTree as ET
    from pathlib import Path

    path = Path(path)
    if not path.is_file():
        return []
    names = []
    for _, el in ET.iterparse(path):
        if el.tag == "list":
            if (el.findtext("stock_code") or "").strip() and (el.findtext("corp_name") or "").strip():
                names.append(el.findtext("corp_name").strip())
            el.clear()
    return names
