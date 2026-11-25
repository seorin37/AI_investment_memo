"""판단 질문(사야 되나·오르나·가격 괜찮아?)의 답 맨 앞에 붙이는 주가 사실 (2026-11-25, 팀장님: 반려하지 말고 권유만 하지 않기).

기사 검색만으로 답하면 오래된 기사·한쪽으로 기운 기사(목표가 하향) 하나가 답이 되거나 답이 없었다.
그래서 DB 종가로 코드가 계산한 사실을 먼저 쓴다: 마지막 종가와 전날 대비, 1개월 전 대비, 52주 범위 안 위치.
예측·권유·평가 말은 쓰지 않는다 (싸다·비싸다·바닥 X). LLM은 쓰지 않는다.
"""

from __future__ import annotations

from datetime import date

SQL = """SELECT trade_date, close FROM prices_daily
WHERE btrim(symbol) = %(s)s AND trade_date <= %(d)s AND close IS NOT NULL ORDER BY trade_date DESC LIMIT 260"""


def _md(d) -> str:
    d = d if isinstance(d, date) else date.fromisoformat(str(d)[:10])
    return f"{d.month}월 {d.day}일"


def _pct(a: float, b: float) -> float:
    return (a / b - 1) * 100 if b else 0.0


def _move(p: float) -> str:
    if abs(p) < 0.05:
        return "변동이 없었어요"
    return f"{abs(p):.1f}% {'올랐어요' if p > 0 else '내렸어요'}"


def brief_from_closes(name: str, rows: list[tuple]) -> list[str]:
    """rows = [(trade_date, close), ...] 최신순. 문장 목록 (자료가 모자라면 있는 만큼)."""
    if not rows:
        return []
    d0, c0 = rows[0][0], float(rows[0][1])
    out = []
    if len(rows) > 1:
        out.append(f"{name}의 {_md(d0)} 종가는 {c0:,.0f}원으로, 전 거래일보다 {_move(_pct(c0, float(rows[1][1])))}.")
    else:
        out.append(f"{name}의 {_md(d0)} 종가는 {c0:,.0f}원이에요.")
    if len(rows) > 21:
        d1, c1 = rows[21][0], float(rows[21][1])
        out.append(f"한 달 전({_md(d1)} 종가 {c1:,.0f}원)보다 {_move(_pct(c0, c1))}.")
    if len(rows) >= 120:
        closes = [float(c) for _, c in rows]
        lo, hi = min(closes), max(closes)
        span = "52주" if len(rows) >= 240 else f"최근 {len(rows)}거래일"
        pos = 0 if hi == lo else round((c0 - lo) / (hi - lo) * 100)
        out.append(f"{span} 종가 범위(최저 {lo:,.0f}원 ~ 최고 {hi:,.0f}원)에서 아래에서 {pos}% 지점이에요.")
    return out


def price_brief(conn, symbol: str, name: str, as_of: date | None = None) -> list[str]:
    """DB 종가로 만든 주가 사실 문장 (읽기 전용)."""
    rows = conn.execute(SQL, {"s": symbol.strip(), "d": as_of or date.today()}).fetchall()
    return brief_from_closes(name, [(r[0], r[1]) for r in rows])
