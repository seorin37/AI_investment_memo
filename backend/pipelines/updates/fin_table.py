"""한 번 답하기(ask) 질문에 넣는 재무 표 근거 (실험, 2026-11-16, DB 읽기 전용).

질문이 실적 숫자·비율("3분기 영업이익률 얼마?", "기아랑 현대차 영업이익률 비교")을 물어도 공시 원문 청크에는
표 앞머리(기간 머리글)만 들어가 숫자가 잘리거나, 비율은 계산이 필요해 LLM이 답하지 못했다 (계산 금지 원칙).
그래서 코드가 DB에서 숫자를 꺼내고 비율도 코드가 계산해 [재무 표] 근거 하나로 넣는다.

- 분기 손익: financials_quarterly(분기 단독값, 누계 차감은 적재 때 끝남) 최근 max_quarters개
- 비율: 2026-11-17부터 0017 financial_metrics에서 읽는다 (분기 영업이익률·순이익률, ROE·이자보상배율(TTM), 부채·유동·당좌비율,
  유보율 — 기업정보 페이지와 같은 숫자). 표에 없는 전년 대비 증감률·연간 영업이익률·잠정 영업이익률만 코드가 계산
- 그보다 최신 잠정실적이 있으면 disclosure_events(prelim_earnings) 정리값을 '잠정' 줄로 더한다
- 연간: financials annual 최근 3년 (사업보고서 확정치)
- 재무상태: financials 최근 기간의 자산·부채·자본
- 질문에 다른 상장사 이름이 있으면(비교 질문) 그 회사 표도 함께 (최대 max_others개)
금액은 compare_prior.korean_won 형식 그대로 (checks.numbers가 같은 값으로 읽는다). 비율은 소수 첫째 자리.
"""

from __future__ import annotations

import re

from .compare_prior import korean_won
from .models import Candidate, Evidence

FIN_DOC = "fintable"
FIN_PREFIX = "fin:"

Q_SQL = """SELECT period_end, quarter, fs_div, revenue, operating_income, net_income FROM financials_quarterly
WHERE symbol = %(s)s ORDER BY period_end DESC LIMIT %(n)s"""
ANNUAL_SQL = """SELECT period_end, fs_div, revenue, operating_income, net_income FROM financials
WHERE symbol = %(s)s AND period_type = 'annual' ORDER BY period_end DESC LIMIT %(n)s"""
BS_SQL = """SELECT period_end, period_type, fs_div, total_assets, total_liabilities, total_equity FROM financials
WHERE symbol = %(s)s AND total_assets IS NOT NULL ORDER BY period_end DESC LIMIT 1"""
PRELIM_SQL = """SELECT d.rcept_dt, d.title, e.fields FROM disclosure_events e JOIN disclosures d ON d.rcept_no = e.rcept_no
WHERE d.symbol = %(s)s AND e.event_type = 'prelim_earnings' AND NOT e.is_correction ORDER BY d.rcept_dt DESC LIMIT 1"""
NAME_SQL = "SELECT btrim(symbol), name FROM stocks"
FIN_CO_SQL = "SELECT 1 FROM financials_fin WHERE symbol = %(s)s LIMIT 1"

_FS = {"consolidated": "연결", "separate": "별도", "CFS": "연결", "OFS": "별도"}


def _pct(num, den) -> str:
    if num is None or den in (None, 0):
        return "-"
    return f"{float(num) / float(den) * 100:.1f}%"


def _num(v, unit: str) -> str:
    return f"{float(v):,.2f}{unit}" if unit == "배" else f"{float(v):,.1f}{unit}"


# 0017 financial_metrics (2026-11-17 배포). 비율은 여기서 읽고, 표에 없는 것(전년 대비 증감률·연간·잠정 이익률)만 코드가 계산
METRICS_SQL = """SELECT period_end, operating_margin, net_margin, roe, debt_ratio, current_ratio, quick_ratio,
  interest_coverage, interest_coverage_basis, reserve_ratio FROM financial_metrics
WHERE symbol = %(s)s ORDER BY period_end DESC LIMIT 12"""
METRIC_COLS = ("operating_margin", "net_margin", "roe", "debt_ratio", "current_ratio", "quick_ratio",
               "interest_coverage", "interest_coverage_basis", "reserve_ratio")
METRIC_LABELS = (("ROE(최근 4분기)", "roe", "%"), ("부채비율", "debt_ratio", "%"), ("유동비율", "current_ratio", "%"),
                 ("당좌비율", "quick_ratio", "%"), ("이자보상배율(최근 4분기)", "interest_coverage", "배"),
                 ("유보율", "reserve_ratio", "%"))
INTEREST_BASIS = {"income_statement": "손익계산서 이자비용", "cf_adjustment": "현금흐름표 이자비용 조정",
                  "cf_paid": "현금흐름표 이자 지급액(현금 기준)"}


def _metrics(conn, symbol: str) -> dict:
    """period_end → {지표}. financial_metrics 표가 없으면(0017 전 DB) 빈 dict — 이때 비율은 보이지 않는다."""
    if conn.execute("SELECT to_regclass('public.financial_metrics')").fetchone()[0] is None:
        return {}
    return {r[0]: dict(zip(METRIC_COLS, r[1:])) for r in conn.execute(METRICS_SQL, {"s": symbol}).fetchall()}


# 사건 공시 표준 비율 (0018 disclosure_event_metrics, 2026-11-17 배포). 정정된 원본은 빼고 최근 1년 사건만
EVENT_METRICS_SQL = """SELECT m.event_type, m.base_date, m.metrics, m.inputs FROM disclosure_event_metrics m
WHERE m.symbol = %(s)s AND m.base_date >= CURRENT_DATE - 365 AND m.metrics <> '{}'::jsonb
  AND NOT EXISTS (SELECT 1 FROM disclosure_events c WHERE c.corrects = m.rcept_no)
ORDER BY m.base_date DESC, m.rcept_no DESC LIMIT %(n)s"""
EVENT_NAMES = {"rights_offering": "유상증자", "treasury_buy": "자사주 취득", "treasury_sell": "자사주 처분",
               "share_cancel": "주식 소각", "dividend": "배당"}
EVENT_METRIC_LABELS = (  # (키, 이름, 단위) 단위: krw 금액 | % | 배
    ("raise_krw", "조달 금액", "krw"), ("dilution_pct", "희석률(신주 ÷ 기존 주식)", "%"),
    ("raise_to_prev_op_income_x", "직전 사업연도 영업이익 대비", "배"), ("raise_to_equity_pct", "자본총계 대비", "%"),
    ("raise_to_market_cap_pct", "시가총액 대비", "%"), ("amount_krw", "금액", "krw"),
    ("amount_to_market_cap_pct", "시가총액 대비", "%"), ("shares_pct", "상장주식 수 대비", "%"),
    ("cancel_pct", "발행주식 대비 소각 비율", "%"), ("total_krw", "배당금 총액", "krw"),
    ("payout_ratio_pct", "배당성향(직전 사업연도 지배주주 순이익 대비)", "%"))


def event_lines(conn, symbol: str, limit: int = 5) -> list[str]:
    """최근 1년 사건 공시의 표준 비율 줄. 표가 없거나(0018 전 DB) 사건이 없으면 빈 목록."""
    if conn.execute("SELECT to_regclass('public.disclosure_event_metrics')").fetchone()[0] is None:
        return []
    out = []
    for etype, base, m, inputs in conn.execute(EVENT_METRICS_SQL, {"s": symbol, "n": limit}).fetchall():
        parts = []
        for key, label, unit in EVENT_METRIC_LABELS:
            if m.get(key) is None:
                continue
            v = m[key]
            parts.append(f"{label} {korean_won(v) if unit == 'krw' else _num(v, unit)}")
        basis = []
        if "prev_op_income" in inputs and "raise_to_prev_op_income_x" in m:
            basis.append(f"영업이익은 {inputs['prev_op_income'].get('period_end', '')[:4]}년 연간")
        if "market_cap" in inputs and any(k.endswith("market_cap_pct") for k in m):
            basis.append(f"시가총액은 {inputs['market_cap'].get('trade_date')} 기준")
        out.append(f"- {base} {EVENT_NAMES.get(etype, etype)} 공시 (사건 비율 표): " + " · ".join(parts)
                   + (f" ({', '.join(basis)})" if basis else ""))
    return out


# 주가 요약 (2026-11-18): 질문 답이 공시·뉴스와 함께 주가도 근거로 쓰게. 등락률·52주 고저는 코드가 계산 (LLM 계산 금지 원칙 유지)
PRICE_SQL = """SELECT trade_date, close, market_cap FROM prices_daily
WHERE symbol = %(s)s AND trade_date >= CURRENT_DATE - 400 AND close IS NOT NULL ORDER BY trade_date DESC LIMIT 260"""


def price_lines(conn, symbol: str) -> list[str]:
    """최근 종가·1주(5거래일)·1개월(20거래일) 등락률·52주(최근 250거래일) 최고·최저와 날짜·시가총액. 시세가 없으면 빈 목록."""
    rows = conn.execute(PRICE_SQL, {"s": symbol}).fetchall()
    if not rows:
        return []
    last_d, last, cap = rows[0]

    def chg(n: int) -> str:
        if len(rows) <= n or not rows[n][1]:
            return ""
        return f"{(float(last) / float(rows[n][1]) - 1) * 100:+.1f}%"
    year = rows[:250]
    hi = max(year, key=lambda r: r[1])
    lo = min(year, key=lambda r: r[1])
    parts = [f"종가 {float(last):,.0f}원"]
    for label, n in (("1주 전 대비", 5), ("1개월 전 대비", 20)):
        if chg(n):
            parts.append(f"{label} {chg(n)} ({rows[n][0]} 종가 {float(rows[n][1]):,.0f}원)")
    parts.append(f"52주 최고 {float(hi[1]):,.0f}원({hi[0]}) · 최저 {float(lo[1]):,.0f}원({lo[0]})")
    parts.append(f"52주 최고가 대비 {(float(last) / float(hi[1]) - 1) * 100:+.1f}%")
    if cap:
        parts.append(f"시가총액 {korean_won(cap)}")
    return [f"- 주가 ({last_d} 기준, 시세 DB): " + " · ".join(parts)]


def _qlabel(period_end, quarter) -> str:
    return f"{period_end.year}년 {quarter}분기" if quarter else str(period_end)


def company_table(conn, symbol: str, name: str, max_quarters: int = 6, max_years: int = 3) -> str | None:
    rows = conn.execute(Q_SQL, {"s": symbol, "n": max_quarters}).fetchall()
    # 금융사(은행·보험·증권)는 영업이익률·부채비율이 뜻이 달라 빼고 금액만 (11-16 기업정보 UI 결정과 같게)
    fin_co = conn.execute(FIN_CO_SQL, {"s": symbol}).fetchone() is not None
    lines = []
    prelim = conn.execute(PRELIM_SQL, {"s": symbol}).fetchone()
    if prelim:
        dt, title, f = prelim
        f = f or {}
        end = f.get("period_end")
        if end and (not rows or end > str(rows[0][0])) and f.get("revenue") is not None:
            basis = "연결" if "연결" in (title or "") else "별도"
            # 순이익은 지배주주 순이익 (financials·financials_quarterly와 같은 기준, 2026-11 재무 결정). 없으면 전체 순이익
            ni = "net_income_owners" if f.get("net_income_owners") is not None else "net_income"
            ni_label = "지배주주 순이익" if ni == "net_income_owners" else "순이익"
            lines.append(f"- {end} 끝 분기 (잠정, {basis}, {dt} 공시): 매출액 {korean_won(f.get('revenue'))} · "
                         f"영업이익 {korean_won(f.get('op_income'))}"
                         + (f" · {ni_label} {korean_won(f.get(ni))}" if f.get(ni) is not None else "")
                         + ("" if fin_co else f" · 영업이익률 {_pct(f.get('op_income'), f.get('revenue'))}")
                         + "".join(f" · {lab} 전년 같은 분기 대비 {(f[k] / f[k + '_prev_y'] - 1) * 100:+.1f}%"
                                   for lab, k in (("영업이익", "op_income"), (ni_label, ni))
                                   if f.get(k) is not None and (f.get(k + "_prev_y") or 0) > 0))
    by_q = {(r[0].year, r[1]): r for r in rows}

    def yoy(end, q, i, label):                              # 전년 같은 분기 대비 증감률 (코드 계산)
        prev = by_q.get((end.year - 1, q))
        cur = by_q.get((end.year, q))
        if prev is None or cur is None or cur[i] is None or not prev[i] or prev[i] <= 0:
            return ""
        return f" · {label} 전년 같은 분기 대비 {(float(cur[i]) / float(prev[i]) - 1) * 100:+.1f}%"
    metrics = _metrics(conn, symbol)                         # 0017 financial_metrics (period_end → 지표). 표가 없으면 {}
    for end, q, fs, rev, op, ni in rows:
        m = metrics.get(end) or {}
        # 분기 이익률은 재무 지표 표 값 (기업정보 페이지와 같은 숫자). 금융사 이익률은 표에 있어도 화면 결정대로 띄우지 않는다
        margins = "" if fin_co else "".join(f" · {lab} {_num(m.get(k), '%')}" for lab, k in
                                           (("영업이익률", "operating_margin"), ("순이익률", "net_margin")) if m.get(k) is not None)
        lines.append(f"- {_qlabel(end, q)} (기간 끝 {end}, {_FS.get(fs, fs or '-')}): 매출액 {korean_won(rev)} · 영업이익 {korean_won(op)} · "
                     f"지배주주 순이익 {korean_won(ni)}"                # financials.net_income = 지배주주 순이익 (재무 결정)
                     + margins + yoy(end, q, 4, "영업이익") + yoy(end, q, 5, "지배주주 순이익"))
    # 연간 (사업보고서 확정치, 2026-11-17): "작년 영업이익"을 분기 합산 없이 답하게 (LLM은 더하기도 하지 않는다)
    years = conn.execute(ANNUAL_SQL, {"s": symbol, "n": max_years}).fetchall()
    by_y = {r[0].year: r for r in years}
    for end, fs, rev, op, ni in years:
        prev = by_y.get(end.year - 1)
        growth = "".join(f" · {lab} 전년 대비 {(float(cur) / float(p) - 1) * 100:+.1f}%"
                         for lab, cur, p in (("영업이익", op, prev and prev[3]), ("지배주주 순이익", ni, prev and prev[4]))
                         if cur is not None and p and p > 0)
        lines.append(f"- {end.year}년 연간 (사업보고서 확정치, 회계연도 끝 {end}, {_FS.get(fs, fs or '-')}): "
                     f"매출액 {korean_won(rev)} · 영업이익 {korean_won(op)} · 지배주주 순이익 {korean_won(ni)}"
                     + ("" if fin_co else f" · 연간 영업이익률 {_pct(op, rev)}") + growth)
    lines += event_lines(conn, symbol)                     # 사건 공시 표준 비율 (0018)
    lines += price_lines(conn, symbol)                     # 주가 요약 (2026-11-18, 질문 답에 주가도 근거로)
    bs = conn.execute(BS_SQL, {"s": symbol}).fetchone()
    if bs:
        end, ptype, fs, ta, tl, te = bs
        lines.append(f"- 재무상태 {end} ({_FS.get(fs, fs or '-')}): 자산총계 {korean_won(ta)} · 부채총계 {korean_won(tl)} · "
                     f"자본총계 {korean_won(te)}")
    # 최신 기간의 재무 지표 (financial_metrics). 값이 있는 것만 (없는 지표는 기업정보 화면처럼 뺀다)
    if metrics:
        end = max(metrics)
        m = metrics[end]
        # 금융사는 이자보상배율을 뺀다 (2026-11-17 결정: 은행 등은 이자비용이 본업 비용이라 "0.46배" 같은 값이 오해를 부른다)
        parts = [f"{lab} {_num(m.get(k), unit)}" for lab, k, unit in METRIC_LABELS
                 if m.get(k) is not None and not (fin_co and k == "interest_coverage")]
        if parts:
            basis = INTEREST_BASIS.get(m.get("interest_coverage_basis") or "", "")
            lines.append(f"- 재무 지표 {end} (재무 지표 표): " + " · ".join(parts)
                         + (f" (이자보상배율은 {basis} 기준)" if basis and m.get("interest_coverage") is not None and not fin_co
                            else ""))
    if not lines:
        return None
    return f"[{name}] 분기 금액은 분기 단독값, 연간 금액은 그해 전체 값이에요.\n" + "\n".join(lines)


def other_symbols(conn, text: str, symbol: str, max_others: int = 2) -> list[tuple[str, str]]:
    """질문 글에 이름이 나온 다른 상장사 (긴 이름 먼저, 2글자 이하 이름은 오탐이 많아 뺀다)."""
    names = sorted(((s, n) for s, n in conn.execute(NAME_SQL).fetchall() if n and len(n) >= 3 and s != symbol),
                   key=lambda x: -len(x[1]))
    found, used = [], text or ""
    for s, n in names:
        if n in used:
            found.append((s, n))
            used = used.replace(n, " ")
        if len(found) >= max_others:
            break
    return found


def fin_evidence(conn, symbol: str, name: str, question: str, start_index: int, aliases: dict | None = None) -> list[Evidence]:
    """[재무 표] 근거 하나 (E 번호는 start_index+1). 질문에 다른 회사가 있으면 그 회사 표도 같은 근거에 넣는다."""
    text = question or ""
    for real, alts in (aliases or {}).items():           # "현대차"·"KB" 같은 줄임말을 정식 이름으로
        for a in alts:
            if a in text and real not in text:
                text = text.replace(a, real)
    parts = [company_table(conn, symbol, name)]
    parts += [company_table(conn, s, n) for s, n in other_symbols(conn, text, symbol)]
    body = "\n\n".join(p for p in parts if p)
    if not body:
        return []
    body = ("코드가 재무 DB에서 꺼낸 값이에요. 분기 이익률·ROE·부채비율·유동비율·당좌비율·이자보상배율·유보율은 재무 지표 표"
            "(기업정보 페이지와 같은 값)이고, 전년 대비 증감률·연간 영업이익률·잠정 영업이익률은 코드가 계산했어요. "
            "사건 공시 줄의 비율(희석률·시가총액 대비 등)은 사건 비율 표 값이고, "
            "주가 줄의 등락률·52주 고저는 시세 DB로 코드가 계산했어요.\n" + body)
    dates = re.findall(r"\d{4}-\d{2}-\d{2}", body)
    c = Candidate(ref=f"{FIN_PREFIX}{symbol}", kind="disclosure", symbol=symbol, date=max(dates) if dates else "",
                  title="재무 표", text=body,
                  url=None, source="DART", similarity=1.0, doc=FIN_DOC)
    return [Evidence(f"E{start_index + 1}", c, body)]
