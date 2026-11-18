"""RSS 기사에 종목을 태깅한다 (제목·요약에 alias가 있으면 news_stocks에 연결).

지정한 기간(발행시각 기준)의 기사 중 아직 종목 연결이 없는 기사만 훑는다.
"""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

import yaml

log = logging.getLogger("tagger")


def load_stocks(path: Path) -> dict[str, list[str]]:
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    return {code: spec["aliases"] for code, spec in cfg["stocks"].items()}


def load_title_only(path: Path) -> set[str]:
    """제목에 alias가 있을 때만 태깅할 종목 코드 (stocks.yaml의 title_only: true)."""
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    return {code for code, spec in cfg["stocks"].items() if spec.get("title_only")}


def match_stocks(title: str, summary: str | None, stocks: dict[str, list[str]],
                 title_only: set[str] | None = None) -> list[str]:
    title_only = title_only or set()
    both = f"{title} {summary or ''}".casefold()
    only_title = title.casefold()
    return [code for code, aliases in stocks.items()
            if any(a.casefold() in (only_title if code in title_only else both) for a in aliases)]


def tag_window(conn, stocks: dict[str, list[str]], since: datetime, until: datetime,
               title_only: set[str] | None = None) -> tuple[int, int]:
    """(훑은 기사 수, 새로 만든 연결 수)."""
    scanned = links = 0
    with conn.cursor() as cur:
        cur.execute("""
            SELECT a.id, a.title, a.summary FROM news_articles a
            WHERE a.published_at >= %s AND a.published_at < %s
              AND NOT EXISTS (SELECT 1 FROM news_stocks s WHERE s.news_id = a.id)""", (since, until))
        for news_id, title, summary in cur.fetchall():
            scanned += 1
            for code in match_stocks(title, summary, stocks, title_only):
                cur.execute("INSERT INTO news_stocks (news_id, symbol) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                            (news_id, code))
                links += cur.rowcount
    return scanned, links
