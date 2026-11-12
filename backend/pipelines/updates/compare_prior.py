"""실적·배당 공시 카드의 비교 근거: 직전 같은 기간 값을 DB에서 찾아 근거로 함께 넣는다 (2026-11-10, card_schema v2, 읽기 전용).

근거에 들어간 공시마다 (접수번호 하나에 하나, 최대 max_items개):
- 잠정실적(disclosure_events.event_type=prelim_earnings): 그 공시 표에서 규칙으로 뽑은 정리값(fields)의 당기·전년 동기·직전 분기,
  누계 당기·전년 동기. 원문 청크에 표 일부만 들어가도 비교값이 빠지지 않게 한다.
- 배당(dividend): 같은 종목의 앞선 배당 공시 중 배당기준일이 1년 전 ±45일인 것(작년 같은 분기)과 바로 앞 배당.
  없으면 "찾지 못했다"와 DB의 배당 공시가 언제부터 있는지를 적는다 (LLM은 '비교 자료 없음'을 쓴다).
- 정기보고서(분기·반기·사업보고서): financials의 같은 기간 종류(q1·half·q3·annual, 누계) 당기와 1년 전 값.
  financials는 연결·별도 표시가 없어서, 당기 값 하나 이상이 근거 원문의 숫자와 같을 때만 넣는다 (기준이 같다고 볼 수 있을 때만).
금액은 원 단위 정수를 "24조 4,489억 2,900만원"처럼 한국식으로 그대로 적는다 (반올림하지 않는다, checks.numbers가 같은 값으로 읽는다).
만든 근거는 Candidate(ref="cmp:<접수번호>", doc="compare")이고 LLM 입력에는 [직전 같은 기간 비교]로 보인다.
"""

from __future__ import annotations

from datetime import date, timedelta

from .checks import evidence_numbers
from .evidence import rcept_of
from .models import Candidate, Evidence

COMPARE_DOC = "compare"
COMPARE_PREFIX = "cmp:"
DIVIDEND_WINDOW_DAYS = 45

DISC_SQL = """SELECT d.rcept_no, btrim(d.symbol), d.rcept_dt, d.title, d.kind::text, d.period_end, e.event_type, e.fields
FROM disclosures d LEFT JOIN disclosure_events e ON e.rcept_no = d.rcept_no WHERE d.rcept_no = ANY(%(nos)s)"""
PRIOR_DIVIDEND_SQL = """SELECT d.rcept_no, d.rcept_dt, e.fields FROM disclosure_events e JOIN disclosures d ON d.rcept_no = e.rcept_no
WHERE e.event_type = 'dividend' AND d.symbol = %(symbol)s AND d.rcept_no <> %(rcept_no)s AND d.rcept_dt <= %(day)s
  AND NOT e.is_correction ORDER BY d.rcept_dt DESC"""
DIVIDEND_SINCE_SQL = "SELECT min(d.rcept_dt) FROM disclosure_events e JOIN disclosures d ON d.rcept_no = e.rcept_no WHERE e.event_type = 'dividend'"
FIN_SQL = """SELECT period_end, revenue, operating_income, net_income FROM financials
WHERE symbol = %(symbol)s AND period_type = %(ptype)s AND period_end = ANY(%(ends)s)"""

_EARN = [("매출액", "revenue"), ("영업이익", "op_income"), ("당기순이익", "net_income")]


def korean_won(value) -> str:
    """원 단위 정수 → "24조 4,489억 2,900만원" (0인 단위는 뺀다, 1만 원 아래 자투리도 그대로 적는다)."""
    if value is None:
        return "-"
    v = int(value)
    sign, v = ("-" if v < 0 else ""), abs(v)
    jo, rest = divmod(v, 10 ** 12)
    eok, rest = divmod(rest, 10 ** 8)
    man, won = divmod(rest, 10 ** 4)
    parts = [f"{jo:,}조" if jo else "", f"{eok:,}억" if eok else "", f"{man:,}만" if man else "", f"{won:,}" if won else ""]
    text = " ".join(p for p in parts if p)
    return f"{sign}{text or '0'}원"


def period_type(kind: str, period_end: date | None) -> str | None:
    """disclosures.kind·period_end → financials.period_type (q1·half·q3·annual)."""
    if period_end is None:
        return None
    if kind == "annual":
        return "annual"
    if kind == "half":
        return "half"
    if kind == "quarterly":
        return {3: "q1", 9: "q3"}.get(period_end.month)
    return None


def _year_before(d: date) -> date:
    try:
        return d.replace(year=d.year - 1)
    except ValueError:                                       # 2월 29일
        return d.replace(year=d.year - 1, day=28)


def earnings_text(title: str, rcept_dt, f: dict) -> str | None:
    rows = []
    for label, key in _EARN:
        cur, py, pq = f.get(key), f.get(f"{key}_prev_y"), f.get(f"{key}_prev_q")
        if cur is None or (py is None and pq is None):
            continue
        rows.append(f"- {label}: 당기 {korean_won(cur)} · 전년 동기 {korean_won(py)} · 직전 분기 {korean_won(pq)}")
    for label, key in _EARN[:2]:
        cur, py = f.get(f"{key}_ytd"), f.get(f"{key}_ytd_prev_y")
        if cur is not None and py is not None:
            rows.append(f"- 누계 {label}: 당기 {korean_won(cur)} · 전년 동기 {korean_won(py)}")
    if not rows:
        return None
    span = f"{f.get('period_start') or '?'}~{f.get('period_end') or '?'}"
    return (f"기준 공시: {title} ({rcept_dt} 접수) 표의 정리값. 당기 기간 {span}. 금액은 원 단위를 그대로 적었어요.\n"
            + "\n".join(rows))


def dividend_text(conn, symbol: str, rcept_no: str, rcept_dt: date, title: str, f: dict) -> str:
    record = date.fromisoformat(f["record_date"]) if f.get("record_date") else None
    rows = conn.execute(PRIOR_DIVIDEND_SQL, {"symbol": symbol, "rcept_no": rcept_no, "day": rcept_dt}).fetchall()
    fmt = lambda fx: (f"{fx.get('dividend_kind') or '배당'} 보통주 1주당 {fx['dps_common']:,}원" if fx.get("dps_common") is not None
                      else f"{fx.get('dividend_kind') or '배당'} 1주당 배당금 정보 없음") + f" (배당기준일 {fx.get('record_date') or '-'})"
    head = f"기준 공시: {title} ({rcept_dt} 접수), 이번 배당: {fmt(f)}."
    lines = []
    if record is not None:
        target = _year_before(record)
        same = [r for r in rows if r[2].get("record_date")
                and abs((date.fromisoformat(r[2]["record_date"]) - target).days) <= DIVIDEND_WINDOW_DAYS]
        if same:
            lines.append(f"- 작년 같은 시기 배당: {fmt(same[0][2])} ({same[0][1]} 접수)")
        else:
            since = conn.execute(DIVIDEND_SINCE_SQL).fetchone()[0]
            lines.append(f"- 작년 같은 시기(배당기준일 {target} 전후) 배당 공시는 DB에서 찾지 못했어요 (DB의 배당 공시는 {since} 접수분부터 있어요).")
    if rows:
        lines.append(f"- 바로 앞 배당: {fmt(rows[0][2])} ({rows[0][1]} 접수)")
    elif record is None:
        lines.append("- 앞선 배당 공시는 DB에서 찾지 못했어요.")
    return head + "\n" + "\n".join(lines)


def periodic_text(conn, symbol: str, kind: str, period_end: date, title: str, rcept_dt, shown: str) -> str | None:
    ptype = period_type(kind, period_end)
    if ptype is None:
        return None
    prev_end = _year_before(period_end)
    rows = {r[0]: r for r in conn.execute(FIN_SQL, {"symbol": symbol, "ptype": ptype, "ends": [period_end, prev_end]}).fetchall()}
    cur, prev = rows.get(period_end), rows.get(prev_end)
    if cur is None:
        return None
    seen = evidence_numbers(shown)
    if not any(v is not None and round(float(v), 6) in seen for v in cur[1:]):
        return None                                          # 근거 원문과 같은 기준인지 확인할 수 없다
    lines = []
    for label, i in (("매출액", 1), ("영업이익", 2), ("당기순이익", 3)):
        if cur[i] is not None:
            lines.append(f"- {label}(누계): {period_end} {korean_won(cur[i])} · {prev_end} "
                         + (korean_won(prev[i]) if prev is not None and prev[i] is not None else "자료 없음"))
    return f"기준 공시: {title} ({rcept_dt} 접수). 재무 DB의 같은 기간({ptype}, 누계) 값이에요.\n" + "\n".join(lines) if lines else None


def prior_evidence(conn, evidence: list[Evidence], max_items: int = 2) -> list[Evidence]:
    """근거 공시의 직전 같은 기간 비교 근거 (E 번호는 기존 근거 다음부터). 실적·배당·정기보고서가 아니면 만들지 않는다."""
    discs = [e for e in evidence if e.candidate.kind == "disclosure" and e.candidate.doc != COMPARE_DOC]
    nos = list(dict.fromkeys(rcept_of(e.candidate.ref) for e in discs))
    if not nos:
        return []
    shown = {}
    for e in discs:
        shown.setdefault(rcept_of(e.candidate.ref), []).append(f"{e.candidate.title} {e.shown_text}")
    info = {r[0]: r for r in conn.execute(DISC_SQL, {"nos": nos}).fetchall()}
    out, seen_keys = [], set()
    n = len(evidence)
    for no in nos:
        if no not in info or len(out) >= max_items:
            continue
        _, symbol, rcept_dt, title, kind, period_end, etype, fields = info[no]
        fields = fields or {}
        text, key = None, None
        if etype == "prelim_earnings":
            text, key = earnings_text(title, rcept_dt, fields), ("earn", fields.get("period_end"), title)
        elif etype == "dividend":
            text, key = dividend_text(conn, symbol, no, rcept_dt, title, fields), ("div", fields.get("record_date"))
        elif kind in ("quarterly", "half", "annual"):
            text, key = periodic_text(conn, symbol, kind, period_end, title, rcept_dt, " ".join(shown[no])), ("fin", period_end)
        if not text or key in seen_keys:
            continue
        seen_keys.add(key)
        n += 1
        c = Candidate(ref=f"{COMPARE_PREFIX}{no}", kind="disclosure", symbol=symbol, date=str(rcept_dt),
                      title=f"직전 같은 기간 비교 · {title}", text=text, url=None, source="DART", similarity=1.0, doc=COMPARE_DOC)
        out.append(Evidence(f"E{n}", c, text))
    return out


def is_compare_ref(ref: str) -> bool:
    return ref.startswith(COMPARE_PREFIX)
