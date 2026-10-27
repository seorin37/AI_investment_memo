"""4) 결과 보고 — 생성한 메모를 사람이 검수하기 쉽게 정리한다.

    python -m eval.memo_personas.report

- review.md: 유형·근거·기업·길이 분포, 무작위 3명×10개 전체, B/C 문항 10개, 메모↔근거 예시 5개, 실패 목록, Gemini 토큰 사용량
- summary.txt: 카톡으로 보내기 쉬운 20줄 요약
"""

from __future__ import annotations

import random
import sys
from collections import Counter

from .common import COMPANIES, FAIL, OK, load_config, read_json, read_jsonl, rpath, say, setup_console, write_text
from .llm import MOCK_MODEL
from .slots import SENTENCE_LABEL

LENGTH_BINS = [(15, "~15자"), (30, "16~30자"), (60, "31~60자"), (10**9, "61자 이상")]


def length_bin(text: str) -> str:
    return next(label for limit, label in LENGTH_BINS if len(text) <= limit)


def table(counter: Counter, header: str, order=None, total=None) -> list[str]:
    total = total or sum(counter.values()) or 1
    keys = order or [k for k, _ in counter.most_common()]
    rows = [f"| {header} | 개수 | 비율 |", "|---|---|---|"]
    rows += [f"| {k} | {counter.get(k, 0)} | {counter.get(k, 0) / total:.1%} |" for k in keys]
    return rows


def memo_line(m: dict) -> str:
    text = m["memo_text"].replace("|", "\\|")
    raw = "" if m["memo_text"] == m["memo_text_raw"] else f" (원문: {m['memo_text_raw']})"
    return (f"| {m['slot']} | {m['target_company']} | {m['sentence_type']} {SENTENCE_LABEL.get(m['sentence_type'], '')} | "
            f"{m['evidence_type']} | {m['answerability']} | {text}{raw} |")


def build(cfg: dict) -> tuple[str, str] | None:
    d = rpath(cfg["paths"]["memos_dir"])
    memos = read_jsonl(d / "memos.jsonl")
    if not memos:
        return None
    failed = read_jsonl(d / "failed.jsonl")
    usage = read_jsonl(d / "usage.jsonl")
    design = read_json(d / "slot_design.json")
    persons = {f.stem: read_json(f) for f in (d / "persons").glob("*.json")}
    ev_dir = rpath(cfg["paths"]["evidence_dir"])
    items = {}
    for f in ev_dir.glob("*.json"):
        items.update({i["key"]: i for i in read_json(f).get("items", [])})
    slot_keys = {(p["persona_id"], s["slot"]): s["evidence_keys"] for p in design["persons"] for s in p["slots"]}
    people = sorted({m["persona_id"] for m in memos})
    models = Counter(m["generator_model"] for m in memos)
    rng = random.Random(cfg["generation"]["seed"])

    st = Counter(m["sentence_type"] for m in memos)
    et = Counter(m["evidence_type"] for m in memos)
    an = Counter(m["answerability"] for m in memos)
    assigned = Counter(m["target_company"] for m in memos)
    mentioned = Counter(c for m in memos for c in m["companies_mentioned"])
    ln = Counter(length_bin(m["memo_text_raw"]) for m in memos)
    dec = Counter(m["expected_decision_draft"] for m in memos)
    track = [m for m in memos if m["sentence_type"].startswith("A")]
    comp_share = sum(m["evidence_type"] == "복합" for m in track) / max(len(track), 1)
    ins_share = sum(m["answerability"] == "자료 부족" for m in track) / max(len(track), 1)
    typo_n = sum(m["memo_text"] != m["memo_text_raw"] for m in memos)
    flags = [f for p in persons.values() for f in p.get("flags", [])]
    regen = Counter(p["attempts"] for p in persons.values() if p["status"] == "done")
    tok = {k: sum(u[k] for u in usage) for k in ("prompt_tokens", "output_tokens", "thinking_tokens", "total_tokens")}
    is_mock = MOCK_MODEL in models

    L = ["# 메모 생성 결과 검수", ""]
    if is_mock:
        L += ["> ⚠️ 목업(mock-gemini)으로 만든 결과입니다. 실제 Gemini 결과가 아니므로 평가에 쓰지 않습니다.", ""]
    L += [f"- 메모 {len(memos)}개 · 완료 {len(people)}명 · 실패 {len(failed)}명 · 모델 {', '.join(models)}",
          f"- 추적형(A) {len(track)}개 중 복합 근거 {comp_share:.1%}, 자료 부족 {ins_share:.1%}",
          f"- 오타 후처리 적용 {typo_n}개 (원문은 memo_text_raw) · 유사 메모 표시 {len(flags)}쌍 · "
          f"재생성: " + ", ".join(f"{k}회 시도 {v}명" for k, v in sorted(regen.items())),
          "- expected_decision_draft는 초안이며 정답이 아닙니다. review_status는 모두 pending입니다.", ""]
    L += ["## 문장 유형", ""] + table(st, "유형", sorted(st, key=lambda k: (k[0], int(k[1:])))) + [""]
    L += ["## 근거 유형", ""] + table(et, "근거") + ["", "## 답할 수 있는지(answerability)", ""] + table(an, "구분") + [""]
    L += ["## 기업 (배정 vs 실제 언급)", "", "| 기업 | 배정 슬롯 | 메모에서 언급 |", "|---|---|---|"]
    L += [f"| {c} | {assigned.get(c, 0)} | {mentioned.get(c, 0)} |" for c in COMPANIES]
    others = {c: n for c, n in mentioned.items() if c not in COMPANIES}
    L += [f"| 그 밖의 종목 | - | {sum(others.values())} ({', '.join(f'{c} {n}' for c, n in Counter(others).most_common(6))}) |", ""]
    L += ["## 길이 (원문 글자 수)", ""] + table(ln, "길이", [b for _, b in LENGTH_BINS]) + [""]
    L += ["## 판정 초안(expected_decision_draft)", ""] + table(dec, "초안") + [""]

    L += ["## 무작위 3명 × 10개", ""]
    for pid in sorted(rng.sample(people, min(3, len(people)))):
        L += [f"### {pid}", "", "| 슬롯 | 기업 | 유형 | 근거 | 답 | 메모 |", "|---|---|---|---|---|---|"]
        L += [memo_line(m) for m in memos if m["persona_id"] == pid] + [""]
    bc = [m for m in memos if m["sentence_type"][0] in "BC"]
    L += ["## B/C 문항 10개", "", "| 슬롯 | 기업 | 유형 | 근거 | 답 | 메모 |", "|---|---|---|---|---|---|"]
    L += [memo_line(m) for m in sorted(rng.sample(bc, min(10, len(bc))), key=lambda m: m["memo_id"])] + [""]
    L += ["## 메모 ↔ 근거 예시 5개", ""]
    with_ev = [m for m in track if m["evidence_ids"]]
    for m in sorted(rng.sample(with_ev, min(5, len(with_ev))), key=lambda m: m["memo_id"]):
        L += [f"**{m['memo_id']}** ({m['target_company']}, {m['sentence_type']}, {m['evidence_type']}, 계기: {m['trigger']})", "",
              f"> {m['memo_text_raw']}", ""]
        for k in slot_keys.get((m["persona_id"], m["slot"]), []):
            if k in items:
                L.append(f"- 근거 `{items[k]['type']}`: {items[k]['text'][:220]}  \n  ID: {', '.join(items[k]['ids'])}")
        L.append("")
    L += ["## 유사 메모 표시 (삭제하지 않음)", ""] + ([f"- {f}" for f in flags] or ["- 없음"]) + [""]
    L += ["## 실패 목록", ""]
    L += [f"- {f['persona_id']} (시도 {f['attempts']}회): " + "; ".join(f["problems"][:3]) for f in failed] or ["- 없음"]
    L += ["", "## Gemini 토큰 사용량", "",
          f"- 호출 {len(usage)}회 · 입력 {tok['prompt_tokens']:,} · 출력 {tok['output_tokens']:,} · thinking {tok['thinking_tokens']:,}"
          f" · 합계 {tok['total_tokens']:,}",
          f"- 완료한 사람 1명당 평균 합계 {tok['total_tokens'] / max(len(people), 1):,.0f} 토큰", ""]
    review = "\n".join(L) + "\n"

    ex = [m for m in memos if m["sentence_type"][0] == "A"][:1] + bc[:1]
    S = [f"[메모 생성 결과] {'⚠️목업 ' if is_mock else ''}모델 {', '.join(models)}",
         f"완료 {len(people)}명 / 메모 {len(memos)}개 / 실패 {len(failed)}명",
         f"추적형 {len(track)} · 폴백·혼합 {len(memos) - len(track)}",
         f"복합 근거 {comp_share:.0%} · 자료 부족 {ins_share:.0%} (추적형 기준)",
         "유형: " + " ".join(f"{k} {st[k]}" for k in sorted(st, key=lambda k: (k[0], int(k[1:])))[:10]),
         "유형(계속): " + " ".join(f"{k} {st[k]}" for k in sorted(st, key=lambda k: (k[0], int(k[1:])))[10:]),
         "근거: " + " ".join(f"{k} {v}" for k, v in et.most_common()),
         "기업 배정: " + " ".join(f"{c} {assigned.get(c, 0)}" for c in COMPANIES),
         "기업 언급: " + " ".join(f"{c} {mentioned.get(c, 0)}" for c in COMPANIES),
         "길이: " + " ".join(f"{b} {ln.get(b, 0)}" for _, b in LENGTH_BINS),
         f"오타 적용 {typo_n}개 · 유사 표시 {len(flags)}쌍",
         "재생성: " + ", ".join(f"{k}회 {v}명" for k, v in sorted(regen.items())),
         f"토큰 합계 {tok['total_tokens']:,} (입력 {tok['prompt_tokens']:,} / 출력 {tok['output_tokens']:,} / thinking {tok['thinking_tokens']:,})",
         f"호출 {len(usage)}회",
         "실패: " + (", ".join(f["persona_id"] for f in failed) or "없음")]
    S += [f"예시 {m['memo_id']} {m['sentence_type']}: {m['memo_text'][:60]}" for m in ex]
    S += [f"자세히: {d.name}/review.md"]
    return review, "\n".join(S[:20]) + "\n"


def main(argv=None) -> int:
    setup_console()
    cfg = load_config()
    d = rpath(cfg["paths"]["memos_dir"])
    if not (d / "slot_design.json").exists():
        say(FAIL, "생성 결과가 없습니다", fix="python -m eval.memo_personas.generate_memos --pilot 을 먼저 실행하세요.")
        return 1
    out = build(cfg)
    if out is None:
        say(FAIL, "완료한 메모가 없습니다", fix="generate_memos 출력과 failed.jsonl을 확인하세요.")
        return 1
    review, summary = out
    write_text(d / "review.md", review)
    write_text(d / "summary.txt", summary)
    say(OK, "보고서 저장", f"{d}/review.md, summary.txt")
    print("\n" + summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
