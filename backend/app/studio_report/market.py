"""주간보고서 국내 증시 칸 — 지수 숫자(코드) + 시황 정리 7~8문장·날짜별 흐름(LLM) (2026-11-23).

- 숫자: 코스피·코스닥(market_indices), 원/달러·국고채 3년·미국 10년물(economic_observations). 등락은 코드 계산.
- 기사: 그 주 시황 기사 — 제목에 지수 이름과 '마감·시황'이 있는 기사를 거래일마다 최대 3건(본문 청크가 있는 것 먼저, 같은 사건 하나).
- LLM이 실패하면 summary는 코드 문장(지수 등락만), flow는 빈 목록.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any

from .story import ask, md, sentences, check_text, verify_texts, WEEKDAYS

MARKET_PROMPT = "configs/report_market_prompt.md"
PER_DAY = 3
SCHEMA_MARKET = {"name": "report_market", "strict": True,
                 "schema": {"type": "object", "additionalProperties": False,
                            "properties": {"summary": {"type": "string"},
                                           "flow": {"type": "array", "items": {
                                               "type": "object", "additionalProperties": False,
                                               "properties": {"day": {"type": "string"}, "text": {"type": "string"},
                                                              "refs": {"type": "array", "items": {"type": "integer"}}},
                                               "required": ["day", "text", "refs"]}}},
                            "required": ["summary", "flow"]}}

INDEX_ROWS_SQL = """SELECT trade_date AS day, close AS value FROM market_indices
WHERE code = :c AND trade_date BETWEEN :since AND :until ORDER BY trade_date"""
OBS_ROWS_SQL = """SELECT observation_date AS day, value FROM economic_observations
WHERE indicator_code = :c AND value IS NOT NULL AND observation_date BETWEEN :since AND :until ORDER BY observation_date"""
MARKET_NEWS_SQL = """SELECT a.id, a.title, a.summary, a.published_at, a.url, src.name AS source, cm.cluster_id,
       (SELECT nc.chunk_text FROM news_chunks nc WHERE nc.news_id = a.id ORDER BY nc.chunk_index LIMIT 1) AS chunk,
       (SELECT l.lead_text FROM news_article_leads l WHERE l.news_id = a.id) AS lead
FROM news_articles a LEFT JOIN news_sources src ON src.id = a.source_id
LEFT JOIN news_cluster_members cm ON cm.news_id = a.id
WHERE a.published_at >= :start AND a.published_at < :end
  AND a.title ~ '(코스피|코스닥|증시)' AND a.title ~ '(마감|시황|장마감|증시\\s*(요약|브리핑))'
  AND a.title !~ '\\[특징주\\]|상장 첫날|입성'"""

MACROS = (("코스피", INDEX_ROWS_SQL, "KOSPI", "pt"), ("코스닥", INDEX_ROWS_SQL, "KOSDAQ", "pt"),
          ("원/달러", OBS_ROWS_SQL, "USD_KRW", "원"), ("국고채 3년", OBS_ROWS_SQL, "KR_GOV_3Y", "%"),
          ("미국 10년물", OBS_ROWS_SQL, "US_TREASURY_10Y", "%"))


def _rows(db, sql, **p) -> list[dict]:
    from sqlalchemy import text
    return [dict(r) for r in db.execute(text(sql), p).mappings().all()]


def macro_lines(db, monday: date, last_day: date) -> tuple[list[str], list[dict]]:
    """LLM 입력 줄과 화면 지수 칸 [{name, value, pct}]. 지수는 날마다, 거시 지표는 주간만."""
    lines, cells = ["숫자 (코드 계산):"], []
    for name, sql, code, unit in MACROS:
        rows = _rows(db, sql, c=code, since=monday - timedelta(days=10), until=last_day)
        week = [r for r in rows if r["day"] >= monday]
        before = [r for r in rows if r["day"] < monday]
        if not week or not before:
            continue
        prev, now = float(before[-1]["value"]), float(week[-1]["value"])
        if unit == "%":                                   # 금리는 %p 변화
            lines.append(f"- {name}: {md(week[-1]['day'])} {now:.2f}%, 지난주보다 {now - prev:+.2f}%p")
            continue
        pct = (now - prev) / prev * 100
        cells.append({"name": name, "value": f"{now:,.2f}", "pct": round(pct, 1)})
        lines.append(f"- {name}: {md(week[-1]['day'])} {now:,.2f}, 지난주 마지막 {prev:,.2f}보다 {pct:+.1f}%")
        if unit == "pt":
            b = prev
            for r in week:
                v = float(r["value"])
                lines.append(f"    · {md(r['day'])}({WEEKDAYS[r['day'].weekday()]}) {v:,.2f} (전날보다 {(v - b) / b * 100:+.1f}%)")
                b = v
    return lines, cells


def pick_market_news(rows: list[dict], days: list[date], per_day: int = PER_DAY) -> list[dict]:
    """거래일마다 본문이 있는 '마감' 기사 먼저 per_day건. 같은 사건(cluster)·같은 제목 앞부분은 하나."""
    from .build import SEOUL
    by_day: dict[date, list[dict]] = {d: [] for d in days}
    for r in rows:
        d = r["published_at"].astimezone(SEOUL).date()
        if d in by_day:
            by_day[d].append(r)
    out = []
    for d in days:
        seen_c, seen_t = set(), set()
        cands = sorted(by_day[d], key=lambda r: (not r.get("chunk"), "마감" not in (r["title"] or ""), -len(r.get("chunk") or ""),
                                                  r["published_at"]))
        k = 0
        for r in cands:
            key = re.sub(r"\W", "", (r["title"] or "").lower())[:16]
            if (r.get("cluster_id") is not None and r["cluster_id"] in seen_c) or key in seen_t:
                continue
            seen_t.add(key)
            if r.get("cluster_id") is not None:
                seen_c.add(r["cluster_id"])
            out.append({**r, "day": d})
            k += 1
            if k >= per_day:
                break
    return out


def code_summary(cells: list[dict], last_day: date) -> str:
    bits = [f"{c['name']}는 {c['value']}로 지난주보다 {abs(c['pct']):.1f}% {'올랐' if c['pct'] > 0 else '내렸' if c['pct'] < 0 else '같았'}어요"
            for c in cells if c["name"] in ("코스피", "코스닥")]
    return (f"{md(last_day)} 기준 " + ", ".join(bits) + ".") if bits else ""


def market_section(db, monday: date, last_day: date, start: datetime, end: datetime, call, first_no: int) -> dict[str, Any]:
    """{cells, summary, flow, items(번호·출처), source, meta}. 기사 번호는 first_no부터."""
    lines, cells = macro_lines(db, monday, last_day)
    days = [monday + timedelta(days=k) for k in range((last_day - monday).days + 1) if (monday + timedelta(days=k)).weekday() < 5]
    news = pick_market_news(_rows(db, MARKET_NEWS_SQL, start=start, end=end), days)
    items = []
    for n, r in enumerate(news, first_no):
        snip = (r.get("summary") or "").strip()
        if len(snip) < 40:
            snip = (r.get("lead") or r.get("chunk") or "").strip()
        items.append({"no": n, "day": r["day"], "title": (r["title"] or "").strip(), "src": r.get("source") or "",
                      "ref": f"news:{r['id']}", "url": r.get("url"), "snippet": re.sub(r"\s+", " ", snip)[:300]})
    fallback = {"cells": cells, "summary": code_summary(cells, last_day), "flow": [], "items": items, "source": "code",
                "meta": {"tries": 0, "problems": [], "usage": {"input": 0, "output": 0}}}
    if call is None or not items:
        return fallback
    source = "\n".join(["한 주: " + f"{md(monday)}({WEEKDAYS[0]}) ~ {md(last_day)}({WEEKDAYS[last_day.weekday()]})", *lines,
                        "시황 기사 (번호 · 날짜 · 출처 · 제목 / 내용은 본문 앞부분):"]
                       + [f"[{i['no']}] {md(i['day'])}({WEEKDAYS[i['day'].weekday()]}) · {i['src']} · {i['title']}"
                          + (f"\n    내용: {i['snippet']}" if i["snippet"] else "") for i in items])
    nos = {i["no"] for i in items}

    def check(out: dict) -> list[str]:
        probs = check_text(out.get("summary", ""), source, nos, 4, 9, 1000, "summary")
        flow = out.get("flow") or []
        if not (2 <= len(flow) <= 5):
            probs.append(f"flow: {len(flow)}줄 (3~5줄)")
        for f in flow:
            probs += check_text(f.get("text", ""), source, nos, 1, 2, 80, "flow", need_refs=False)
            if set(f.get("refs") or []) - nos:
                probs.append(f"flow: 입력에 없는 번호 {sorted(set(f['refs']) - nos)}")
        return probs
    out, meta = ask(call, MARKET_PROMPT, source, SCHEMA_MARKET, check)
    if out is None:
        return {**fallback, "meta": meta}
    flow = [{"day": f["day"], "text": f["text"].strip(), "src": "".join(f"[{r}]" for r in f.get("refs") or [])} for f in out["flow"]]
    # 검수: 시황 문장·흐름 줄을 근거와 대조해 뒷받침되지 않는 것은 뺀다
    texts = {"summary": out["summary"].strip(), **{f"flow{k}": f["text"] for k, f in enumerate(flow)}}
    cleaned, removed, vu = verify_texts(call, source, texts)
    meta["usage"] = {k: meta["usage"][k] + vu[k] for k in ("input", "output")}
    meta["removed"], meta["verify_failed"] = removed, vu["failed"]
    flow = [{**f, "text": cleaned[f"flow{k}"]} for k, f in enumerate(flow) if cleaned.get(f"flow{k}")]
    summary = cleaned["summary"] or fallback["summary"]
    return {"cells": cells, "summary": summary, "flow": flow, "items": items, "source": "llm", "meta": meta}


__all__ = ["market_section", "pick_market_news", "macro_lines", "code_summary", "sentences"]
