"""후보 관련성 판정을 파이프라인에 연결한다 (2026-11-10): 후보 검색 → 관련성 판정(항목별 뉴스 후보를 묶어 1회) → O인 후보만 카드 생성.

- 대상: 뉴스 후보 중 종류별 최소 유사도(topic.min_similarity_*)를 넘은 것만. 넘지 못한 뉴스는 어차피 카드 근거가 되지 않아
  판정하지 않고 뺀다. 공시는 판정하지 않고 그대로 둔다.
- 프롬프트: configs/candidate_relevance_prompt.md (autolabel.build_prompt와 같은 입력 모양, 후보 순서는 항목별 고정 시드로 섞음).
  출력 {"scope": company|industry, "labels": [{id, relevant, code}]}. 유사도는 LLM에 보여 주지 않는다.
- 판정 뒤 남은 후보가 하나도 없으면(판정 전에는 있었는데) 카드 생성을 부르지 않고 no_relevant_candidates.
  판정 호출이 실패하거나 응답을 읽을 수 없으면 카드를 만들지 않는다(relevance_failed). CreditsExhausted는 그대로 올린다.
- 설정 relevance: {enabled(기본 true), prompt, model(없으면 카드 생성과 같은 모델), max_text, seed}.
"""

from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass, field

from . import autolabel
from .evidence import threshold_key
from .models import Candidate, CreditsExhausted, TrackingItem

DEFAULTS = {"enabled": True, "prompt": "configs/candidate_relevance_prompt.md", "model": None,
            "max_text": autolabel.MAX_TEXT, "seed": 7}
SCOPES = ("company", "industry")


@dataclass
class Relevance:
    scope: str = ""                                            # company | industry | "" (판정 안 함·못 읽음)
    labels: dict[str, tuple[bool, str]] = field(default_factory=dict)   # ref → (관련, 이유 코드)
    judged: int = 0
    failed: str = ""                                           # 실패 이유 (call_failed:<예외> | parse_failed)
    below_floor: int = 0                                       # 최소 유사도를 못 넘어 판정하지 않고 뺀 뉴스 수

    def to_dict(self) -> dict:
        rel = sum(ok for ok, _ in self.labels.values())
        codes: dict[str, int] = {}
        for _, code in self.labels.values():
            codes[code or "-"] = codes.get(code or "-", 0) + 1
        return {"scope": self.scope, "judged": self.judged, "relevant": rel, "dropped": self.judged - rel,
                "codes": codes, "failed": self.failed, "below_floor": self.below_floor,
                "labels": {ref: {"relevant": ok, "code": code} for ref, (ok, code) in self.labels.items()}}


def config(cfg: dict | None) -> dict:
    return {**DEFAULTS, **(cfg or {})}


def parse_scope(raw: str) -> str:
    match = re.search(r"\{.*\}", raw or "", re.DOTALL)
    try:
        scope = json.loads(match.group(0)).get("scope") if match else ""
    except (json.JSONDecodeError, AttributeError):
        return ""
    return scope if scope in SCOPES else ""


def judge_news(item: TrackingItem, news: list[Candidate], call, prompt: str, max_text: int = autolabel.MAX_TEXT,
               seed: int = 7) -> Relevance:
    """뉴스 후보(이미 최소 유사도를 넘은 것)를 한 번에 판정한다."""
    if not news:
        return Relevance()
    order = list(news)
    random.Random(f"{seed}:{item.item_id}").shuffle(order)
    cands = [{"cid": f"C{k + 1}", "kind": "news_chunks" if c.doc == "chunk" else "news", "date": c.date,
              "title": c.title, "text": c.text} for k, c in enumerate(order)]
    meta = {"symbol": item.symbol, "description": item.description, "memo": item.memo_text}
    try:
        raw = call(autolabel.build_prompt(meta, cands, max_text=max_text, prompt=prompt))
    except CreditsExhausted:
        raise
    except Exception as exc:
        return Relevance(judged=len(order), failed=f"call_failed:{type(exc).__name__}")
    labels = autolabel.parse_labels(raw, [c["cid"] for c in cands])
    if labels is None:
        return Relevance(judged=len(order), failed="parse_failed")
    codes = autolabel.parse_codes(raw)
    out = {}
    for k, c in enumerate(order):
        cid = f"C{k + 1}"
        out[c.ref] = (labels[cid], codes.get(cid, ""))
    return Relevance(parse_scope(raw), out, len(order))


def filter_candidates(item: TrackingItem, cands: list[Candidate], floor: dict[str, float], call, rcfg: dict,
                      prompt: str) -> tuple[list[Candidate], Relevance, str | None]:
    """(카드 생성에 넘길 후보, 판정 결과, 멈출 이유). 멈출 이유: no_relevant_candidates | relevance_failed | None.
    공시는 그대로, 뉴스는 최소 유사도를 넘고 판정이 O인 것만 남긴다."""
    limit = lambda c: floor.get(threshold_key(c), floor[c.kind])
    over = [c for c in cands if c.kind == "news" and c.similarity >= limit(c)]
    below = sum(1 for c in cands if c.kind == "news" and c.similarity < limit(c))
    if not over:
        return list(cands), Relevance(below_floor=below), None             # 판정할 뉴스가 없다 (공시·임계값 아래 뉴스는 그대로)
    rel = judge_news(item, over, call, prompt, rcfg.get("max_text", autolabel.MAX_TEXT), rcfg.get("seed", 7))
    rel.below_floor = below
    if rel.failed:
        return [], rel, "relevance_failed"
    kept = [c for c in cands if c.kind != "news" or rel.labels.get(c.ref, (False, ""))[0]]
    usable = [c for c in kept if c.similarity >= limit(c)]
    return kept, rel, (None if usable else "no_relevant_candidates")


def estimate(run_dir, floor: dict[str, float], prompt: str, max_text: int = autolabel.MAX_TEXT,
             model: str = "gpt-6.1-sol") -> dict:
    """LLM 없이 돈 실행(--llm none)의 candidates.csv로 판정 호출 수·토큰·비용을 어림한다 (relevance_compare와 같은 계수)."""
    from pathlib import Path

    from .relevance_compare import OUTPUT_TOKENS_PER_CAND, PRICES, TOKENS_PER_CHAR, read_csv

    rows = read_csv(Path(run_dir) / "candidates.csv")
    key = {"news": "news", "news_chunks": "news_chunks"}
    by_item: dict[str, list[dict]] = {}
    for r in rows:
        k = key.get(r["종류"])
        if k and float(r["유사도"]) >= floor.get(k, floor["news"]):
            by_item.setdefault(r["item_id"], []).append(r)
    chars = 0
    for rs in by_item.values():
        cands = [{"cid": f"C{i + 1}", "kind": r["종류"], "date": r["날짜"], "title": r["제목"], "text": r["내용(앞부분)"]}
                 for i, r in enumerate(rs)]
        chars += len(autolabel.build_prompt({"symbol": rs[0]["symbol"], "description": rs[0]["항목"],
                                             "memo": rs[0]["메모 문장"]}, cands, max_text=max_text, prompt=prompt))
    n = sum(len(v) for v in by_item.values())
    tin, tout = int(chars * TOKENS_PER_CHAR), OUTPUT_TOKENS_PER_CAND * n
    pin, pout = PRICES.get(model, (None, None))
    return {"calls": len(by_item), "candidates": n, "input_tokens": tin, "output_tokens": tout,
            "usd": None if pin is None else round(tin * pin / 1e6 + tout * pout / 1e6, 4)}


def main(argv: list[str] | None = None) -> int:
    import argparse

    from ..common.config import load_config
    from .topic import thresholds

    ap = argparse.ArgumentParser(description="관련성 판정 비용 어림 (LLM·DB 없음)")
    ap.add_argument("--estimate", required=True, help="--llm none으로 돈 experiment 실행 폴더")
    ap.add_argument("--config", default="configs/updates.yaml")
    args = ap.parse_args(argv)
    cfg = load_config(args.config)
    rcfg = config(cfg.get("relevance"))
    floor, _ = thresholds(cfg["topic"])
    print(json.dumps(estimate(args.estimate, floor, autolabel.load_prompt(rcfg["prompt"]), rcfg["max_text"],
                              rcfg.get("model") or "gpt-6.1-sol"), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
