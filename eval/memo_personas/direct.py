"""DB·Gemini 없이 Claude Code가 직접 쓰는 메모 1,000개 — 설계·배치 안내·조립·검사.

서린이 정답(근거 ID·답변 가능성)은 DB로 따로 매기기로 해서, 여기서는 메모와 문장별 판정 라벨만 만든다.
- design: slots.py의 build_design을 가짜 근거로 돌려 원래 시드의 문장 유형·B/C 150개 배정·파일럿 10명을 그대로 가져온다.
  그 위에 35% 메모를 2~3문장 유형 섞기로 표시하고, 배치(10명씩)를 나눈다.
- brief --batch N: 그 배치 사람들의 페르소나 서술과 슬롯을 출력한다 (쓰기 전에 다시 읽는 용도).
- build --batch N: drafts/batch_NN.json(직접 쓴 메모)을 설계와 합쳐 memos.jsonl을 다시 만들고 검사 결과를 저장한다.

실행: PYTHONPATH=backend python -m eval.memo_personas.direct design | brief --batch 1 | build --batch 1
"""

from __future__ import annotations

import argparse
import collections
import random
import re
import sys
from pathlib import Path

from .checks import mentions, parse_numbers, similar_pairs, style_problems
from .common import (COMPANIES, OK, WARN, FAIL, load_config, load_personas, read_json, rpath, setup_console,
                     write_json, write_jsonl, write_text)
from .prompt import TYPE_GUIDE, first_sentences
from .slots import EVIDENCE_TYPES, build_design

OUT_DIR = "results/memo_personas/memos_direct"
GENERATOR = "claude-code-direct"
BATCH_SIZE = 10
MIX_SHARE = 0.35
SIMILARITY = 0.9
MAX_CHARS = 300
DECISION_KO = {"A": "추적", "C": "일부 추적", "B": "추적 안 함"}
DECISIONS = {"추적", "일부 추적", "추적 안 함", "확인 필요"}
ALL_TYPES = list(TYPE_GUIDE)
# 섞을 때 붙이는 보조 문장 유형 (실제 팀 메모에서 자주 보인 조합 위주. 광고·다른 종목만은 드물게)
SECONDARY_WEIGHTS = {"B1": 9, "B2": 7, "B3": 7, "B4": 9, "B5": 6, "B7": 5, "B8": 4, "B9": 5, "B6": 1, "B10": 1,
                     "C1": 6, "C2": 5, "C3": 3, "C4": 3, "C5": 2,
                     "A1": 7, "A2": 4, "A3": 5, "A4": 7, "A5": 4}
# 배정 기업을 말하지 않는 유형만 있는 메모에는 같은 성격의 보조 문장만 붙인다
NO_COMPANY_SECONDARY = {"B1": 1, "B3": 1, "B4": 1, "B5": 1, "B7": 1}
PRICE_TYPES = {"A2", "C1", "C4"}
# 상대 가격 조건 표지 ("10% 빠지면", "전고점", "60일선") — 팀 기준표 v0.2에서 확인 필요
RELATIVE_PRICE = re.compile(r"%|퍼|프로|고점|저점|신고가|신저가|일선|이평|평단|반토막|두 배|거래량")


# 길이: 짧게 쓰는 사람은 60% 이상 20자 이하, 배치 전체는 20자 이하 35% 이상·51자 이상 20% 이하
SHORT_CHARS, LONG_CHARS = 20, 51
SHORT_PERSON_MIN, SHORT_BATCH_MIN, LONG_BATCH_MAX = 0.6, 0.35, 0.20
MIX_RANGE = (0.25, 0.35)
UNVERIFIED_MAX = 5
# 끝맺음: 같은 사람 2회, 배치 8회까지 (비슷한 꼴은 같은 끝맺음으로 센다)
ENDINGS = {"알림": ("알림", "알림 받기", "알림 받자"), "보자": ("보자",), "볼 것": ("볼 것",),
           "지켜보기": ("지켜보기",), "확인": ("확인", "확인하기", "확인하자", "확인해두자")}
ENDING_PERSON_MAX, ENDING_BATCH_MAX = 2, 8
_TAIL = " .,!?~…ㅋㅎㅠㅜ"
# 용어 수준: 입문(3년 미만)은 전문용어 0, 기본(3~9년)도 0, 10년 이상이거나 직업이 맞으면 허용
EXPERT_TERMS = ["CET1", "NIM", "순이자마진", "PF", "충당금", "대손", "비이자이익", "이자이익", "수수료 이익", "연체율",
                "자본비율", "BIS", "CAPEX", "capex", "가이던스", "퀄", "수율", "재고자산", "현금흐름", "ROE", "ROA",
                "판관비", "분리과세", "비은행", "밸류업", "컨센서스", "감가상각", "레버리지"]
BASIC_TERMS = ["PER", "PBR", "EPS", "배당성향", "영업이익", "순이익", "잠정실적", "자사주", "소각", "시총", "시가총액",
               "주주환원", "환원율", "컨콜", "사업보고서", "분기보고서"]
EXPERT_JOBS = ("회계", "경리", "경영 기획", "컨설턴트", "전자제품 개발", "금속·재료 공학")


# 별명: 한 사람이 같은 이름을 메모 4개 넘게 쓰지 않는다 (대소문자 무시, 긴 이름부터 맞춘다)
ALIAS_MAX = 4
ALIAS_GROUPS = {"삼성전자": ["삼성전자", "만전자", "삼전", "삼성"], "SK하이닉스": ["sk하이닉스", "하이닉스", "만닉스", "하닉"],
                "NAVER": ["naver", "네이버", "넵"], "KB금융": ["kb금융", "kb국민", "국민은행", "케이비", "kb"]}
_ALIAS_RE = re.compile("|".join(sorted({re.escape(a) for al in ALIAS_GROUPS.values() for a in al}, key=len, reverse=True)))
B7_REPEAT_MAX = 2  # 같은 의미 없음 문장은 1,000개 전체에서 2번까지


def aliases_used(text: str) -> set[str]:
    return {m.group(0) for m in _ALIAS_RE.finditer(text.lower())}


def term_tier(p: dict) -> str:
    if int(p["experience_years"]) >= 10 or any(j in p["occupation"] for j in EXPERT_JOBS):
        return "전문"
    return "기본" if int(p["experience_years"]) >= 3 else "입문"


def find_terms(text: str, terms: list[str]) -> list[str]:
    return [t for t in terms if re.search(rf"(?<![A-Za-z]){re.escape(t)}(?![A-Za-z])", text)]


def ending_of(sentence: str) -> str | None:
    core = sentence.rstrip(_TAIL)
    return next((k for k, forms in ENDINGS.items() if core.endswith(forms)), None)


def abs_prices(text: str) -> list[float]:
    """절대 가격으로 보이는 수: "20만", "130만원", "17만5천", "20만전자" (%, 주, 분기 같은 단위가 붙은 수는 제외)."""
    return [n["value"] for n in parse_numbers(text) if n["kind"] in ("plain", "won") and n["value"] >= 10_000]


# ─────────────────────────────────────────────────────────────
# 설계
# ─────────────────────────────────────────────────────────────
def fake_packs() -> tuple[dict, dict]:
    """build_design이 요구하는 모양만 맞춘 가짜 근거. 문장 유형·B/C 배정은 근거와 무관한 난수로 정해진다."""
    def item(c, t, i):
        return {"key": f"{c}:{t}:{i}", "type": t, "kind": t, "ids": [f"{c}:{t}:{i}"], "text": "", "memo_hint": ""}
    packs = {c: {"symbol": c, "as_of_date": None,
                 "price": {"close": 100, "low_52w": {"price": 80}, "high_52w": {"price": 120}},
                 "items": [item(c, t, i) for t in EVIDENCE_TYPES if t != "거시" for i in range(20)]}
             for c in COMPANIES}
    return packs, {"items": [item("macro", "거시", i) for i in range(20)]}


def make_design(cfg: dict) -> dict:
    personas = load_personas(cfg)
    packs, macro = fake_packs()
    base = build_design(personas, packs, macro, cfg)
    rng = random.Random(f"{cfg['generation']['seed']}:direct")
    keys = [(p["persona_id"], s["slot"]) for p in base["persons"] for s in p["slots"]]
    mixed = set(rng.sample(keys, round(len(keys) * MIX_SHARE)))
    pilot = base["pilot"]
    rest = sorted(p["persona_id"] for p in personas if p["persona_id"] not in pilot)
    batches = [pilot] + [rest[i:i + BATCH_SIZE] for i in range(0, len(rest), BATCH_SIZE)]
    persons = {}
    for p in base["persons"]:
        out = []
        for s in p["slots"]:
            st = s["sentence_type"]
            if s.get("answerability") == "자료 부족":
                need = ["DB 밖 가능"]
            elif st[0] == "B":
                need = []
            else:
                need = list(s["evidence_parts"])
            rec = {"slot": s["slot"], "company": s["target_company"], "role": s["role"], "status": s["status"],
                   "primary_type": st, "call_names": s["call_names"], "length": s["length"], "data_need": need,
                   "trigger": s["trigger"] if st[0] != "A" or s.get("answerability") == "자료 부족"
                   else trigger_hint(need, rng), "mixed": (p["persona_id"], s["slot"]) in mixed}
            if s.get("missing_topic"):
                rec["missing_topic"] = s["missing_topic"]
            if s.get("other_company"):
                rec["other_company"] = s["other_company"]
            if rec["mixed"]:
                pool = NO_COMPANY_SECONDARY if st in ("B5", "B7", "B10") else SECONDARY_WEIGHTS
                n = 2 if rng.random() < 0.3 else 1
                sec: list[str] = []
                while len(sec) < n:
                    t = rng.choices(list(pool), weights=list(pool.values()))[0]
                    if t != st and t not in sec:
                        sec.append(t)
                rec["secondary_types"] = sec
            out.append(rec)
        persons[p["persona_id"]] = out
    return {"seed": cfg["generation"]["seed"], "mix_share": MIX_SHARE, "batches": batches, "persons": persons,
            "source": "slots.build_design(가짜 근거) — 문장 유형·B/C 배정·파일럿은 원래 시드와 같음"}


def trigger_hint(need: list[str], rng: random.Random) -> str:
    words = {"공시": ["공시 알림 보고", "공시 뜬 거 보고"], "뉴스": ["뉴스 보고", "기사 보고"],
             "주가·거래": ["차트 보다가", "주가 알림 보고", "거래량 터진 거 보고"], "재무": ["실적 발표 보고", "실적 기사 보고"],
             "거시": ["환율 뉴스 보고", "금리 뉴스 보고"]}
    return " + ".join(rng.choice(words[t]) for t in need if t in words) or "그냥 생각나서"


# ─────────────────────────────────────────────────────────────
# 배치 안내 (쓰기 전에 다시 읽기)
# ─────────────────────────────────────────────────────────────
def brief(design: dict, batch: int, cfg: dict) -> str:
    people = {p["persona_id"]: p for p in load_personas(cfg)}
    lines = []
    for pid in design["batches"][batch - 1]:
        p = people[pid]
        nem = p.get("nemotron") or {}
        lines += [f"## {pid} · {p['age']}세 {p['sex']} · {p['province_full']} · {p['occupation']}"
                  f"{'(' + p['unemployed_type'] + ')' if p.get('unemployed_type') else ''} · {p['family_type']}",
                  f"- 경력 {p['experience_years']}년 · {p['invest_style']} · {p['risk_profile']} · {p['investment_horizon']}"
                  f" · 목적 {p['fund_purpose']} · 원천 {p['fund_source']} · 정보 {p['info_source']}",
                  f"- 관심 공부: {', '.join(p['learning_interest'])} · 별명 {p.get('nickname')}",
                  f"- 말투: 반말 {p['w_banmal']} · ㅋㅋ {p['w_laugh']} · 말줄임표 {p['w_ellipsis']} · 길이 {p['w_length']}"
                  f" · 오타율 {p['w_typo_rate']}",
                  f"- 서술: {first_sentences(nem.get('persona'), 1)} {first_sentences(nem.get('professional_persona'), 1)}",
                  f"- 가족: {first_sentences(nem.get('family_persona'), 1)}",
                  f"- 취미: {first_sentences(nem.get('hobbies_and_interests'), 1)}"]
        for s in design["persons"][pid]:
            extra = " + ".join(s.get("secondary_types", []))
            lines.append(f"  {s['slot']:>2}. {s['company']}({s['role']}/{s['status']}) {s['primary_type']}"
                         f"{' + ' + extra if extra else ''} · {s['length']} · 계기 {s['trigger']} · 근거 {s['data_need'] or '-'}"
                         f"{' · 부족:' + s['missing_topic'] if s.get('missing_topic') else ''}"
                         f"{' · 다른:' + s['other_company'] if s.get('other_company') else ''} · 이름 {s['call_names'][:3]}")
        lines.append("")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────
# 조립과 검사
# ─────────────────────────────────────────────────────────────
def expected(t: str, override: str | None) -> str:
    return override or DECISION_KO[t[0]]


def assemble(design: dict, batch: int, draft: dict, prices: dict) -> list[dict]:
    rows = []
    for pid in design["batches"][batch - 1]:
        for d in draft.get(pid, []):
            s = next(x for x in design["persons"][pid] if x["slot"] == d["slot"])
            sents = [{"text": x[0], "intended_type": x[1], "expected_decision": expected(x[1], x[2] if len(x) > 2 else None)}
                     for x in d["sents"]]
            # 본문을 따로 안 쓰면 문장을 sep(기본 줄바꿈)으로 잇는다
            body, title = d.get("body") or d.get("sep", "\n").join(x["text"] for x in sents), d.get("title", "")
            need = list(d.get("need", s["data_need"]))
            if any(x["intended_type"] in ("A2", "C1") for x in sents) and "주가·거래" not in need and "DB 밖 가능" not in need:
                need.append("주가·거래")  # 섞인 가격 조건 문장도 주가로 확인한다
            rows.append({
                "memo_id": f"{pid}-{d['slot']:02d}", "persona_id": pid, "slot": d["slot"], "batch": batch,
                "company_primary": s["company"], "companies_mentioned": mentions(f"{title} {body}"),
                "primary_type": s["primary_type"], "mixed": len({x["intended_type"] for x in sents}) > 1,
                # 오타는 1,000개를 다 쓴 뒤 typo 단계에서 memo_body에만 넣는다. 라벨은 memo_body_clean 기준
                "memo_title": title, "memo_body": body, "memo_body_clean": body, "sentences": sents,
                "trigger": s["trigger"], "data_need": need,
                "price_basis": price_basis(sents, prices), "topic_unverified": bool(d.get("unv")),
                "generator": GENERATOR, "review_status": "pending",
            })
    return rows


def price_basis(sents: list[dict], prices: dict) -> dict | None:
    """가격 문장이 있으면 기준일과 절대/상대 여부를 남긴다 (절대 가격은 price_ref.json의 52주 범위 안에서만 썼다)."""
    ps = [x for x in sents if x["intended_type"] in PRICE_TYPES]
    if not ps:
        return None
    kinds = ["절대" if abs_prices(x["text"]) else ("상대" if RELATIVE_PRICE.search(x["text"]) else "가격 없음") for x in ps]
    return {"as_of": prices["as_of"], "source": prices["source"], "kinds": kinds}


def check_batch(design: dict, batch: int, rows: list[dict], earlier: list[dict], prices: dict, people: dict,
                lex=None) -> dict:
    fails, warns, terms = [], [], []
    n = len(rows) or 1
    short = sum(len(r["memo_body"]) <= SHORT_CHARS for r in rows) / n
    long_ = sum(len(r["memo_body"]) >= LONG_CHARS for r in rows) / n
    mixed = sum(r["mixed"] for r in rows) / n
    if short < SHORT_BATCH_MIN:
        fails.append(f"배치: 20자 이하 {short:.0%} < {SHORT_BATCH_MIN:.0%}")
    if long_ > LONG_BATCH_MAX:
        fails.append(f"배치: 51자 이상 {long_:.0%} > {LONG_BATCH_MAX:.0%}")
    if not MIX_RANGE[0] <= mixed <= MIX_RANGE[1]:
        fails.append(f"배치: 섞인 메모 {mixed:.0%}가 {MIX_RANGE[0]:.0%}~{MIX_RANGE[1]:.0%} 밖")
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
        if p["w_length"] == "짧게" and got:
            share = sum(len(r["memo_body"]) <= SHORT_CHARS for r in got.values()) / len(got)
            if share < SHORT_PERSON_MIN:
                fails.append(f"{pid}(짧게): 20자 이하 {share:.0%} < {SHORT_PERSON_MIN:.0%}")
        endings = collections.Counter(e for r in got.values() for x in r["sentences"] if (e := ending_of(x["text"])))
        fails += [f"{pid}: '{k}' 끝맺음 {v}회 > {ENDING_PERSON_MAX}" for k, v in endings.items() if v > ENDING_PERSON_MAX]
        alias_counts = collections.Counter(a for r in got.values() for a in aliases_used(f"{r['memo_title']} {r['memo_body']}"))
        fails += [f"{pid}: 별명 '{a}' 메모 {c}개 > {ALIAS_MAX}" for a, c in alias_counts.items() if c > ALIAS_MAX]
        all_text = " ".join(f"{r['memo_title']} {r['memo_body']}" for r in got.values())
        tier, expert, basic = term_tier(p), find_terms(all_text, EXPERT_TERMS), find_terms(all_text, BASIC_TERMS)
        terms.append({"persona_id": pid, "experience_years": p["experience_years"], "occupation": p["occupation"],
                      "tier": tier, "expert": expert, "basic": basic})
        if tier != "전문" and expert:
            fails.append(f"{pid}({tier}·경력 {p['experience_years']}년): 전문용어 {expert}")
        for slot, r in sorted(got.items()):
            s = want[slot]
            tag = f"{r['memo_id']}({s['primary_type']})"
            types = [x["intended_type"] for x in r["sentences"]]
            text = f"{r['memo_title']} {r['memo_body']}"
            if any(t not in ALL_TYPES for t in types):
                fails.append(f"{tag}: 알 수 없는 유형 {types}")
            if any(x["expected_decision"] not in DECISIONS for x in r["sentences"]):
                fails.append(f"{tag}: 알 수 없는 판정 라벨")
            if s["primary_type"] not in types:
                fails.append(f"{tag}: 주 유형 문장이 없음 {types}")
            # 섞기 슬롯은 짧게 쓰려고 한 유형만 써도 된다 (배치 섞기 비율 25~35%만 지킨다)
            if len(set(types)) > 3:
                fails.append(f"{tag}: 유형 {len(set(types))}개 > 3")
            if not s["mixed"] and len(set(types)) > 1:
                fails.append(f"{tag}: 섞기 슬롯이 아닌데 유형이 여럿 {types}")
            pos = 0
            for x in r["sentences"]:
                i = r["memo_body"].find(x["text"], pos)
                if i < 0:
                    fails.append(f"{tag}: 문장이 본문에 순서대로 없음 '{x['text']}'")
                    break
                pos = i + len(x["text"])
            exempt = set(types) <= {"B5", "B7", "B10"} | ({"B1", "B3", "B4"} if s["primary_type"] in ("B5", "B7", "B10") else set())
            if not exempt and s["company"] not in r["companies_mentioned"]:
                fails.append(f"{tag}: 배정 기업 언급 없음")
            if exempt and s["company"] in r["companies_mentioned"]:
                fails.append(f"{tag}: {s['primary_type']} 메모에 배정 기업 이름이 나옴")
            if s.get("other_company") and not any(o != s["company"] for o in r["companies_mentioned"]):
                fails.append(f"{tag}: 다른 종목({s['other_company']}) 언급 없음")
            fails += [f"{tag}: {p}" for p in style_problems(text)]
            if len(r["memo_body"]) > MAX_CHARS:
                fails.append(f"{tag}: 본문 {len(r['memo_body'])}자 > {MAX_CHARS}")
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
            if lex is not None:
                warns += segment_warnings(r, lex, tag)
        for a, b, ratio in similar_pairs([{"slot": r["slot"], "memo_text_raw": r["memo_body"]} for r in got.values()],
                                         SIMILARITY):
            fails.append(f"{pid}: 슬롯 {a}·{b} 유사도 {ratio}")
    b7 = collections.Counter(x["text"].strip() for r in earlier + rows for x in r["sentences"] if x["intended_type"] == "B7")
    fails += [f"B7 '{t}' 전체 {c}회 > {B7_REPEAT_MAX}" for t, c in b7.items() if c > B7_REPEAT_MAX]
    repeats = repeated_phrases(rows, earlier)
    warns += [f"반복 표현 '{g}' — 이번 배치 {k}회, 앞 배치 {m}회" for g, k, m in repeats]
    return {"fails": fails, "warns": warns, "terms": terms, "endings": batch_endings, "unverified": unv}


def segment_warnings(r: dict, lex, tag: str) -> list[str]:
    """실제 판정 파이프라인의 문장 분리·규칙 판정과 라벨이 어긋나는지 (실패가 아니라 검수 참고용)."""
    from pipelines.tracking.judge import judge_memo
    from pipelines.tracking.segment import split_sentences
    out = []
    segs = [g.text for g in split_sentences(r["memo_body"], lex)]
    if len(segs) != len(r["sentences"]):
        out.append(f"{tag}: 문장 분리 {len(segs)}개 ≠ 라벨 {len(r['sentences'])}개 {segs}")
        return out
    code = {"삼성전자": "005930", "SK하이닉스": "000660", "NAVER": "035420", "KB금융": "105560"}[r["company_primary"]]
    rule_ko = {"normal": "추적", "partial": "일부 추적", "full_fallback": "추적 안 함", "needs_confirmation": "확인 필요"}
    for j, x in zip(judge_memo(r["memo_body"], code, lex), r["sentences"]):
        if j.judged_by == "rule" and rule_ko[j.decision] != x["expected_decision"]:
            out.append(f"{tag}: 규칙 판정 {j.category}/{rule_ko[j.decision]} ≠ 라벨 {x['intended_type']}/{x['expected_decision']}"
                       f" '{x['text']}'")
    return out


_WORD = re.compile(r"[가-힣A-Za-z0-9]+")


def trigrams(text: str) -> set[str]:
    w = _WORD.findall(text.lower())
    return {" ".join(w[i:i + 3]) for i in range(len(w) - 2)}


def repeated_phrases(rows: list[dict], earlier: list[dict], limit: int = 15) -> list[tuple[str, int, int]]:
    """세 어절 묶음이 이번 배치에서 4번 이상, 또는 앞 배치까지 합쳐 전체 메모의 1% 이상 나오면 표시한다."""
    now = collections.Counter(g for r in rows for g in trigrams(r["memo_body"]))
    before = collections.Counter(g for r in earlier for g in trigrams(r["memo_body"]))
    total = len(rows) + len(earlier)
    hits = [(g, n, before[g]) for g, n in now.items() if n >= 4 or (n >= 2 and n + before[g] >= max(5, total * 0.01))]
    return sorted(hits, key=lambda x: -(x[1] + x[2]))[:limit]


# ─────────────────────────────────────────────────────────────
# 분포표
# ─────────────────────────────────────────────────────────────
def length_bucket(body: str) -> str:
    n = len(body)
    return "짧게(~20자)" if n <= 20 else ("보통(21~50자)" if n <= 50 else "길게(51자~)")


def table(title: str, counter: collections.Counter, order=None) -> list[str]:
    keys = order or sorted(counter)
    total = sum(counter.values()) or 1
    out = [f"### {title}", "", "| 값 | 개수 | 비율 |", "|---|---:|---:|"]
    out += [f"| {k} | {counter[k]} | {counter[k] / total:.0%} |" for k in keys if counter[k]]
    return out + [""]


def report(rows: list[dict], result: dict, batch: int) -> str:
    sents = [x for r in rows for x in r["sentences"]]
    lines = [f"# 배치 {batch} 검사 결과", "",
             f"- 메모 {len(rows)}개 · 문장 {len(sents)}개 · 섞인 메모 {sum(r['mixed'] for r in rows)}개",
             f"- {OK if not result['fails'] else FAIL} 실패 {len(result['fails'])}건 · {WARN} 참고 {len(result['warns'])}건", ""]
    lines += table("주 유형 (메모 기준)", collections.Counter(r["primary_type"] for r in rows), ALL_TYPES)
    lines += table("문장 유형 (문장 기준)", collections.Counter(x["intended_type"] for x in sents), ALL_TYPES)
    lines += table("기대 판정 (문장 기준)", collections.Counter(x["expected_decision"] for x in sents),
                   ["추적", "일부 추적", "추적 안 함", "확인 필요"])
    lines += table("가격 문장 (A2·C1·C4)", collections.Counter(k for r in rows for k in (r["price_basis"] or {}).get("kinds", [])),
                   ["절대", "상대", "가격 없음"])
    lines += table("배정 기업", collections.Counter(r["company_primary"] for r in rows), COMPANIES)
    lines += table("본문 길이", collections.Counter(length_bucket(r["memo_body"]) for r in rows),
                   ["짧게(~20자)", "보통(21~50자)", "길게(51자~)"])
    lines += table("끝맺음 (알림·보자·볼 것·지켜보기·확인, 배치 8회 이하)", result["endings"], list(ENDINGS))
    lines += [f"- 들은 소식(topic_unverified): {result['unverified']}개 (배치 {UNVERIFIED_MAX}개 이하)", "",
              "### 페르소나별 용어", "", "| 페르소나 | 경력 | 직업 | 수준 | 전문용어 | 기본 용어 |", "|---|---:|---|---|---:|---:|"]
    lines += [f"| {t['persona_id']} | {t['experience_years']}년 | {t['occupation']} | {t['tier']} | "
              f"{len(t['expert'])} {'(' + ', '.join(t['expert']) + ')' if t['expert'] else ''} | {len(t['basic'])} |"
              for t in result["terms"]]
    lines += ["", "## 실패", ""] + [f"- {x}" for x in result["fails"]] + ["", "## 참고", ""] + [f"- {x}" for x in result["warns"]]
    return "\n".join(lines) + "\n"


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
    if args.cmd == "brief":
        print(brief(design, args.batch, cfg))
        return 0
    if args.cmd == "typo":
        return apply_typos(design, out, cfg)
    if args.cmd == "summary":
        return summarize(design, out, cfg)
    draft = read_json(out / "drafts" / f"batch_{args.batch:02d}.json")
    prices = read_json(out / "price_ref.json")  # 팀 DB prices_daily에서 읽기 전용으로 뽑은 종가·52주 고저
    rows = assemble(design, args.batch, draft, prices)
    # 반복·B7 검사는 다른 배치 전부와 비교한다 (앞 배치를 고쳐 다시 돌릴 때도 같은 기준)
    earlier = [r for b in range(1, len(design["batches"]) + 1) if b != args.batch
               for r in read_json_lines(out / f"batch_{b:02d}.jsonl")]
    try:
        from pipelines.tracking.lexicon import load_lexicon
        lex = load_lexicon()
    except Exception as exc:  # 판정 파이프라인을 못 불러와도 기본 검사는 한다
        print(f"{WARN} 문장 분리 대조 생략: {type(exc).__name__}")
        lex = None
    people = {p["persona_id"]: p for p in load_personas(cfg)}
    result = check_batch(design, args.batch, rows, earlier, prices, people, lex)
    write_jsonl(out / f"batch_{args.batch:02d}.jsonl", rows)
    all_rows = [r for b in range(1, len(design["batches"]) + 1) for r in read_json_lines(out / f"batch_{b:02d}.jsonl")]
    write_jsonl(out / "memos.jsonl", all_rows)
    write_text(out / "checks" / f"batch_{args.batch:02d}.md", report(rows, result, args.batch))
    print(report(rows, result, args.batch))
    return 1 if result["fails"] else 0


def summarize(design: dict, out: Path, cfg: dict) -> int:
    """1,000개 전체 통계(summary.md)와 팀 공유용 판정 파이프라인 문제 목록(pipeline_issues.md). 숫자는 jsonl에서 다시 센다."""
    from pipelines.tracking.judge import judge_memo
    from pipelines.tracking.lexicon import load_lexicon
    from pipelines.tracking.segment import split_sentences
    people = {p["persona_id"]: p for p in load_personas(cfg)}
    rows = [r for b in range(1, len(design["batches"]) + 1) for r in read_json_lines(out / f"batch_{b:02d}.jsonl")]
    n = len(rows)
    sents = [x for r in rows for x in r["sentences"]]
    prim = collections.Counter(r["primary_type"] for r in rows)
    bc_bad = {t: prim[t] for t in ALL_TYPES if t[0] in "BC" and prim[t] != 10}
    endings = collections.Counter(e for x in sents if (e := ending_of(x["text"])))
    tiers = collections.defaultdict(lambda: [0, 0, 0])  # 사람 수, 전문용어 쓴 사람, 전문용어 개수
    for pid in {r["persona_id"] for r in rows}:
        text = " ".join(f"{r['memo_title']} {r['memo_body_clean']}" for r in rows if r["persona_id"] == pid)
        t, ex = term_tier(people[pid]), find_terms(text, EXPERT_TERMS)
        tiers[t][0] += 1
        tiers[t][1] += bool(ex)
        tiers[t][2] += len(ex)
    lines = ["# 메모 1,000개 전체 통계", "", f"- 메모 {n}개 · 문장 {len(sents)}개 · 생성 {GENERATOR}", "",
             "## 설계 대조", "",
             f"- 기업: {dict(collections.Counter(r['company_primary'] for r in rows))} (목표 250×4)",
             f"- 주 유형 A/B/C: {dict(collections.Counter(r['primary_type'][0] for r in rows))} (목표 850/100/50)",
             f"- B·C 15종 각 10개: {'✅ 모두 10개' if not bc_bad else '❌ ' + str(bc_bad)}", ""]
    lines += table("주 유형", prim, ALL_TYPES)
    lines += table("문장 기대 판정", collections.Counter(x["expected_decision"] for x in sents),
                   ["추적", "일부 추적", "추적 안 함", "확인 필요"])
    lines += table("본문 길이 (memo_body_clean)", collections.Counter(length_bucket(r["memo_body_clean"]) for r in rows),
                   ["짧게(~20자)", "보통(21~50자)", "길게(51자~)"])
    lines += table("끝맺음 (알림·보자·볼 것·지켜보기·확인)", endings, list(ENDINGS))
    lines += table("가격 문장", collections.Counter(k for r in rows for k in (r["price_basis"] or {}).get("kinds", [])),
                   ["절대", "상대", "가격 없음"])
    lines += [f"- 섞인 메모: {sum(r['mixed'] for r in rows)}개 ({sum(r['mixed'] for r in rows) / n:.0%})",
              f"- 들은 소식(topic_unverified): {sum(r['topic_unverified'] for r in rows)}개", "",
              "### 용어 수준", "", "| 수준 | 사람 | 전문용어 쓴 사람 | 전문용어 수 |", "|---|---:|---:|---:|"]
    lines += [f"| {t} | {v[0]} | {v[1]} | {v[2]} |" for t, v in sorted(tiers.items())]
    write_text(out / "summary.md", "\n".join(lines) + "\n")

    lex = load_lexicon()
    code = {"삼성전자": "005930", "SK하이닉스": "000660", "NAVER": "035420", "KB금융": "105560"}
    rule_ko = {"normal": "추적", "partial": "일부 추적", "full_fallback": "추적 안 함", "needs_confirmation": "확인 필요"}
    over, under, judge = [], [], []
    for r in rows:
        body = r["memo_body_clean"]
        segs = [g.text for g in split_sentences(body, lex)]
        if len(segs) > len(r["sentences"]):
            over.append((r["memo_id"], [x["text"] for x in r["sentences"]], segs))
        elif len(segs) < len(r["sentences"]):
            under.append((r["memo_id"], [x["text"] for x in r["sentences"]], segs))
        else:
            for j, x in zip(judge_memo(body, code[r["company_primary"]], lex), r["sentences"]):
                if j.judged_by == "rule" and rule_ko[j.decision] != x["expected_decision"]:
                    judge.append((r["memo_id"], x["text"], f"{j.category}/{rule_ko[j.decision]}",
                                  f"{x['intended_type']}/{x['expected_decision']}"))
    il = ["# 판정 파이프라인 문제 목록 (평가 메모 1,000개로 확인)", "",
          "`backend/pipelines/tracking`의 문장 분리(segment.py)와 규칙 판정(judge.py)을 평가 메모의 라벨과 대조한 결과입니다.",
          "라벨은 메모 작성 의도 기준이고, 규칙 판정은 LLM 단계 전에 확정되는 것만 비교했습니다.", "",
          f"## 1. 문장을 더 잘게 자름 ({len(over)}건)", "",
          "연결 표현(…보니, …다니, …던데)이나 명사(판매자, 시설투자)를 문장 끝으로 보고 자릅니다.", "",
          "| 메모 | 라벨 문장 | 분리 결과 |", "|---|---|---|"]
    il += [f"| {m} | {' / '.join(a)} | {' / '.join(b)} |" for m, a, b in over]
    # 어디서 잘랐는지: 마지막이 아닌 조각의 끝 어절
    cut_words = collections.Counter(s.split()[-1] for _, _, segs in over for s in segs[:-1] if s.split())
    il += ["", "자른 지점(조각 끝 어절) 빈도:", "", "| 끝 어절 | 건수 |", "|---|---:|"]
    il += [f"| {w} | {c} |" for w, c in cut_words.most_common(15)]
    il += ["", f"## 2. 문장을 덜 자름 ({len(under)}건)", "", "| 메모 | 라벨 문장 | 분리 결과 |", "|---|---|---|"]
    il += [f"| {m} | {' / '.join(a)} | {' / '.join(b)} |" for m, a, b in under]
    il += ["", f"## 3. 규칙 판정이 라벨과 다름 ({len(judge)}건)", "", "| 메모 | 문장 | 규칙 판정 | 라벨 |", "|---|---|---|---|"]
    il += [f"| {m} | {t} | {a} | {b} |" for m, t, a, b in judge]
    write_text(out / "pipeline_issues.md", "\n".join(il) + "\n")
    print("\n".join(lines))
    print(f"\n{OK} {out / 'summary.md'}\n{OK} {out / 'pipeline_issues.md'} — 더 자름 {len(over)} · 덜 자름 {len(under)} · 규칙 판정 {len(judge)}")
    return 0


def apply_typos(design: dict, out: Path, cfg: dict) -> int:
    """1,000개를 다 쓴 뒤 한 번: memo_body_clean(원문, 라벨 기준)에 페르소나 오타율만큼 오타를 넣어 memo_body에 쓴다."""
    from .typo import inject
    people = {p["persona_id"]: p for p in load_personas(cfg)}
    paths = [out / f"batch_{b:02d}.jsonl" for b in range(1, len(design["batches"]) + 1)]
    missing = [p.name for p in paths if not p.exists()]
    if missing:
        print(f"{FAIL} 아직 없는 배치: {missing} — 1,000개를 다 쓴 뒤 실행하세요.")
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


def read_json_lines(path: Path) -> list[dict]:
    import json
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()] if path.exists() else []


if __name__ == "__main__":
    sys.exit(main())
