"""뉴스 테이블 전용 DB 조회 (news_sources / news_feeds)와 중복 판별 해시."""

from __future__ import annotations

import hashlib
import re

_KEY_RE = re.compile(r"[\W_]+", re.UNICODE)


def content_hash(source_code: str, title: str) -> str:
    """제목 기준 해시. 매체가 다르면 같은 제목이어도 다른 기사로 본다."""
    key = f"{source_code}|{_KEY_RE.sub('', title).casefold()}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def source_ids(cur) -> dict[str, int]:
    cur.execute("SELECT code, id FROM news_sources WHERE enabled")
    return dict(cur.fetchall())


def load_feeds_from_db(cur) -> list[dict]:
    cur.execute("""
        SELECT s.code, s.name, f.section, f.feed_url
        FROM news_feeds f JOIN news_sources s ON s.id = f.source_id
        WHERE f.enabled AND s.enabled ORDER BY s.id, f.section""")
    return [{"source_code": c, "publisher": n, "section": sec, "url": u}
            for c, n, sec, u in cur.fetchall()]
