"""AI 업데이트 카드 → 계약(frontend/docs/API_CONTRACT.md)의 AiUpdate · MemoTimeline · MemoUpdateSummary 모양 (2026-11-11).

계약 필드는 그대로 채우고, 계약에 없던 값은 덧붙인다 (계약 문서에 적음):
- card: 카드 v2 전체(details — headline·when·facts·memo_link·coverage·run_id …), item: 추적 항목(종류·설명·상태·last_checked_at),
  sources: 근거 목록(news|disclosure, 제목·매체·링크·날짜·quote), price: 가격 카드 칸(state·observed_value·observed_trade_date),
  created_at: 카드를 만든 시각.
- type: DB의 price_condition은 계약의 'price'로. title: 대표 근거의 제목(가격 카드는 "종가 N원"), headline: 카드 제목.
- relevance: 대표 뉴스의 관련성 판정 유사도(tracking_matches), 없으면 1.0.
"""

from __future__ import annotations

from typing import Any

from .repository import UpdatesRepository

DART_URL = "https://dart.fss.or.kr/dsaf001/main.do?rcpNo={}"


class MemoNotFoundError(LookupError):
    pass


class UpdateNotFoundError(LookupError):
    pass


def _source(s: dict[str, Any]) -> dict[str, Any]:
    if s["news_id"] is not None:
        return {"kind": "news", "ref": f"news:{s['news_id']}", "title": s["news_title"], "source": s["news_source"] or "뉴스",
                "url": s["news_url"], "published_at": s["published_at"], "quote": s["quote"]}
    return {"kind": "disclosure", "ref": f"disc:{s['disclosure_rcept_no']}", "title": s["disclosure_title"], "source": "DART",
            "url": DART_URL.format(s["disclosure_rcept_no"]), "published_at": s["rcept_dt"], "quote": s["quote"]}


class UpdatesService:
    def __init__(self, repository: UpdatesRepository) -> None:
        self.repository = repository

    def _ai_updates(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        sources = self.repository.sources([int(r["id"]) for r in rows])
        pairs = [(int(r["item_id"]), s["news_id"]) for r in rows for s in sources.get(int(r["id"]), []) if s["news_id"]]
        sims = self.repository.similarities(pairs)
        return [self._ai_update(r, [_source(s) for s in sources.get(int(r["id"]), [])], sims) for r in rows]

    def _ai_update(self, r: dict[str, Any], srcs: list[dict[str, Any]], sims: dict) -> dict[str, Any]:
        is_price = r["type"] == "price_condition"
        lead = srcs[0] if srcs else None
        value = float(r["observed_value"]) if r["observed_value"] is not None else None
        if is_price:
            title, source, url, published = (f"종가 {value:,.0f}원" if value is not None else r["title"]), "KRX", None, \
                r["observed_trade_date"]
        else:
            title = lead["title"] if lead else r["title"]
            source, url, published = (lead["source"], lead["url"], lead["published_at"]) if lead else ("", None, None)
        news_sims = [sims[(int(r["item_id"]), int(s["ref"].split(":")[1]))] for s in srcs
                     if s["kind"] == "news" and (int(r["item_id"]), int(s["ref"].split(":")[1])) in sims]
        details = r["details"] or {}
        return {
            # 계약 (MarketUpdate + AiUpdate)
            "id": str(r["id"]), "stock_code": r["symbol"], "stock_name": r["stock_name"] or r["symbol"],
            "type": "price" if is_price else r["type"], "title": title or "", "source": source or "", "url": url,
            "published_at": published or r["created_at"],
            "memo_id": str(r["memo_id"]), "memo_title": r["memo_title"] or "", "memo_version": int(r["memo_version"] or 1),
            "summary": r["summary"], "headline": r["title"], "read": bool(r["is_read"]),
            "relevance": round(max(news_sims), 4) if news_sims else 1.0,
            # 덧붙인 값
            "created_at": r["created_at"], "reason": r["reason"], "card": details,
            "item": {"id": str(r["item_id"]), "type": r["item_type"], "description": r["item_description"],
                     "status": r["item_status"], "last_checked_at": r["last_checked_at"]},
            "sources": srcs,
            "price": {"state": r["price_state"], "observed_value": value, "observed_trade_date": r["observed_trade_date"]}
            if is_price else None,
        }

    def stock_ai_updates(self, user_id: int, symbol: str, limit: int = 100) -> list[dict[str, Any]]:
        return self._ai_updates(self.repository.cards(user_id, symbol=symbol, limit=limit))

    def memo_timeline(self, user_id: int, memo_id: int) -> dict[str, Any]:
        memo = self.repository.memo(user_id, memo_id)
        if memo is None:
            raise MemoNotFoundError(memo_id)
        rows = self.repository.cards(user_id, memo_id=memo_id, ai_linked_only=False, limit=500)
        updates = self._ai_updates(rows)
        entries = []
        for r, u in zip(rows, updates):
            snap = {"version": int(r["memo_version"] or 1), "title": r["snapshot_title"] or "", "body": r["snapshot_body"] or "",
                    "saved_at": r["snapshot_at"]}
            entries.append({"kind": "update", "at": r["created_at"], "update": u, "memo_snapshot": snap})
        for rev in self.repository.revisions(memo_id):
            version = {"version": rev["revision_no"], "title": rev["title"] or "", "body": rev["content"] or "",
                       "saved_at": rev["created_at"]}
            entries.append({"kind": "memo_created" if rev["revision_no"] == 1 else "memo_edit", "at": rev["created_at"],
                            "version": version})
        if memo["ai_linked"] and memo["ai_linked_at"]:
            entries.append({"kind": "ai_linked", "at": memo["ai_linked_at"]})
        entries.sort(key=lambda e: e["at"], reverse=True)
        items = self.repository.items(memo_id)
        return {"memo_id": str(memo_id), "entries": entries,
                "price_condition_count": sum(1 for i in items if i["type"] in ("price_below", "price_above")),
                # 덧붙인 값: 항목별 마지막 확인 시각
                "tracking_items": [{"id": str(i["id"]), "type": i["type"], "description": i["description"],
                                    "status": i["status"], "last_checked_at": i["last_checked_at"]} for i in items]}

    def summary(self, user_id: int, per_memo: int = 5) -> list[dict[str, Any]]:
        """종목별 읽지 않은 카드 (AI 켠 메모만). new_count = 그 종목의 읽지 않은 카드 수."""
        rows = self.repository.cards(user_id, unread_only=True, limit=500)
        updates = self._ai_updates(rows)
        by_stock: dict[str, dict[str, Any]] = {}
        for r, u in zip(rows, updates):
            st = by_stock.setdefault(r["symbol"], {"stock_code": r["symbol"], "stock_name": r["stock_name"] or r["symbol"],
                                                   "new_count": 0, "memos": {}})
            st["new_count"] += 1
            memo = st["memos"].setdefault(r["memo_id"], {"memo_id": str(r["memo_id"]), "title": r["memo_title"] or "",
                                                         "color": r["color"] or "yellow", "updates": []})
            if len(memo["updates"]) < per_memo:
                memo["updates"].append(u)
        out = [{**v, "memos": list(v["memos"].values())} for v in by_stock.values()]
        return sorted(out, key=lambda v: -v["new_count"])

    def mark_read(self, user_id: int, update_id: int) -> None:
        if not self.repository.mark_read(user_id, update_id):
            raise UpdateNotFoundError(update_id)
