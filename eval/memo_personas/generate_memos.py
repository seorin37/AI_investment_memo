"""3) 메모 생성 — 1명당 OpenAI 1회 호출로 메모 10개. 사람 단위로 저장해서 끊겨도 같은 명령으로 이어서 한다.

    python -m eval.memo_personas.generate_memos --pilot   # 파일럿 10명(100개) 만들고 멈춤
    python -m eval.memo_personas.generate_memos --all     # 나머지 전부 (완료한 사람은 건너뜀)

- 슬롯(기업·문장 유형·근거·계기)은 코드가 먼저 정한다(slots.py). 설계는 slot_design.json에 저장해 재실행 때 그대로 쓴다.
- 자동 검사(checks.py)에 걸리면 그 사람만 최대 2번 다시 만들고, 그래도 안 되면 failed.jsonl에 남기고 다음 사람으로 넘어간다.
- 429(분당 한도)는 기다렸다 재시도, 일일 한도에 닿으면 "내일 같은 명령을 다시 실행"을 안내하고 멈춘다.
- usage(입력·출력·thinking(reasoning) 토큰)는 호출마다 usage.jsonl에 남긴다.
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime

from . import checks, typo
from .common import (FAIL, OK, WARN, append_jsonl, company_codes, load_config, load_env, load_personas, read_json,
                     rpath, say, setup_console, sha256_file, write_json, write_jsonl)
from .llm import MEMO_SCHEMA, APIError, BadResponse, DailyQuotaExceeded, RateLimited, make_client, parse_json
from .prompt import build_prompt
from .slots import build_design

EXIT_PAUSED = 2


class RequestBudget:
    """분당·일일 요청 한도. 일일 횟수는 파일에 남겨 재실행해도 이어서 센다(PC 날짜 기준)."""

    def __init__(self, path, rpm: float, rpd: int, clock=time.time, sleep=time.sleep):
        self.path, self.rpm, self.rpd, self.clock, self.sleep = path, rpm, rpd, clock, sleep
        self.state = read_json(path) if path.exists() else {}

    def take(self) -> None:
        today = datetime.now().strftime("%Y-%m-%d")
        if self.state.get("date") != today:
            self.state = {"date": today, "count": 0, "last": 0.0}
        if self.state["count"] >= self.rpd:
            raise DailyQuotaExceeded(f"설정한 일일 요청 한도(requests_per_day={self.rpd})에 도달")
        wait = self.state["last"] + 60.0 / self.rpm - self.clock()
        if wait > 0:
            self.sleep(wait)
        self.state["count"] += 1
        self.state["last"] = self.clock()
        write_json(self.path, self.state)


def call_with_backoff(client, prompt: str, budget: RequestBudget, llm_cfg: dict, sleep=time.sleep):
    retries, base = llm_cfg["backoff_retries"], llm_cfg["backoff_base_sec"]
    for k in range(retries + 1):
        budget.take()
        try:
            return client.generate(prompt, MEMO_SCHEMA)
        except RateLimited as exc:
            if k == retries:
                raise
            delay = exc.retry_after if exc.retry_after is not None else base * 2 ** k
            print(f"   ⏳ {exc} → {delay:.0f}초 기다렸다 다시 시도 ({k + 1}/{retries})", flush=True)
            sleep(delay)
    raise AssertionError("unreachable")


# ─────────────────────────────────────────────────────────────
# 입력 불러오기
# ─────────────────────────────────────────────────────────────
def load_evidence(cfg: dict):
    d = rpath(cfg["paths"]["evidence_dir"])
    packs = {}
    for name, code in company_codes(cfg).items():
        f = d / f"{code}.json"
        if not f.exists():
            return None, None, f
        packs[name] = read_json(f)
    if not (d / "macro.json").exists():
        return None, None, d / "macro.json"
    return packs, read_json(d / "macro.json"), None


def fingerprint(cfg: dict) -> dict:
    pd_, ed = rpath(cfg["paths"]["personas_dir"]), rpath(cfg["paths"]["evidence_dir"])
    files = [f"{c}.json" for c in company_codes(cfg).values()] + ["macro.json"]
    return {"personas": sha256_file(pd_ / "personas.jsonl")[:16] + sha256_file(pd_ / "slot_plan.csv")[:16],
            "evidence": {f: sha256_file(ed / f)[:16] for f in files},
            "seed": cfg["generation"]["seed"], "mode": "mock" if cfg["llm"].get("mock") else "real"}


def load_or_build_design(cfg, personas, packs, macro, memos_dir):
    path = memos_dir / "slot_design.json"
    fp = fingerprint(cfg)
    persons_dir = memos_dir / "persons"
    started = persons_dir.exists() and any(persons_dir.glob("*.json"))
    if path.exists():
        design = read_json(path)
        if design["fingerprint"] == fp:
            return design
        if started:
            changed = [k for k in ("personas", "evidence", "seed", "mode") if design["fingerprint"].get(k) != fp[k]]
            say(FAIL, "처음 생성할 때와 입력이 달라졌습니다", "바뀐 것: " + ", ".join(changed),
                fix=f"export_evidence를 다시 실행했거나 설정을 바꿨다면, 지금까지 결과와 섞이면 안 됩니다.\n"
                    f"{memos_dir.name} 폴더 이름을 바꿔 보관한 뒤(예: {memos_dir.name}_old) --pilot부터 다시 실행하세요.\n"
                    f"잘 모르겠으면 상규에게 이 화면을 보내 주세요.")
            return None
    design = build_design(personas, packs, macro, cfg)
    design["fingerprint"] = fp
    design["created_at"] = datetime.now().isoformat(timespec="seconds")
    write_json(path, design)
    s = design["summary"]
    say(OK, "슬롯 설계 저장", f"{s['slots']}슬롯 · 추적형 {s['tracking']} · 폴백·혼합 {s['fallback_mixed']} · "
        f"복합 {s['composite_share_of_tracking']:.0%} · 자료 부족 {s['insufficient_share_of_tracking']:.0%}")
    if design["adjustments"]:
        moved = {}
        for a in design["adjustments"]:
            moved[(a["company"], a["from"], a["to"])] = moved.get((a["company"], a["from"], a["to"]), 0) + 1
        for (c, f, t), k in moved.items():
            say(WARN, f"근거 부족으로 배분 조정: {c} {f} → {t} {k}슬롯")
    return design


# ─────────────────────────────────────────────────────────────
# 한 사람 생성
# ─────────────────────────────────────────────────────────────
def to_records(person: dict, dp: dict, data: dict, model: str) -> list[dict]:
    by_slot = {s["slot"]: s for s in dp["slots"]}
    out = []
    for m in data["memos"]:
        s = by_slot.get(m["slot"])
        raw = m["memo_text"].strip()
        out.append({
            "memo_id": f"{person['persona_id']}-{m['slot']:02d}", "persona_id": person["persona_id"], "slot": m["slot"],
            "target_company": s["target_company"] if s else None,
            "companies_mentioned": checks.mentions(raw),
            "sentence_type": s["sentence_type"] if s else None,
            "evidence_type": s["evidence_type"] if s else None,
            "evidence_parts": s["evidence_parts"] if s else [],
            "evidence_ids": s["evidence_ids"] if s else [],
            "as_of_date": s["as_of_date"] if s else None,
            "memo_text": raw, "memo_text_raw": raw,
            "trigger": s["trigger"] if s else None,
            "answerability": s["answerability"] if s else None,
            "expected_decision_draft": s["expected_decision_draft"] if s else None,
            "generator_model": model, "review_status": "pending", "qc_flags": [],
        })
    return sorted(out, key=lambda r: r["slot"])


def generate_person(person, dp, ctx) -> dict:
    cfg, client, budget, memos_dir = ctx["cfg"], ctx["client"], ctx["budget"], ctx["memos_dir"]
    feedback, tries, usage = None, [], []
    for attempt in range(1, cfg["generation"]["regenerate_max"] + 2):
        prompt = build_prompt(person, dp, ctx["items"], feedback)
        try:
            res = call_with_backoff(client, prompt, budget, cfg["llm"])
            u = {"persona_id": person["persona_id"], "attempt": attempt, "model": res.model,
                 "at": datetime.now().isoformat(timespec="seconds"), **res.usage.as_dict()}
            usage.append(u)
            append_jsonl(memos_dir / "usage.jsonl", u)
            data = parse_json(res.text, MEMO_SCHEMA)
        except BadResponse as exc:
            tries.append({"attempt": attempt, "problems": [str(exc)]})
            feedback = [f"응답 형식 오류({exc}). 설명 없이 JSON 하나만, 스키마대로 출력한다."]
            print(f"   ↻ {person['persona_id']} {attempt}차: {exc} → 다시 생성", flush=True)
            continue
        memos = to_records(person, dp, data, res.model)
        problems, flags = checks.check_person(dp, memos, ctx["known_ids"], ctx["items"], ctx["price_ranges"],
                                              cfg["generation"]["similarity_flag"])
        tries.append({"attempt": attempt, "problems": problems})
        if not problems:
            for m in memos:
                m["memo_text"] = typo.inject(m["memo_text_raw"], float(person.get("w_typo_rate") or 0), m["memo_id"])
                m["qc_flags"] = [f for f in flags if f"슬롯 {m['slot']}↔" in f or f"↔{m['slot']} " in f]
            return {"persona_id": person["persona_id"], "status": "done", "attempts": attempt, "tries": tries,
                    "flags": flags, "memos": memos, "usage": usage, "finished_at": datetime.now().isoformat(timespec="seconds")}
        feedback = problems
        print(f"   ↻ {person['persona_id']} {attempt}차 검사 실패 {len(problems)}건 (예: {problems[0]}) → 다시 생성", flush=True)
    return {"persona_id": person["persona_id"], "status": "failed", "attempts": len(tries), "tries": tries,
            "problems": tries[-1]["problems"] if tries else [], "usage": usage,
            "finished_at": datetime.now().isoformat(timespec="seconds")}


def rebuild_outputs(memos_dir, personas) -> dict:
    order = {p["persona_id"]: i for i, p in enumerate(personas)}
    done, failed = [], []
    for f in sorted((memos_dir / "persons").glob("*.json"), key=lambda f: order.get(f.stem, 10**6)):
        r = read_json(f)
        (done if r["status"] == "done" else failed).append(r)
    write_jsonl(memos_dir / "memos.jsonl", [m for r in done for m in r["memos"]])
    write_jsonl(memos_dir / "failed.jsonl", [{"persona_id": r["persona_id"], "attempts": r["attempts"],
                                              "problems": r["problems"], "at": r["finished_at"]} for r in failed])
    return {"done": [r["persona_id"] for r in done], "failed": [r["persona_id"] for r in failed]}


def main(argv=None) -> int:
    setup_console()
    ap = argparse.ArgumentParser(description="페르소나 100명 × 메모 10개 생성 (사람 단위로 이어서 실행)")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--pilot", action="store_true", help="파일럿 10명(100개)만 만들고 멈춤")
    g.add_argument("--all", action="store_true", help="나머지 전부 (완료한 사람은 건너뜀)")
    args = ap.parse_args(argv)

    load_env()
    cfg = load_config()
    memos_dir = rpath(cfg["paths"]["memos_dir"])
    try:
        client = make_client(cfg)
    except APIError as exc:
        say(FAIL, str(exc), fix=exc.guide)
        return 1
    try:
        personas = load_personas(cfg)
    except FileNotFoundError:
        say(FAIL, "페르소나 파일이 없습니다", cfg["paths"]["personas_dir"], fix="git pull로 feature/sanggue-next 브랜치를 받았는지 확인하세요.")
        return 1
    packs, macro, missing = load_evidence(cfg)
    if packs is None:
        say(FAIL, "근거 자료가 없습니다", str(missing.name), fix="python -m eval.memo_personas.export_evidence 를 먼저 실행하세요.")
        return 1
    if any(not p.get("as_of_date") for p in packs.values()):
        say(FAIL, "주가가 없는 기업이 있어 생성할 수 없습니다", fix="export_evidence 결과의 coverage.md를 상규에게 보내 주세요.")
        return 1
    design = load_or_build_design(cfg, personas, packs, macro, memos_dir)
    if design is None:
        return 1

    items = {i["key"]: i for p in packs.values() for i in p["items"]} | {i["key"]: i for i in macro["items"]}
    ctx = {"cfg": cfg, "client": client, "memos_dir": memos_dir, "items": items,
           "known_ids": {x for i in items.values() for x in i["ids"]},
           "price_ranges": {c: (p["price"]["low_52w"]["price"], p["price"]["high_52w"]["price"]) for c, p in packs.items()},
           "budget": RequestBudget(memos_dir / "_state" / "requests.json", cfg["llm"]["requests_per_minute"],
                                   cfg["llm"]["requests_per_day"])}
    by_id = {p["persona_id"]: p for p in personas}
    dps = {d["persona_id"]: d for d in design["persons"]}
    targets = design["pilot"] if args.pilot else [p["persona_id"] for p in personas]
    persons_dir = memos_dir / "persons"
    done_before = {f.stem for f in persons_dir.glob("*.json") if read_json(f)["status"] == "done"} if persons_dir.exists() else set()
    todo = [pid for pid in targets if pid not in done_before]
    label = "파일럿" if args.pilot else "전체"
    print(f"{label} {len(targets)}명 중 완료 {len(targets) - len(todo)}명 · 이번에 할 사람 {len(todo)}명"
          + (" (목업 모드: OpenAI를 부르지 않음)" if cfg["llm"].get("mock") else f" · 모델 {client.model}"))

    code = 0
    try:
        for k, pid in enumerate(todo, 1):
            t0 = time.time()
            rec = generate_person(by_id[pid], dps[pid], ctx)
            write_json(persons_dir / f"{pid}.json", rec)
            tok = sum(u["total_tokens"] for u in rec["usage"])
            mark = OK if rec["status"] == "done" else FAIL
            say(mark, f"[{k}/{len(todo)}] {pid}", f"{'완료' if rec['status'] == 'done' else '실패(failed.jsonl)'} · "
                f"시도 {rec['attempts']}회 · 토큰 {tok:,} · {time.time() - t0:.0f}초")
    except DailyQuotaExceeded as exc:
        say(WARN, str(exc), fix="오늘은 여기까지입니다. 내일 같은 명령을 다시 실행하세요. 완료한 사람은 건너뛰고 이어서 합니다.")
        code = EXIT_PAUSED
    except RateLimited as exc:
        say(WARN, f"{exc} — 여러 번 기다려도 풀리지 않았습니다",
            fix="10분쯤 뒤에 같은 명령을 다시 실행하세요. 완료한 사람은 건너뜁니다.")
        code = EXIT_PAUSED
    except APIError as exc:
        say(FAIL, str(exc), fix=exc.guide)
        code = 1
    except KeyboardInterrupt:
        say(WARN, "중간에 멈췄습니다", fix="같은 명령을 다시 실행하면 완료한 사람은 건너뛰고 이어서 합니다.")
        code = 130
    finally:
        state = rebuild_outputs(memos_dir, personas) if persons_dir.exists() else {"done": [], "failed": []}

    in_target = lambda ids: [x for x in ids if x in set(targets)]  # noqa: E731
    print(f"\n{label}: 완료 {len(in_target(state['done']))}/{len(targets)}명, 실패 {len(in_target(state['failed']))}명 · "
          f"전체 누적 {len(state['done']) * 10}개 메모 → {memos_dir}/memos.jsonl")
    if state["failed"]:
        print("   실패한 사람은 failed.jsonl에 있습니다. 같은 명령을 다시 실행하면 실패한 사람만 다시 시도합니다.")
    if code == 0:
        if args.pilot:
            print("다음 단계: python -m eval.memo_personas.report → summary.txt를 상규에게 카톡으로 보내고 확인받은 뒤 --all 실행")
        else:
            print("다음 단계: python -m eval.memo_personas.report")
    return code


if __name__ == "__main__":
    sys.exit(main())
