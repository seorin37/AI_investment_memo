"""운영 DB의 AI 업데이트 상태를 파일로 떠 두기 (읽기 전용) (2026-11-17).

    PYTHONPATH=backend python -m pipelines.updates.db_state_snapshot <폴더>

06:30 매일 실행(daily → experiment --store db)이 DB에서 읽는 것을 그대로 파일로 옮긴다:
- 대상 항목: db_store.load_items (AI가 켜진 일반 메모의 active 항목) → items.json {item_ids, symbols}
- 마지막 확인 시각: tracking_items.last_checked_at → item_state.json (item_state.FileItemStateStore 형식)
- 이미 카드에 쓴 근거: update_sources → used_refs.json (used_refs.FileUsedRefStore 형식)
그러면 experiment --store file --item-ids … --item-state … --used-refs …로 06:30과 같은 조건의 실행을 DB 쓰기 없이 돌릴 수 있다.
DB에는 읽기 전용 연결만 쓴다.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import psycopg

from pipelines.common.db import get_read_dsn

from .db_store import USED_SQL, load_items, refs_from_rows
from .item_state import FILE_VERSION as STATE_VERSION
from .used_refs import FILE_VERSION as REFS_VERSION


def snapshot(conn) -> tuple[dict, dict, dict]:
    items = load_items(conn, None)
    ids = [i.item_id for i in items]
    rows = conn.execute("SELECT id, last_checked_at FROM tracking_items WHERE id = ANY(%(ids)s)",
                        {"ids": [int(i) for i in ids]}).fetchall()
    state = {str(i): {"last_checked_at": ts.isoformat(), "status": "", "reason": ""} for i, ts in rows if ts is not None}
    used = {}
    for iid in ids:
        refs = refs_from_rows(conn.execute(USED_SQL, {"item": int(iid)}).fetchall())
        if refs:
            used[iid] = {r: "" for r in sorted(refs)}
    meta = {"item_ids": ids, "symbols": sorted({i.symbol for i in items}),
            "types": {t: sum(i.type == t for i in items) for t in sorted({i.type for i in items})}}
    return meta, {"version": STATE_VERSION, "items": state}, {"version": REFS_VERSION, "items": used}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="운영 DB의 업데이트 상태 → 파일 (읽기 전용)")
    ap.add_argument("out")
    args = ap.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    with psycopg.connect(get_read_dsn()) as conn:
        conn.read_only = True
        meta, state, used = snapshot(conn)
        conn.rollback()
    for name, data in (("items.json", meta), ("item_state.json", state), ("used_refs.json", used)):
        (out / name).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"items": len(meta["item_ids"]), "types": meta["types"], "with_last_checked": len(state["items"]),
                      "with_used_refs": len(used["items"]), "out": str(out)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
