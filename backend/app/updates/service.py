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


CONTRACT_TYPES = ("disclosure", "news", "price")


def contract_type(db_type: str, sources: list[dict[str, Any]]) -> str:
    """DB 카드 종류 → 계약 UpdateType(disclosure|news|price). 카드를 내보내는 모든 API가 이 함수 하나를 쓴다.

    - price_condition → price
    - 0019 질문 답(answer)과 그 밖의 새 종류 → 대표 근거 종류(news|disclosure), 근거가 없으면(답을 못 찾은 카드) news
    원래 종류는 응답의 card_type 에 그대로 남긴다.
    """
    if db_type == "price_condition":
        return "price"
    if db_type in CONTRACT_TYPES:
        return db_type
    return sources[0]["kind"] if sources else "news"


class UpdatesService:
    def __init__(self, repository: UpdatesRepository) -> None:
        self.repository = repository

    def _ai_updates(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        sources = self.repository.sources([int(r["id"]) for r in rows])
        pairs = [(int(r["item_id"]), s["news_id"]) for r in rows for s in sources.get(int(r["id"]), []) if s["news_id"]]
        sims = self.repository.similarities(pairs)
        closes = {int(r["id"]): self.repository.recent_closes(r["symbol"], r["observed_trade_date"])
                  for r in rows if r["type"] == "price_condition" and r["observed_trade_date"] is not None}
        return [self._ai_update(r, [_source(s) for s in sources.get(int(r["id"]), [])], sims, closes.get(int(r["id"]), []))
                for r in rows]

    def _ai_update(self, r: dict[str, Any], srcs: list[dict[str, Any]], sims: dict,
                   closes: list[tuple[Any, float]] | None = None) -> dict[str, Any]:
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
            "type": contract_type(r["type"], srcs), "title": title or "", "source": source or "", "url": url,
            "published_at": published or r["created_at"],
            "memo_id": str(r["memo_id"]), "memo_title": r["memo_title"] or "", "memo_version": int(r["memo_version"] or 1),
            "summary": r["summary"], "headline": r["title"], "read": bool(r["is_read"]),
            "relevance": round(max(news_sims), 4) if news_sims else 1.0,
            # 덧붙인 값
            "created_at": r["created_at"], "reason": r["reason"], "card": details,
            "memo_color": r["color"] or "yellow",               # 2026-11-22 업데이트 화면 메모 색 (C-21)
            "card_type": r["type"],                             # DB 원래 종류 (answer 등). 계약 type 은 contract_type
            "answer_status": details.get("answer_status") if r["type"] == "answer" else None,
            "item": {"id": str(r["item_id"]), "type": r["item_type"], "description": r["item_description"],
                     "status": r["item_status"], "last_checked_at": r["last_checked_at"]},
            "sources": srcs,
            # 2026-11-22 업데이트 화면 가격 카드: 조건가·방향(tracking_items)·최근 10거래일 종가(prices_daily, 원시 종가)
            "price": {"state": r["price_state"], "observed_value": value, "observed_trade_date": r["observed_trade_date"],
                      "threshold": float(r["price_threshold"]) if r.get("price_threshold") is not None else None,
                      "direction": {"price_above": "above", "price_below": "below"}.get(r["item_type"]),
                      "closes": [c for _, c in closes or []], "closes_from": closes[0][0] if closes else None}
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

    def market_updates(self, user_id: int, stock_code: str | None = None, limit: int | None = None,
                       days: int = 30) -> list[dict[str, Any]]:
        """홈·최신 업데이트 피드 (계약 MarketUpdate[]): 지금 내 종목의 최근 days일 카드, 최신순.

        AI 연결을 나중에 끈 메모의 카드도 포함한다. 같은 근거(종목·종류·링크·제목)가 메모 여러 개에 붙은 카드는 하나로 줄인다.
        answer 카드의 type 변환은 _ai_update(contract_type)가 이미 한다.
        """
        rows = self.repository.cards(user_id, symbol=stock_code, ai_linked_only=False, active_stocks_only=True,
                                     recent_days=days, limit=500)
        out: list[dict[str, Any]] = []
        seen: set[tuple] = set()
        for update in self._ai_updates(rows):
            key =(update["stock_code"], update["type"], update["url"] or "", update["title"])
            if key in seen:
                continue
            seen.add(key)
            out.append(update)
            if limit is not None and len(out) >= limit:
                break
        return out

    def mark_read(self, user_id: int, update_id: int) -> None:
        if not self.repository.mark_read(user_id, update_id):
            raise UpdateNotFoundError(update_id)

    def mark_memo_read(self, user_id: int, memo_id: int) -> int:
        """메모 창에서 AI 업데이트를 봤을 때: 그 메모의 안 읽은 카드를 모두 읽음으로. 바꾼 수를 돌려준다."""
        changed = self.repository.mark_memo_read(user_id, memo_id)
        if changed is None:
            raise MemoNotFoundError(memo_id)
        return changed
