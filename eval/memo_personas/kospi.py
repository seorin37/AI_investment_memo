"""코스피 다양화 메모 1,000개 (100명 × 10) — 4곳만 다룬 memos_direct·memos_long은 그대로 두고 따로 만든다.

팀 요청(2026-11-05): 4곳으로 돌려 본 결과, LLM 평가에 쓰려면 코스피 여러 기업에 걸친 메모가 필요하다.
짧은 메모와 2~3줄 메모를 섞고, 20대 비속어·업종 테마·기업 비교·공시 이벤트·잡담도 넣는다. 쓰는 사람은 Claude Code(직접 작성).

- ref: 팀 DB(조회 전용)에서 기업별 종가·52주 고저·20/60일선·최근 공시 제목을 읽어 company_ref.json에 둔다.
- design: 사람마다 10개 슬롯(종류·길이·기업·주 유형·계기·가격 방식·비속어 여부). 기업은 kospi_companies.py 391곳.
- brief --batch N / build --batch N / summary / typo: direct.py·long.py와 같은 흐름. 배치는 memos_direct 설계와 같다.

실행: PYTHONPATH=backend python -m eval.memo_personas.kospi ref | design | brief --batch 1 | build --batch 1 | summary | typo
"""

from __future__ import annotations

import argparse
import collections
import difflib
import random
import re
import sys
from pathlib import Path

from .checks import style_problems
from .common import (OK, WARN, FAIL, load_config, load_env, load_personas, read_database_url, read_json, rpath, setup_console,
                     write_json, write_jsonl, write_text)
from .checks import parse_numbers
from .direct import (ALL_TYPES, BASIC_TERMS, DECISIONS, ENDINGS, EXPERT_TERMS, PRICE_TYPES, RELATIVE_PRICE,
                     ending_of, expected, find_terms, read_json_lines, repeated_phrases, table, term_tier)
from .direct import OUT_DIR as DIRECT_DIR
from .kospi_companies import COMPANY_LIST, INDUSTRY_OF, INDUSTRIES, call_names, mentions, protected_words
from .prompt import first_sentences

OUT_DIR = "results/memo_personas/memos_kospi"
GENERATOR = "claude-code-direct"
SLOTS = 10
SEED = "kospi-diverse-v1"

# 종류별 개수(1,000개)와 주 유형
KIND_TYPES = {
    "일반": {"A1": 90, "A2": 90, "A4": 70, "A5": 70, "C1": 60, "C2": 50, "C4": 40, "C5": 20,
             "B2": 35, "B3": 25, "B8": 30, "B9": 20},
    "이벤트": {"A3": 90, "A1": 20, "A4": 25, "C2": 15},
    "테마": {"A1": 45, "A4": 25, "A5": 20, "C4": 10},
    "비교": {"C3": 100},
    "잡담": {"B1": 20, "B5": 15, "B7": 15},
}
KINDS = list(KIND_TYPES)
# 사람별 짧은 메모 개수 (나머지는 2~3줄). 짧게 47명·보통 32명·길게 21명 → 짧게 505 : 길게 495
SHORT_PER_PERSON = {"짧게": 6, "보통": 5, "길게": 3}
SHORT_CHARS = {"짧게": 40, "기타": 70}  # 짧은 메모 최대 글자 수 (한 줄)
LONG_CHARS = {"짧게": (35, 120), "기타": (50, 220)}  # 2~3줄 메모
LINES = (2, 3)
TYPES_MAX = 4
UNVERIFIED_MAX = 7  # 배치 100개당 (DB에 없는 소문 이벤트 포함)
ENDING_PERSON_MAX, ENDING_BATCH_MAX = 3, 10
ALIAS_MAX = 4  # 같은 사람이 같은 별명을 쓰는 메모 수
SIMILARITY = 0.8
PER_PERSON_MAX = 3  # 한 사람이 같은 기업으로 쓰는 메모 수
# 비속어: 센 표현은 34세 이하만, 35세 이상은 약한 표현만 (상규 지시 2026-11-05: 35세 이상에도 다양하게)
STRONG_SWEAR = re.compile(r"ㅅㅂ|ㅆㅂ|시발|씨발|존나|졸라|ㅈㄴ|개빡|ㅈ같|좆|병신|ㅂㅅ|미친|지랄|개같|개털|개박살|개떡")
MILD_SWEAR = re.compile(r"젠장|제기랄|빌어먹을|망할|썅|미치겠|돌겠|염병|육시랄|열받|빡치|에라이|우라질|ㅆ(?!ㅂ)|더럽게|드럽게")
PROFANITY = re.compile(f"{STRONG_SWEAR.pattern}|{MILD_SWEAR.pattern}")
PROFANITY_AGE_MAX = 34  # 이 나이 넘으면 센 표현 금지
SWEAR_SHARE = 0.35  # 34세 이하 사람의 메모 중 비속어를 넣을 몫
OLDER_SWEAR = 25  # 35세 이상 슬롯 중 약한 비속어를 넣을 개수 (단타·공격형 사람 우선)
# 설계 보완(v2): 빠졌던 폴백 유형과 DB에 없는 이벤트
FALLBACK_ADD = {"B10": 15, "B4": 12, "B6": 10}  # B10은 비교 C3에서 8, 나머지는 일반 A1에서
EVENT_NOT_IN_DB = 40  # 이벤트 150개 중 DB에 없는 이벤트(아직 안 나온 공시·들은 소문)
TITLE_OVERLAP_MIN = 5  # 메모와 참고 공시 제목이 이만큼 연속으로 같으면 경고
DATA_NEEDS = {"공시", "뉴스", "주가·거래", "재무", "거시", "DB 밖 가능"}
DEFAULT_NEED = {"A1": ["뉴스"], "A2": ["주가·거래"], "A3": ["공시"], "A4": ["뉴스"], "A5": ["재무"], "C1": ["주가·거래"],
                "C2": ["재무"], "C3": ["재무"], "C4": ["주가·거래"], "C5": ["뉴스"]}
TRIGGERS = {"A1": ["뉴스 보고", "기사 보고", "지인 얘기 듣고", "유튜브 보고"], "A2": ["차트 보다가", "주가 알림 보고"],
            "A3": ["공시 알림 보고", "일정 보다가"], "A4": ["뉴스 보고", "커뮤니티 글 보고", "지인 얘기 듣고"],
            "A5": ["실적 기사 보고", "뉴스 보고"], "C1": ["차트 보다가", "계좌 보다가"], "C2": ["뉴스 보고", "계좌 보다가"],
            "C3": ["커뮤니티 글 보고", "뉴스 보고"], "C4": ["차트 보다가", "실적 기사 보고"], "C5": ["뉴스 보고", "출근길에"],
            "B1": ["계좌 보다가"], "B2": ["매매하고 나서"], "B3": ["계좌 보다가"], "B5": ["그냥"], "B7": ["그냥"],
            "B8": ["커뮤니티 글 보고"], "B9": ["뉴스 보고"]}
THEME_TRIGGERS = ["테마 기사 보고", "커뮤니티 글 보고", "업종 뉴스 보고", "지인 얘기 듣고"]
EVENT_TRIGGERS = ["공시 알림 보고", "공시 뜬 거 보고", "일정 보다가"]
# 직업·성향별로 더 관심 가질 만한 업종 (가중치 +3). 없으면 고르게
JOB_AFFINITY = [
    (("간호", "요양", "돌봄", "보건", "치과", "사회복지"), ["바이오·제약", "화장품"]),
    (("운전원", "버스", "화물차"), ["자동차", "에너지·유틸리티", "해운·물류"]),
    (("용접", "잠수", "기계 조작", "재단기", "포장"), ["조선", "철강·금속", "기계·로봇"]),
    (("전자제품 개발",), ["반도체", "전자부품"]), (("금속·재료",), ["철강·금속", "2차전지"]),
    (("화학물",), ["화학", "2차전지"]), (("건축", "토목"), ["건설·건자재"]), (("전기 감리",), ["전력기기·전선", "에너지·유틸리티"]),
    (("헬리콥터",), ["방산·우주", "항공·여행·레저"]), (("철도",), ["방산·우주", "해운·물류"]),
    (("여행",), ["항공·여행·레저"]), (("판매원", "상점", "음식", "음료", "주방", "체인점"), ["식품·음료", "유통"]),
    (("유치원", "교육", "상담"), ["서비스·교육", "엔터·미디어"]),
    (("회계", "경리", "컨설턴트", "경영 기획", "헤드헌터"), ["증권", "은행·금융지주"]),
    (("미디어", "콘텐츠"), ["엔터·미디어", "인터넷·게임"]), (("경비원", "청소"), ["은행·금융지주", "리츠·인프라", "통신·IT서비스"]),
    (("텔레마케터", "상담원"), ["통신·IT서비스", "보험·카드"]), (("법률", "법무", "행정", "비서", "사무"), ["보험·카드", "은행·금융지주"]),
]
RISK_AFFINITY = {"공격": ["2차전지", "바이오·제약", "조선", "방산·우주", "인터넷·게임"],
                 "안정": ["은행·금융지주", "통신·IT서비스", "에너지·유틸리티", "리츠·인프라", "보험·카드"]}


# ─────────────────────────────────────────────────────────────
# 기업 기준 (DB 조회 전용)
# ─────────────────────────────────────────────────────────────
# 가격은 수정주가(adjusted_prices_daily) — 원주가는 액면분할 전 가격이 섞여 52주 범위가 틀어진다(대한제분 10,670~161,300).
# 시가총액만 prices_daily에서 읽는다
REF_SQL = """
with last as (select max(trade_date) d from adjusted_prices_daily),
w as (select a.symbol, a.trade_date, a.close,
      row_number() over (partition by a.symbol order by a.trade_date desc) rn
      from adjusted_prices_daily a, last where a.trade_date > last.d - 366),
m as (select distinct on (symbol) symbol, market_cap from prices_daily order by symbol, trade_date desc)
select s.symbol, s.name, max(w.close) filter (where rn = 1) close, max(m.market_cap) mcap,
       max(w.trade_date) filter (where rn = 1) as_of, max(w.close) high_52w, min(w.close) low_52w,
       round(avg(w.close) filter (where rn <= 20)) ma20, round(avg(w.close) filter (where rn <= 60)) ma60
from stocks s join w using (symbol) left join m using (symbol) where s.name = any(%s) group by s.symbol, s.name
"""
DISC_SQL = """
select symbol, rcept_dt, title, rcept_no from (
  select symbol, rcept_dt, title, rcept_no, row_number() over (partition by symbol order by rcept_dt desc, rcept_no desc) rn
  from disclosures where symbol = any(%s) and rcept_dt >= %s) t where rn <= 5
"""


def _connect():
    import psycopg
    load_env()
    url = read_database_url()
    if not url:
        raise SystemExit(f"{FAIL} READONLY_DATABASE_URL(또는 DATABASE_URL)이 없습니다.")
    url = re.sub(r"^postgres(ql)?(\+\w+)?://", "postgresql://", url)
    return psycopg.connect(url, connect_timeout=5, options="-c default_transaction_read_only=on -c statement_timeout=120s")


def load_disclosures(c, by_sym: dict) -> dict:
    out = collections.defaultdict(list)
    for sym, dt, title, no in c.execute(DISC_SQL, (list(by_sym), "20260501")).fetchall():
        out[by_sym[sym.strip()]].append({"rcept_no": str(no).strip(), "rcept_dt": str(dt), "title": " ".join(title.split())})
    return out


def refresh_disclosures(ref: dict) -> dict:
    """가격은 그대로 두고 공시 목록만 다시 읽는다 (접수번호 추가용). 이미 쓴 메모의 가격 기준이 바뀌지 않게."""
    with _connect() as c:
        disc = load_disclosures(c, {v["symbol"]: k for k, v in ref["companies"].items()})
    for name, v in ref["companies"].items():
        v["disclosures"] = disc.get(name, [])
    return ref


def make_ref() -> dict:
    with _connect() as c:
        rows = c.execute(REF_SQL, (COMPANY_LIST,)).fetchall()
        comp = {}
        for sym, name, close, mcap, as_of, hi, lo, ma20, ma60 in rows:
            comp[name] = {"symbol": sym.strip(), "industry": INDUSTRY_OF[name], "close": float(close), "mcap": float(mcap or 0),
                          "high_52w": float(hi), "low_52w": float(lo), "ma20": float(ma20), "ma60": float(ma60),
                          "disclosures": []}
            as_of_all = str(as_of)
        disc = load_disclosures(c, {v["symbol"]: k for k, v in comp.items()})
        for name in comp:
            comp[name]["disclosures"] = disc.get(name, [])
    missing = [n for n in COMPANY_LIST if n not in comp]
    if missing:
        raise SystemExit(f"{FAIL} DB에 가격이 없는 기업: {missing}")
    return {"as_of": as_of_all, "source": "prices_daily·disclosures (팀 DB, 조회 전용)", "companies": comp}


# ─────────────────────────────────────────────────────────────
# 설계
# ─────────────────────────────────────────────────────────────
def quotas(ref: dict, total: int, rng: random.Random) -> dict:
    """시총 순위로 기업별 메모 수: 1~20위 8, 21~60위 5, 61~120위 3, 121위~1조 2, 1조 미만 1(일부 2) — 합계를 total에 맞춘다."""
    ranked = sorted(COMPANY_LIST, key=lambda n: -ref["companies"][n]["mcap"])
    q = {}
    for i, n in enumerate(ranked):
        big = ref["companies"][n]["mcap"] >= 1e12
        q[n] = 8 if i < 20 else 5 if i < 60 else 3 if i < 120 else 2 if big else 1
    small = [n for n in ranked if q[n] == 1]
    rng.shuffle(small)
    diff = total - sum(q.values())
    for n in small[:max(diff, 0)]:
        q[n] += 1
    if diff < 0:
        for n in [n for n in ranked if q[n] > 2][:(-diff)]:
            q[n] -= 1
    return q


def affinity(p: dict) -> dict:
    w = {ind: 1.0 for ind in INDUSTRIES}
    for keys, inds in JOB_AFFINITY:
        if any(k in p["occupation"] for k in keys):
            for ind in inds:
                w[ind] += 3
    for k, inds in RISK_AFFINITY.items():
        if k in p["risk_profile"]:
            for ind in inds:
                w[ind] += 2
    return w


def make_design(cfg: dict, ref: dict) -> dict:
    people = sorted(load_personas(cfg), key=lambda x: x["persona_id"])
    rng = random.Random(SEED)
    n_chat = sum(KIND_TYPES["잡담"].values())
    q = quotas(ref, len(people) * SLOTS - n_chat, rng)
    left = dict(q)
    chat_people = set(rng.sample([p["persona_id"] for p in people], n_chat))
    # 1) 사람마다 보유·관심 종목(포트폴리오)을 고르고 슬롯에 나눈다
    plan = {}
    for p in rng.sample(people, len(people)):
        pid, aff = p["persona_id"], affinity(p)
        k = SLOTS - (pid in chat_people)
        m = min(rng.randint(5, 8), k)
        cands = [c for c in COMPANY_LIST if left[c] > 0]
        port: list[str] = []
        while len(port) < m and cands:
            weights = [left[c] * aff[INDUSTRY_OF[c]] for c in cands]
            c = rng.choices(cands, weights=weights)[0]
            port.append(c)
            cands.remove(c)
        comps = list(port)
        while len(comps) < k:
            # 같은 기업은 한 사람에 3개까지. 남은 몫이 없으면 포트폴리오에 새 기업을 더한다
            opts = [x for x in port if comps.count(x) < PER_PERSON_MAX and left[x] - comps.count(x) > 0]
            if not opts and cands:
                c = rng.choices(cands, weights=[left[x] * aff[INDUSTRY_OF[x]] for x in cands])[0]
                port.append(c)
                cands.remove(c)
            else:
                opts = opts or [x for x in port if comps.count(x) < PER_PERSON_MAX]
                c = max(opts, key=lambda x: (left[x] - comps.count(x), rng.random()))
            comps.append(c)
        for c in comps:
            left[c] -= 1
        plan[pid] = comps
    # 2) 한 번도 안 쓰인 기업은 가장 많이 쓰인 기업 슬롯과 바꾼다 (업종이 맞는 사람 우선)
    used = collections.Counter(c for cs in plan.values() for c in cs)
    for c in [c for c in COMPANY_LIST if not used[c]]:
        best = max(((pid, i) for pid, cs in plan.items() for i, x in enumerate(cs)),
                   key=lambda t: (used[plan[t[0]][t[1]]] - q[plan[t[0]][t[1]]], plan[t[0]].count(plan[t[0]][t[1]]),
                                  affinity(next(p for p in people if p["persona_id"] == t[0]))[INDUSTRY_OF[c]]))
        old = plan[best[0]][best[1]]
        plan[best[0]][best[1]] = c
        used[old] -= 1
        used[c] += 1
    # 3) 종류·주 유형: 잡담은 정해진 사람에게 1개, 나머지 950개는 종류 풀을 섞어 나눈다
    pool = [(kind, t) for kind in KINDS if kind != "잡담" for t, n in KIND_TYPES[kind].items() for _ in range(n)]
    rng.shuffle(pool)
    chat_pool = [t for t, n in KIND_TYPES["잡담"].items() for _ in range(n)]
    rng.shuffle(chat_pool)
    young = {p["persona_id"] for p in people if int(p["age"]) <= PROFANITY_AGE_MAX}
    persons, price_flip = {}, 0
    for p in people:
        pid = p["persona_id"]
        comps = plan[pid]
        holdings = set(comps[:max(1, len(set(comps)) // 2)])
        slots_kind = [pool.pop() for _ in comps]
        # 이벤트는 최근 공시가 있는 기업에만
        for i, (kind, t) in enumerate(slots_kind):
            if kind == "이벤트" and not ref["companies"][comps[i]]["disclosures"]:
                j = next((j for j, (kk, _) in enumerate(pool) if kk != "이벤트"), None)
                if j is not None:
                    slots_kind[i], pool[j] = pool[j], slots_kind[i]
        recs = []
        for i, (c, (kind, t)) in enumerate(zip(comps, slots_kind), 1):
            info = ref["companies"][c]
            rec = {"slot": i, "kind": kind, "company": c, "industry": INDUSTRY_OF[c],
                   "status": "보유" if c in holdings else "관심", "primary_type": t,
                   "call_names": call_names(c),
                   "trigger": rng.choice(THEME_TRIGGERS if kind == "테마" else EVENT_TRIGGERS if kind == "이벤트"
                                         else TRIGGERS[t])}
            if kind == "비교":
                same = [x for x in INDUSTRIES[INDUSTRY_OF[c]].split() if x in INDUSTRY_OF and x != c]
                rec["other_company"] = rng.choice(same) if same else rng.choice(COMPANY_LIST)
            if kind == "테마":
                rec["theme"] = INDUSTRY_OF[c]
            if kind == "이벤트":
                rec["disclosures"] = info["disclosures"][:3]
            if t in PRICE_TYPES:
                rec["price"] = "절대" if price_flip % 2 == 0 else "상대"
                price_flip += 1
            recs.append(rec)
        if pid in chat_people:
            recs.append({"slot": SLOTS, "kind": "잡담", "company": None, "industry": None, "status": None,
                         "primary_type": chat_pool.pop(), "call_names": [], "trigger": "그냥"})
        # 길이: 사람 성향만큼 짧게, 나머지 2~3줄. 잡담 B7은 항상 짧게
        n_short = SHORT_PER_PERSON[p["w_length"]]
        order = sorted(recs, key=lambda r: (r["primary_type"] != "B7", r["kind"] != "잡담", rng.random()))
        for j, r in enumerate(order):
            r["length"] = "짧게" if j < n_short else "길게"
        if pid in young:
            for r in rng.sample(recs, round(len(recs) * SWEAR_SHARE)):
                if r["primary_type"] != "B7":
                    r["swear"] = True
        persons[pid] = sorted(recs, key=lambda r: r["slot"])
    batches = read_json(rpath(DIRECT_DIR) / "design.json")["batches"]
    return {"seed": SEED, "batches": batches, "persons": persons, "quotas": q,
            "kind_types": KIND_TYPES, "short_per_person": SHORT_PER_PERSON,
            "source": "kospi.make_design — 배치는 memos_direct 설계와 같음, 기업은 kospi_companies.py"}


ROUTINE = ("분기보고서", "반기보고서", "사업보고서", "기업설명회")


def revise_design(design: dict, ref: dict, cfg: dict) -> dict:
    """v2 (2026-11-05 검토 반영): B10·B4·B6 추가, 이벤트 40개는 DB에 없는 이벤트, 나머지 이벤트는 공시 1건(event_ref)에 묶기,
    35세 이상 약한 비속어 25개. 이미 쓴 배치 1도 같은 규칙으로 다시 쓴다."""
    if design.get("revision") == "v2":
        return design
    rng = random.Random(f"{SEED}:v2")
    people = {p["persona_id"]: p for p in load_personas(cfg)}
    slots = [(pid, r) for pid, rs in sorted(design["persons"].items()) for r in rs]
    a1 = [x for x in slots if x[1]["kind"] == "일반" and x[1]["primary_type"] == "A1"]
    c3 = [x for x in slots if x[1]["kind"] == "비교"]
    rng.shuffle(a1)
    rng.shuffle(c3)
    picks = {"B10": c3[:8] + a1[:7], "B4": a1[7:19], "B6": a1[19:29]}
    for t, xs in picks.items():
        for pid, r in xs:
            for k in ("theme", "price", "disclosures"):
                r.pop(k, None)
            r["primary_type"] = t
            if t == "B10":
                r["kind"] = "다른종목"
                pool = [c for c in COMPANY_LIST if c != r["company"] and c not in {x["company"] for x in design["persons"][pid]}]
                same = [c for c in pool if INDUSTRY_OF[c] == r["industry"]]
                r["other_company"] = rng.choice(same if same and rng.random() < 0.5 else pool)
                r["trigger"] = rng.choice(["커뮤니티 글 보고", "뉴스 보고", "지인 얘기 듣고"])
            else:
                r["kind"] = "일반"
                r.pop("other_company", None)
                r["trigger"] = "그냥" if t == "B4" else rng.choice(["문자 받고", "커뮤니티 글 보고", "단톡방 보다가"])
    events = [x for x in slots if x[1]["kind"] == "이벤트"]
    rng.shuffle(events)
    for i, (pid, r) in enumerate(events):
        disc = ref["companies"][r["company"]]["disclosures"]
        if i < EVENT_NOT_IN_DB or not disc:
            r["event_in_db"] = False
            r["event_ref"] = None
            r["event_hint"] = "아직 안 나온 공시" if i % 2 == 0 else "들은 소문"
        else:
            main = [d for d in disc if not any(w in d["title"] for w in ROUTINE)] or disc
            r["event_in_db"] = True
            r["event_ref"] = rng.choice(main[:3])
        r.pop("disclosures", None)
    older = [pid for pid, p in people.items() if int(p["age"]) > PROFANITY_AGE_MAX]
    weight = {pid: 3 if ("단타" in people[pid]["invest_style"] or "공격" in people[pid]["risk_profile"]) else 1 for pid in older}
    chosen: list[str] = []
    while len(chosen) < OLDER_SWEAR:
        pid = rng.choices(older, weights=[weight[x] for x in older])[0]
        if pid not in chosen:
            chosen.append(pid)
    for pid in chosen:
        cand = [r for r in design["persons"][pid] if r["primary_type"] != "B7" and not r.get("swear")]
        rng.choice(cand)["swear"] = "약하게"
    for pid, rs in design["persons"].items():
        for r in rs:
            if r.get("swear") is True:
                r["swear"] = "세게"
    design["revision"] = "v2"
    design["revision_note"] = ("B10 15(C3 8·A1 7)·B4 12·B6 10 추가, 이벤트 40개 DB 밖, 이벤트마다 event_ref 1건, "
                               "35세 이상 약한 비속어 25개")
    return design


# ─────────────────────────────────────────────────────────────
# 작성용 요약 · 조립 · 검사
# ─────────────────────────────────────────────────────────────
def abs_prices(text: str) -> list[float]:
    """절대 가격: '원'이 붙은 수(100원 이상, 싼 종목 '5천원'도), 단위 없는 수는 1만 이상('2만6천', '110만')."""
    return [n["value"] for n in parse_numbers(text)
            if (n["kind"] == "won" and n["value"] >= 100) or (n["kind"] == "plain" and n["value"] >= 10_000)]


def won(v: float) -> str:
    return f"{v:,.0f}"


def brief(design: dict, batch: int, cfg: dict, ref: dict) -> str:
    people = {p["persona_id"]: p for p in load_personas(cfg)}
    short = collections.defaultdict(list)
    for r in read_json_lines(rpath(DIRECT_DIR) / "memos.jsonl"):
        short[r["persona_id"]].append(r["memo_body_clean"])
    lines = []
    for pid in design["batches"][batch - 1]:
        p = people[pid]
        nem = p.get("nemotron") or {}
        lines += [f"## {pid} · {p['age']}세 {p['sex']} · {p['province_full']} · {p['occupation']}"
                  f"{'(' + p['unemployed_type'] + ')' if p.get('unemployed_type') else ''} · {p['family_type']}",
                  f"- 경력 {p['experience_years']}년({term_tier(p)}) · {p['invest_style']} · {p['risk_profile']} · "
                  f"{p['investment_horizon']} · 목적 {p['fund_purpose']} · 정보 {p['info_source']}",
                  f"- 말투: 반말 {p['w_banmal']} · ㅋㅋ {p['w_laugh']} · 말줄임표 {p['w_ellipsis']} · 길이 {p['w_length']}",
                  f"- 서술: {first_sentences(nem.get('persona'), 2)}",
                  f"- 일: {first_sentences(nem.get('professional_persona'), 1)}",
                  "- 예전 메모: " + " | ".join(short[pid][i] for i in (0, 3, 6) if i < len(short[pid]))]
        for s in design["persons"][pid]:
            head = f"  {s['slot']}. [{s['kind']}·{s['length']}{'·비속어 ' + s['swear'] if s.get('swear') else ''}] {s['primary_type']}"
            if s["company"]:
                info = ref["companies"][s["company"]]
                head += f" {s['company']}({s['industry']}·{s['status']}) 이름 {'/'.join(s['call_names'])} · 계기 {s['trigger']}"
                if s.get("price"):
                    head += (f" · 가격 {s['price']}: 종가 {won(info['close'])} · 52주 {won(info['low_52w'])}~{won(info['high_52w'])}"
                             f" · 20일 {won(info['ma20'])} · 60일 {won(info['ma60'])}")
            else:
                head += " (기업 없음)"
            if s.get("other_company"):
                head += f" · {'다른 종목(보드 기업은 쓰지 않음)' if s['primary_type'] == 'B10' else '비교'} {s['other_company']}"
            if s.get("theme"):
                head += f" · 테마 {s['theme']}"
            lines.append(head)
            if s["kind"] == "이벤트":
                if s.get("event_ref"):
                    e = s["event_ref"]
                    lines.append(f"     공시 {e['rcept_dt']} {e['title']} ({e['rcept_no']}) — 제목 그대로 쓰지 말 것")
                else:
                    lines.append(f"     DB에 없는 이벤트: {s.get('event_hint')}")
        lines.append("")
    return "\n".join(lines)


def price_basis(sents: list[dict], ref: dict) -> dict | None:
    ps = [x for x in sents if x["intended_type"] in PRICE_TYPES]
    if not ps:
        return None
    kinds = ["절대" if abs_prices(x["text"]) else ("상대" if RELATIVE_PRICE.search(x["text"]) else "가격 없음") for x in ps]
    return {"as_of": ref["as_of"], "source": ref["source"], "kinds": kinds}


def assemble(design: dict, batch: int, draft: dict, ref: dict) -> list[dict]:
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
            need = list(d["need"]) if "need" in d else sorted({n for x in sents for n in DEFAULT_NEED.get(x["intended_type"], [])})
            if any(x["intended_type"] in ("A2", "C1") for x in sents) and "주가·거래" not in need:
                need.append("주가·거래")
            rows.append({
                "memo_id": f"{pid}-K{d['slot']:02d}", "persona_id": pid, "slot": d["slot"], "batch": batch,
                "kind": s["kind"], "length": s["length"], "company_primary": s["company"],
                "symbol": ref["companies"][s["company"]]["symbol"] if s["company"] else None,
                "industry": s["industry"], "companies_mentioned": mentions(body),
                "other_company": s.get("other_company"), "theme": s.get("theme"),
                "primary_type": s["primary_type"], "mixed": len({x["intended_type"] for x in sents}) > 1,
                "memo_title": "", "memo_body": body, "memo_body_clean": body, "sentences": sents,
                "trigger": d.get("trigger", s["trigger"]), "data_need": need,
                "price_basis": price_basis(sents, ref), "topic_unverified": bool(d.get("unv")),
                "profanity": bool(PROFANITY.search(body)), "generator": GENERATOR, "review_status": "pending",
            })
            if s["kind"] == "이벤트":
                rows[-1]["event_in_db"] = s.get("event_in_db")
                rows[-1]["event_ref"] = s.get("event_ref")
    return rows


def aliases_used(text: str, names: list[str]) -> set[str]:
    low = text.lower()
    return {n for n in names if n.lower() in low}


def check_batch(design: dict, batch: int, rows: list[dict], earlier: list[dict], ref: dict, people: dict,
                old_memos: dict, lex=None) -> dict:
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
        lenkey = "짧게" if p["w_length"] == "짧게" else "기타"
        endings = collections.Counter(e for r in got.values() for x in r["sentences"] if (e := ending_of(x["text"])))
        fails += [f"{pid}: '{k}' 끝맺음 {v}회 > {ENDING_PERSON_MAX}" for k, v in endings.items() if v > ENDING_PERSON_MAX]
        names = sorted({a for s in want.values() for a in s["call_names"][1:]}, key=len, reverse=True)
        alias_counts = collections.Counter(a for r in got.values() for a in aliases_used(r["memo_body_clean"], names))
        fails += [f"{pid}: 별명 '{a}' 메모 {c}개 > {ALIAS_MAX}" for a, c in alias_counts.items() if c > ALIAS_MAX]
        all_text = " ".join(r["memo_body_clean"] for r in got.values())
        tier, expert, basic = term_tier(p), find_terms(all_text, EXPERT_TERMS), find_terms(all_text, BASIC_TERMS)
        terms.append({"persona_id": pid, "experience_years": p["experience_years"], "occupation": p["occupation"],
                      "tier": tier, "expert": expert, "basic": basic})
        if tier != "전문" and expert:
            fails.append(f"{pid}({tier}·경력 {p['experience_years']}년): 전문용어 {expert}")
        for slot, r in sorted(got.items()):
            s = want.get(slot)
            if not s:
                continue
            tag = f"{r['memo_id']}({s['kind']}·{s['primary_type']})"
            types = [x["intended_type"] for x in r["sentences"]]
            body = r["memo_body_clean"]
            n_lines = body.count("\n") + 1
            if s["length"] == "짧게":
                if n_lines != 1:
                    fails.append(f"{tag}: 짧은 메모인데 {n_lines}줄")
                if len(body) > SHORT_CHARS[lenkey]:
                    fails.append(f"{tag}: 짧은 메모 {len(body)}자 > {SHORT_CHARS[lenkey]}자 (길이 {p['w_length']})")
            else:
                lo, hi = LONG_CHARS[lenkey]
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
            if s["primary_type"] == "B10":
                if s["company"] in r["companies_mentioned"]:
                    fails.append(f"{tag}: 다른 종목만 쓰는 메모인데 보드 기업 {s['company']} 언급")
            elif s["company"]:
                if s["company"] not in r["companies_mentioned"]:
                    fails.append(f"{tag}: 배정 기업 {s['company']} 언급 없음 (찾은 것 {r['companies_mentioned']})")
            elif r["companies_mentioned"]:
                fails.append(f"{tag}: 잡담인데 기업 언급 {r['companies_mentioned']}")
            if s.get("other_company") and s["other_company"] not in r["companies_mentioned"]:
                fails.append(f"{tag}: 비교 기업 {s['other_company']} 언급 없음")
            fails += [f"{tag}: {x}" for x in style_problems(body)]
            prof, strong = PROFANITY.search(body), STRONG_SWEAR.search(body)
            if strong and int(p["age"]) > PROFANITY_AGE_MAX:
                fails.append(f"{tag}: {p['age']}세인데 센 비속어 '{strong.group(0)}' (35세 이상은 약한 표현만)")
            if s.get("swear") and not prof:
                fails.append(f"{tag}: 비속어 슬롯인데 비속어 없음")
            if s["kind"] == "이벤트":
                if "event_ref" not in r:
                    fails.append(f"{tag}: 이벤트인데 event_ref 키 없음")
                elif s.get("event_in_db") and not r["event_ref"]:
                    fails.append(f"{tag}: DB 이벤트인데 event_ref 없음")
                elif not s.get("event_in_db") and r["event_ref"]:
                    fails.append(f"{tag}: DB 밖 이벤트인데 event_ref 있음")
                if r.get("event_ref"):
                    a, b = re.sub(r"\s", "", body), re.sub(r"[\s()]", "", r["event_ref"]["title"])
                    m = difflib.SequenceMatcher(None, a, b, autojunk=False).find_longest_match(0, len(a), 0, len(b))
                    if m.size >= TITLE_OVERLAP_MIN:
                        warns.append(f"{tag}: 공시 제목과 '{a[m.a:m.a + m.size]}' 그대로 겹침 — 사람 말로 풀어 쓰기")
            for x in r["sentences"]:
                if x["intended_type"] not in PRICE_TYPES or not s["company"]:
                    continue
                info = ref["companies"][s["company"]]
                vals = abs_prices(x["text"])
                for v in vals:
                    if not info["low_52w"] <= v <= info["high_52w"]:
                        fails.append(f"{tag}: 가격 {won(v)}원이 52주 범위({won(info['low_52w'])}~{won(info['high_52w'])}) 밖")
                if x["intended_type"] in ("A2", "C1") and not vals and RELATIVE_PRICE.search(x["text"]) \
                        and x["expected_decision"] != "확인 필요":
                    fails.append(f"{tag}: 상대 가격 조건인데 라벨이 '{x['expected_decision']}' (v0.2 기준 확인 필요)")
                if x["intended_type"] in ("A2", "C1") and vals and x["expected_decision"] == "확인 필요":
                    fails.append(f"{tag}: 절대 가격 조건인데 라벨이 확인 필요")
            if s.get("price") == "절대" and s["primary_type"] in ("A2", "C1") and \
                    not any(abs_prices(x["text"]) for x in r["sentences"] if x["intended_type"] in PRICE_TYPES):
                warns.append(f"{tag}: 절대 가격 슬롯인데 절대 가격이 없음")
            for old in old_memos.get(pid, []):
                ratio = difflib.SequenceMatcher(None, body, old).ratio()
                if ratio >= SIMILARITY:
                    fails.append(f"{tag}: 예전 메모 '{old}'와 유사도 {ratio:.2f}")
            if lex is not None and s["company"]:
                warns += segment_warnings(r, lex, tag)
        bodies = sorted(got.values(), key=lambda r: r["slot"])
        for i in range(len(bodies)):
            for j in range(i + 1, len(bodies)):
                ratio = difflib.SequenceMatcher(None, bodies[i]["memo_body_clean"], bodies[j]["memo_body_clean"]).ratio()
                if ratio >= SIMILARITY:
                    fails.append(f"{pid}: 슬롯 {bodies[i]['slot']}·{bodies[j]['slot']} 유사도 {ratio:.2f}")
    warns += [f"반복 표현 '{g}' — 이번 배치 {k}회, 다른 배치 {m}회" for g, k, m in repeated_phrases(rows, earlier)]
    return {"fails": fails, "warns": warns, "terms": terms, "endings": batch_endings, "unverified": unv}


def segment_warnings(r: dict, lex, tag: str) -> list[str]:
    """팀 판정 파이프라인의 문장 분리·규칙 판정과 라벨이 어긋나는지 (실패가 아니라 검수 참고용)."""
    from pipelines.tracking.judge import judge_memo
    from pipelines.tracking.segment import split_sentences
    segs = [g.text for g in split_sentences(r["memo_body"], lex)]
    if len(segs) != len(r["sentences"]):
        return [f"{tag}: 문장 분리 {len(segs)}개 ≠ 라벨 {len(r['sentences'])}개 {segs}"]
    rule_ko = {"normal": "추적", "partial": "일부 추적", "full_fallback": "추적 안 함", "needs_confirmation": "확인 필요"}
    out = []
    for j, x in zip(judge_memo(r["memo_body"], r["symbol"], lex), r["sentences"]):
        if j.judged_by == "rule" and rule_ko[j.decision] != x["expected_decision"]:
            out.append(f"{tag}: 규칙 판정 {j.category}/{rule_ko[j.decision]} ≠ 라벨 {x['intended_type']}/{x['expected_decision']}"
                       f" '{x['text']}'")
    return out


def report(rows: list[dict], result: dict, title: str) -> str:
    sents = [x for r in rows for x in r["sentences"]]
    lines = [f"# {title}", "",
             f"- 메모 {len(rows)}개 · 문장 {len(sents)}개 (메모당 {len(sents) / (len(rows) or 1):.1f}) · "
             f"평균 {sum(len(r['memo_body_clean']) for r in rows) / (len(rows) or 1):.0f}자 · "
             f"기업 {len({r['company_primary'] for r in rows if r['company_primary']})}곳",
             f"- {OK if not result['fails'] else FAIL} 실패 {len(result['fails'])}건 · {WARN} 참고 {len(result['warns'])}건", ""]
    lines += table("종류", collections.Counter(r["kind"] for r in rows), KINDS + ["다른종목"])
    lines += table("길이", collections.Counter(r["length"] for r in rows), ["짧게", "길게"])
    lines += table("주 유형 (메모 기준)", collections.Counter(r["primary_type"] for r in rows), ALL_TYPES)
    lines += table("문장 유형 (문장 기준)", collections.Counter(x["intended_type"] for x in sents), ALL_TYPES)
    lines += table("기대 판정 (문장 기준)", collections.Counter(x["expected_decision"] for x in sents),
                   ["추적", "일부 추적", "추적 안 함", "확인 필요"])
    lines += table("가격 문장 (A2·C1·C4)", collections.Counter(k for r in rows for k in (r["price_basis"] or {}).get("kinds", [])),
                   ["절대", "상대", "가격 없음"])
    lines += table("업종", collections.Counter(r["industry"] for r in rows if r["industry"]))
    lines += table("줄 수", collections.Counter(f"{r['memo_body_clean'].count(chr(10)) + 1}줄" for r in rows), ["1줄", "2줄", "3줄"])
    lines += table("끝맺음 (알림·보자·볼 것·지켜보기·확인)", result["endings"], list(ENDINGS))
    lines += [f"- 들은 소식(topic_unverified): {result['unverified']}개",
              f"- 비속어 섞인 메모: {sum(r['profanity'] for r in rows)}개 (센 표현 {sum(bool(STRONG_SWEAR.search(r['memo_body_clean'])) for r in rows)}개는 {PROFANITY_AGE_MAX}세 이하만)",
              f"- 이벤트: DB 공시 {sum(r.get('event_in_db') is True for r in rows)}개 · DB 밖 {sum(r.get('event_in_db') is False for r in rows)}개",
              f"- 두 기업 이상 언급: {sum(len(r['companies_mentioned']) >= 2 for r in rows)}개", "",
              "### 페르소나별 용어", "", "| 페르소나 | 경력 | 직업 | 수준 | 전문용어 | 기본 용어 |", "|---|---:|---|---|---:|---:|"]
    lines += [f"| {t['persona_id']} | {t['experience_years']}년 | {t['occupation']} | {t['tier']} | "
              f"{len(t['expert'])} {'(' + ', '.join(t['expert']) + ')' if t['expert'] else ''} | {len(t['basic'])} |"
              for t in result["terms"]]
    lines += ["", "## 실패", ""] + [f"- {x}" for x in result["fails"]] + ["", "## 참고", ""] + [f"- {x}" for x in result["warns"]]
    return "\n".join(lines) + "\n"


def old_by_person() -> dict:
    out = collections.defaultdict(list)
    for r in read_json_lines(rpath(DIRECT_DIR) / "memos.jsonl"):
        out[r["persona_id"]].append(r["memo_body_clean"])
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
    ap.add_argument("cmd", choices=["ref", "design", "revise", "brief", "build", "summary", "typo"])
    ap.add_argument("--batch", type=int, default=1)
    ap.add_argument("--disclosures-only", action="store_true", help="ref: 가격은 두고 공시 목록만 다시 읽기")
    args = ap.parse_args(argv)
    cfg = load_config()
    out = rpath(OUT_DIR)
    if args.cmd == "ref":
        ref = refresh_disclosures(read_json(out / "company_ref.json")) if args.disclosures_only else make_ref()
        write_json(out / "company_ref.json", ref)
        print(f"{OK} {out / 'company_ref.json'} · 기업 {len(ref['companies'])}곳 · 기준일 {ref['as_of']}")
        return 0
    ref = read_json(out / "company_ref.json")
    if args.cmd == "design":
        if (out / "design.json").exists():
            print(f"{WARN} design.json이 이미 있습니다. 다시 만들려면 직접 지운 뒤 실행하세요.")
            return 1
        write_json(out / "design.json", make_design(cfg, ref))
        print(f"{OK} {out / 'design.json'}")
        return 0
    design = read_json(out / "design.json")
    if args.cmd == "revise":
        write_json(out / "design.json", revise_design(design, ref, cfg))
        print(f"{OK} 설계 v2: {design['revision_note']}")
        return 0
    paths = [out / f"batch_{b:02d}.jsonl" for b in range(1, len(design["batches"]) + 1)]
    if args.cmd == "brief":
        print(brief(design, args.batch, cfg, ref))
        return 0
    if args.cmd == "typo":
        return apply_typos(paths, out, cfg)
    if args.cmd == "summary":
        return summarize(design, paths, out, cfg, ref)
    draft = read_json(out / "drafts" / f"batch_{args.batch:02d}.json")
    rows = assemble(design, args.batch, draft, ref)
    earlier = [r for i, p in enumerate(paths, 1) if i != args.batch and p.exists() for r in read_json_lines(p)]
    people = {p["persona_id"]: p for p in load_personas(cfg)}
    result = check_batch(design, args.batch, rows, earlier, ref, people, old_by_person(), load_lex())
    write_jsonl(out / f"batch_{args.batch:02d}.jsonl", rows)
    write_jsonl(out / "memos.jsonl", [r for p in paths if p.exists() for r in read_json_lines(p)])
    text = report(rows, result, f"배치 {args.batch} 검사 결과")
    write_text(out / "checks" / f"batch_{args.batch:02d}.md", text)
    print(text)
    return 1 if result["fails"] else 0


def summarize(design: dict, paths: list[Path], out: Path, cfg: dict, ref: dict) -> int:
    """1,000개 전체를 배치 검사 기준으로 다시 돌려 summary.md에 쓴다. 숫자는 jsonl에서 다시 센다."""
    rows = [r for p in paths if p.exists() for r in read_json_lines(p)]
    people = {p["persona_id"]: p for p in load_personas(cfg)}
    old, lex = old_by_person(), load_lex()
    merged = {"fails": [], "warns": [], "terms": [], "endings": collections.Counter(), "unverified": 0}
    for b in range(1, len(paths) + 1):
        part = [r for r in rows if r["batch"] == b]
        if not part:
            continue
        res = check_batch(design, b, part, [r for r in rows if r["batch"] != b], ref, people, old, lex)
        for k in ("fails", "warns", "terms"):
            merged[k] += res[k]
        merged["endings"] += res["endings"]
        merged["unverified"] += res["unverified"]
    text = report(rows, merged, f"코스피 다양화 메모 {len(rows)}개 전체 통계")
    write_text(out / "summary.md", text)
    print(text)
    return 1 if merged["fails"] else 0


def apply_typos(paths: list[Path], out: Path, cfg: dict) -> int:
    """1,000개를 다 쓴 뒤 한 번: memo_body_clean(원문, 라벨 기준)에 페르소나 오타율만큼 오타를 넣어 memo_body에 쓴다."""
    from . import typo
    typo._PROTECTED = sorted(set(typo._PROTECTED) | protected_words(), key=len, reverse=True)  # 391곳 이름·별명도 보호
    people = {p["persona_id"]: p for p in load_personas(cfg)}
    missing = [p.name for p in paths if not p.exists()]
    if missing:
        print(f"{FAIL} 아직 없는 배치: {missing} — 1,000개를 다 쓴 뒤 실행하세요.")
        return 1
    all_rows, changed = [], 0
    for path in paths:
        rows = read_json_lines(path)
        for r in rows:
            rate = float(people[r["persona_id"]]["w_typo_rate"] or 0)
            r["memo_body"] = typo.inject(r["memo_body_clean"], rate, r["memo_id"])
            r["typo_applied"] = r["memo_body"] != r["memo_body_clean"]
            changed += r["typo_applied"]
        write_jsonl(path, rows)
        all_rows += rows
    write_jsonl(out / "memos.jsonl", all_rows)
    print(f"{OK} 오타 주입: {changed}/{len(all_rows)}개 메모 변경 (원문은 memo_body_clean)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
