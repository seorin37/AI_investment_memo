"""전망 근거 규칙(2026-11-18 N08) 지시문으로 지난 카드 입력을 다시 돌리기 (DB 쓰기 없음, usage_log에 쓰지 않음).

    # 비용 어림만 (호출 없음)
    PYTHONPATH=backend python -m pipelines.updates.forecast_rule_rerun <실행 폴더…> --estimate
    # 다시 돌리기: 카드 호출 → 코드 검사(check_card_v2, 운영 설정) → 통과하면 검수 호출. 이어서 N08 묶음 반복
    PYTHONPATH=backend python -m pipelines.updates.forecast_rule_rerun <실행 폴더…> --repeat 2 --max-usd 1.0 --out 결과.json

- 입력: 실행 폴더 llm_io.jsonl의 카드 호출(stage card). 프롬프트의 항목·메모·근거는 그대로 두고 지시문 문장만 바꾼다
  (REWRITES: 고치기 전 문장 → configs/update_judge_prompt_v2*.md·updates.yaml extra_rules의 지금 문장). 변형마다 몇 개가 바뀌었는지 남긴다.
- 형식 재요청: 운영(topic._judge_v2_run)처럼 형식 코드(topic._FORMAT_CODES)만이면 한 번 고쳐 달라고 한다.
- 반복(--repeat N): card_repeat_survey 묶음 중 호출이 2번 이상인 묶음마다 첫 실행(A 변형이 있으면 A) 프롬프트를 바꾼 지시문으로 N번 더.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from pipelines.common.config import load_config, resolve_path

from .card_repeat_survey import card_calls, group
from .checks import _banned_hit, check_card_v2, forecast_subjects, prediction_text
from .judge import parse_card_v2
from .models import Card
from .number_check_compare import parse_evidence
from .usage import usd

_OLD_RULE_LINES = ("- 회사의 전망은 사실처럼 단정하지 않고 \"회사는 ~라고 밝혔어요\"처럼 발화 주체를 표시합니다.\n"
                   "- 증권사·언론의 전망·예상치도 \"KB증권은 ~로 전망했어요\"처럼 출처를 주어로 씁니다. "
                   "주체 없이 \"~로 전망돼요\", \"~로 예상돼요\"라고 쓰지 않습니다.\n"
                   "- 아직 일어나지 않은 일(전망치, 예상치)을 headline이나 facts에서 일어난 일처럼 쓰지 않습니다.\n")
_OLD_EXPLAIN = ("전망·예상은 사실처럼 쓰지 않고, 쓸 때도 말한 사람을 밝힙니다. 전망만 있고 확인된 사실이 없는 근거로는 카드를 만들지 않습니다.\n"
                "- 근거 하나에 확인된 사실과 전망이 섞여 있으면, 확인된 사실(발표된 수치·통계·일어난 일)은 카드에 쓰고 전망은 말한 사람을 "
                "밝혀 전하거나 뺍니다.")
_OLD_EXTRA = ("- 전망·예상·추정을 다룬 기사는 사실 근거로 쓰지 않는다.",
              "- 전망·예상·추정은 사실로 쓰지 않는다. 같은 기사에 확인된 사실(발표된 수치·통계·일어난 일)이 있으면 그 사실은 쓴다.")


def rewrites() -> list[tuple[str, str]]:
    """(고치기 전, 지금) 문장 쌍. 지금 문장은 저장소 파일에서 읽는다."""
    v2 = resolve_path("configs/update_judge_prompt_v2.md").read_text(encoding="utf-8")
    ex = resolve_path("configs/update_judge_prompt_v2_explain.md").read_text(encoding="utf-8")
    block = v2[v2.index("[전망 근거]"):v2.index("\n\n[관련성 판단]")]
    line = lambda text, head: next(l for l in text.splitlines() if l.startswith(head))          # noqa: E731
    alert = line(v2, "- 메모가 새 소식을 계속 알려 달라고 하면")
    topic = load_config("configs/updates.yaml")["topic"]
    extra = next(r for r in topic["extra_rules"] if r.startswith("전망·예상·추정 기사도"))
    reason_max = topic.get("reason_max", 80)
    ex_new = ex[ex.index("전망·예상은 사실처럼 쓰지 않고, 쓸 때도"):ex.index("전망이 섞여 있다는 이유만으로")].rstrip()
    pairs = [("2. 매수·매도 권유, 종목 추천, 가격·실적 예측을 하지 않습니다.", line(v2, "2. 매수·매도 권유")),
             (_OLD_RULE_LINES, ""),
             ("\n\n[관련성 판단]\n", f"\n\n{block}\n\n[관련성 판단]\n"),
             ("- 같은 종목의 자료라도 추적 관심사와 관계없으면 no_update입니다.",
              f"- 같은 종목의 자료라도 추적 관심사와 관계없으면 no_update입니다.\n{alert}"),
             ("사건 한 줄, 평가·전망 표현 금지", line(v2, "- headline:").split("이내, ", 1)[1]),
             ("전망·권유·평가 금지", "스스로 전망하는 말·권유·평가 금지"),
             ("- memo_link: 이 사건이 메모의 어떤 관심사와 연결되는지 한 문장.",
              line(v2, "- memo_link:").split(". ", 1)[0].replace("{reason_max}", str(reason_max)) + "."),
             ("- 예측: 오를 거예요, 상승할 가능성이 높아요, 회복될 전망이에요", line(v2, "- 예측(")),
             ("- 사실을 말하기에 근거가 부족함\n", v2[v2.index("- 사실을 말하기에"):v2.index("- 입력 근거끼리 충돌")]),
             (_OLD_EXPLAIN, ex_new)]
    pairs += [(old, f"- {extra}") for old in _OLD_EXTRA]
    return pairs


def rewrite(prompt: str, pairs) -> tuple[str, list[int]]:
    applied = []
    for i, (old, new) in enumerate(pairs):
        if old in prompt and (i != 2 or "\n[전망 근거]\n" not in prompt):
            prompt = prompt.replace(old, new, 1)
            applied.append(i)
    return prompt, applied


def _field(prompt: str, name: str) -> str:
    m = re.search(rf"^- {name}: (.*)$", prompt, re.M)
    return m.group(1).strip() if m else ""


def judge(client, prompt: str, memo: str, cfg: dict, banned: list[str], verify: bool, spent: list[float]) -> dict:
    """카드 호출 → 코드 검사(형식만 어긋나면 한 번 재요청) → (통과하면) 검수 호출. spent[0]에 비용을 더한다."""
    from .topic import _FORMAT_CODES, _repair_prompt_v2, _verify

    def call(p: str) -> str:
        before = len(client.calls)
        try:
            return client(p)
        finally:
            for rec in client.calls[before:]:
                spent[0] += usd(client.model, rec.prompt_tokens or 0, rec.output_tokens or 0) or 0.0

    raw = call(prompt)
    card = parse_card_v2(raw or "")
    row = {"status": "parse_fail" if card is None else card.status}
    if card is None or card.status != "update":
        return row
    evidence = parse_evidence(prompt)
    explain = bool(card.explanation)
    ccfg = {**cfg, "explanation": {**(cfg.get("explanation") or {}), "enabled": explain}}
    codes = check_card_v2(card, evidence, banned, ccfg, memo)
    # 운영(topic._judge_v2_run)처럼 형식만 어긋나면 한 번 고쳐 달라고 한다
    if codes and ccfg.get("format_retry", 0) and set(codes) <= _FORMAT_CODES:
        row["retried"] = codes
        raw = call(_repair_prompt_v2(prompt, raw, codes, ccfg))
        card2 = parse_card_v2(raw or "")
        if card2 is None or card2.status != "update":
            row["status"] = "parse_fail" if card2 is None else card2.status
            return row
        card = card2
        explain = bool(card.explanation)
        codes = check_card_v2(card, evidence, banned, ccfg, memo)
    # 걸린 문장 표시: check_card_v2와 같게 문장 단위·사실 문장의 전망 주체(names)를 넘긴다
    texts = [card.headline, *(t for t, _ in card.facts), card.memo_link] + (
        [s for s in re.split(r"(?<=[.!?])\s+", card.explanation) if s.strip()] if explain else [])
    names = forecast_subjects(t for t, eid in card.facts if eid)
    row.update(card={"headline": card.headline, "when": card.when, "facts": [list(f) for f in card.facts],
                     "memo_link": card.memo_link, "explanation": card.explanation}, codes=codes,
               prediction=prediction_text(texts, cfg, names) if cfg.get("prediction_terms") else None,
               banned_sentences=[t for t in texts if _banned_hit([t], banned, cfg, names)])
    if verify and not codes:
        facts = [(t, eid) for t, eid in card.facts if eid]
        extra = [s.strip() for s in re.split(r"(?<=[.!?])\s+", card.explanation) if s.strip()] if explain else []
        vcard = Card("update", card.headline, [t for t, _ in facts] + extra, card.memo_link, [(e, t) for t, e in facts],
                     card.confidence)
        vcodes, notes = _verify(vcard, evidence, call, _field(prompt, "종목"), _field(prompt, "항목"))
        row.update(verify=vcodes, verify_notes=notes)
    return row


def reverify(calls: list[dict], prev: Path, max_usd: float, out: str | None) -> int:
    """prev(이전 결과)에서 검수를 받은 카드(verify가 있는 줄)에 지금 VERIFY_INSTRUCTION으로 검수만 다시. 전후 막힌 문장 비교."""
    from pipelines.tracking.openai_client import OpenAIClient

    from .topic import _verify
    by = {(c["run"], c["item_id"]): c for c in calls}
    rows = [r for r in json.loads(prev.read_text(encoding="utf-8"))["rows"] if r.get("verify") is not None]
    spent, results, clients = [0.0], [], {}
    for r in rows:
        if spent[0] >= max_usd:
            break
        c, card = by[(r["run"], r["item_id"])], r["card"]
        client = clients.setdefault(c["model"], OpenAIClient.from_env(c["model"]))

        def call(p: str, client=client) -> str:
            before = len(client.calls)
            try:
                return client(p)
            finally:
                for rec in client.calls[before:]:
                    spent[0] += usd(client.model, rec.prompt_tokens or 0, rec.output_tokens or 0) or 0.0
        facts = [(t, eid) for t, eid in card["facts"] if eid]
        extra = [s.strip() for s in re.split(r"(?<=[.!?])\s+", card.get("explanation") or "") if s.strip()]
        vcard = Card("update", card["headline"], [t for t, _ in facts] + extra, card["memo_link"], [(e, t) for t, e in facts], 0.9)
        codes, notes = _verify(vcard, parse_evidence(c["new_prompt"]), call, _field(c["new_prompt"], "종목"),
                               _field(c["new_prompt"], "항목"))
        results.append({"run": r["run"], "item_id": r["item_id"], "before": r["verify"], "before_notes": r.get("verify_notes"),
                        "after": codes, "after_notes": notes,
                        "new_blocked": [n for n in notes if n not in (r.get("verify_notes") or [])]})
    report = {"cards": len(results), "usd": round(spent[0], 6),
              "blocked_before": sum(bool(x["before"]) for x in results), "blocked_after": sum(bool(x["after"]) for x in results),
              "results": results}
    text = json.dumps(report, ensure_ascii=False, indent=1)
    if out:
        Path(out).write_text(text, encoding="utf-8")
    print(text[:8000])
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="전망 근거 규칙 지시문으로 지난 카드 입력 다시 돌리기")
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--estimate", action="store_true")
    ap.add_argument("--chars-per-token", type=float, default=1.73, help="어림용 (2026-11-18 실행 카드 호출 8회 실측)")
    ap.add_argument("--out-tokens", type=int, default=450, help="어림용 카드 호출당 출력 토큰 (추론 포함, 실측 284에 설명 문단 여유)")
    ap.add_argument("--repeat", type=int, default=0)
    ap.add_argument("--max-usd", type=float, default=1.0)
    ap.add_argument("--only", nargs="*", default=[], help="이 호출만: 실행이름앞부분:항목 (예: C2_all:10 run_20261118:3)")
    ap.add_argument("--reverify", help="이전 결과 JSON: 코드 검사를 통과해 검수를 받은 카드에 지금 검수 지시문으로 검수만 다시 (카드 호출 없음)")
    ap.add_argument("--out")
    args = ap.parse_args(argv)
    pairs = rewrites()
    calls = [c for r in map(Path, args.runs) for c in card_calls(r)]
    if args.only:
        calls = [c for c in calls if any(c["run"].split("/")[0].startswith(o.rsplit(":", 1)[0]) and c["item_id"] == o.rsplit(":", 1)[1]
                                         or c["run"].split("/")[1].startswith(o.rsplit(":", 1)[0]) and c["item_id"] == o.rsplit(":", 1)[1]
                                         for o in args.only)]
    for c in calls:
        c["new_prompt"], c["applied"] = rewrite(c["prompt"], pairs)
    groups = [g for g in group(calls) if g["calls"] > 1]
    applied = Counter((c["run"].split("/")[0], tuple(c["applied"])) for c in calls)
    if args.estimate:
        chars = sum(len(c["new_prompt"]) for c in calls)
        rep_chars = sum(len(next(c for c in calls if f"{c['item_id']}:{c['evidence_key']}" == g["key"])["new_prompt"])
                        for g in groups) * args.repeat
        n = len(calls) + len(groups) * args.repeat
        card_usd = (chars + rep_chars) / args.chars_per_token * 2.0 / 1e6 + n * args.out_tokens * 10.0 / 1e6
        verify_usd = len(calls) * 0.8 * 0.003
        print(json.dumps({"card_calls": len(calls), "repeat_calls": len(groups) * args.repeat, "groups": len(groups),
                          "applied": {f"{k[0]} {list(k[1])}": v for k, v in applied.items()},
                          "usd_card": round(card_usd, 3), "usd_verify_guess": round(verify_usd, 3),
                          "usd_total_guess": round(card_usd + verify_usd, 3)}, ensure_ascii=False, indent=1))
        return 0

    from pipelines.tracking.openai_client import OpenAIClient
    if args.reverify:
        return reverify(calls, Path(args.reverify), args.max_usd, args.out)
    real = load_config("configs/updates.yaml")
    cfg, banned = {**real["topic"]}, list(real["banned"])
    clients: dict[str, OpenAIClient] = {}
    spent, rows, stopped = [0.0], [], False
    for c in calls:
        if spent[0] >= args.max_usd:
            stopped = True
            break
        client = clients.setdefault(c["model"], OpenAIClient.from_env(c["model"]))
        r = judge(client, c["new_prompt"], c["memo"], cfg, banned, bool(cfg.get("verify_call")), spent)
        rows.append({"run": c["run"], "item_id": c["item_id"], "key": f"{c['item_id']}:{c['evidence_key']}",
                     "old_status": c["status"], "applied": c["applied"], **r})
    reps = defaultdict(list)
    for g in groups if args.repeat else []:
        pick = [c for c in calls if f"{c['item_id']}:{c['evidence_key']}" == g["key"]]
        c = next((x for x in pick if x["run"].startswith("A/")), pick[0])
        for _ in range(args.repeat):
            if spent[0] >= args.max_usd:
                stopped = True
                break
            r = judge(clients.setdefault(c["model"], OpenAIClient.from_env(c["model"])), c["new_prompt"], c["memo"],
                      cfg, banned, False, spent)
            reps[g["key"]].append({"run": c["run"], "status": r["status"]})
    summary = {"card_calls": len(rows), "stopped_max_usd": stopped, "usd": round(spent[0], 6),
               "old": dict(Counter(r["old_status"] for r in rows)), "new": dict(Counter(r["status"] for r in rows)),
               "applied": {f"{k[0]} {list(k[1])}": v for k, v in applied.items()}}
    group_rows = []
    for g in groups:
        mine = [r for r in rows if r["key"] == g["key"]]
        group_rows.append({"key": g["key"], "memo": g["memo"][:60], "old": dict(Counter(r["old_status"] for r in mine)),
                           "new": dict(Counter(r["status"] for r in mine)),
                           "new_repeat_same_prompt": [x["status"] for x in reps.get(g["key"], [])],
                           "old_split": len({r["old_status"] for r in mine}) > 1,
                           "new_split": len({r["status"] for r in mine}) > 1})
    out = {"summary": summary, "groups": group_rows, "rows": rows}
    text = json.dumps(out, ensure_ascii=False, indent=1)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(json.dumps({"summary": summary, "groups": group_rows}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
