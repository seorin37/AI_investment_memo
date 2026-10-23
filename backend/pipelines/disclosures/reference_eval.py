"""사실 그룹 형식 평가기준표(WO-018 정렬판) 로더와 지표 (WO-019).

정답 판정: 질문의 required_fact_groups는 그룹 간 AND. 그룹은 상위 k 안에 그 그룹 valid_evidence_or의
(rcept_no, chunk_index) 중 하나라도 있으면 충족(그룹 안 OR).
- Complete@k     : 모든 그룹을 충족한 질문 비율
- GroupRecall@k  : 질문별 충족 그룹 비율의 평균
- MRR            : 첫 근거 청크(어느 그룹이든) 순위의 역수, 결과(final_k) 안에 없으면 0
"""

from __future__ import annotations

import json
import random
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean

Key = tuple[str, int]
KS = (5, 10)


@dataclass(frozen=True)
class RefQuestion:
    id: str
    symbol: str
    company: str
    query: str
    group_ids: tuple[str, ...]
    groups: tuple[frozenset, ...]
    needs_human_check: bool
    question_type: str
    design_intent: str
    periods: tuple[str, ...] = field(default=())

    @property
    def evidence(self) -> frozenset:
        return frozenset().union(*self.groups) if self.groups else frozenset()


def load_reference(path: Path) -> tuple[list[RefQuestion], list[dict]]:
    """(채점 질문, 제외 질문 요약) — eval_status=scored만 채점한다."""
    scored: list[RefQuestion] = []
    excluded: list[dict] = []
    with Path(path).open(encoding="utf-8-sig") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            try:
                question = _to_question(row)
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"{row.get('id', '?')}: 기준표 행을 읽을 수 없습니다 ({type(exc).__name__}: {exc})") from None
            if question is None:
                excluded.append({"id": row["id"], "reason": row.get("exclude_reason", "")})
            else:
                scored.append(question)
    return scored, excluded


def _to_question(row: dict) -> RefQuestion | None:
    """채점 대상이 아니면 None."""
    if row.get("eval_status") != "scored":
        return None
    groups = tuple(frozenset((e["rcept_no"], int(e["chunk_index"])) for e in g["valid_evidence_or"]) for g in row["required_fact_groups"])
    if not groups or not all(groups):
        raise ValueError("채점 대상인데 근거 없는 사실 그룹이 있습니다.")
    return RefQuestion(
        id=row["id"],
        symbol=row["symbol"],
        company=row.get("company", ""),
        query=row["question_original"],
        group_ids=tuple(g["group_id"] for g in row["required_fact_groups"]),
        groups=groups,
        needs_human_check=bool(row.get("needs_human_check")),
        question_type=row.get("question_type", ""),
        design_intent=row.get("design_intent", ""),
        periods=tuple(sorted({t["period_end"] for t in row.get("target_reports", []) if t.get("period_end")})),
    )


def score_question(ranked: list[Key], question: RefQuestion) -> dict:
    result = {}
    for k in KS:
        top = set(ranked[:k])
        hit = [bool(group & top) for group in question.groups]
        result[f"complete@{k}"] = 1.0 if all(hit) else 0.0
        result[f"group_recall@{k}"] = sum(hit) / len(hit)
    evidence = question.evidence
    result["rr"] = next((1.0 / rank for rank, key in enumerate(ranked, 1) if key in evidence), 0.0)
    return result


METRICS = tuple([f"complete@{k}" for k in KS] + [f"group_recall@{k}" for k in KS] + ["rr"])


def aggregate(rows: list[dict]) -> dict:
    """질문별 지표 → 평균 (rr 평균 = MRR)."""
    if not rows:
        return {"n": 0}
    out = {"n": len(rows)}
    for metric in METRICS:
        out["mrr" if metric == "rr" else metric] = round(mean(r[metric] for r in rows), 4)
    return out


def grouped(rows: list[dict], key: str) -> dict:
    buckets: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        buckets[str(row[key])].append(row)
    return {name: aggregate(items) for name, items in sorted(buckets.items())}


def stratified_split(questions: list[RefQuestion], dev_ratio: float, seed: int) -> tuple[list[str], list[str]]:
    """기업별로 같은 비율이 되게 고정 시드로 dev/test 분할 (질문 id 정렬 후 섞기 → 재현 가능)."""
    if not 0 < dev_ratio < 1:
        raise ValueError("dev 비율은 0과 1 사이여야 합니다.")
    rng = random.Random(seed)
    by_symbol: dict[str, list[str]] = defaultdict(list)
    for q in questions:
        by_symbol[q.symbol].append(q.id)
    dev, test = [], []
    for symbol in sorted(by_symbol):
        ids = sorted(by_symbol[symbol])
        rng.shuffle(ids)
        cut = int(len(ids) * dev_ratio + 0.5)  # 반올림(half up), 2문항 이상이면 dev·test 모두 1개 이상
        if len(ids) >= 2:
            cut = min(max(cut, 1), len(ids) - 1)
        dev.extend(sorted(ids[:cut]))
        test.extend(sorted(ids[cut:]))
    return dev, test


def stratified_limit(questions: list[RefQuestion], limit: int) -> list[RefQuestion]:
    """스모크용: 기업마다 id 순으로 앞에서 고르게 limit개."""
    by_symbol: dict[str, list[RefQuestion]] = defaultdict(list)
    for q in sorted(questions, key=lambda q: q.id):
        by_symbol[q.symbol].append(q)
    picked: list[RefQuestion] = []
    round_index = 0
    while len(picked) < limit and any(round_index < len(v) for v in by_symbol.values()):
        for symbol in sorted(by_symbol):
            if round_index < len(by_symbol[symbol]) and len(picked) < limit:
                picked.append(by_symbol[symbol][round_index])
        round_index += 1
    return picked
