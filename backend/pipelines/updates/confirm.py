"""확인 필요(needs_confirmation) 응답의 질문과 선택지 — 코드가 계산한다 (LLM 없음, 2026-11-10).

- 상대 가격 조건("고점에서 30% 빠지면")은 tracking.price.parse_relative로 기준어·%·방향을 꺼내고,
  prices_daily(읽기 전용)의 일봉으로 기준값을 구해 조건가를 계산한다.
  고점: 52주 고점(최근 거래일부터 365일 안의 최고 high)과 최근 20거래일 고점 두 개. 저점·바닥은 같은 방식의 저가.
  지금·현재·여기(또는 기준어 없는 %): 최근 종가 하나.
- 선택지 하나 = {label, item: {type, price_threshold, description}, basis: {kind, label, value, trade_date, as_of, pct, direction}}.
  basis.value는 기준값, basis.trade_date는 그 기준값이 나온 거래일(기준일), as_of는 계산에 쓴 최근 거래일이다.
  조건가는 원 단위 반올림. 사용자가 고르면 그 item으로 가격 항목을 만들면 된다 (화면·저장은 아직 없다).
- 평단가·매수가 기준, 방향을 모르는 문장, 이동평균선·거래량·가격 범위 같은 조건, 일봉이 없는 종목은 선택지 없이 질문만.
"""

from __future__ import annotations

from datetime import date, timedelta

from ..tracking.price import RelativeCondition, parse_relative

PRICE_WINDOW_SQL = """SELECT trade_date, high, low, close FROM prices_daily
WHERE symbol = %(symbol)s ORDER BY trade_date DESC LIMIT 260"""
RECENT_DAYS = 20

_BASE_LABEL = {"high": "고점", "low": "저점"}
_GENERIC = {
    "PRICE_THRESHOLD_MISSING": "알림 받을 가격을 정확히 알려 주시겠어요?",
    "LOW_CONFIDENCE": "이 문장을 추적할 내용으로 볼지 확인해 주시겠어요?",
}
_UNSUPPORTED = "이 조건은 아직 그대로 추적하지 못해요. 알림 받을 가격을 알려 주시겠어요?"


def price_window(conn, symbol: str) -> list[tuple]:
    """최근 일봉 (trade_date, high, low, close) 최신순. 없으면 빈 목록."""
    with conn.cursor() as cur:
        cur.execute(PRICE_WINDOW_SQL, {"symbol": symbol})
        return [(d, float(h), float(l), float(c)) for d, h, l, c in cur.fetchall()]


def _obj(word: str) -> str:
    """을/를 (마지막 글자 받침)."""
    last = word[-1] if word else ""
    if "가" <= last <= "힣":
        return word + ("을" if (ord(last) - 0xAC00) % 28 else "를")
    return word + "을(를)"


def base_points(rows: list[tuple], base: str) -> list[dict]:
    """기준값 후보. rows는 최신순 (trade_date, high, low, close)."""
    if not rows:
        return []
    as_of = rows[0][0]
    if base == "current":
        return [{"kind": "close", "label": "최근 종가", "value": rows[0][3], "trade_date": str(as_of), "as_of": str(as_of)}]
    if base not in ("high", "low"):
        return []
    col, pick = (1, max) if base == "high" else (2, min)
    word = "고점" if base == "high" else "저점"
    since = as_of - timedelta(days=365) if isinstance(as_of, date) else None
    year = [r for r in rows if since is None or r[0] > since]
    out = []
    for kind, label, window in ((f"52w_{base}", f"52주 {word}", year), (f"20d_{base}", f"최근 20거래일 {word}", rows[:RECENT_DAYS])):
        best = pick(window, key=lambda r: r[col])
        out.append({"kind": kind, "label": label, "value": best[col], "trade_date": str(best[0]), "as_of": str(as_of)})
    return out


def threshold(value: float, pct: float, direction: str) -> int:
    return int(round(value * (1 - pct / 100) if direction == "below" else value * (1 + pct / 100)))


def build_options(cond: RelativeCondition, rows: list[tuple]) -> list[dict]:
    if cond.direction is None:
        return []
    word = "아래로" if cond.direction == "below" else "위로"
    out = []
    for p in base_points(rows, cond.base):
        thr = threshold(p["value"], cond.pct, cond.direction)
        how = f"에서 {cond.pct:g}% → " if cond.pct else " → "
        out.append({"label": f"{p['label']} {p['value']:,.0f}원({p['trade_date']}){how}{thr:,}원 {word}",
                    "item": {"type": f"price_{cond.direction}", "price_threshold": thr, "description": f"{thr:,}원 {word}"},
                    "basis": {**p, "pct": cond.pct, "direction": cond.direction}})
    # 52주와 20거래일 고점이 같은 날이면 선택지 하나로 (같은 조건가를 두 번 보여 주지 않는다)
    seen, uniq = set(), []
    for o in out:
        key = o["item"]["price_threshold"]
        if key not in seen:
            seen.add(key)
            uniq.append(o)
    return uniq


def confirmation(text: str, reason_code: str | None, rows: list[tuple]) -> tuple[str, list[dict], dict | None]:
    """(질문, 선택지, 풀어 본 조건). rows는 그 종목의 최근 일봉 (price_window)."""
    cond = parse_relative(text or "")
    if cond is None:                     # 가격 조건 질문은 미지원 조건일 때만. 그 밖(이유를 모르는 LLM 판정 등)은 추적 여부를 묻는다
        if reason_code == "UNSUPPORTED_CONDITION":
            return _UNSUPPORTED, [], None
        return _GENERIC.get(reason_code or "", _GENERIC["LOW_CONFIDENCE"]), [], None
    info = {"base": cond.base, "pct": cond.pct, "direction": cond.direction, "base_word": cond.base_word}
    if cond.base == "cost":
        return f"{_obj(cond.base_word or '평단가')} 알려 주시면 그 가격 기준으로 알려 드릴게요.", [], info
    if cond.direction is None:
        return "오르는 쪽과 내리는 쪽 중 어느 쪽을 알려 드릴까요?", [], info
    options = build_options(cond, rows)
    if cond.base == "current":
        question = "지금 가격(최근 종가) 기준으로 볼까요?"
    else:
        word = cond.base_word or _BASE_LABEL[cond.base]
        question = f"'{word}'{_obj(word)[len(word):]} 어느 가격으로 볼까요?"     # '고점'을 어느 가격으로 볼까요?
    info["no_price_rows"] = not rows                     # 일봉이 없으면 선택지 없이 질문만
    return question, options, info
