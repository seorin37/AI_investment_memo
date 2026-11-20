"""같은 근거로 카드가 나왔다 안 나왔다 하는지 세기 (2026-11-18 N08 조사, 코드는 바꾸지 않음).

    # 기록만 (LLM 호출 없음): llm_io.jsonl의 카드 호출을 (항목, 메모, 새 근거 블록)으로 묶어 결과가 갈린 묶음을 센다
    PYTHONPATH=backend python -m pipelines.updates.card_repeat_survey <실행 폴더…> [--out 결과.json]
    # 반복: 고른 카드 프롬프트를 글자 하나 안 바꾸고 N번 다시 보낸다 (usage_log에는 쓰지 않고 결과 파일에 비용을 적는다)
    PYTHONPATH=backend python -m pipelines.updates.card_repeat_survey <실행 폴더…> --repeat 5 --pick <키…> --max-usd 0.5 --out 결과.json

- 묶음 키: 항목 ID · 메모 문장 · "# 새 근거" 블록 sha1 앞 10자. 지시문(답변 길이 변형 등)이 달라도 근거가 같으면 한 묶음이다.
- 결과: update / no_update / 파싱 실패. 같은 묶음 안에서 프롬프트 전체 sha1이 같은 호출끼리는 '입력이 완전히 같은' 반복이다.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from .judge import parse_card_v2
from .number_check_compare import _SECTION, parse_memo


def _sha(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]


def status_of(raw: str | None) -> str:
    card = parse_card_v2(raw or "")
    return "parse_fail" if card is None else card.status


def card_calls(run: Path):
    for row in map(json.loads, filter(str.strip, (run / "llm_io.jsonl").read_text(encoding="utf-8").splitlines())):
        if row["stage"] != "card":
            continue
        m = _SECTION.search(row["prompt"])
        yield {"run": f"{run.parent.name}/{run.name}", "item_id": row["item_id"], "model": row.get("model"),
               "memo": parse_memo(row["prompt"]), "evidence_key": _sha(m.group(1)) if m else "",
               "prompt_key": _sha(row["prompt"]), "status": status_of(row.get("response")), "prompt": row["prompt"]}


def group(calls: list[dict]) -> list[dict]:
    by = defaultdict(list)
    for c in calls:
        by[(c["item_id"], c["memo"], c["evidence_key"])].append(c)
    out = []
    for (item, memo, ev), cs in by.items():
        statuses = Counter(c["status"] for c in cs)
        same_prompt = defaultdict(list)
        for c in cs:
            same_prompt[c["prompt_key"]].append(c["status"])
        out.append({"key": f"{item}:{ev}", "item_id": item, "memo": memo, "calls": len(cs), "statuses": dict(statuses),
                    "split": len(statuses) > 1, "prompts": len(same_prompt),
                    "same_prompt_repeats": {k: v for k, v in same_prompt.items() if len(v) > 1},
                    "runs": [f"{c['run']}={c['status']}" for c in cs]})
    return sorted(out, key=lambda g: (not g["split"], -g["calls"], g["key"]))


def _pick(calls: list[dict], spec: str) -> dict:
    """"항목:근거키" → 그 묶음의 첫 호출, "항목:근거키@실행이름앞부분"(예 @B/) → 그 실행의 호출."""
    key, _, run = spec.partition("@")
    return next(c for c in calls if f"{c['item_id']}:{c['evidence_key']}" == key and c["run"].startswith(run))


def repeat(calls: list[dict], specs: list[str], n: int, max_usd: float) -> tuple[list[dict], float]:
    """고른 프롬프트를 그대로 n번 보낸다. 비용이 max_usd를 넘으면 멈춘다."""
    from pipelines.tracking.openai_client import OpenAIClient

    from .usage import usd
    clients: dict[str, OpenAIClient] = {}
    spent, out = 0.0, []
    for spec in specs:
        c = _pick(calls, spec)
        client = clients.setdefault(c["model"], OpenAIClient.from_env(c["model"]))
        res = {"key": spec, "run": c["run"], "recorded": c["status"], "model": c["model"], "temperature_sent": None,
               "statuses": []}
        for _ in range(n):
            if spent >= max_usd:
                res["stopped"] = "max_usd"
                break
            before = len(client.calls)
            try:
                raw = client(c["prompt"])
            except Exception as exc:                    # noqa: BLE001 — 호출 실패도 결과로 남긴다
                raw = None
                res.setdefault("errors", []).append(type(exc).__name__)
            for rec in client.calls[before:]:
                spent += usd(client.model, rec.prompt_tokens or 0, rec.output_tokens or 0) or 0.0
            res["statuses"].append(status_of(raw))
        res["temperature_sent"] = client.temperature    # None이면 모델이 temperature를 받지 않아 빼고 보냈다
        res["counts"] = dict(Counter(res["statuses"]))
        out.append(res)
    return out, round(spent, 6)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="같은 근거 카드 호출의 결과 갈림 세기")
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--repeat", type=int, default=0)
    ap.add_argument("--pick", nargs="*", default=[], help="반복할 묶음 키 (기록 모드 출력의 key)")
    ap.add_argument("--max-usd", type=float, default=0.5)
    ap.add_argument("--out")
    args = ap.parse_args(argv)
    calls = [c for r in map(Path, args.runs) for c in card_calls(r)]
    groups = group(calls)
    report = {"runs": args.runs, "card_calls": len(calls), "groups": len(groups),
              "multi_call_groups": sum(g["calls"] > 1 for g in groups), "split_groups": sum(g["split"] for g in groups),
              "statuses": dict(Counter(c["status"] for c in calls)),
              "groups_detail": [g for g in groups if g["calls"] > 1]}
    if args.repeat:
        report["repeat"], report["repeat_usd"] = repeat(calls, args.pick, args.repeat, args.max_usd)
    text = json.dumps(report, ensure_ascii=False, indent=1)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(text[:6000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
