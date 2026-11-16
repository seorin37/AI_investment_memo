"""같은 사건 묶기 — 공시와 같은 사건을 다룬 기사를 공시 카드의 보조 기사(supporting_news)로 붙인다 (configs/updates.yaml same_event).

기준 (2026-11-09 공시-기사 30쌍 O/X 판정으로 정함, 기본은 꺼짐):
- 같은 종목(후보 검색이 이미 종목으로 거른다), 기사 발행일이 공시일 days_before일 전 ~ days_after일 뒤
- 공시 청크 × 기사 원문 청크(news_chunks) dense 코사인 최댓값이 min_similarity(0.70) 이상이면 묶는다
- number_similarity(0.62) 이상 min_similarity 미만이면, 공시의 핵심 숫자(금액·주식 수)가 기사 본문에도 있을 때만 묶는다
  (같은 회사의 다른 사건 기사가 0.69까지 올라왔다: 2026-11-04 SK바이오팜 FDA 공시 × 3분기 실적 기사)
- 원문 청크가 없는 기사는 묶지 않는다 (제목+요약 유사도는 시황 기사와 갈리지 않았다). 그대로 독립 근거로 남는다
- event_only면 수시공시만 묶는다 (정기보고서는 형식 문구가 많아 비교하지 않는다)
묶는 단위는 공시(접수번호)다: 같은 공시의 다른 청크도 같은 공시로 본다. 기사가 여러 공시와 맞으면 유사도가 높은 공시 하나.
읽기 전용: SELECT만 쓴다. 어느 기사를 근거에서 뺄지는 evidence.split_same_event가, 카드에 붙이는 건 topic.check_topic이 한다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from .checks import all_numbers, evidence_numbers
from .evidence import rcept_of
from .models import Candidate

DEFAULTS = {"enabled": False, "min_similarity": 0.70, "number_similarity": 0.62, "days_before": 1, "days_after": 3,
            "event_only": True, "number_tolerance": 0.005}

PAIR_SQL = """SELECT nc.news_id, dc.rcept_no, max(1 - (dc.dense_embedding <=> nc.dense_embedding))
FROM news_chunks nc
JOIN disclosure_chunks dc ON dc.rcept_no = ANY(%(r)s) AND dc.dense_embedding IS NOT NULL
WHERE nc.news_id = ANY(%(n)s)
GROUP BY nc.news_id, dc.rcept_no"""
DISCLOSURE_TEXT_SQL = """SELECT rcept_no, string_agg(chunk_text, ' ' ORDER BY chunk_index) FROM disclosure_chunks
WHERE rcept_no = ANY(%(r)s) GROUP BY rcept_no"""
BODY_SQL = "SELECT news_id, body FROM news_article_bodies WHERE news_id = ANY(%(n)s)"

# 금액·주식 수로 보지 않는 큰 숫자: 날짜(20261103)
_YMD = re.compile(r"^(19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])$")
# 단위가 붙은 금액·주식 수 ("1조 3412억원", "14,103,466,480,000원", "3,900,000주"). 나눠 쓴 금액은 checks가 한 값으로 읽는다
_AMOUNT = re.compile(r"(?:\d[\d,]*(?:\.\d+)?\s*(?:조|억|만|천)?\s*)+(?:원|주)")


@dataclass(frozen=True)
class Link:
    rcept_no: str
    similarity: float
    rule: str                 # similarity(유사도만으로) | numbers(유사도 + 핵심 숫자)


def key_numbers(text: str) -> set[float]:
    """공시의 핵심 숫자: 금액·주식 수. '원'·'주'가 붙은 값(1만 이상)과, 표 머리 단위를 반영한 큰 값(100만 이상, 날짜 제외)."""
    out = {v for m in _AMOUNT.finditer(text or "") for v in all_numbers(m.group(0)) if v >= 1e4}
    out |= {v for v in evidence_numbers(text or "") if v >= 1e6 and not (v.is_integer() and _YMD.match(str(int(v))))}
    return out


def shares_number(keys: set[float], text: str, tolerance: float = DEFAULTS["number_tolerance"]) -> bool:
    """기사 글에 핵심 숫자가 하나라도 있나. 기사는 반올림해 쓰므로("1조3400억") 상대 오차 tolerance까지 같은 값으로 본다."""
    values = all_numbers(text or "")
    return any(abs(v - k) <= tolerance * k for k in keys for v in values if v >= 1e4)


def decide(similarity: float, shared: bool, cfg: dict) -> str | None:
    if similarity >= cfg["min_similarity"]:
        return "similarity"
    if similarity >= cfg["number_similarity"] and shared:
        return "numbers"
    return None


def in_window(news_day: str, disclosure_day: str, cfg: dict) -> bool:
    gap = (date.fromisoformat(news_day) - date.fromisoformat(disclosure_day)).days
    return -cfg["days_before"] <= gap <= cfg["days_after"]


def link_same_event(conn, candidates: list[Candidate], cfg: dict | None = None) -> dict[str, Link]:
    """후보 안에서 같은 사건으로 묶을 (기사 ref → Link). 원문 청크가 없는 기사는 PAIR_SQL에 안 나와 묶이지 않는다."""
    cfg = {**DEFAULTS, **(cfg or {})}
    discs: dict[str, str] = {}                                   # 접수번호 → 공시일
    for c in candidates:
        if c.kind == "disclosure" and (c.doc == "event" or not cfg["event_only"]):
            discs.setdefault(rcept_of(c.ref), c.date)
    news = {int(c.ref.split(":", 1)[1]): c for c in candidates if c.kind == "news"}
    if not discs or not news:
        return {}
    with conn.cursor() as cur:
        cur.execute(PAIR_SQL, {"r": sorted(discs), "n": sorted(news)})
        pairs = [(int(n), r, float(s)) for n, r, s in cur.fetchall()
                 if s is not None and in_window(news[int(n)].date, discs[r], cfg)]
        need = [(n, r) for n, r, s in pairs if cfg["number_similarity"] <= s < cfg["min_similarity"]]
        texts, bodies = {}, {}
        if need:
            cur.execute(DISCLOSURE_TEXT_SQL, {"r": sorted({r for _, r in need})})
            texts = dict(cur.fetchall())
            cur.execute(BODY_SQL, {"n": sorted({n for n, _ in need})})
            bodies = {int(n): b for n, b in cur.fetchall()}
    keys = {r: key_numbers(t) for r, t in texts.items()}
    need_set = set(need)
    links: dict[str, Link] = {}
    for n, r, s in sorted(pairs, key=lambda p: -p[2]):
        ref = f"news:{n}"
        if ref in links:
            continue                                             # 유사도가 더 높은 공시에 이미 묶였다
        shared = (n, r) in need_set and shares_number(keys.get(r, set()), bodies.get(n, ""), cfg["number_tolerance"])
        rule = decide(s, shared, cfg)
        if rule:
            links[ref] = Link(r, round(s, 4), rule)
    return links
