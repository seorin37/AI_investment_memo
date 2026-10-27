"""맥북 점검용 가짜 데이터 — 실제 스키마 컬럼 이름 그대로의 행을 만든다. 수치는 모두 지어낸 값이다.

임시 Postgres에 넣어 export_evidence의 SQL을 실제로 돌리거나(fake_db.py), DB 없이 근거 묶음을 만들 때(테스트) 쓴다.
"""

from __future__ import annotations

import random
from datetime import date, datetime, timedelta, timezone

AS_OF = date(2026, 10, 23)
COMPANIES = {"005930": "삼성전자", "000660": "SK하이닉스", "035420": "NAVER", "105560": "KB금융"}
BASE_PRICE = {"005930": 70_000, "000660": 200_000, "035420": 200_000, "105560": 80_000}
BASE_VOLUME = {"005930": 15_000_000, "000660": 3_000_000, "035420": 800_000, "105560": 1_500_000}
UTC = timezone.utc


def weekdays(end: date, n: int) -> list[date]:
    out, d = [], end
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d -= timedelta(days=1)
    return out[::-1]


def tick(p: float) -> int:
    t = 100 if p < 200_000 else 500
    return int(round(p / t) * t)


def prices(symbol: str, rng: random.Random, as_of: date = AS_OF) -> list[dict]:
    days = weekdays(as_of, 300)
    spikes = set(rng.sample(range(len(days) - 55, len(days) - 1), 4))
    p, out = BASE_PRICE[symbol] * 0.8, []
    for i, d in enumerate(days):
        p *= 1 + rng.gauss(0.0008, 0.016)
        close = tick(p)
        hi, lo = tick(close * (1 + abs(rng.gauss(0, 0.008)))), tick(close * (1 - abs(rng.gauss(0, 0.008))))
        vol = int(BASE_VOLUME[symbol] * rng.uniform(0.7, 1.3) * (rng.uniform(2.3, 3.6) if i in spikes else 1))
        out.append({"symbol": symbol, "trade_date": d, "open": tick(close * rng.uniform(0.99, 1.01)), "high": max(hi, close),
                    "low": min(lo, close), "close": close, "volume": vol})
    return out


DISC = [("분기보고서 (2026.09)", "quarterly", date(2026, 9, 30)), ("연결재무제표기준영업(잠정)실적(공정공시)", "major", None),
        ("현금ㆍ현물배당결정", "major", None), ("반기보고서 (2026.06)", "half", date(2026, 6, 30)),
        ("주요사항보고서(자기주식취득결정)", "major", None), ("기업설명회(IR)개최(안내공시)", "other", None),
        ("분기보고서 (2026.03)", "quarterly", date(2026, 3, 31)), ("사업보고서 (2025.12)", "annual", date(2025, 12, 31)),
        ("임원ㆍ주요주주특정증권등소유상황보고서", "other", None)]


def disclosures(symbol: str, as_of: date = AS_OF) -> tuple[list[dict], list[dict]]:
    name = COMPANIES[symbol]
    rows, chunks, cid = [], [], int(symbol) * 100
    for k, (title, kind, pe) in enumerate(DISC):
        d = as_of - timedelta(days=6 + k * 19)
        no = f"{d:%Y%m%d}{int(symbol) % 1000:03d}{k:03d}"
        rows.append({"rcept_no": no, "symbol": symbol, "title": title, "kind": kind, "period_end": pe, "rcept_dt": d,
                     "source_url": None if k % 3 == 2 else f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={no}"})
        texts = [("표지", "【 대표이사 등의 확인 】"),
                 ("경영진단 및 분석의견", f"{name}의 당기 연결 기준 매출액은 {70 + k}조 {k * 111:,}억원으로 전년 동기 대비 "
                                   f"{3 + k}.{k}% 증가했습니다. 영업이익은 {5 + k}조 {k * 37:,}억원을 기록했습니다. 주요 제품 수요 회복과 "
                                   "환율 효과가 반영되었으며, 고부가 제품 비중 확대로 수익성이 개선되었습니다. 향후 설비투자는 수요에 맞춰 탄력적으로 운영할 계획입니다."),
                 ("사업의 내용" if kind != "major" else None,
                  f"당사는 {name} 사업 부문에서 국내외 고객에게 제품과 서비스를 제공하고 있습니다. 주요 시장은 아시아와 북미이며, "
                  f"매출 비중은 국내 {20 + k}%, 해외 {80 - k}%입니다.")]
        for j, (sec, txt) in enumerate(texts):
            cid += 1
            chunks.append({"id": cid, "rcept_no": no, "chunk_index": j, "section": sec, "chunk_text": txt})
    return rows, chunks


NEWS_TITLES = ["{n}, 3분기 영업이익 {a}조원…전년比 {b}% 증가", "{n} 주가 52주 신고가 경신", "외국인 {n} {c}거래일 연속 순매수",
               "{n}, 신규 설비투자 {a}조원 발표", "증권가 \"{n} 목표가 상향\"", "{n} 배당 확대 검토", "{n} 노사 임금협상 타결",
               "{n}, 해외 법인 설립 추진", "{n} 신제품 공개…시장 반응은", "[속보] {n} 자사주 {a}천억 매입", "{n} 경영진 교체설",
               "{n}, AI 투자 확대", "{n} 3분기 실적 발표 일정 공지", "{n} 협력사와 공급계약 체결", "{n} 주주총회 안건 공개",
               "{n} 해외 매출 비중 {b}%로 확대", "{n}, 친환경 투자 계획", "{n} 신용등급 유지", "{n} 임원 인사 단행",
               "{n} 신사업 진출 가능성", "{n} 2분기 실적 리뷰"]


def news(symbol: str, rng: random.Random, start_id: int, as_of: date = AS_OF) -> list[dict]:
    name, out = COMPANIES[symbol], []
    for k, t in enumerate(NEWS_TITLES):
        title = t.format(n=name, a=rng.randint(2, 15), b=rng.randint(5, 40), c=rng.randint(3, 9))
        when = datetime.combine(as_of - timedelta(days=2 + k * 4), datetime.min.time(), UTC) + timedelta(hours=1 + k % 9)
        out.append({"id": start_id + k, "source_id": 1 + k % 4, "url": f"https://news.example.com/{symbol}/{k}",
                    "title": title, "summary": f"{name} 관련 소식입니다. {title}", "published_at": when})
    # 같은 제목(접두어만 다름) 중복과 3개월보다 오래된 기사
    dup = dict(out[1], id=start_id + 50, url=f"https://news.example.com/{symbol}/dup", title="[단독] " + out[1]["title"],
               published_at=out[1]["published_at"] - timedelta(hours=3))
    old = dict(out[0], id=start_id + 51, url=f"https://news.example.com/{symbol}/old", title=f"{name} 옛날 기사",
               published_at=datetime.combine(as_of - timedelta(days=120), datetime.min.time(), UTC))
    return out + [dup, old]


def financials(symbol: str) -> list[dict]:
    scale = {"005930": 1.0, "000660": 0.45, "035420": 0.03, "105560": 0.0}[symbol]
    out = []
    for year in (2024, 2025, 2026):
        cum_rev = cum_op = cum_ni = 0
        for q, (ptype, md) in enumerate((("q1", (3, 31)), ("half", (6, 30)), ("q3", (9, 30)), ("annual", (12, 31))), 1):
            pe = date(year, *md)
            if pe > date(2026, 6, 30):
                break
            g = 1 + (year - 2024) * 0.08 + q * 0.01
            cum_rev += int(75e12 * scale * g) if scale else 0
            cum_op += int(6e12 * scale * g * (0.8 if (year, q) == (2026, 2) else 1)) if scale else int(1.5e12 * g)
            cum_ni += int(4.5e12 * scale * g) if scale else int(1.3e12 * g)
            out.append({"symbol": symbol, "period_end": pe, "period_type": ptype, "fs_div": "consolidated",
                        "revenue": cum_rev or None, "operating_income": cum_op, "net_income": cum_ni,
                        "total_liabilities": int((1e14 if scale else 6e14) * g), "total_equity": int((3.5e14 if scale else 6e13) * g)})
    return out


def financials_fin(symbol: str) -> list[dict]:
    if symbol != "105560":
        return []
    out = []
    for year in (2025, 2026):
        for ptype, md, k in (("q1", (3, 31), 1), ("half", (6, 30), 2), ("q3", (9, 30), 3), ("annual", (12, 31), 4)):
            pe = date(year, *md)
            if pe > date(2026, 6, 30):
                break
            out.append({"symbol": symbol, "period_end": pe, "period_type": ptype, "net_interest_income": int(3.2e12 * k),
                        "fee_income": int(0.95e12 * k), "loan_loss_provision": int(0.5e12 * k), "solvency_ratio": 15.8 + k * 0.1})
    return out


def macro(rng: random.Random, as_of: date = AS_OF) -> list[dict]:
    out = [{"indicator_code": "KR_POLICY_RATE", "observation_date": date(2026, 5, 28), "value": 2.5},
           {"indicator_code": "KR_POLICY_RATE", "observation_date": date(2026, 8, 27), "value": 2.5}]
    level = {"USD_KRW": 1380.0, "KR_GOV_3Y": 2.6, "KR_GOV_10Y": 2.9, "WTI_SPOT": 68.0}
    for d in weekdays(as_of - timedelta(days=1), 150):
        for code in level:
            level[code] *= 1 + rng.gauss(0, 0.004)
            out.append({"indicator_code": code, "observation_date": d, "value": round(level[code], 3 if code != "USD_KRW" else 2)})
    return out


def all_rows(seed: int = 7, as_of: date = AS_OF) -> dict:
    rng = random.Random(seed)
    data = {"prices": [], "disclosures": [], "chunks": [], "news": [], "news_stocks": [], "financials": [],
            "financials_fin": [], "macro": macro(rng, as_of)}
    for k, symbol in enumerate(COMPANIES):
        data["prices"] += prices(symbol, rng, as_of)
        d, c = disclosures(symbol, as_of)
        data["disclosures"] += d
        data["chunks"] += c
        n = news(symbol, rng, 1000 + k * 100, as_of)
        data["news"] += n
        data["news_stocks"] += [{"news_id": x["id"], "symbol": symbol} for x in n]
        data["financials"] += financials(symbol)
        data["financials_fin"] += financials_fin(symbol)
    return data


def packs_without_db(cfg: dict, seed: int = 7, as_of: date = AS_OF) -> tuple[dict, dict]:
    """DB 없이 export_evidence의 계산 함수로 근거 묶음을 만든다 (단위 테스트용). 반환: ({종목코드: pack}, macro)."""
    from ..export_evidence import MACRO_CODES, company_pack, macro_pack, sub_months

    data = all_rows(seed, as_of)
    names = {"KR_POLICY_RATE": "한국은행 기준금리", "USD_KRW": "원/달러 환율", "KR_GOV_3Y": "국고채 3년", "KR_GOV_10Y": "국고채 10년",
             "WTI_SPOT": "WTI 현물가격"}
    units = {"KR_POLICY_RATE": "%", "USD_KRW": "KRW/USD", "KR_GOV_3Y": "%", "KR_GOV_10Y": "%", "WTI_SPOT": "USD/barrel"}
    src = {1: "서울경제", 2: "매일경제", 3: "한국경제", 4: "연합뉴스"}
    packs = {}
    for symbol, name in COMPANIES.items():
        since = datetime.combine(sub_months(as_of, cfg["evidence"]["news_months"]), datetime.min.time(), UTC)
        news_rows = sorted([dict(n, source_name=src[n["source_id"]]) for n in data["news"]
                            if n["id"] in {x["news_id"] for x in data["news_stocks"] if x["symbol"] == symbol}
                            and n["published_at"] >= since], key=lambda n: (n["published_at"], n["id"]), reverse=True)
        drows = sorted([d for d in data["disclosures"] if d["symbol"] == symbol], key=lambda d: d["rcept_dt"],
                       reverse=True)[: cfg["evidence"]["disclosures_max"]]
        nos = {d["rcept_no"] for d in drows}
        chunks = [c for c in data["chunks"] if c["rcept_no"] in nos and c["section"] != "표지"]
        rows = {"prices": [p for p in data["prices"] if p["symbol"] == symbol], "disclosures": drows, "chunks": chunks,
                "news": news_rows, "financials": [f for f in data["financials"] if f["symbol"] == symbol],
                "financials_fin": [f for f in data["financials_fin"] if f["symbol"] == symbol]}
        packs[symbol] = company_pack(name, symbol, as_of, rows, cfg)
    base_day = sub_months(as_of, cfg["evidence"]["macro_change_months"])

    def latest(d):
        out = []
        for code in MACRO_CODES:
            obs = [o for o in data["macro"] if o["indicator_code"] == code and o["observation_date"] <= d]
            if obs:
                o = max(obs, key=lambda o: o["observation_date"])
                out.append({**o, "name": names[code], "unit": units[code]})
        return out

    macro_p = macro_pack(latest(as_of), latest(base_day), as_of, base_day, cfg)
    return packs, macro_p
