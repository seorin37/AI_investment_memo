"""LLM 사용량 기록 (2026-11-11, 결정 (다): tracking_usage_events는 쓰지 않고 파일로).

- 실행마다 results/updates/usage_log.jsonl에 한 줄: 실행 시각, 실행 폴더, 항목 수, 단계별 호출 수·토큰·비용, 합계, 카드 수.
- 실행 폴더에 usage_by_item.csv: 항목 × 단계마다 호출 수·토큰·비용.
- 단계: relevance(관련성 판정) · card(카드 작성) · format_retry(형식 재요청) · verify(검수 호출). 카드 단계 호출은 프롬프트로 구분한다.
- 비용은 relevance_compare.PRICES (1M 토큰당 입력·출력 USD). 모델 가격을 모르면 비용은 비운다.
항목당 하루 평균 비용은 `python -m pipelines.updates.usage_daily`.
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from .models import CreditsExhausted

STAGES = ("relevance", "card", "format_retry", "verify")
LOG_PATH = "results/updates/usage_log.jsonl"
CSV_COLUMNS = ["item_id", "symbol", "item_type", "stage", "model", "calls", "prompt_tokens", "output_tokens",
               "reasoning_tokens", "usd"]


def stage_of(prompt: str) -> str:
    """카드 단계에서 부른 호출의 단계 (topic.py의 프롬프트 모양으로)."""
    if "당신은 memo's 업데이트 카드의 검수기입니다" in prompt:
        return "verify"
    if "# 수정 요청" in prompt:
        return "format_retry"
    return "card"


def usd(model: str | None, prompt_tokens: int, output_tokens: int) -> float | None:
    from .relevance_compare import PRICES
    pin, pout = PRICES.get(model or "", (None, None))
    return None if pin is None else prompt_tokens * pin / 1e6 + output_tokens * pout / 1e6


class UsageTracker:
    """LLM 호출 함수를 감싸 항목·단계별로 client.calls에 새로 붙은 기록을 모은다. 호출 자체는 그대로 한다."""

    def __init__(self):
        self.rows: list[dict] = []

    def caller(self, client, item, stage: str | None = None):
        if client is None:
            return None

        def call(prompt: str) -> str:
            before = len(client.calls)
            try:
                return client(prompt)
            except CreditsExhausted:
                raise
            finally:
                for c in client.calls[before:]:
                    self.rows.append({"item_id": item.item_id, "symbol": item.symbol, "item_type": item.type,
                                      "stage": stage or stage_of(prompt), "model": client.model,
                                      "prompt_tokens": c.prompt_tokens or 0, "output_tokens": c.output_tokens or 0,
                                      "reasoning_tokens": c.reasoning_tokens or 0})
        return call

    def by_item(self) -> list[dict]:
        agg: dict[tuple, dict] = {}
        for r in self.rows:
            key = (r["item_id"], r["stage"], r["model"])
            a = agg.setdefault(key, {**{k: r[k] for k in ("item_id", "symbol", "item_type", "stage", "model")},
                                     "calls": 0, "prompt_tokens": 0, "output_tokens": 0, "reasoning_tokens": 0})
            a["calls"] += 1
            for k in ("prompt_tokens", "output_tokens", "reasoning_tokens"):
                a[k] += r[k]
        out = []
        for a in agg.values():
            cost = usd(a["model"], a["prompt_tokens"], a["output_tokens"])
            out.append({**a, "usd": None if cost is None else round(cost, 6)})
        return sorted(out, key=lambda a: (a["item_id"], STAGES.index(a["stage"]) if a["stage"] in STAGES else 9))

    def stages(self) -> dict:
        out = defaultdict(lambda: {"calls": 0, "prompt_tokens": 0, "output_tokens": 0, "reasoning_tokens": 0, "usd": 0.0})
        for a in self.by_item():
            s = out[a["stage"]]
            for k in ("calls", "prompt_tokens", "output_tokens", "reasoning_tokens"):
                s[k] += a[k]
            s["usd"] = None if a["usd"] is None or s["usd"] is None else s["usd"] + a["usd"]
        return {k: {**v, "usd": None if v["usd"] is None else round(v["usd"], 6)} for k, v in out.items()}


def write_usage(tracker: UsageTracker, run_dir: Path, log_path: Path, *, items: int, topic_items: int, cards: int,
                fresh_items: int, extra: dict | None = None, now: datetime | None = None) -> dict:
    """usage_by_item.csv(실행 폴더)와 usage_log.jsonl(한 줄 더하기). 반환: 로그 줄."""
    rows = tracker.by_item()
    with (run_dir / "usage_by_item.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        w.writeheader()
        w.writerows(rows)
    stages = tracker.stages()
    total = {k: sum(s[k] for s in stages.values()) for k in ("calls", "prompt_tokens", "output_tokens", "reasoning_tokens")}
    costs = [s["usd"] for s in stages.values()]
    total["usd"] = None if any(c is None for c in costs) else round(sum(costs), 6)
    line = {"run_at": (now or datetime.now().astimezone()).isoformat(timespec="seconds"), "run_dir": str(run_dir),
            "items": items, "topic_items": topic_items, "fresh_items": fresh_items,
            "items_with_calls": len({r["item_id"] for r in rows}), "stages": stages, "total": total, "cards": cards,
            **(extra or {})}
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")
    return line
