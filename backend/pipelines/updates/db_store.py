"""카드·관련성 판정·마지막 확인 시각을 기존 DB 테이블에 쓴다 (2026-11-11, 새 테이블·마이그레이션 없음).

대응
- update_card → tracking_updates(type: 근거에 공시가 있으면 disclosure 아니면 news, title=headline, summary=facts를 이은 문장,
  reason=memo_link, details=카드 v2 전체 JSON(coverage 포함)) + update_sources(근거마다 1행: news_id 또는 disclosure_rcept_no 하나만,
  quote=근거 문장, 공시는 "[청크 3,5] 문장"). 같은 공시의 청크 여러 개는 한 행으로 합친다 (update_sources_disclosure_uq).
  비교용 근거(cmp:…)는 DB 행이 없어 details에만 남는다.
- price_card → tracking_updates(type=price_condition, price_state, observed_value=종가, observed_trade_date, tracking_revision_id 필수).
  **update_sources·price_events는 만들지 않는다**: 0005 트리거(trg_reject_price_condition_source)가 가격 조건 업데이트의
  update_sources 행을 거부하고, price_events.event_type(volume_surge·high_52w·low_52w·big_move·ma_cross)에 '사용자 조건 도달'이 없다.
  같은 항목·같은 버전·같은 거래일은 ux_tracking_updates_price_condition_daily로 한 번만 (ON CONFLICT DO NOTHING).
- no_new_info / no_data → 행 없음. tracking_items.last_checked_at만 갱신. no_data는 로그에도 남긴다.
- needs_confirmation / 메모 단위 out_of_scope → DB에 쓰지 않는다 (response.memo_analysis_responses가 돌려준다).
- 관련성 판정 → tracking_matches (판정한 뉴스 후보 전체, similarity, decision relevant/irrelevant, decided_at). 다시 판정하면 갱신.
- memo_revision_id·tracking_revision_id는 그 항목의 최신 버전을 조회해서 넣는다.
- 저장소: DbUsedRefStore(이미 쓴 근거 = 그 항목 update_sources), DbItemStateStore(tracking_items.last_checked_at).
쓰기 연결은 check_test_target으로 로컬 테스트 DB(127.0.0.1·localhost:5433, 이름에 test)만 허용한다.
공용 DB(SHARED_TARGETS)는 allow_shared=True(experiment --allow-shared-write)일 때만, 주소와 연결 정보 둘 다 맞을 때만 쓴다.
2026-11-11 추가: 실행마다 run_id를 tracking_updates.details에 남기고, 이번 실행이 넣거나 바꾼 행(카드·근거·판정·확인 시각과
바뀌기 전 값)을 manifest로 모은다 → 실행 폴더 db_rows.json → db_cleanup.py가 그 실행분만 지우거나 되돌린다.
tracking_matches에는 run_id를 둘 칸이 없어(마이그레이션 금지) manifest로만 남긴다.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from urllib.parse import urlparse

from .models import Response, TrackingItem, UpdateDraft

log = logging.getLogger(__name__)

TEST_HOSTS = ("127.0.0.1", "localhost")
TEST_PORT = 5433
SHARED_TARGETS = {("192.168.0.105", 15432, "memos")}          # 공용 DB (host, port, db). --allow-shared-write일 때만
_CHUNKS = re.compile(r"^\[청크 ([\d,]+)\]\s*")


class NotTestDatabase(RuntimeError):
    pass


def _allowed(host, port, dbname, allow_shared: bool) -> bool:
    if host in TEST_HOSTS and int(port or 0) == TEST_PORT and "test" in (dbname or ""):
        return True
    return allow_shared and (host, int(port or 0), dbname) in SHARED_TARGETS


def check_test_target(dsn: str, allow_shared: bool = False) -> str:
    """쓰기 대상이 로컬 테스트 DB(또는 allow_shared면 공용 DB)인지 확인하고 "host:port/db"를 돌려준다 (비밀번호는 다루지 않는다)."""
    u = urlparse(re.sub(r"^(postgres(?:ql)?)\+\w+://", r"\1://", dsn.strip()))
    name = (u.path or "").lstrip("/")
    target = f"{u.hostname}:{u.port}/{name}"
    if not _allowed(u.hostname, u.port, name, allow_shared):
        raise NotTestDatabase(f"쓰기를 허용한 DB가 아니라서 쓰지 않습니다: {target} "
                              f"(로컬 테스트 DB 127.0.0.1:5433/*test*, 공용 DB는 --allow-shared-write일 때만)")
    return target


def check_conn(conn, allow_shared: bool = False) -> str:
    """연결이 실제로 허용한 DB를 가리키는지 연결 정보(conn.info)로 다시 확인한다. 쓰기 클래스가 만들어질 때 부른다."""
    info = conn.info
    target = f"{info.host}:{info.port}/{info.dbname}"
    if not _allowed(info.host, info.port, info.dbname, allow_shared):
        raise NotTestDatabase(f"쓰기를 허용한 DB 연결이 아니라서 쓰지 않습니다: {target}")
    return target


def shared_write_dsn() -> str:
    """공용 DB 쓰기 주소 (DATABASE_URL, 앱 계정). --allow-shared-write일 때만 부른다. 값은 출력하지 않는다."""
    from ..common.db import database_url
    return database_url()


def finish(conn, allow_shared: bool = False) -> None:
    """쓰기를 확정하고 연결을 닫는다 (experiment에는 commit을 두지 않는다 — ReadOnlyGuardTest)."""
    check_conn(conn, allow_shared)
    conn.commit()
    conn.close()


# ------------------------------------------------------------------ 테스트 DB 준비 (2026-11-11, test_db_prep copy)
def _test_columns(dst, table: str) -> list[str]:
    """테스트 DB 쪽 열 (생성 열은 넣을 수 없어 뺀다)."""
    return [r[0] for r in dst.execute("""SELECT column_name FROM information_schema.columns
        WHERE table_name = %s AND is_generated = 'NEVER' ORDER BY ordinal_position""", (table,)).fetchall()]


def copy_table(src, dst, table: str, select_sql, columns: list[str] | None = None) -> int:
    """공용 DB의 SELECT 결과를 테스트 DB 테이블로 COPY 한다 (값을 텍스트 그대로 옮겨 vector·jsonb도 같게). 반환: 행 수.
    select_sql은 psycopg.sql로 값을 넣은 SELECT (열 순서는 columns와 같아야 한다)."""
    from psycopg import sql

    check_conn(dst)
    cols = columns or _test_columns(dst, table)
    ident = sql.SQL(", ").join(sql.Identifier(c) for c in cols)
    n = 0
    with src.cursor().copy(sql.SQL("COPY ({}) TO STDOUT").format(select_sql)) as out, \
            dst.cursor().copy(sql.SQL("COPY {} ({}) FROM STDIN").format(sql.Identifier(table), ident)) as inp:
        for block in out:
            inp.write(block)
            n += bytes(block).count(b"\n")
    return n


def seed_memos(dst, memos: list[dict], email: str = "updates-test@example.invalid") -> dict:
    """평가 메모를 테스트 사용자 메모로 넣고, 정답 항목을 tracking_items·tracking_item_revisions(1번)로 넣는다.
    memo_revisions 1번은 trg_capture_memo_revision이 만든다. 반환: {메모 ID: [(항목 id, 정답 항목)]}."""
    check_conn(dst)
    row = dst.execute("SELECT id FROM users WHERE email = %s", (email,)).fetchone()
    uid = row[0] if row else dst.execute("INSERT INTO users (email, display_name) VALUES (%s, 'updates test') RETURNING id",
                                         (email,)).fetchone()[0]
    out = {}
    for m in memos:
        mid = dst.execute("INSERT INTO memos (user_id, symbol, title, content) VALUES (%s, %s, %s, %s) RETURNING id",
                          (uid, m["symbol"], m["memo_id"], m["text"])).fetchone()[0]
        out[m["memo_id"]] = []
        for s in m["sentences"]:
            for it in s["items"]:
                if it["type"] not in ("topic", "price_below", "price_above"):
                    continue
                kw = ", ".join(it.get("keywords") or []) or None
                iid = dst.execute("""INSERT INTO tracking_items (memo_id, type, description, keywords, price_threshold)
                    VALUES (%s, %s, %s, %s, %s) RETURNING id""",
                                  (mid, it["type"], it["description"], kw, it.get("price_threshold"))).fetchone()[0]
                dst.execute("""INSERT INTO tracking_item_revisions (tracking_item_id, revision_no, type, description, keywords,
                    price_threshold) VALUES (%s, 1, %s, %s, %s, %s)""",
                            (iid, it["type"], it["description"], kw, it.get("price_threshold")))
                out[m["memo_id"]].append((iid, it))
    return out


def enable_test_memos_ai(dst) -> int:
    """테스트 DB 전용: 시범 note 메모의 AI 연결을 켠다 (매일 실행 대상 조건 확인용). 로컬 테스트 DB가 아니면 멈춘다."""
    check_conn(dst)                                             # allow_shared 없이: 테스트 DB만
    return dst.execute("""UPDATE memos SET ai_linked = true, ai_linked_at = COALESCE(ai_linked_at, now())
        WHERE kind = 'note' AND deleted_at IS NULL AND NOT ai_linked""").rowcount


# ------------------------------------------------------------------ 항목 읽기
ITEMS_SQL = """SELECT ti.id, btrim(m.symbol), ti.type::text, COALESCE(r.description, ti.description),
       COALESCE(r.keywords, ti.keywords), COALESCE(r.price_threshold, ti.price_threshold), m.content
FROM tracking_items ti
JOIN memos m ON m.id = ti.memo_id
LEFT JOIN LATERAL (SELECT description, keywords, price_threshold FROM tracking_item_revisions
                   WHERE tracking_item_id = ti.id ORDER BY revision_no DESC LIMIT 1) r ON true
WHERE ti.status = 'active' AND m.deleted_at IS NULL AND m.ai_linked AND m.kind = 'note'
  AND (%(all)s OR btrim(m.symbol) = ANY(%(symbols)s))
ORDER BY ti.id"""
REVISIONS_SQL = """SELECT
  (SELECT mr.id FROM memo_revisions mr JOIN tracking_items ti ON ti.memo_id = mr.memo_id
    WHERE ti.id = %(item)s ORDER BY mr.revision_no DESC LIMIT 1),
  (SELECT tr.id FROM tracking_item_revisions tr WHERE tr.tracking_item_id = %(item)s ORDER BY tr.revision_no DESC LIMIT 1)"""


def load_items(conn, symbols) -> list[TrackingItem]:
    """AI가 켜진 note 메모의 활성 추적 항목 (최신 버전의 설명·핵심어·조건가). item_id는 tracking_items.id 문자열."""
    out = []
    params = {"all": symbols is None, "symbols": list(symbols or [])}     # symbols None = 전체 활성 항목
    for iid, sym, typ, desc, kw, threshold, content in conn.execute(ITEMS_SQL, params).fetchall():
        keywords = tuple(k.strip() for k in re.split(r"[,\n]", kw or "") if k.strip())
        out.append(TrackingItem(item_id=str(iid), symbol=sym, type=typ, description=desc, keywords=keywords,
                                price_threshold=None if threshold is None else int(threshold), memo_text=content or ""))
    return out


def item_memos(conn, item_ids) -> dict[str, str]:
    """항목 id → 메모 id (같은 메모 카드 합치기용)."""
    rows = conn.execute("SELECT id, memo_id FROM tracking_items WHERE id = ANY(%(ids)s)",
                        {"ids": [int(i) for i in item_ids]}).fetchall()
    return {str(i): str(m) for i, m in rows}


def latest_revisions(conn, item_id: str) -> tuple[int | None, int | None]:
    """(memo_revision_id, tracking_revision_id) — 그 항목의 최신 버전."""
    row = conn.execute(REVISIONS_SQL, {"item": int(item_id)}).fetchone()
    return (row[0], row[1]) if row else (None, None)


# ------------------------------------------------------------------ 저장소
USED_SQL = """SELECT us.news_id, us.disclosure_rcept_no, us.quote FROM update_sources us
JOIN tracking_updates tu ON tu.id = us.update_id WHERE tu.tracking_item_id = %(item)s"""


def refs_from_rows(rows) -> set[str]:
    """update_sources 행 → 후보 ref (news:<id>, disc:<접수번호>#<청크>). 청크 번호가 없는 공시는 disc:<접수번호>(문서 단위)."""
    out = set()
    for news_id, rcept, quote in rows:
        if news_id is not None:
            out.add(f"news:{news_id}")
        elif rcept:
            m = _CHUNKS.match(quote or "")
            out |= {f"disc:{rcept}#{i}" for i in m.group(1).split(",")} if m else {f"disc:{rcept}"}
    return out


class DbUsedRefStore:
    """이미 카드에 쓴 근거 = 그 항목 tracking_updates의 update_sources. 기록은 DbCardWriter가 카드와 함께 한다 (record는 아무것도 안 함)."""

    def __init__(self, conn):
        self.conn = conn

    def used(self, item_id: str) -> set[str]:
        return refs_from_rows(self.conn.execute(USED_SQL, {"item": int(item_id)}).fetchall())

    def record(self, item_id: str, refs, at: str | None = None) -> None:
        return None


class DbItemStateStore:
    """마지막 확인 시각 = tracking_items.last_checked_at. 응답 유형은 DB에 둘 칸이 없어 남기지 않는다 (no_data는 로그)."""

    def __init__(self, conn, manifest: dict | None = None, allow_shared: bool = False):
        check_conn(conn, allow_shared)
        self.conn, self.manifest = conn, manifest

    def get(self, item_id: str) -> dict | None:
        row = self.conn.execute("SELECT last_checked_at FROM tracking_items WHERE id = %(item)s", {"item": int(item_id)}).fetchone()
        if not row or row[0] is None:
            return None
        return {"last_checked_at": row[0].isoformat()}

    def record(self, response: Response) -> None:
        if response.scope != "item" or not response.item_id:
            return
        if response.type == "no_data":
            log.info("no_data item=%s reason=%s checked_at=%s", response.item_id, response.reason, response.checked_at)
        if self.manifest is not None:                           # 되돌리기용: 바뀌기 전 값
            prev = self.conn.execute("SELECT last_checked_at FROM tracking_items WHERE id = %(item)s",
                                     {"item": int(response.item_id)}).fetchone()
            self.manifest["last_checked"].append({"item_id": int(response.item_id),
                                                  "prev": prev[0].isoformat() if prev and prev[0] else None,
                                                  "set": response.checked_at})
        self.conn.execute("UPDATE tracking_items SET last_checked_at = %(ts)s WHERE id = %(item)s",
                          {"ts": datetime.fromisoformat(response.checked_at), "item": int(response.item_id)})


# ------------------------------------------------------------------ 쓰기
INSERT_UPDATE = """INSERT INTO tracking_updates (tracking_item_id, type, title, summary, reason, details, memo_revision_id,
  tracking_revision_id) VALUES (%(item)s, %(type)s, %(title)s, %(summary)s, %(reason)s, %(details)s::jsonb, %(memo_rev)s, %(track_rev)s)
RETURNING id"""
INSERT_PRICE = """INSERT INTO tracking_updates (tracking_item_id, type, title, summary, reason, details, memo_revision_id,
  tracking_revision_id, price_state, observed_value, observed_trade_date)
VALUES (%(item)s, 'price_condition', %(title)s, %(summary)s, %(reason)s, %(details)s::jsonb, %(memo_rev)s, %(track_rev)s,
  %(state)s, %(value)s, %(trade_date)s)
ON CONFLICT (tracking_item_id, tracking_revision_id, observed_trade_date) WHERE type = 'price_condition' DO NOTHING
RETURNING id"""
INSERT_SOURCE = """INSERT INTO update_sources (update_id, news_id, disclosure_rcept_no, quote)
VALUES (%(update)s, %(news)s, %(rcept)s, %(quote)s)"""
UPSERT_MATCH = """INSERT INTO tracking_matches (tracking_item_id, news_id, similarity, decision, decided_at)
VALUES (%(item)s, %(news)s, %(sim)s, %(decision)s, now())
ON CONFLICT (tracking_item_id, news_id) DO UPDATE SET similarity = EXCLUDED.similarity, decision = EXCLUDED.decision,
  decided_at = EXCLUDED.decided_at
RETURNING id"""
PREV_MATCH = """SELECT id, similarity, decision::text, decided_at FROM tracking_matches
WHERE tracking_item_id = %(item)s AND news_id = %(news)s"""
HAS_PRICE_CARD = """SELECT EXISTS (SELECT 1 FROM tracking_updates WHERE tracking_item_id = %(item)s AND type = 'price_condition'
  AND tracking_revision_id IS NOT DISTINCT FROM %(rev)s)"""


def new_manifest(run_id: str, target: str) -> dict:
    """이번 실행이 DB에 넣거나 바꾼 행 (db_cleanup.py가 읽는다)."""
    return {"run_id": run_id, "target": target, "tracking_updates": [], "tracking_matches_inserted": [],
            "tracking_matches_updated": [], "last_checked": []}


def source_rows(draft: UpdateDraft) -> list[dict]:
    """카드 근거 → update_sources 행 값. 뉴스는 기사마다, 공시는 접수번호마다 하나 (청크 번호를 quote 앞에). cmp: 근거는 뺀다."""
    news, discs = {}, {}
    for ref, quote in draft.sources:
        if ref.startswith("news:"):
            nid = int(ref.split(":", 1)[1])
            news[nid] = " ".join(q for q in (news.get(nid), quote) if q)
        elif ref.startswith("disc:"):
            rcept, _, idx = ref.split(":", 1)[1].partition("#")
            d = discs.setdefault(rcept, {"chunks": [], "quotes": []})
            if idx and idx not in d["chunks"]:
                d["chunks"].append(idx)
            if quote:
                d["quotes"].append(quote)
    rows = [{"news": nid, "rcept": None, "quote": q or None} for nid, q in news.items()]
    for rcept, d in discs.items():
        head = f"[청크 {','.join(d['chunks'])}] " if d["chunks"] else ""
        rows.append({"news": None, "rcept": rcept, "quote": (head + " ".join(d["quotes"])).strip() or None})
    return rows


class DbCardWriter:
    def __init__(self, conn, run_id: str = "", manifest: dict | None = None, allow_shared: bool = False):
        check_conn(conn, allow_shared)
        self.conn, self.run_id = conn, run_id
        self.manifest = manifest if manifest is not None else new_manifest(run_id, check_conn(conn, allow_shared))
        self.written = {"update_card": 0, "price_card": 0, "price_duplicate": 0, "sources": 0, "matches": 0,
                        "failed": 0}

    def has_price_card(self, item: TrackingItem) -> bool:
        """그 항목·최신 항목 버전에 가격 카드가 이미 있는가 (없으면 처음 확인 때 near·reached여도 한 번 만든다)."""
        _, track_rev = latest_revisions(self.conn, item.item_id)
        return bool(self.conn.execute(HAS_PRICE_CARD, {"item": int(item.item_id), "rev": track_rev}).fetchone()[0])

    def write(self, item: TrackingItem, draft: UpdateDraft, card: dict) -> int | None:
        """카드 한 장 → tracking_updates (+ update_sources). card는 results.draft_to_dict 모양 (details에 그대로 + run_id).
        카드 하나가 실패해도 다른 카드는 남게 savepoint 안에서 쓴다. 실패하면 예외를 그대로 올린다 (호출자가 그 항목을 실패로 센다)."""
        with self.conn.transaction():
            return self._write(item, draft, card)

    def _write(self, item: TrackingItem, draft: UpdateDraft, card: dict) -> int | None:
        memo_rev, track_rev = latest_revisions(self.conn, item.item_id)
        base = {"item": int(item.item_id), "title": draft.title, "summary": draft.summary, "reason": draft.reason,
                "details": json.dumps({**card, "run_id": self.run_id}, ensure_ascii=False, default=str),
                "memo_rev": memo_rev, "track_rev": track_rev}
        if draft.type == "price_condition":
            if track_rev is None:
                raise ValueError(f"가격 카드에는 tracking_revision_id가 필요합니다 (항목 {item.item_id}에 버전 없음)")
            row = self.conn.execute(INSERT_PRICE, {**base, "state": draft.price_state,
                                                   "value": (draft.details or {}).get("close"),
                                                   "trade_date": draft.observed_trade_date}).fetchone()
            if row is None:
                self.written["price_duplicate"] += 1
                return None
            self.written["price_card"] += 1
            self.manifest["tracking_updates"].append(row[0])
            return row[0]
        rows = source_rows(draft)
        utype = "disclosure" if any(r["rcept"] for r in rows) else "news"
        update_id = self.conn.execute(INSERT_UPDATE, {**base, "type": utype}).fetchone()[0]
        for r in rows:
            self.conn.execute(INSERT_SOURCE, {"update": update_id, **r})
        self.written["update_card"] += 1
        self.written["sources"] += len(rows)
        self.manifest["tracking_updates"].append(update_id)       # update_sources는 카드를 지우면 함께 지워진다 (ON DELETE CASCADE)
        return update_id

    def write_matches(self, item: TrackingItem, labels: dict[str, tuple[bool, str]], similarity: dict[str, float]) -> int:
        """관련성 판정한 뉴스 후보 전체 → tracking_matches. labels: ref → (관련, 이유 코드)."""
        with self.conn.transaction():                          # 판정 기록이 실패해도 다른 항목은 남게
            return self._write_matches(item, labels, similarity)

    def _write_matches(self, item: TrackingItem, labels: dict[str, tuple[bool, str]], similarity: dict[str, float]) -> int:
        n = 0
        for ref, (ok, _) in labels.items():
            if not ref.startswith("news:"):
                continue
            key = {"item": int(item.item_id), "news": int(ref.split(":", 1)[1])}
            prev = self.conn.execute(PREV_MATCH, key).fetchone()
            mid = self.conn.execute(UPSERT_MATCH, {**key, "sim": float(similarity.get(ref, 0.0)),
                                                   "decision": "relevant" if ok else "irrelevant"}).fetchone()[0]
            if prev is None:
                self.manifest["tracking_matches_inserted"].append(mid)
            else:                                               # 되돌리기용: 바뀌기 전 판정
                self.manifest["tracking_matches_updated"].append(
                    {"id": mid, "similarity": prev[1], "decision": prev[2],
                     "decided_at": prev[3].isoformat() if prev[3] else None})
            n += 1
        self.written["matches"] += n
        return n
