"""슬롯 설계 — LLM을 부르기 전에 코드로 1,000개 슬롯의 문장 유형·근거 유형·근거 항목·계기를 정한다.

- 인당 10슬롯(3단계 slot_plan.csv의 기업 배정 그대로). 그중 1~2개는 폴백·혼합(B·C, 전체 약 15%), 나머지 8~9개는 추적형(A1~A5)
- 추적형 근거: 공시/뉴스/주가·거래/재무/거시/복합. 복합 33%(지시: 30% 이상), '자료 부족' 10%
- 근거가 모자란 기업은 그 유형을 다른 유형으로 옮기고 adjustments에 기록한다
- sentence_type과 expected_decision_draft는 따로 둔다. 후자는 초안이지 정답이 아니다
  (A→normal, B→full_fallback, C→partial: backend/pipelines/tracking/llm.py DECISION_OF와 같은 규칙)
같은 시드·같은 입력이면 항상 같은 설계가 나온다(random.Random만 사용).
"""

from __future__ import annotations

import math
import random

from .common import COMPANIES

A_WEIGHTS = {"A1": 30, "A2": 20, "A3": 15, "A4": 20, "A5": 15}
BC_TYPES = [f"B{i}" for i in range(1, 11)] + [f"C{i}" for i in range(1, 6)]
SENTENCE_LABEL = {
    "A1": "주제 관찰", "A2": "가격 조건", "A3": "예정 이벤트", "A4": "궁금증", "A5": "투자 가설",
    "B1": "감정", "B2": "지난 매매", "B3": "원칙", "B4": "본인 할 일", "B5": "범위 밖", "B6": "광고·스팸",
    "B7": "의미 없음", "B8": "단순 가격 예측", "B9": "부정·무관심", "B10": "다른 종목만",
    "C1": "조건+행동", "C2": "대상+감정", "C3": "비교", "C4": "예측", "C5": "범위 밖 단어",
}
DECISION_DRAFT = {"A": "normal", "B": "full_fallback", "C": "partial"}
EVIDENCE_TYPES = ["공시", "뉴스", "주가·거래", "재무", "거시"]
SINGLE_WEIGHTS = {"공시": 22, "뉴스": 30, "주가·거래": 22, "재무": 18, "거시": 8}
PAIRS = [("뉴스", "주가·거래"), ("공시", "재무"), ("재무", "주가·거래"), ("거시", "주가·거래"), ("뉴스", "재무"),
         ("공시", "주가·거래"), ("뉴스", "거시")]
# 문장 유형별로 말이 되는 근거 (A2 가격 조건은 주가가 꼭 들어간다, A3 예정 이벤트는 공시·뉴스·재무)
SINGLE_ALLOWED = {"A2": {"주가·거래"}, "A3": {"공시", "뉴스", "재무"}}
PAIR_REQUIRES = {"A2": "주가·거래"}
C_EVIDENCE = {"C1": ["주가·거래"], "C2": ["뉴스", "주가·거래"], "C3": ["주가·거래", "뉴스"], "C4": ["재무", "주가·거래"],
              "C5": ["뉴스", "공시"]}
CALL_NAMES = {"삼성전자": ["삼전", "삼성전자", "삼성"], "SK하이닉스": ["하닉", "하이닉스", "SK하이닉스"],
              "NAVER": ["네이버", "naver", "NAVER"], "KB금융": ["KB", "국민은행", "KB금융"]}
OTHER_FOR = {"삼성전자": ["SK하이닉스", "애플", "TSMC"], "SK하이닉스": ["삼성전자", "엔비디아", "마이크론"],
             "NAVER": ["카카오", "구글", "크래프톤"], "KB금융": ["신한지주", "하나금융지주", "삼성생명"]}
# '자료 부족' 문항 주제 — DB(공시 발췌·뉴스·재무·주가)로 답하기 어려운 내부 세부 지표 위주
MISSING_TOPICS = {
    "삼성전자": ["파운드리 고객사별 수주 현황", "평택 라인별 가동률", "메모리 재고 일수", "HBM 고객사별 납품 비중",
             "임원 성과급 지급 기준", "해외 공장 인력 재배치 계획"],
    "SK하이닉스": ["HBM 고객사별 단가", "청주 신규 팹 장비 반입 일정", "중국 우시 공장 가동률", "M15X 클린룸 공사 진척률",
               "성과급 PS 지급률", "낸드 자회사 손익 세부"],
    "NAVER": ["웹툰 해외 유료 이용자 수", "커머스 판매자 수수료 인상 효과", "하이퍼클로바X 유료 고객 수", "스마트스토어 판매자 이탈률",
              "치지직 월 이용자 수", "데이터센터 각 세종 가동률"],
    "KB금융": ["부동산 PF 대출 충당금 세부 내역", "부서별 대출 연체율 세부", "자사주 소각 일정 세부", "인도네시아 자회사 부실채권 비율",
             "지점 통폐합 계획", "디지털 뱅킹 월 이용자 수"],
}
INFO_TRIGGER = {"유튜브": "유튜브 보고", "종토방·커뮤니티": "종토방 글 보고", "증권앱 뉴스": "증권앱 뉴스 보다가",
                "공시 직접": "공시 목록 보다가", "지인": "지인 말 듣고", "직장 동료": "직장 동료 말 듣고", "신문·방송": "경제 뉴스 보다가"}
BC_TRIGGER = {"B1": "주가 보다가", "B2": "매매하고 나서", "B3": "손실 보고 나서", "B4": "주말 계획 세우다가", "B5": "그냥 생각나서",
              "B6": "광고 문자 받고", "B7": "그냥", "B8": "주가 보다가", "B9": "뉴스 보고", "B10": "지인 말 듣고",
              "C1": "주가 보다가", "C2": "뉴스 보고", "C3": "다른 종목 보다가", "C4": "실적 보고", "C5": "점심 먹다가"}
LENGTH_BY_PREF = {"짧게": {"짧게": 60, "보통": 30, "길게": 10}, "보통": {"짧게": 30, "보통": 50, "길게": 20},
                  "길게": {"짧게": 15, "보통": 45, "길게": 40}}
AGE_BUCKETS = ["20대", "30대", "40대", "50대", "60대", "70대+"]


def largest_remainder(weights: dict, total: int) -> dict:
    s = sum(weights.values())
    raw = {k: v / s * total for k, v in weights.items()}
    out = {k: int(math.floor(v)) for k, v in raw.items()}
    for k in sorted(raw, key=lambda k: (-(raw[k] - out[k]), list(weights).index(k)))[: total - sum(out.values())]:
        out[k] += 1
    return out


def wpick(rng: random.Random, table: dict):
    keys = [k for k, w in table.items() if w > 0]
    return rng.choices(keys, weights=[table[k] for k in keys])[0]


def trigger_for(parts: list[str], items: list[dict], persona: dict, rng: random.Random) -> str:
    kinds = {i["kind"] for i in items}
    near_high = any(i["kind"] == "high_52w" and "신고가" in i["memo_hint"] for i in items)
    t = []
    for p in parts:
        if p == "주가·거래":
            t.append("거래량 터진 거 보고" if "volume_spike" in kinds else
                     ("신고가 얘기 보고" if near_high else rng.choice(["차트 보다가", "주가 알림 보고"])))
        elif p == "뉴스":
            t.append(INFO_TRIGGER.get(persona.get("info_source"), "뉴스 보고") if persona.get("info_source") in
                     ("지인", "직장 동료", "종토방·커뮤니티", "유튜브") and rng.random() < 0.5 else rng.choice(["뉴스 보고", "기사 보고"]))
        elif p == "공시":
            t.append(rng.choice(["공시 알림 보고", "공시 뜬 거 보고"]))
        elif p == "재무":
            t.append(rng.choice(["실적 발표 보고", "실적 기사 보고"]))
        elif p == "거시":
            t.append(rng.choice(["환율 뉴스 보고", "금리 뉴스 보고"]))
    return " + ".join(dict.fromkeys(t))


def price_levels(pack: dict) -> list[str]:
    """현재가 주변의 둥근 가격 (실제 52주 범위 안). 예: '6만4천원'."""
    p = pack.get("price")
    if not isinstance(p, dict):
        return []
    close, lo, hi = p["close"], p["low_52w"]["price"], p["high_52w"]["price"]
    out = []
    for f in (0.92, 1.06, 0.96, 1.1):
        v = close * f
        mag = 10 ** max(0, len(str(int(v))) - 2)
        v = int(round(v / mag) * mag)
        v = min(max(v, int(lo * 0.9)), int(hi * 1.1))
        out.append(korean_won(v))
    return list(dict.fromkeys(out))


def korean_won(v: int) -> str:
    man, rest = divmod(v, 10_000)
    cheon = rest // 1000
    if man and cheon:
        return f"{man:,}만{cheon}천원"
    if man:
        return f"{man:,}만원"
    return f"{v:,}원"


def pick_pilot(personas: list[dict], size: int, rng: random.Random) -> list[str]:
    """대표 기업 4곳·연령대 6개가 모두 들어가고 투자 경력이 섞이도록 고른다(고정 시드)."""
    order = personas[:]
    rng.shuffle(order)
    chosen: list[dict] = []
    per_company = math.ceil(size / len(COMPANIES))
    while len(chosen) < min(size, len(order)):
        def score(p):
            comp_n = sum(1 for c in chosen if c["primary_company"] == p["primary_company"])
            return ((comp_n < 2) * 10 + (comp_n < per_company) * 4
                    + (p["age_bucket"] not in {c["age_bucket"] for c in chosen}) * 3
                    + (p["experience_band"] not in {c["experience_band"] for c in chosen}) * 2)
        best = max((p for p in order if p not in chosen), key=lambda p: (score(p), -order.index(p)))
        chosen.append(best)
    return sorted(c["persona_id"] for c in chosen)


def build_design(personas: list[dict], packs: dict[str, dict], macro: dict, cfg: dict) -> dict:
    """packs: {기업명: pack}. 반환: {'persons': [...], 'adjustments': [...], 'pilot': [...], 'summary': {...}}"""
    g = cfg["generation"]
    rng = random.Random(g["seed"])
    min_items = cfg["evidence"]["min_items"]
    items_by = {c: {t: [i for i in packs[c]["items"] if i["type"] == t] for t in EVIDENCE_TYPES if t != "거시"}
                for c in packs}
    for c in items_by:
        items_by[c]["거시"] = macro["items"]
    available = {c: {t for t in EVIDENCE_TYPES if len(items_by[c][t]) >= min_items[t]} for c in packs}
    for c in available:  # 주가가 아예 없으면 생성할 수 없지만, 최소 건수 미달이어도 1건 이상이면 쓴다
        if items_by[c]["주가·거래"]:
            available[c].add("주가·거래")
    adjustments: list[dict] = []

    n = len(personas)
    slots_all = [(p, s) for p in personas for s in p["slots"]]
    n_fb = min(max(round(len(slots_all) * g["fallback_share"]), n), 2 * n)
    two = set(rng.sample([p["persona_id"] for p in personas], n_fb - n))
    fb_slots = {p["persona_id"]: set(rng.sample([s["slot"] for s in p["slots"]], 2 if p["persona_id"] in two else 1))
                for p in personas}
    bc = [BC_TYPES[i % len(BC_TYPES)] for i in range(n_fb)]
    rng.shuffle(bc)
    # 한 사람 안에서 같은 B·C 유형이 겹치지 않게 바꿔 넣는다
    fb_order = [(p["persona_id"], s) for p in personas for s in sorted(fb_slots[p["persona_id"]])]
    for i in range(1, len(fb_order)):
        if fb_order[i][0] == fb_order[i - 1][0] and bc[i] == bc[i - 1]:
            j = next((k for k in range(len(bc)) if bc[k] != bc[i] and fb_order[k][0] != fb_order[i][0]
                      and (k == 0 or fb_order[k - 1][0] != fb_order[k][0] or bc[k - 1] != bc[i])
                      and (k + 1 >= len(bc) or fb_order[k + 1][0] != fb_order[k][0] or bc[k + 1] != bc[i])), None)
            if j is not None:
                bc[i], bc[j] = bc[j], bc[i]
    bc_of = {key: t for key, t in zip(fb_order, bc)}

    track = [(p["persona_id"], s["slot"]) for p, s in slots_all if s["slot"] not in fb_slots[p["persona_id"]]]
    a_list = [t for t, k in largest_remainder(A_WEIGHTS, len(track)).items() for _ in range(k)]
    rng.shuffle(a_list)
    a_of = dict(zip(track, a_list))
    n_ins = round(len(track) * g["insufficient_share"])
    ins = set(rng.sample([k for k in track if a_of[k] != "A2"], n_ins))
    rest = [k for k in track if k not in ins]
    comp = set(rng.sample(rest, math.ceil(len(track) * g["composite_min_share"])))

    persons = []
    used_global: dict[str, int] = {}
    for p in personas:
        prng = random.Random(f"{g['seed']}:{p['persona_id']}")
        used: dict[str, int] = {}
        missing_pool = {}
        out = []
        for s in p["slots"]:
            c, key = s["company"], (p["persona_id"], s["slot"])
            pack = packs[c]
            st = bc_of.get(key) or a_of[key]
            # 별명 섞기: 슬롯마다 먼저 쓸 이름을 바꾼다(대표 종목은 페르소나 별명을 자주)
            nick = str(p["nickname"]) if c == p["primary_company"] and p.get("nickname") else None
            first = nick if nick and prng.random() < 0.6 else prng.choice(CALL_NAMES[c])
            names = list(dict.fromkeys([first] + CALL_NAMES[c] + ([nick] if nick else [])))
            rec = {"slot": s["slot"], "target_company": c, "symbol": pack["symbol"], "role": s["role"], "status": s["status"],
                   "sentence_type": st, "sentence_label": SENTENCE_LABEL[st],
                   "expected_decision_draft": DECISION_DRAFT[st[0]], "as_of_date": pack["as_of_date"],
                   "call_names": names, "length": wpick(prng, LENGTH_BY_PREF.get(p.get("w_length"), LENGTH_BY_PREF["보통"]))}
            parts: list[str] = []
            if st[0] == "B":
                rec.update(evidence_type="없음", answerability="해당 없음")
            elif key in ins:
                pool = missing_pool.setdefault(c, prng.sample(MISSING_TOPICS[c], len(MISSING_TOPICS[c])))
                rec.update(evidence_type="없음", answerability="자료 부족", missing_topic=pool.pop(0) if pool else MISSING_TOPICS[c][0])
            elif st[0] == "C":
                parts = [next((t for t in C_EVIDENCE[st] if t in available[c]), "주가·거래")]
                if parts[0] != C_EVIDENCE[st][0]:
                    adjustments.append({"company": c, "persona_id": p["persona_id"], "slot": s["slot"], "from": C_EVIDENCE[st][0], "to": parts[0]})
                rec.update(evidence_type=parts[0], answerability="근거 있음")
            elif key in comp:
                need = PAIR_REQUIRES.get(st)
                cands = [pr for pr in PAIRS if all(t in available[c] for t in pr) and (need is None or need in pr)]
                if cands:
                    parts = list(prng.choice(cands))
                    rec.update(evidence_type="복합", answerability="근거 있음")
                else:
                    adjustments.append({"company": c, "persona_id": p["persona_id"], "slot": s["slot"], "from": "복합", "to": "단일"})
            if st[0] == "A" and not parts and rec.get("answerability") != "자료 부족":
                allowed = SINGLE_ALLOWED.get(st, set(EVIDENCE_TYPES))
                want = wpick(prng, {t: w for t, w in SINGLE_WEIGHTS.items() if t in allowed})
                if want not in available[c]:
                    ok = {t: w for t, w in SINGLE_WEIGHTS.items() if t in allowed and t in available[c]} or {"주가·거래": 1}
                    got = wpick(prng, ok)
                    adjustments.append({"company": c, "persona_id": p["persona_id"], "slot": s["slot"], "from": want, "to": got})
                    want = got
                parts = [want]
                rec.update(evidence_type=want, answerability="근거 있음")
            chosen = []
            for t in parts:
                pool = items_by[c][t]
                it = min(pool, key=lambda i: (used.get(i["key"], 0), used_global.get(i["key"], 0), prng.random()))
                used[it["key"]] = used.get(it["key"], 0) + 1
                used_global[it["key"]] = used_global.get(it["key"], 0) + 1
                chosen.append(it)
            rec["evidence_parts"] = parts
            rec["evidence_keys"] = [i["key"] for i in chosen]
            rec["evidence_ids"] = list(dict.fromkeys(x for i in chosen for x in i["ids"]))
            if st[0] == "B":
                rec["trigger"] = BC_TRIGGER[st]
            elif rec.get("answerability") == "자료 부족":
                rec["trigger"] = INFO_TRIGGER.get(p.get("info_source"), "지인 말 듣고")
            else:
                rec["trigger"] = trigger_for(parts, chosen, p, prng) if st[0] == "A" else BC_TRIGGER[st]
            if st in ("A2", "C1", "C4"):
                rec["price_levels"] = price_levels(pack)
            if st in ("B10", "C3"):
                rec["other_company"] = prng.choice(OTHER_FOR[c])
            out.append(rec)
        persons.append({"persona_id": p["persona_id"], "slots": out})

    flat = [s for x in persons for s in x["slots"]]
    tr = [s for s in flat if s["sentence_type"][0] == "A"]
    summary = {
        "slots": len(flat), "tracking": len(tr), "fallback_mixed": len(flat) - len(tr),
        "composite_share_of_tracking": round(sum(s["evidence_type"] == "복합" for s in tr) / max(len(tr), 1), 3),
        "insufficient_share_of_tracking": round(sum(s["answerability"] == "자료 부족" for s in tr) / max(len(tr), 1), 3),
        "available_types": {c: sorted(v) for c, v in available.items()},
    }
    return {"persons": persons, "adjustments": adjustments, "summary": summary,
            "pilot": pick_pilot(personas, g["pilot_size"], random.Random(f"{g['seed']}:pilot"))}
