"""2~3줄 메모 300개 (100명 × 3) — 기존 짧은 메모 1,000개(memos_direct)는 그대로 두고 따로 만든다.

팀 요청: 페르소나 메모가 너무 짧아서, 실제로 쓸 법한 두세 줄짜리도 필요하다. 쓰는 사람은 여전히 Claude Code(직접 작성).
- design: 사람마다 3개 슬롯(기업·주 유형·계기). 기업은 대표 종목 → 관심 종목 → 4곳 75개씩 맞추기 순으로 고른다.
- brief --batch N / build --batch N / summary / typo: direct.py와 같은 흐름. 배치 구성(10명씩, 파일럿 먼저)도 direct 설계를 따른다.
- 검사는 direct.py 기준을 그대로 쓰고 길이만 바꾼다: 2~3줄, 짧게 쓰는 사람 35~120자, 나머지 50~220자.

실행: PYTHONPATH=backend python -m eval.memo_personas.long design | brief --batch 1 | build --batch 1 | summary | typo
"""

from __future__ import annotations

import argparse
import collections
import difflib
import random
import re
import sys
from pathlib import Path

from .checks import mentions, similar_pairs, style_problems
from .common import (COMPANIES, OK, WARN, FAIL, load_config, load_personas, read_json, rpath, setup_console,
                     write_json, write_jsonl, write_text)
from .direct import (ALIAS_MAX, ALL_TYPES, BASIC_TERMS, DECISIONS, ENDINGS, EXPERT_TERMS, PRICE_TYPES, RELATIVE_PRICE,
                     abs_prices, aliases_used, ending_of, expected, find_terms, price_basis, read_json_lines,
                     repeated_phrases, segment_warnings, table, term_tier)
from .direct import OUT_DIR as DIRECT_DIR
from .prompt import first_sentences

OUT_DIR = "results/memo_personas/memos_long"
GENERATOR = "claude-code-direct"
SLOTS = 3
# 주 유형 300개: A 210 (5종 × 42), C 50 (5종 × 10), B 40 (길게 쓸 만한 4종 × 10). B5·B7·B10은 두세 줄로 쓸 일이 없어 뺀다
TYPE_POOL = {**{t: 42 for t in ("A1", "A2", "A3", "A4", "A5")}, **{t: 10 for t in ("C1", "C2", "C3", "C4", "C5")},
             **{t: 10 for t in ("B2", "B3", "B8", "B9")}}
TRIGGERS = {"A1": ["뉴스 보고", "기사 보고", "지인 얘기 듣고", "유튜브 보고"], "A2": ["차트 보다가", "주가 알림 보고"],
            "A3": ["공시 알림 보고", "일정 보다가"], "A4": ["뉴스 보고", "커뮤니티 글 보고", "지인 얘기 듣고"],
            "A5": ["실적 기사 보고", "뉴스 보고"], "C1": ["차트 보다가", "계좌 보다가"], "C2": ["뉴스 보고", "계좌 보다가"],
            "C3": ["커뮤니티 글 보고", "뉴스 보고"], "C4": ["차트 보다가", "실적 기사 보고"], "C5": ["뉴스 보고", "출근길에"],
            "B2": ["매매하고 나서"], "B3": ["계좌 보다가"], "B8": ["커뮤니티 글 보고"], "B9": ["뉴스 보고"]}
DATA_NEEDS = {"공시", "뉴스", "주가·거래", "재무", "거시", "DB 밖 가능"}
LINES = (2, 3)
CHARS = {"짧게": (35, 120), "기타": (50, 220)}
TYPES_MAX = 4
UNVERIFIED_MAX = 3  # 배치 30개당
ENDING_PERSON_MAX, ENDING_BATCH_MAX = 2, 6
SIMILARITY = 0.8  # 같은 사람 안, 그리고 같은 사람의 짧은 메모와
# 비속어: 20대 느낌으로 조금만. 35세 이상은 쓰지 않는다
PROFANITY = re.compile(r"ㅅㅂ|ㅆㅂ|시발|씨발|존나|졸라|ㅈㄴ|개빡|빡치|ㅈ같|좆|병신|ㅂㅅ|미친|지랄|염병|개같|개털|개박살|개떡")
PROFANITY_AGE_MAX = 34


def make_design(cfg: dict) -> dict:
    people = load_personas(cfg)
    rng = random.Random(f"{cfg['generation']['seed']}:long")
    pool = [t for t, n in TYPE_POOL.items() for _ in range(n)]
    rng.shuffle(pool)
    count = collections.Counter()
    persons = {}
    for p in sorted(people, key=lambda x: x["persona_id"]):
        interest = [c for c in (p.get("interest_statuses") or {}) if c != p["primary_company"]]
        picks = [p["primary_company"], interest[0] if interest else p["primary_company"]]
        # 세 번째는 4곳 75개씩 맞추기: 덜 쓴 기업 중 관심 종목을 먼저
        third = min(COMPANIES, key=lambda c: (count[c] + picks.count(c), c not in interest + [p["primary_company"]], c))
        picks.append(third)
        out = []
        for i, c in enumerate(picks, 1):
            count[c] += 1
            t = pool.pop()
            status = "보유" if c == p["primary_company"] and p["primary_status"] == "보유" else \
                (p.get("interest_statuses") or {}).get(c, p["primary_status"] if c == p["primary_company"] else "모름")
            rec = {"slot": i, "company": c, "status": status, "primary_type": t, "trigger": rng.choice(TRIGGERS[t])}
            if t == "C3":
                rec["other_company"] = rng.choice([x for x in COMPANIES if x != c])
            out.append(rec)
        persons[p["persona_id"]] = out
    batches = read_json(rpath(DIRECT_DIR) / "design.json")["batches"]
    return {"seed": cfg["generation"]["seed"], "batches": batches, "persons": persons, "type_pool": TYPE_POOL,
            "companies": dict(count), "source": "long.make_design — 배치는 memos_direct 설계와 같음"}


def brief(design: dict, batch: int, cfg: dict) -> str:
    people = {p["persona_id"]: p for p in load_personas(cfg)}
    short = {r["memo_id"]: r["memo_body_clean"] for r in read_json_lines(rpath(DIRECT_DIR) / "memos.jsonl")}
    lines = []
    for pid in design["batches"][batch - 1]:
        p = people[pid]
        nem = p.get("nemotron") or {}
        lines += [f"## {pid} · {p['age']}세 {p['sex']} · {p['province_full']} · {p['occupation']}"
                  f"{'(' + p['unemployed_type'] + ')' if p.get('unemployed_type') else ''} · {p['family_type']}",
                  f"- 경력 {p['experience_years']}년({term_tier(p)}) · {p['invest_style']} · {p['risk_profile']} · "
                  f"{p['investment_horizon']} · 목적 {p['fund_purpose']} · 정보 {p['info_source']}",
                  f"- 관심 공부: {', '.join(p['learning_interest'])} · 관심 종목 {p.get('interest_statuses')}",
                  f"- 말투: 반말 {p['w_banmal']} · ㅋㅋ {p['w_laugh']} · 말줄임표 {p['w_ellipsis']} · 길이 {p['w_length']}",
                  f"- 서술: {first_sentences(nem.get('persona'), 2)}",
                  f"- 일: {first_sentences(nem.get('professional_persona'), 1)}",
                  f"- 취미: {first_sentences(nem.get('hobbies_and_interests'), 1)}",
                  "- 짧은 메모 예: " + " | ".join(short.get(f"{pid}-{i:02d}", "") for i in (1, 4, 7))]
        for s in design["persons"][pid]:
            lines.append(f"  {s['slot']}. {s['company']}({s['status']}) {s['primary_type']} · 계기 {s['trigger']}"
                         f"{' · 다른:' + s['other_company'] if s.get('other_company') else ''}")
        lines.append("")
    return "\n".join(lines)


def assemble(design: dict, batch: int, draft: dict, prices: dict) -> list[dict]:
    rows = []
    for pid in design["batches"][batch - 1]:
        for d in draft.get(pid, []):
            s = next(x for x in design["persons"][pid] if x["slot"] == d["slot"])
            # lines: 줄마다 [문장, 유형, (판정 덮어쓰기)] 목록. 줄 안 문장은 공백으로 잇는다
            sents, body_lines = [], []
            for line in d["lines"]:
                body_lines.append(" ".join(x[0] for x in line))
                sents += [{"text": x[0], "intended_type": x[1], "expected_decision": expected(x[1], x[2] if len(x) > 2 else None)}
                          for x in line]
            body = "\n".join(body_lines)
            need = list(d.get("need", []))
            if any(x["intended_type"] in ("A2", "C1") for x in sents) and "주가·거래" not in need:
                need.append("주가·거래")
            rows.append({
                "memo_id": f"{pid}-L{d['slot']}", "persona_id": pid, "slot": d["slot"], "batch": batch,
                "company_primary": s["company"], "companies_mentioned": mentions(body),
                "primary_type": s["primary_type"], "mixed": len({x["intended_type"] for x in sents}) > 1,
                "memo_title": "", "memo_body": body, "memo_body_clean": body, "sentences": sents,
                "trigger": d.get("trigger", s["trigger"]), "data_need": need,
                "price_basis": price_basis(sents, prices), "topic_unverified": bool(d.get("unv")),
                "generator": GENERATOR, "review_status": "pending",
            })
    return rows


def check_batch(design: dict, batch: int, rows: list[dict], earlier: list[dict], prices: dict, people: dict,
                short_memos: dict, lex=None) -> dict:
    fails, warns, terms = [], [], []
    unv = sum(r["topic_unverified"] for r in rows)
    if unv > UNVERIFIED_MAX:
        fails.append(f"배치: 들은 소식(topic_unverified) {unv}개 > {UNVERIFIED_MAX}")
    batch_endings = collections.Counter(e for r in rows for x in r["sentences"] if (e := ending_of(x["text"])))
    fails += [f"배치: '{k}' 끝맺음 {v}회 > {ENDING_BATCH_MAX}" for k, v in batch_endings.items() if v > ENDING_BATCH_MAX]
    by_person = collections.defaultdict(list)
    for r in rows:
        by_person[r["persona_id"]].append(r)
    for pid in design["batches"][batch - 1]:
        want = {s["slot"]: s for s in design["persons"][pid]}
        got = {r["slot"]: r for r in by_person.get(pid, [])}
        if set(got) != set(want):
            fails.append(f"{pid}: 슬롯 불일치 받은 {sorted(got)} / 배정 {sorted(want)}")
        p = people[pid]
        lo, hi = CHARS["짧게" if p["w_length"] == "짧게" else "기타"]
        endings = collections.Counter(e for r in got.values() for x in r["sentences"] if (e := ending_of(x["text"])))
        fails += [f"{pid}: '{k}' 끝맺음 {v}회 > {ENDING_PERSON_MAX}" for k, v in endings.items() if v > ENDING_PERSON_MAX]
        alias_counts = collections.Counter(a for r in got.values() for a in aliases_used(r["memo_body_clean"]))
        fails += [f"{pid}: 별명 '{a}' 메모 {c}개 > {ALIAS_MAX}" for a, c in alias_counts.items() if c > ALIAS_MAX]
        all_text = " ".join(r["memo_body_clean"] for r in got.values())
        tier, expert, basic = term_tier(p), find_terms(all_text, EXPERT_TERMS), find_terms(all_text, BASIC_TERMS)
        terms.append({"persona_id": pid, "experience_years": p["experience_years"], "occupation": p["occupation"],
                      "tier": tier, "expert": expert, "basic": basic})
        if tier != "전문" and expert:
            fails.append(f"{pid}({tier}·경력 {p['experience_years']}년): 전문용어 {expert}")
        for slot, r in sorted(got.items()):
            s = want[slot]
            tag = f"{r['memo_id']}({s['primary_type']})"
            types = [x["intended_type"] for x in r["sentences"]]
            body = r["memo_body_clean"]
            n_lines = body.count("\n") + 1
            if not LINES[0] <= n_lines <= LINES[1]:
                fails.append(f"{tag}: {n_lines}줄 (2~3줄)")
            if not lo <= len(body) <= hi:
                fails.append(f"{tag}: {len(body)}자 ({lo}~{hi}자, 길이 {p['w_length']})")
            if len(types) < 2:
                fails.append(f"{tag}: 문장 {len(types)}개 < 2")
            if any(t not in ALL_TYPES for t in types):
                fails.append(f"{tag}: 알 수 없는 유형 {types}")
            if any(x["expected_decision"] not in DECISIONS for x in r["sentences"]):
                fails.append(f"{tag}: 알 수 없는 판정 라벨")
            if s["primary_type"] not in types:
                fails.append(f"{tag}: 주 유형 문장이 없음 {types}")
            if len(set(types)) > TYPES_MAX:
                fails.append(f"{tag}: 유형 {len(set(types))}개 > {TYPES_MAX}")
            if bad := [x for x in r["data_need"] if x not in DATA_NEEDS]:
                fails.append(f"{tag}: 알 수 없는 data_need {bad}")
            if s["company"] not in r["companies_mentioned"]:
                fails.append(f"{tag}: 배정 기업 언급 없음")
            if s.get("other_company") and not any(o != s["company"] for o in r["companies_mentioned"]):
                fails.append(f"{tag}: 다른 종목({s['other_company']}) 언급 없음")
            fails += [f"{tag}: {x}" for x in style_problems(body)]
            if PROFANITY.search(body) and int(p["age"]) > PROFANITY_AGE_MAX:
                fails.append(f"{tag}: {p['age']}세인데 비속어 '{PROFANITY.search(body).group(0)}'")
            for x in r["sentences"]:
                if x["intended_type"] not in PRICE_TYPES:
                    continue
                ref = prices["companies"][r["company_primary"]]
                vals = abs_prices(x["text"])
                for v in vals:
                    if not ref["low_52w"] <= v <= ref["high_52w"]:
                        fails.append(f"{tag}: 가격 {v:,.0f}원이 52주 범위({ref['low_52w']:,}~{ref['high_52w']:,}) 밖")
                if x["intended_type"] in ("A2", "C1") and not vals and RELATIVE_PRICE.search(x["text"]) \
                        and x["expected_decision"] != "확인 필요":
                    fails.append(f"{tag}: 상대 가격 조건인데 라벨이 '{x['expected_decision']}' (v0.2 기준 확인 필요)")
                if x["intended_type"] in ("A2", "C1") and vals and x["expected_decision"] == "확인 필요":
                    fails.append(f"{tag}: 절대 가격 조건인데 라벨이 확인 필요")
            # 짧은 메모를 늘려 쓴 것처럼 보이지 않게: 같은 사람의 짧은 메모 10개와 비교
            for sid, old in short_memos.get(pid, {}).items():
                ratio = difflib.SequenceMatcher(None, body, old).ratio()
                if ratio >= SIMILARITY:
                    fails.append(f"{tag}: 짧은 메모 {sid}와 유사도 {ratio:.2f}")
            if lex is not None:
                warns += segment_warnings(r, lex, tag)
        for a, b, ratio in similar_pairs([{"slot": r["slot"], "memo_text_raw": r["memo_body_clean"]} for r in got.values()],
                                         SIMILARITY):
            fails.append(f"{pid}: 슬롯 {a}·{b} 유사도 {ratio}")
    warns += [f"반복 표현 '{g}' — 이번 배치 {k}회, 다른 배치 {m}회" for g, k, m in repeated_phrases(rows, earlier)]
    return {"fails": fails, "warns": warns, "terms": terms, "endings": batch_endings, "unverified": unv}


def length_bucket(body: str) -> str:
    n = len(body)
    return "~50자" if n <= 50 else ("51~100자" if n <= 100 else ("101~150자" if n <= 150 else "151자~"))


LENGTH_ORDER = ["~50자", "51~100자", "101~150자", "151자~"]


def report(rows: list[dict], result: dict, title: str) -> str:
    sents = [x for r in rows for x in r["sentences"]]
    lines = [f"# {title}", "",
             f"- 메모 {len(rows)}개 · 문장 {len(sents)}개 (메모당 {len(sents) / (len(rows) or 1):.1f}) · "
             f"평균 {sum(len(r['memo_body_clean']) for r in rows) / (len(rows) or 1):.0f}자",
             f"- {OK if not result['fails'] else FAIL} 실패 {len(result['fails'])}건 · {WARN} 참고 {len(result['warns'])}건", ""]
    lines += table("주 유형 (메모 기준)", collections.Counter(r["primary_type"] for r in rows), ALL_TYPES)
    lines += table("문장 유형 (문장 기준)", collections.Counter(x["intended_type"] for x in sents), ALL_TYPES)
    lines += table("기대 판정 (문장 기준)", collections.Counter(x["expected_decision"] for x in sents),
                   ["추적", "일부 추적", "추적 안 함", "확인 필요"])
    lines += table("가격 문장 (A2·C1·C4)", collections.Counter(k for r in rows for k in (r["price_basis"] or {}).get("kinds", [])),
                   ["절대", "상대", "가격 없음"])
    lines += table("배정 기업", collections.Counter(r["company_primary"] for r in rows), COMPANIES)
    lines += table("줄 수", collections.Counter(f"{r['memo_body_clean'].count(chr(10)) + 1}줄" for r in rows), ["2줄", "3줄"])
    lines += table("본문 길이", collections.Counter(length_bucket(r["memo_body_clean"]) for r in rows), LENGTH_ORDER)
    lines += table("끝맺음 (알림·보자·볼 것·지켜보기·확인)", result["endings"], list(ENDINGS))
    lines += [f"- 들은 소식(topic_unverified): {result['unverified']}개",
              f"- 비속어 섞인 메모: {sum(bool(PROFANITY.search(r['memo_body_clean'])) for r in rows)}개 ({PROFANITY_AGE_MAX}세 이하만)", "",
              "### 페르소나별 용어", "", "| 페르소나 | 경력 | 직업 | 수준 | 전문용어 | 기본 용어 |", "|---|---:|---|---|---:|---:|"]
    lines += [f"| {t['persona_id']} | {t['experience_years']}년 | {t['occupation']} | {t['tier']} | "
              f"{len(t['expert'])} {'(' + ', '.join(t['expert']) + ')' if t['expert'] else ''} | {len(t['basic'])} |"
              for t in result["terms"]]
    lines += ["", "## 실패", ""] + [f"- {x}" for x in result["fails"]] + ["", "## 참고", ""] + [f"- {x}" for x in result["warns"]]
    return "\n".join(lines) + "\n"


def short_by_person() -> dict:
    out = collections.defaultdict(dict)
    for r in read_json_lines(rpath(DIRECT_DIR) / "memos.jsonl"):
        out[r["persona_id"]][r["memo_id"]] = r["memo_body_clean"]
    return out


def load_lex():
    try:
        from pipelines.tracking.lexicon import load_lexicon
        return load_lexicon()
    except Exception as exc:  # 판정 파이프라인을 못 불러와도 기본 검사는 한다
        print(f"{WARN} 문장 분리 대조 생략: {type(exc).__name__}")
        return None


def main(argv=None) -> int:
    setup_console()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", choices=["design", "brief", "build", "summary", "typo"])
    ap.add_argument("--batch", type=int, default=1)
    args = ap.parse_args(argv)
    cfg = load_config()
    out = rpath(OUT_DIR)
    if args.cmd == "design":
        if (out / "design.json").exists():
            print(f"{WARN} design.json이 이미 있습니다. 다시 만들려면 직접 지운 뒤 실행하세요.")
            return 1
        write_json(out / "design.json", make_design(cfg))
        print(f"{OK} {out / 'design.json'}")
        return 0
    design = read_json(out / "design.json")
    paths = [out / f"batch_{b:02d}.jsonl" for b in range(1, len(design["batches"]) + 1)]
    if args.cmd == "brief":
        print(brief(design, args.batch, cfg))
        return 0
    if args.cmd == "typo":
        return apply_typos(paths, out, cfg)
    if args.cmd == "summary":
        return summarize(design, paths, out, cfg)
    draft = read_json(out / "drafts" / f"batch_{args.batch:02d}.json")
    prices = read_json(rpath(DIRECT_DIR) / "price_ref.json")  # 짧은 메모와 같은 가격 기준 (2026-11-02)
    rows = assemble(design, args.batch, draft, prices)
    earlier = [r for i, p in enumerate(paths, 1) if i != args.batch for r in read_json_lines(p)]
    people = {p["persona_id"]: p for p in load_personas(cfg)}
    result = check_batch(design, args.batch, rows, earlier, prices, people, short_by_person(), load_lex())
    write_jsonl(out / f"batch_{args.batch:02d}.jsonl", rows)
    write_jsonl(out / "memos.jsonl", [r for p in paths for r in read_json_lines(p)])
    text = report(rows, result, f"배치 {args.batch} 검사 결과")
    write_text(out / "checks" / f"batch_{args.batch:02d}.md", text)
    print(text)
    return 1 if result["fails"] else 0


def summarize(design: dict, paths: list[Path], out: Path, cfg: dict) -> int:
    """300개 전체를 배치 검사 기준으로 다시 돌려 summary.md에 쓴다. 숫자는 jsonl에서 다시 센다."""
    rows = [r for p in paths for r in read_json_lines(p)]
    people = {p["persona_id"]: p for p in load_personas(cfg)}
    prices = read_json(rpath(DIRECT_DIR) / "price_ref.json")
    short, lex = short_by_person(), load_lex()
    merged = {"fails": [], "warns": [], "terms": [], "endings": collections.Counter(), "unverified": 0}
    for b in range(1, len(paths) + 1):
        part = [r for r in rows if r["batch"] == b]
        res = check_batch(design, b, part, [r for r in rows if r["batch"] != b], prices, people, short, lex)
        for k in ("fails", "warns", "terms"):
            merged[k] += res[k]
        merged["endings"] += res["endings"]
        merged["unverified"] += res["unverified"]
    text = report(rows, merged, f"2~3줄 메모 {len(rows)}개 전체 통계")
    write_text(out / "summary.md", text)
    print(text)
    return 1 if merged["fails"] else 0


def apply_typos(paths: list[Path], out: Path, cfg: dict) -> int:
    """300개를 다 쓴 뒤 한 번: memo_body_clean(원문, 라벨 기준)에 페르소나 오타율만큼 오타를 넣어 memo_body에 쓴다."""
    from .typo import inject
    people = {p["persona_id"]: p for p in load_personas(cfg)}
    missing = [p.name for p in paths if not p.exists()]
    if missing:
        print(f"{FAIL} 아직 없는 배치: {missing} — 300개를 다 쓴 뒤 실행하세요.")
        return 1
    all_rows, changed = [], 0
    for path in paths:
        rows = read_json_lines(path)
        for r in rows:
            rate = float(people[r["persona_id"]]["w_typo_rate"] or 0)
            r["memo_body"] = inject(r["memo_body_clean"], rate, r["memo_id"])
            r["typo_applied"] = r["memo_body"] != r["memo_body_clean"]
            changed += r["typo_applied"]
        write_jsonl(path, rows)
        all_rows += rows
    write_jsonl(out / "memos.jsonl", all_rows)
    print(f"{OK} 오타 주입: {changed}/{len(all_rows)}개 메모 변경 (원문은 memo_body_clean)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
