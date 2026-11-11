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

2026-11-09 검수(run_20261109_133043 review_findings.md)로 넣은 후보 거르기 (configs/updates.yaml recent.filters.
코드 기본값은 모두 꺼짐 = 예전과 같음, 설정 파일은 periodic_date: period_end · latest_version_only: true):
- periodic_date: period_end — 정기보고서의 최신순 기준(정렬·후보 날짜)을 접수일 대신 보고 기간 끝으로 (없으면 접수일).
  [기재정정] 옛 보고서가 정정 접수일(2026-03-24) 때문에 최신 자료로 뽑혔다. 수시공시는 period_end가 없어 접수일 그대로.
  기간 시작(since) 비교는 접수일 그대로.
- latest_version_only: 같은 보고서의 원본·정정본이 같이 있으면 가장 늦게 접수한 것만. disclosure_events.corrects가 정기보고서에는
  없고 일부 수시공시 정정에도 비어 있어서, 회사·종류·제목(앞의 [기재정정] 같은 표시를 뗀 것)·기간으로 묶는다.
  수시공시는 기간이 없어 정정 표시가 있는 더 늦은 공시가 30일 안에 있을 때만 이전 것을 뺀다.
- dedupe_same_text: 가져온 공시 후보 중 본문(맨 앞 "[회사 연도 | 절]" 머리말을 뗀 것)이 같은 청크는 가장 최근 보고서
  (후보 날짜 → 접수번호 순, 같은 보고서 안에서는 유사도 높은 것) 하나만 남긴다. 반기·사업보고서에 되풀이되는 각주 (R17~19).
  처음엔 '여러 보고서에 나오면 제외'(boilerplate_min_docs)로 했다가 최신 배당 절까지 빠져서 중복 제거로 바꿨다.
- news_require_company: false | true(제목 + 앞부분 news_company_lead_chars자) | title(제목만) — 종목명·별칭이 없는 뉴스를 뺀다.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta

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

FILTER_DEFAULTS = {"periodic_date": "rcept_dt", "latest_version_only": False, "dedupe_same_text": False,
                   "news_require_company": False, "news_company_lead_chars": 150}
NEWS_COMPANY_MODES = (False, True, "title")
CORRECTION_DAYS = 30
# 제목 앞의 [기재정정]·[첨부정정]·[첨부추가] 같은 표시를 뗀 제목
BASE_TITLE = r"regexp_replace({t}.title, '^(\[[^]]*\]\s*)+', '')"
# 정기보고서: 기간 끝(없으면 접수일). 수시공시: 접수일
PERIOD_DATE = f"(CASE WHEN d.kind::text IN {EVENT_KINDS} THEN d.rcept_dt ELSE COALESCE(d.period_end, d.rcept_dt) END)"
# 더 늦게 접수한 같은 보고서가 있으면 뺀다
NEWER_VERSION = rf"""NOT EXISTS (SELECT 1 FROM disclosures d2
    WHERE d2.symbol = d.symbol AND d2.kind = d.kind AND d2.rcept_no <> d.rcept_no
      AND {BASE_TITLE.format(t="d2")} = {BASE_TITLE.format(t="d")}
      AND (d2.rcept_dt, d2.rcept_no) > (d.rcept_dt, d.rcept_no)
      AND CASE WHEN d.kind::text IN {EVENT_KINDS}
               THEN d2.title ~ '^\[[^]]*정정' AND d2.rcept_dt <= d.rcept_dt + {CORRECTION_DAYS}
               ELSE d2.period_end IS NOT DISTINCT FROM d.period_end END)"""
# 새 자료만 받기 (2026-11-10, 항목의 마지막 확인 시각 이후). 수집 시각 기준 (2026-11-10 두 번째 결정):
# - 마지막 확인 이후 '검색에 쓸 수 있게 된' 자료만: 공시 max(created_at, 청크 embedded_at).
#   뉴스는 기사가 처음 검색 가능해진 시각 = 제목+요약 임베딩 시각(없으면 collected_at) (2026-11-10 chunks 전환 결정).
#   나중에 원문 청크 임베딩이 붙어도 다시 새 자료로 보지 않는다. 대신 처음 검색 가능해진 게 확인 전이어도
#   원문 청크로 찾은 기사(doc="chunk")는 청크 임베딩이 마지막 확인 뒤에 붙었고, 아직 그 항목 카드에 쓰이지 않았고,
#   발행 3일 안이면 남긴다 (late chunk, 2026-11-10 (가) 결정: 청크가 붙은 뒤 한 번만 다시 본다).
#   이 판정은 SQL이 아니라 drop_not_ready가 후보마다 한다.
# - 그중 발행 시각(공시는 접수일)이 FRESH_PUBLISHED_DAYS일 안인 것만: 오래된 자료를 다시 적재·임베딩해도 새 소식이 아니다.
# - 원본이 마지막 확인 전에 이미 적재돼 있던 보고서의 정정(기재정정 등)은 새 자료가 아니다. 원본은 disclosure_events.corrects
#   (수시공시) 또는 같은 종류·같은 제목(앞 [..] 표시 뗀 것)·같은 기간 끝(정기보고서)/30일 안(수시공시)의 앞선 보고서.
# period_end는 정렬에만 쓴다. %(pub_since)s = 발행 기준 시작일, %(fresh_ts)s = 마지막 확인 시각.
FRESH_PUBLISHED_DAYS = 3
FRESH_DISCLOSURE = rf"""d.rcept_dt >= %(pub_since)s
  AND NOT (d.title ~ '^\[[^]]*정정' AND (
    EXISTS (SELECT 1 FROM disclosure_events e JOIN disclosures d0 ON d0.rcept_no = e.corrects
            WHERE e.rcept_no = d.rcept_no AND d0.created_at < %(fresh_ts)s)
    OR EXISTS (SELECT 1 FROM disclosures d0
            WHERE d0.symbol = d.symbol AND d0.kind = d.kind AND d0.rcept_no <> d.rcept_no AND d0.created_at < %(fresh_ts)s
              AND {BASE_TITLE.format(t="d0")} = {BASE_TITLE.format(t="d")}
              AND CASE WHEN d.kind::text IN {EVENT_KINDS} THEN d0.rcept_dt >= d.rcept_dt - {CORRECTION_DAYS}
                       ELSE d0.period_end IS NOT DISTINCT FROM d.period_end END)))"""
# 청크 텍스트 맨 앞의 머리말 "[KB금융 2025 반기 | I. 회사의 개요 > 4. 주식의 총수 등] "은 보고서·절마다 달라 떼고 비교한다
CHUNK_BODY = r"regexp_replace({t}.chunk_text, '^\[[^]]*\]\s*', '')"
_CHUNK_HEAD = re.compile(r"^\[[^\]]*\]\s*")
_UNIT_HEAD = re.compile(r"^\(단위: [^)]*\) ")


def chunk_body_hash(text: str) -> str:
    """청크 본문 식별값: 수시공시에 붙인 "(단위: …) "와 맨 앞 머리말 하나를 떼고 UTF-8 md5."""
    import hashlib

    body = _CHUNK_HEAD.sub("", _UNIT_HEAD.sub("", text or "", count=1), count=1)
    return hashlib.md5(body.encode("utf-8")).hexdigest()


def dedupe_same_text(cands: list[Candidate]) -> tuple[list[Candidate], list[Candidate]]:
    """본문이 같은 공시 청크는 가장 최근 보고서(후보 날짜, 접수번호 순)의 것 하나만 남긴다. 같은 보고서 안에서는 유사도 높은 것.
    (남긴 후보, 뺀 후보). 순서는 원래 순서를 지킨다. 뉴스는 그대로."""
    best: dict[str, Candidate] = {}
    rank = lambda c: (c.date, c.ref.split(":", 1)[1].split("#", 1)[0], c.similarity)
    for c in cands:
        if c.kind != "disclosure":
            continue
        h = chunk_body_hash(c.text)
        if h not in best or rank(c) > rank(best[h]):
            best[h] = c
    keep = {id(c) for c in best.values()}
    kept = [c for c in cands if c.kind != "disclosure" or id(c) in keep]
    dropped = [c for c in cands if c.kind == "disclosure" and id(c) not in keep]
    return kept, dropped


def recent_disclosure_sql(periodic_date: str = "rcept_dt", latest_version_only: bool = False, fresh: bool = False) -> str:
    """recent.filters에 맞춘 공시 후보 SQL. 모두 기본값이면 RECENT_DISCLOSURE_SQL과 같다.
    periodic_date=period_end는 정렬과 후보 날짜(pick_recent의 최신순)에만 쓴다. 기간 시작(since) 비교는 접수일 그대로
    (2026-11-09: 기간 시작에도 쓰면 2025-11-14 접수 2025.09 분기보고서가 빠졌다)."""
    if periodic_date not in ("rcept_dt", "period_end"):
        raise ValueError(f"periodic_date는 rcept_dt 또는 period_end: {periodic_date}")
    day = PERIOD_DATE if periodic_date == "period_end" else "d.rcept_dt"
    extra = f"\n  AND {NEWER_VERSION}" if latest_version_only else ""
    if fresh:                                            # fresh=True면 %(pub_since)s·%(fresh_ts)s 자리표시자가 필요하다
        extra += f"\n  AND {FRESH_DISCLOSURE}"
    return f"""
SELECT c.rcept_no, c.chunk_index, c.section, c.chunk_text, d.title, {day}, d.source_url, d.kind::text, {UNIT},
       1 - (c.dense_embedding <=> %(q)s::vector) AS sim
FROM disclosure_chunks c
JOIN disclosures d ON d.rcept_no = c.rcept_no
WHERE d.symbol = %(symbol)s AND c.dense_embedding IS NOT NULL AND d.rcept_dt >= %(since)s
  AND {NOT_CORRECTED} AND {SUBSIDIARY}
  AND 1 - (c.dense_embedding <=> %(q)s::vector) >=
      CASE WHEN d.kind::text IN {EVENT_KINDS} THEN %(event_floor)s ELSE %(floor)s END{extra}
ORDER BY {day} DESC, c.dense_embedding <=> %(q)s::vector
LIMIT %(k)s
"""


def search_filters(rcfg: dict | None) -> dict:
    """configs/updates.yaml recent.filters (없는 키는 기본값 = 꺼짐)."""
    unknown = set((rcfg or {}).get("filters") or {}) - set(FILTER_DEFAULTS)
    if unknown:
        raise ValueError(f"recent.filters에 모르는 키: {sorted(unknown)}")
    f = {**FILTER_DEFAULTS, **((rcfg or {}).get("filters") or {})}
    if f["news_require_company"] not in NEWS_COMPANY_MODES:
        raise ValueError(f"news_require_company는 false·true·title 중 하나: {f['news_require_company']!r}")
    return f


def news_company_lead(filters: dict) -> int | None:
    """뉴스 종목명 필터가 보는 앞부분 길이. 꺼짐이면 None, title이면 0(제목만)."""
    mode = filters.get("news_require_company", False)
    if not mode:
        return None
    return 0 if mode == "title" else int(filters.get("news_company_lead_chars", 150))


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
                                 event_floor: float | None = None, include_subsidiary: bool = False,
                                 filters: dict | None = None, fresh_since: datetime | None = None,
                                 pub_since: date | None = None) -> list[Candidate]:
    """floor는 정기보고서, event_floor는 수시공시 임계값 (없으면 floor를 같이 쓴다). filters: search_filters() 결과.
    periodic_date=period_end이면 정기보고서 후보의 date가 보고 기간 끝이다.
    fresh_since: 항목의 마지막 확인 시각. 주면 접수일이 pub_since 이후인 공시만, 원본이 그 시각 전에 적재돼 있던 정정 공시는 뺀다
    (FRESH_DISCLOSURE). 마지막 확인 이후 검색 가능해졌는지는 호출자가 drop_not_ready로 본다."""
    f = {**FILTER_DEFAULTS, **(filters or {})}
    sql = recent_disclosure_sql(f["periodic_date"], f["latest_version_only"], fresh=fresh_since is not None)
    params = {"q": vector_literal(query_vec), "symbol": symbol, "since": since, "k": k, "floor": floor,
              "event_floor": floor if event_floor is None else event_floor, "subsidiary": include_subsidiary}
    if fresh_since is not None:
        if pub_since is None:
            raise ValueError("fresh_since를 주면 pub_since(발행 기준 시작일)도 줘야 합니다")
        params.update(fresh_ts=fresh_since, pub_since=pub_since)
    out = _disclosure_rows(conn, sql, params, symbol)
    return dedupe_same_text(out)[0] if f["dedupe_same_text"] else out


# 후보가 검색에 쓸 수 있게 된 시각 (새 자료만 받기). 제목+요약 뉴스는 그 변형 임베딩, 원문 청크 뉴스는 그 기사 청크 임베딩의 가장 늦은 시각,
# 공시는 그 청크 임베딩 시각과 적재 시각 중 늦은 쪽.
NEWS_READY_SQL = """SELECT a.id, COALESCE(v.embedded_at, a.collected_at), a.published_at,
       (SELECT max(nc.embedded_at) FROM news_chunks nc WHERE nc.news_id = a.id)
FROM news_articles a LEFT JOIN news_embedding_variants v ON v.news_id = a.id AND v.variant = %(variant)s
WHERE a.id = ANY(%(ids)s)"""
DISC_READY_SQL = """SELECT c.rcept_no, c.chunk_index, GREATEST(d.created_at, COALESCE(c.embedded_at, d.created_at))
FROM disclosure_chunks c JOIN disclosures d ON d.rcept_no = c.rcept_no
JOIN unnest(%(nos)s::text[], %(ix)s::int[]) AS k(n, i) ON c.rcept_no = k.n AND c.chunk_index = k.i"""


def news_coverage(conn) -> str | None:
    """DB의 가장 오래된 뉴스 발행일(한국 날짜, YYYY-MM-DD). 기사가 없으면 None. v2 카드 자료 범위 문구에 쓴다."""
    row = conn.execute("SELECT (min(published_at) AT TIME ZONE 'Asia/Seoul')::date FROM news_articles").fetchone()
    return None if row is None or row[0] is None else str(row[0])


def fresh_window(last_checked: datetime | None, now: datetime, since: date,
                 days: int = FRESH_PUBLISHED_DAYS) -> tuple[datetime | date, date | None]:
    """(뉴스 발행 시작, 공시 접수 시작). 첫 확인(last_checked=None)이면 조회 기간 시작 그대로 (공시는 None = 호출자의 시작일).
    새 자료만 받을 때는 지금부터 days일 전 (조회 기간 시작보다 앞이면 조회 기간 시작)."""
    if last_checked is None:
        return since, None
    start = now - timedelta(days=days)
    floor_ts = datetime.combine(since, datetime.min.time(), now.tzinfo)
    start = max(start, floor_ts)
    return start, start.date()


def ready_times(conn, cands: list[Candidate], variant: str = "hybrid",
                published: dict[str, datetime] | None = None,
                chunk_ready: dict[str, datetime | None] | None = None) -> dict[str, datetime]:
    """ref → 검색에 쓸 수 있게 된 시각 (뉴스는 기사가 처음 검색 가능해진 시각). published를 주면 뉴스 발행 시각을,
    chunk_ready를 주면 뉴스 원문 청크 임베딩이 끝난 시각(기사별 마지막, 없으면 None)을 채운다."""
    news = sorted({int(c.ref.split(":", 1)[1]) for c in cands if c.kind == "news"})
    discs = sorted({(c.ref.split(":", 1)[1].split("#", 1)[0], int(c.ref.split("#", 1)[1])) for c in cands
                    if c.kind == "disclosure"})
    out: dict[str, datetime] = {}
    with conn.cursor() as cur:
        if news:
            cur.execute(NEWS_READY_SQL, {"ids": news, "variant": variant})
            for nid, ready, pub, chunk in cur.fetchall():
                out[f"news:{nid}"] = ready
                if published is not None:
                    published[f"news:{nid}"] = pub
                if chunk_ready is not None:
                    chunk_ready[f"news:{nid}"] = chunk
        if discs:
            cur.execute(DISC_READY_SQL, {"nos": [n for n, _ in discs], "ix": [i for _, i in discs]})
            for no, idx, ready in cur.fetchall():
                out[f"disc:{no}#{idx}"] = ready
    return out


def drop_not_ready(conn, cands: list[Candidate], last_checked: datetime, variant: str = "hybrid", *,
                   late_chunk_since: datetime | None = None,
                   used: set[str] | None = None) -> tuple[list[Candidate], list[Candidate], list[Candidate]]:
    """마지막 확인 이후 검색에 쓸 수 있게 된 후보만 남긴다. (남은 후보, 뺀 후보, 남은 후보 중 late chunk).
    시각을 모르는 후보는 뺀다. late chunk: 기사는 확인 전부터 검색 가능했지만 원문 청크로 찾은 후보(doc="chunk")가
    청크 임베딩이 마지막 확인 뒤에 붙었고(청크가 붙은 뒤 한 번만), 발행 late_chunk_since 이후이고, 그 항목 카드에 아직 안 쓴
    기사(used에 없음)면 남긴다. used가 None이면 (쓴 근거 기록이 없어 알 수 없음) 남기지 않는다."""
    published: dict[str, datetime] = {}
    chunk_ready: dict[str, datetime | None] = {}
    times = ready_times(conn, cands, variant, published, chunk_ready)
    kept, dropped, late = [], [], []
    for c in cands:
        ready = times.get(c.ref)
        if ready is not None and ready > last_checked:
            kept.append(c)
            continue
        pub, chunk = published.get(c.ref), chunk_ready.get(c.ref)
        if (c.kind == "news" and c.doc == "chunk" and ready is not None and used is not None and c.ref not in used
                and chunk is not None and chunk > last_checked
                and late_chunk_since is not None and pub is not None and pub >= late_chunk_since):
            kept.append(c)
            late.append(c)
        else:
            dropped.append(c)
    return kept, dropped, late


def company_terms(company: str, symbol: str, rcfg: dict | None = None, symbol_aliases: dict | None = None) -> list[str]:
    """뉴스 종목명 필터에 쓰는 이름: stocks 이름 + recent.company_aliases[이름] + configs/stock_aliases.yaml aliases[종목코드]."""
    terms = [company, *((rcfg or {}).get("company_aliases") or {}).get(company, []),
             *((symbol_aliases or {}).get(symbol) or [])]
    return list(dict.fromkeys(t for t in terms if t))


def load_symbol_aliases(path: str = "configs/stock_aliases.yaml") -> dict[str, list[str]]:
    import yaml

    from ..common.config import resolve_path

    p = resolve_path(path)
    if not p.is_file():
        return {}
    return {str(k): list(v) for k, v in ((yaml.safe_load(p.read_text(encoding="utf-8")) or {}).get("aliases") or {}).items()}


def drop_news_without_company(cands: list[Candidate], names: list[str],
                              lead_chars: int = 150) -> tuple[list[Candidate], list[Candidate]]:
    """뉴스 제목이나 내용 앞 lead_chars자에 종목명·별칭(names)이 하나도 없으면 뺀다 (lead_chars=0이면 제목만).
    (남긴 후보, 뺀 기사). 공시는 그대로. 대소문자는 가리지 않는다 ("naver", "kb")."""
    keys = [n.lower() for n in names if n]
    if not keys:
        return list(cands), []
    kept, dropped = [], []
    for c in cands:
        if c.kind != "news":
            kept.append(c)
            continue
        head = f"{c.title} {(c.text or '')[:lead_chars]}".lower()
        (kept if any(k in head for k in keys) else dropped).append(c)
    return kept, dropped


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
