"""공시 후보 하이브리드 검색 (실험, configs disclosure.search: hybrid, 기본 dense).

기존(dense)은 정기보고서·수시공시 청크를 dense 코사인 하나로 거르고(min_similarity_disclosure 0.64) 최신순으로 고른다.
공시 청크는 길고 표가 많아 dense 점수가 낮게 나와, 질의 낱말("HBM")이 그대로 들어 있는 청크도 0.52~0.57로 떨어진다
(2026-11-16 확인: 삼성전자 연구개발실적 'HBM3E 12H', SK하이닉스 'HBM4 I/O 2,048개').

하이브리드:
1) 종목·기간·정정·자회사 조건(기존 SQL과 같음)에 맞는 청크 전부의 dense 코사인(SQL)과 sparse 점수(질의 sparse · 청크 sparse 내적, 파이썬)를 구한다.
2) 두 점수를 질의마다 min-max 정규화해 가중합(weights, 기본 dense 0.6 · sparse 0.4)으로 줄 세워 상위 k 청크를 고른다.
3) Candidate.similarity에는 진단용 dense 코사인을 그대로 두고 retrieval_score에 하이브리드 점수를 둔다.
   하이브리드 상위 k는 dense 기준으로 다시 버리지 않고 관련성 판정이 통과 여부를 정한다.
읽기 전용: SELECT만 쓴다. 새 자료만 받기(fresh_since)에는 쓰지 않는다(호출자가 기존 함수로 돌린다).
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date

from .candidates import (EVENT_KINDS, NEWER_VERSION, NOT_CORRECTED, PERIOD_DATE, SUBSIDIARY, _disclosure_rows,
                         vector_literal)
from .models import Candidate

DEFAULTS = {"weights": {"dense": 0.6, "sparse": 0.4}, "k": 30, "max_chunks_per_document": 3, "section_boost": 0.25,
            "sparse_reserve": 3}

# 실험(2026-11-17) 질문 종류 → 정기보고서 목차 힌트. 질문 문장 그대로 검색하면 답이 있는 절(예: 유상증자 내역은
# 'III. 재무에 관한 사항 > 7. 증권의 발행을 통한 자금조달')보다 낱말만 겹치는 다른 절(대주주 거래 등)이 위에 왔다.
# 질문(category ask)에서만, 목차가 힌트와 맞는 청크에 점수를 더한다 (LLM 호출 없음). 패턴은 질문 문장에, 힌트는 청크 section에 건다.
SECTION_HINTS: list[tuple[str, tuple[str, ...]]] = [
    (r"유상증자|무상증자|증자|자금\s*조달|조달한|공모|IPO|상장.*(자금|돈)|사채|CB|전환사채", ("증권의 발행을 통한 자금조달", "자금의 사용")),
    (r"뭐야|무엇|무슨\s*사업|뭐가\s*달라|어떻게\s*달라|차이|설명해|어떤\s*사업|정확히", ("사업의 개요", "주요 제품", "사업의 내용 > 1", "사업의 내용 > 2", "기타 참고사항", "경영진단")),   # 업계·기술 설명은 7. 기타 참고사항·IV. 경영진단에 많다 (N25 MRO 정의는 경영진단)
    (r"매출.{0,6}(잡히|인식|반영)|수주|수주잔고|계약|일감", ("매출 및 수주상황",)),
    (r"배당", ("배당에 관한 사항",)),
    (r"인적분할|물적분할|분할|합병|자회사|종속|계열|지분|상장(한|된)?\s*(법인|자회사)", ("회사의 개요", "계열회사", "일반사항", "타법인출자")),
    (r"소송|과징금|제재|해킹|사고|조사", ("우발", "제재", "그 밖에 투자자 보호", "소송")),
    (r"연구|개발|기술|특허|신약|임상", ("연구개발",)),
    (r"가입자|판매량|생산|가동|공장|설비|증설", ("생산 및 설비", "매출 및 수주상황", "주요 제품")),
    (r"대주주|최대주주|지분율|임원|경영진", ("주주에 관한 사항", "임원")),
    (r"(사업|부문).{0,6}(적자|흑자|손익|이익|손실|매출)|부문별", ("부문", "영업부문", "사업부문")),
]


def section_hints(question: str) -> list[str]:
    """질문 문장 → 목차 힌트(겹치지 않게, 순서 유지). 맞는 규칙이 없으면 빈 목록 (점수 그대로)."""
    import re
    out: list[str] = []
    for pattern, hints in SECTION_HINTS:
        if re.search(pattern, question or ""):
            out += [h for h in hints if h not in out]
    return out


def _scope_sql(latest_version_only: bool) -> str:
    extra = f"\n  AND {NEWER_VERSION}" if latest_version_only else ""
    return f"""FROM disclosure_chunks c
JOIN disclosures d ON d.rcept_no = c.rcept_no
WHERE d.symbol = %(symbol)s AND c.dense_embedding IS NOT NULL AND d.rcept_dt >= %(since)s
  AND {NOT_CORRECTED} AND {SUBSIDIARY}{extra}"""


def _minmax(values: dict) -> dict:
    if not values:
        return {}
    lo, hi = min(values.values()), max(values.values())
    span = hi - lo
    return {k: ((v - lo) / span if span > 0 else 0.0) for k, v in values.items()}


def _select_top(score: dict[tuple[str, int], float], k: int, max_per_document: int) -> list[tuple[str, int]]:
    """한 보고서의 비슷한 청크가 후보를 독점하지 않도록 접수번호별 상한을 둔다."""
    top: list[tuple[str, int]] = []
    counts: dict[str, int] = {}
    for key in sorted(score, key=lambda x: (-score[x], x)):
        rcept = key[0]
        if counts.get(rcept, 0) >= max_per_document:
            continue
        top.append(key)
        counts[rcept] = counts.get(rcept, 0) + 1
        if len(top) >= k:
            break
    return top


class DisclosureHybridSearch:
    """한 실행 동안 쓰는 공시 하이브리드 검색. 종목·기간별 청크 sparse는 한 번만 읽어 둔다."""

    def __init__(self, conn, encoder, cfg: dict | None = None):
        self.conn, self.encoder = conn, encoder
        self.cfg = {**DEFAULTS, **(cfg or {})}
        w = self.cfg["weights"]
        total = float(w.get("dense", 0)) + float(w.get("sparse", 0))
        self.w_dense, self.w_sparse = float(w.get("dense", 0)) / total, float(w.get("sparse", 0)) / total
        self._sparse: dict[tuple, dict] = {}

    def _sparse_rows(self, symbol: str, since: date, latest: bool, subsidiary: bool) -> dict:
        key = (symbol, since, latest, subsidiary)
        if key not in self._sparse:
            with self.conn.cursor() as cur:
                cur.execute(f"SELECT c.rcept_no, c.chunk_index, c.sparse_embedding {_scope_sql(latest)}",
                            {"symbol": symbol, "since": since, "subsidiary": subsidiary})
                self._sparse[key] = {(r, int(i)): (sp or {}) for r, i, sp in cur.fetchall()}
        return self._sparse[key]

    def recent(self, symbol: str, query: str, since: date, k: int | None = None, *, filters: dict | None = None,
               include_subsidiary: bool = False, hints: list[str] | None = None) -> list[Candidate]:
        """하이브리드 점수 상위 k 청크 → Candidate. 날짜 최신순 정렬은 호출 쪽 pick_recent가 한다."""
        f = filters or {}
        latest = bool(f.get("latest_version_only"))
        day = PERIOD_DATE if f.get("periodic_date") == "period_end" else "d.rcept_dt"
        k = int(k or self.cfg["k"])
        q = self.encoder.encode_query(query, sparse=True, colbert=False)
        qsparse = {str(t): float(v) for t, v in (q.sparse or {}).items()}
        params = {"q": vector_literal(q.dense), "symbol": symbol, "since": since, "subsidiary": include_subsidiary}
        with self.conn.cursor() as cur:
            cur.execute("SET LOCAL enable_indexscan = off")          # 종목 조건 + HNSW는 결과가 덜 나올 수 있다 (정확 계산)
            try:
                cur.execute(f"SELECT c.rcept_no, c.chunk_index, 1 - (c.dense_embedding <=> %(q)s::vector), c.section"
                            f" {_scope_sql(latest)}", params)
                rows = cur.fetchall()
            finally:
                cur.execute("SET LOCAL enable_indexscan TO DEFAULT")
        dense = {(r, int(i)): float(s) for r, i, s, _ in rows}
        sections = {(r, int(i)): sec or "" for r, i, _, sec in rows}
        sparse_rows = self._sparse_rows(symbol, since, latest, include_subsidiary)
        sparse = {key: sum(qsparse.get(str(t), 0.0) * float(w) for t, w in sparse_rows.get(key, {}).items())
                  for key in dense}
        nd, ns = _minmax(dense), _minmax(sparse)
        score = {key: self.w_dense * nd[key] + self.w_sparse * ns.get(key, 0.0) for key in dense}
        if hints:                                              # 질문 종류에 맞는 목차의 청크에 점수를 더한다 (실험)
            boost = float(self.cfg.get("section_boost", 0.25))
            score = {key: s + (boost if any(h in sections[key] for h in hints) else 0.0) for key, s in score.items()}
            # 질문 낱말이 그대로 든 청크(sparse 상위)는 자리를 보장한다 (2026-11-17 N25: 'MRO' 설명 청크가
            # 가산점을 받은 '사업의 개요' 일반 청크들에 밀려 후보에서 빠졌다)
            reserve = int(self.cfg.get("sparse_reserve", 3))
            top_score = max(score.values()) if score else 0.0
            for key in sorted((k for k, v in sparse.items() if v > 0), key=lambda k: -sparse[k])[:reserve]:
                score[key] = max(score[key], top_score)
        top = _select_top(score, k, int(self.cfg["max_chunks_per_document"]))
        if not top:
            return []
        sql = f"""SELECT c.rcept_no, c.chunk_index, c.section, c.chunk_text, d.title, {day}, d.source_url, d.kind::text,
       NULL::text AS unit, 1 - (c.dense_embedding <=> %(q)s::vector) AS sim
FROM disclosure_chunks c JOIN disclosures d ON d.rcept_no = c.rcept_no
JOIN unnest(%(nos)s::text[], %(ix)s::int[]) AS k(n, i) ON c.rcept_no = k.n AND c.chunk_index = k.i"""
        out = _disclosure_rows(self.conn, sql, {"q": params["q"], "nos": [t[0] for t in top], "ix": [t[1] for t in top]},
                               symbol)
        order = {f"disc:{r}#{i}": n for n, (r, i) in enumerate(top)}
        hybrid = {f"disc:{r}#{i}": score[(r, i)] for r, i in top}
        tagged = [replace(c, retrieval_score=hybrid[c.ref], retrieval="hybrid") for c in out]
        return sorted(tagged, key=lambda c: order.get(c.ref, 1 << 30))


__all__ = ["DisclosureHybridSearch", "EVENT_KINDS"]
