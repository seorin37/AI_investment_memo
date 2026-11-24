"""주간보고서 종목 섹션 만들기 — 1단계: 코드만 (LLM 없음) (2026-11-23, docs/weekly-report-plan.md).

보고서 = 종목 섹션 여러 개. 섹션 모양은 프론트 `ReportStock`(ui/screens/studio/Studio.mock.ts)과 같다.
로고 색(logo·logo_bg·sc·st)은 프론트가 채운다. 맨 위 종합(종목 칸·합계·이번 주 한눈에)은 프론트가 섹션을 모아 계산한다.

- 주가: prices_daily 그 주 월~금 + 지난주 마지막 거래일 종가. 등락률·고가·저가·거래량 변화는 코드가 계산한다.
- 소식: 공시(그 주 접수, 자회사 공시 빼고 정정은 원본과 합침) + 뉴스(제목에 회사 이름, 시황 묶음 빼고, 같은 사건 하나, 최대 3건).
- 내 메모: AI 연결 메모의 추적 항목에 그 주 근거로 붙은 카드 → 연결 소식 수(linked_count).
- 지켜볼 것: 가격 조건까지 거리, 소식이 없으면 다음 주 소식.
- 흐름 문장(story): 지금은 코드 문장. 2단계에서 LLM 문장으로 바꾸고 이 문장은 대체 문장으로 남긴다.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import text

SEOUL = ZoneInfo("Asia/Seoul")
WEEKDAYS = "월화수목금토일"
NEWS_PER_STOCK = 3
# 여러 종목을 한꺼번에 다루는 시황·매매 동향 기사 (종목 소식이 아니다)
ROUNDUP = re.compile(r"시황|초고수|마감\s*[\]】]|\[이런국장|증시\s*(브리핑|요약)|오늘의\s*(증시|종목)|코스피.{0,6}(상승|하락|마감|출발)")
# 지수·시장 전체 기사는 종목 섹션이 아니라 국내 증시 칸 몫이다 (2026-11-23)
MARKET_WIDE = re.compile(r"코스피|코스닥|사이드카|서킷브레이커|증시")
# 제목 앞 [기재정정]·[첨부정정] 같은 표시
TAG = re.compile(r"^\s*\[[^\]]*\]\s*")
# 공시 제목을 읽기 쉽게 (DART 붙여 쓴 이름 → 띄어 쓴 이름). 없으면 원래 제목
DISCLOSURE_NAMES = [
    (re.compile(r"타법인주식및출자증권취득결정"), "타법인 주식 취득 결정"),
    (re.compile(r"타법인주식및출자증권처분결정"), "타법인 주식 처분 결정"),
    (re.compile(r"신규시설투자등"), "신규 시설투자 결정"),
    (re.compile(r"자기주식취득결정"), "자기주식 취득 결정"),
    (re.compile(r"자기주식처분결정"), "자기주식 처분 결정"),
    (re.compile(r"주식소각결정"), "주식 소각 결정"),
    (re.compile(r"현금ㆍ현물배당결정"), "현금 배당 결정"),
    (re.compile(r"연결재무제표기준영업\(잠정\)실적\(공정공시\)"), "연결 영업(잠정)실적"),
    (re.compile(r"영업\(잠정\)실적\(공정공시\)"), "영업(잠정)실적"),
    (re.compile(r"기업설명회\(IR\)개최\(안내공시\)"), "기업설명회(IR) 개최"),
]


# ─── 주 ───────────────────────────────────────────────

def last_week(today: date) -> tuple[date, date]:
    """보고서 주의 월요일과 금요일(주가 거래일 끝). 토·일이면 이번 주, 월~금이면 지난주."""
    monday = today - timedelta(days=today.weekday())
    if today.weekday() < 5:
        monday -= timedelta(days=7)
    return monday, monday + timedelta(days=4)


def news_window(monday: date, now: datetime) -> tuple[datetime, datetime, bool]:
    """소식(뉴스·공시)을 모으는 기간: 월요일 0시 ~ 일요일 밤 12시 (주말 기사도 넣는다, 2026-11-23).
    주말에 만들어 아직 일요일이 안 끝났으면 지금까지. (시작, 끝, 아직 진행 중인 주인지)"""
    start = datetime.combine(monday, time.min, SEOUL)
    end = datetime.combine(monday + timedelta(days=7), time.min, SEOUL)
    now = now.astimezone(SEOUL)
    return start, min(end, now), now < end


def week_label(monday: date) -> tuple[str, str]:
    """('2026년 11월 3주', '11월 3주 주간 보고서'). 그 달의 몇째 월요일 주인지."""
    n = (monday.day - 1) // 7 + 1
    return f"{monday.year}년 {monday.month}월 {n}주", f"{monday.month}월 {n}주 주간 보고서"


def md(d: date) -> str:
    return f"{d.month:02d}.{d.day:02d}"


def won(n: float) -> str:
    return f"{round(n):,}"


def won_short(n: float) -> str:
    """가격 조건 표기: 1,100,000 → '110만 원', 152,900 → '152,900원'."""
    n = round(n)
    return f"{n // 10000:,}만 원" if n % 10000 == 0 else f"{n:,}원"


# ─── 주가 ─────────────────────────────────────────────

def price_block(rows: list[dict], monday: date, friday: date) -> dict[str, Any] | None:
    """rows: 날짜 오름차순 {trade_date, high, low, close, volume} (지난주 포함). 그 주 거래일이 없으면 None."""
    week = [r for r in rows if monday <= r["trade_date"] <= friday]
    before = [r for r in rows if r["trade_date"] < monday]
    if not week or not before:
        return None
    prev = float(before[-1]["close"])
    closes = [float(r["close"]) for r in week]
    close = closes[-1]
    prev_week = [r for r in before if r["trade_date"] >= monday - timedelta(days=7)]
    # 거래량은 하루 평균으로 비교한다 (휴장·시세 누락으로 거래일 수가 다를 수 있다)
    vol_now = sum(int(r["volume"] or 0) for r in week) / len(week)
    vol_before = (sum(int(r["volume"] or 0) for r in prev_week) / len(prev_week)) if prev_week else 0
    lo_all, hi_all = min(closes + [prev]), max(closes + [prev])
    pad = max((hi_all - lo_all) * 0.15, hi_all * 0.005)
    return {
        "trade_dates": [r["trade_date"] for r in week],
        "close": close, "prev": prev, "closes": closes,
        "pct": round((close - prev) / prev * 100, 1),
        "hi": won(max(float(r["high"] or r["close"]) for r in week)),
        "lo": won(min(float(r["low"] or r["close"]) for r in week)),
        "lo_num": min(float(r["low"] or r["close"]) for r in week),   # 메모 제안(이번 주 저가)용 숫자
        "vol": (f"{(vol_now - vol_before) / vol_before * 100:+.0f}%" if vol_before else ""),
        "yr": [math.floor(lo_all - pad), math.ceil(hi_all + pad)],
    }


# ─── 소식 ─────────────────────────────────────────────

@dataclass
class Item:
    kind: str                 # '공시' | '뉴스'
    day: date
    title: str
    src: str
    ref: str                  # disc:<rcept_no> | news:<id>
    url: str | None = None
    score: float = 0.0
    no: int = 0
    linked: bool = False      # 내 메모 추적 항목에 붙은 카드의 근거
    snippet: str = ""         # LLM 입력용 본문 앞부분 (뉴스 요약·리드·첫 청크 / 공시 첫 청크) — 화면에는 안 보인다
    show: bool = True         # '이번 주 소식' 목록에 보인다 (False면 이슈 정리 근거로만 쓰고 출처 목록에만)
    buzz: int = 0             # 같은 날 비슷한 제목의 기사 수 (여러 매체가 다룬 큰 소식일수록 큼) — LLM 입력에 적는다


def clean_disclosure_title(title: str) -> str:
    t = TAG.sub("", title or "").strip()
    for pat, name in DISCLOSURE_NAMES:
        if pat.search(t):
            return name
    return t


def pick_disclosures(rows: list[dict]) -> list[Item]:
    """rows: {rcept_no, title, rcept_dt, source_url}. 자회사 공시는 빼고, 같은 제목(정정 표시 뗀)은 늦게 접수한 것 하나."""
    by_title: dict[str, dict] = {}
    for r in sorted(rows, key=lambda r: (r["rcept_dt"], r["rcept_no"])):
        if "자회사" in (r["title"] or ""):
            continue
        by_title[clean_disclosure_title(r["title"])] = r
    return [Item("공시", r["rcept_dt"], name, "DART", f"disc:{r['rcept_no']}", r.get("source_url"))
            for name, r in by_title.items()]


HANGUL_OR_WORD = re.compile(r"[0-9A-Za-z가-힣]")
# 이름 바로 뒤에 와도 되는 조사 (한 글자, 그 뒤는 한글이 아니어야 한다): "네이버가 …" 는 되고 "네이버스", "삼성디스플레이", "KB증권"은 안 된다
PARTICLES = "가이는은의도와과에를을로서만"


def mentions(title: str, name: str) -> bool:
    """제목에 회사 이름이 낱말로 있는가. 앞은 글자가 아니어야 하고, 뒤는 끝·기호·공백이거나 조사 한 글자(+글자 아님)."""
    t, n = title.lower(), name.lower()
    start = 0
    while (i := t.find(n, start)) >= 0:
        start = i + 1
        if i > 0 and HANGUL_OR_WORD.match(t[i - 1]):
            continue
        rest = t[i + len(n):]
        if not rest or not HANGUL_OR_WORD.match(rest[0]):
            return True
        if rest[0] in PARTICLES and (len(rest) == 1 or not HANGUL_OR_WORD.match(rest[1])):
            return True
    return False


WORD = re.compile(r"[가-힣A-Za-z0-9]{2,}")


def _buzz(rows: list[dict], names: list[str]) -> dict:
    """같은 날 다른 기사들과 낱말 2개 이상을 같이 쓰는 기사 수 — 여러 매체가 다룬 큰 소식일수록 크다.
    score가 같을 때(주말 기사는 아직 0) 큰 소식을 먼저 고르는 데 쓴다. 회사 이름은 낱말에서 뺀다."""
    drop = {n.lower() for n in names}
    words = {r["id"]: {w.lower() for w in WORD.findall(r["title"] or "")} - drop for r in rows}
    days: dict = {}
    for r in rows:
        days.setdefault(r["published_at"].astimezone(SEOUL).date(), []).append(r["id"])
    out = {}
    for ids in days.values():
        for a in ids:
            out[a] = sum(1 for b in ids if b != a and len(words[a] & words[b]) >= 2)
    return out


def pick_news(rows: list[dict], names: list[str], limit: int = NEWS_PER_STOCK, per_day: int | None = None) -> list[Item]:
    """rows: {id, title, published_at, url, score, source, cluster_id}. 제목에 회사 이름이 있는 기사만, 시황 묶음 빼고,
    같은 사건(cluster)·같은 제목은 하나, score 높은 순 limit건 → 날짜순.
    per_day를 주면 날짜마다 돌아가며 하나씩 고른다(하루 최대 per_day) — 주말 기사는 아직 score가 0이라
    점수 순으로만 고르면 늘 밀린다 (2026-11-23)."""
    keys = [n for n in names if n]
    seen_cluster: set = set()
    seen_title: set = set()
    cands: list[Item] = []
    buzz = _buzz(rows, keys)
    for r in sorted(rows, key=lambda r: (-(r["score"] or 0), -buzz.get(r["id"], 0), r["published_at"])):
        title = (r["title"] or "").strip()
        if not any(mentions(title, k) for k in keys) or ROUNDUP.search(title) or MARKET_WIDE.search(title):
            continue
        key = re.sub(r"\W", "", title.lower())[:20]      # 끝이 잘린 같은 제목("…매수자...")도 같은 기사로
        if (r.get("cluster_id") is not None and r["cluster_id"] in seen_cluster) or key in seen_title:
            continue
        seen_title.add(key)
        if r.get("cluster_id") is not None:
            seen_cluster.add(r["cluster_id"])
        cands.append(Item("뉴스", r["published_at"].astimezone(SEOUL).date(), title, r.get("source") or "", f"news:{r['id']}",
                          r.get("url"), float(r["score"] or 0), buzz=buzz.get(r["id"], 0)))
    if per_day is None:
        out = cands[:limit]
    else:
        by_day: dict = {}
        for c in cands:                                   # 날짜별로 점수 순서 유지
            by_day.setdefault(c.day, []).append(c)
        out, k = [], 0
        while len(out) < limit and any(len(v) > k for v in by_day.values()) and k < per_day:
            for d in sorted(by_day):
                if len(by_day[d]) > k and len(out) < limit:
                    out.append(by_day[d][k])
            k += 1
    return sorted(out, key=lambda i: i.day)


# ─── 내 메모 ──────────────────────────────────────────

@dataclass
class MemoLink:
    memo_id: int
    title: str
    created_at: datetime
    topics: list[tuple[int, str]] = field(default_factory=list)      # (item_id, 설명) 주제 항목
    prices: list[tuple[str, float]] = field(default_factory=list)    # (price_below|price_above, 가격)
    linked: dict[str, Item] = field(default_factory=dict)            # 그 주 근거 ref → 소식
    linked_topics: list[str] = field(default_factory=list)


CARD_KIND = {"news": "카드", "disclosure": "카드", "answer": "답", "price_condition": "가격"}
ANSWER_TAIL = re.compile(r"\s*사고파는 결정은 정해 드리지 않아요\.?\s*위 자료로 판단해 보세요\.?\s*$")
NO_ANSWER = "확인되지 않았어요"


def memo_digest_rows(rows: list[dict], numbers: dict[str, int], close: float | None = None, as_of: date | None = None,
                     max_memos: int = 5, max_cards: int = 3) -> list[dict]:
    """메모별 그 주 카드·답·가격 카드 목록 (코드, 카드 문장 그대로). numbers: 보고서 출처 ref → 번호.
    카드가 붙은 메모가 먼저(최근 카드 순), 그다음 최근 작성 순. '확인되지 않았어요' 답은 뺀다."""
    memos: dict[int, dict] = {}
    for r in rows:
        m = memos.get(r["memo_id"])
        if m is None:
            title = (r["title"] or "").strip() or next((ln.strip() for ln in (r["content"] or "").splitlines() if ln.strip()), "")[:40]
            made = r["created_at"].astimezone(SEOUL)
            m = memos[r["memo_id"]] = {"memo_id": str(r["memo_id"]), "title": title or "제목 없는 메모", "_made": made,
                                      "meta": f"{made.month}.{made.day} 작성", "cards": [], "_seen": set(), "prices": []}
        if r.get("item_type") in ("price_below", "price_above") and r.get("price_threshold") is not None:
            th = float(r["price_threshold"])
            if (r["item_type"], th) not in m["prices"]:
                m["prices"].append((r["item_type"], th))
        if r.get("upd_id") is None or r["upd_id"] in m["_seen"]:
            continue
        m["_seen"].add(r["upd_id"])
        text = ANSWER_TAIL.sub("", (r["summary"] or "").strip())
        if r["upd_type"] == "answer" and NO_ANSWER in text:
            continue
        at = r["upd_at"].astimezone(SEOUL)
        refs = sorted({numbers[x] for x in (r.get("refs") or []) if x in numbers})
        m["cards"].append({"id": str(r["upd_id"]), "date": f"{at.month}.{at.day:02d}", "kind": CARD_KIND.get(r["upd_type"], "카드"),
                           "title": (r["upd_title"] or "").strip(), "text": text[:160], "refs": refs, "_at": at})
    out = []
    for m in memos.values():
        m["cards"].sort(key=lambda c: c["_at"], reverse=True)
        more = max(0, len(m["cards"]) - max_cards)
        cards = [{k: v for k, v in c.items() if not k.startswith("_")} for c in m["cards"][:max_cards]]
        status = []
        for kind, th in m["prices"]:
            if close is not None:
                hit = close <= th if kind == "price_below" else close >= th
                cond, day = f"가격 조건 {won_short(th)} {'아래' if kind == 'price_below' else '위'}", f"{md(as_of)} " if as_of else ""
                status.append(f"{cond}는 {day}종가 {won(close)}원으로 도달했어요" if hit
                              else f"{cond}는 {day}종가 {won(close)}원 기준으로 아직이에요")
        out.append({"memo_id": m["memo_id"], "title": m["title"], "meta": m["meta"], "cards": cards, "more": more,
                    "status": status, "_last": m["cards"][0]["_at"] if m["cards"] else None, "_made": m["_made"]})
    out.sort(key=lambda m: (m["_last"] is not None, m["_last"] or m["_made"]), reverse=True)
    return [{k: v for k, v in m.items() if not k.startswith("_")} for m in out[:max_memos]]


def digest_code_line(memos: list[dict]) -> str:
    """카드가 없을 때 쓰는 코드 문장 (+ 가격 조건 상태). LLM이 실패해도 이 문장."""
    n, k = len(memos), sum(1 for m in memos if m["cards"])
    head = f"이번 주 내 메모 {n}개 중 {k}개에 새 소식이 붙었어요." if k else f"이번 주 내 메모 {n}개에 새로 붙은 소식은 없었어요."
    for m in memos:
        for st in m.get("status") or []:
            head += f" '{m['title']}' 메모의 {st}."
            break
    return head


def memo_section(links: list[MemoLink]) -> dict | None:
    """화면 칸이 하나라 카드가 붙은 메모 → 가장 최근 메모 순으로 하나만."""
    if not links:
        return None
    m = sorted(links, key=lambda x: (len(x.linked) > 0, x.created_at), reverse=True)[0]
    meta = f"{m.created_at.astimezone(SEOUL).month}.{m.created_at.astimezone(SEOUL).day} 작성 · AI 연결 중"
    if m.linked:
        nos = ", ".join(f"[{i.no}]" for i in sorted(m.linked.values(), key=lambda i: i.no))
        topic = m.linked_topics[0] if m.linked_topics else (m.topics[0][1] if m.topics else "")
        body = f"메모의 추적 항목 '{topic}'과 관련된 소식 {len(m.linked)}건({nos})이 이번 주에 붙었어요."
    else:
        body = "이번 주 이 메모와 관련된 새 소식은 없었어요."
    return {"memo_id": str(m.memo_id), "title": m.title, "meta": meta, "body": body, "linked_count": len(m.linked)}


# 정기 공시 마감 (12월 결산 기준): 분기 끝 + 45일, 사업보고서는 결산 + 90일
PERIODIC_DUE = [(5, 15, "1분기 보고서"), (8, 14, "반기보고서"), (11, 14, "3분기 보고서"), (3, 31, "사업보고서")]
TRACKED_REPORT = re.compile(r"보고서|실적")


def next_periodic(as_of: date) -> tuple[date, str]:
    """as_of 다음에 오는 정기 공시 마감과 이름."""
    cands = []
    for y in (as_of.year, as_of.year + 1):
        for m, d, name in PERIODIC_DUE:
            due = date(y, m, d)
            if due > as_of:
                cands.append((due, name))
    return min(cands)


def periodic_suggestion(as_of: date, name: str = "", quarter: dict | None = None) -> dict:
    """다음 정기 공시 제안 — 종목 이름과 최근 분기 실적 숫자를 넣어 종목마다 다른 문장으로 (2026-11-24).
    숫자는 quarter_block 값 그대로 (예측 없이 '최근 분기는 얼마였다'만)."""
    due, rep = next_periodic(as_of)
    who = f"{name} " if name else ""
    if quarter and (quarter.get("operating_income") or quarter.get("net_income")):
        key, val = ("영업이익", quarter["operating_income"]) if quarter.get("operating_income") else ("순이익", quarter["net_income"])
        yoy = quarter.get("op_yoy") if key == "영업이익" else None
        q = quarter.get("label", "최근 분기").split(" ")[-1]                       # '2026년 3분기' → '3분기'
        yoy_txt = f", 전년 대비 {yoy:+.1f}%" if isinstance(yoy, (int, float)) else ""
        return {"sid": "periodic", "kind": "schedule",
                "text": f"{due.month}월 {rep}에 {q} 이후 {key}이 어떻게 나오는지 ({q} {val}{yoy_txt})",
                "memo_title": f"{who}{rep} 실적".strip()[:20],
                "memo_body": f"{who}{rep}({due.month}월 {due.day}일까지) 나오면 매출이랑 {key} 알려줘. {q} {key}은 {val}{yoy_txt}였어",
                "why": f"정기 공시 일정 · {quarter.get('label', '최근 분기')} 실적"}
    return {"sid": "periodic", "kind": "schedule", "text": f"{who}{due.year}년 {due.month}월 {rep}에 실적이 어떻게 나오는지",
            "memo_title": f"{who}{rep} 실적".strip()[:20],
            "memo_body": f"{who}{rep}({due.month}월 {due.day}일까지) 나오면 매출이랑 영업이익 알려줘", "why": "정기 공시 일정"}


def watch_lines(links: list[MemoLink], close: float, as_of: date, has_items: bool, *, code: str = "",
                items: list | None = None, lo: float | None = None, suggest: list[dict] | None = None,
                name: str = "", quarter: dict | None = None) -> list[dict]:
    """앞으로 지켜볼 것 = 다음에 추적해 볼 메모 제안 (2026-11-24: 칸이 비지 않게 종목마다 최소 1개).
    제안(kind follow·schedule·price)은 '메모에 추가'로 종목 메모 창에 memo_title·memo_body를 채워 연다.
    이미 추적 중인 가격 조건은 kind tracking(버튼 없이 '추적 중')으로 뒤에 둔다. sid는 보고서 안 종목별 고유값."""
    items = items or []
    topics = [t for m in links for _, t in m.topics]
    has_price = any(m.prices for m in links)
    out: list[dict] = []
    for k, s in enumerate(suggest or []):                                   # 1) LLM: 이번 주 소식의 후속
        out.append({"sid": f"f{k}", "kind": "follow", "text": s["text"], "memo_title": s["memo_title"],
                    "memo_body": s["memo_body"], "why": "이번 주 소식 " + "".join(f"[{r}]" for r in s["refs"])})
    ir = next((i for i in items if i.kind == "공시" and "기업설명회" in (i.title or "")), None)
    if ir is not None:                                                     # 2) 코드: 이번 주 IR 안내 공시
        out.append({"sid": "ir", "kind": "schedule", "text": "IR(기업설명회)에서 어떤 내용이 나오는지",
                    "memo_title": "IR 내용 확인", "memo_body": f"IR 안내 공시[{ir.no}]의 기업설명회 결과나 자료 나오면 알려줘",
                    "why": f"이번 주 공시 [{ir.no}]"})
    if not any(TRACKED_REPORT.search(t) for t in topics):                  # 3) 코드: 다음 정기 공시
        out.append(periodic_suggestion(as_of, name, quarter))
    if not has_price and lo:                                               # 4) 코드: 이번 주 저가 (사실 숫자)
        out.append({"sid": "low", "kind": "price", "text": f"이번 주 저가 {won(lo)}원 아래로 내려가는지",
                    "memo_title": f"{won_short(lo)} 아래면 다시 보기", "memo_body": f"{won(lo)}원 아래로 내려가면 알려줘. 이번 주 저가였어",
                    "why": "이번 주 저가"})
    out = out[:3]
    for k, (m, (kind, th)) in enumerate((m, pr) for m in links for pr in m.prices):   # 5) 이미 추적 중인 가격 조건
        diff = (close - th) / th * 100
        out.append({"sid": f"t{k}", "kind": "tracking", "tracked": True,
                    "text": f"메모의 가격 조건 {won_short(th)}과 {md(as_of)} 종가의 차이 ({abs(diff):.1f}% {'위' if diff >= 0 else '아래'})",
                    "why": "내 메모 가격 조건"})
    return out


# ─── 흐름 문장 (코드) ─────────────────────────────────

def code_story(p: dict, items: list[Item]) -> str:
    last = p["trade_dates"][-1]
    if not items:
        i = max(range(len(p["closes"])), key=lambda k: p["closes"][k])
        d = p["trade_dates"][i]
        return (f"이번 주 새 공시·뉴스는 없었어요. {WEEKDAYS[d.weekday()]}요일({md(d)}) 종가 {won(p['closes'][i])}원이 "
                f"이번 주 가장 높았고, {md(last)} 종가 기준 {won(p['close'])}원이에요.")
    nd = sum(1 for i in items if i.kind == "공시")
    nn = len(items) - nd
    bits = "·".join(b for b in (f"공시 {nd}건" if nd else "", f"뉴스 {nn}건" if nn else "") if b)
    move = "높은" if p["pct"] > 0 else "낮은" if p["pct"] < 0 else "같은"
    pct = f"{abs(p['pct']):.1f}% " if p["pct"] else ""
    return f"이번 주 {bits}이 있었어요. {md(last)} 종가는 지난주보다 {pct}{move} {won(p['close'])}원이에요."


# ─── DB ───────────────────────────────────────────────

PRICES_SQL = """SELECT trade_date, high, low, close, volume FROM prices_daily
WHERE symbol = :s AND trade_date BETWEEN :since AND :until ORDER BY trade_date"""
STOCK_SQL = """SELECT btrim(us.symbol) AS code, s.name, us.status::text AS status FROM user_stocks us
JOIN stocks s ON s.symbol = us.symbol WHERE us.user_id = :u AND us.deleted_at IS NULL ORDER BY us.created_at, us.symbol"""
DISC_SQL = """SELECT rcept_no, title, rcept_dt, source_url FROM disclosures
WHERE symbol = :s AND rcept_dt BETWEEN :mon AND :fri"""
NEWS_SQL = """SELECT a.id, a.title, a.published_at, a.url, ns.score, src.name AS source, cm.cluster_id
FROM news_stocks ns JOIN news_articles a ON a.id = ns.news_id
LEFT JOIN news_sources src ON src.id = a.source_id
LEFT JOIN news_cluster_members cm ON cm.news_id = a.id
WHERE ns.symbol = :s AND a.published_at >= :start AND a.published_at < :end"""
MEMO_SQL = """SELECT m.id AS memo_id, m.title, m.content, m.created_at, ti.id AS item_id, ti.type::text AS type,
       ti.description, ti.price_threshold
FROM memos m JOIN tracking_items ti ON ti.memo_id = m.id
WHERE m.user_id = :u AND m.symbol = :s AND m.deleted_at IS NULL AND m.ai_linked AND ti.status = 'active'
  AND ti.type::text <> 'ask'
ORDER BY m.id, ti.id"""
LINKED_SQL = """SELECT tu.tracking_item_id AS item_id, us.news_id, us.disclosure_rcept_no AS rcept_no,
       a.title AS news_title, a.published_at, a.url AS news_url, src.name AS source,
       d.title AS disc_title, d.rcept_dt, d.source_url
FROM tracking_updates tu JOIN update_sources us ON us.update_id = tu.id
LEFT JOIN news_articles a ON a.id = us.news_id LEFT JOIN news_sources src ON src.id = a.source_id
LEFT JOIN disclosures d ON d.rcept_no = us.disclosure_rcept_no
WHERE tu.tracking_item_id = ANY(:ids)
  AND ((a.published_at >= :start AND a.published_at < :end) OR d.rcept_dt BETWEEN :mon AND :fri)"""
# 이번 주 내 메모 정리 (2026-11-24): 그 종목의 AI 연결 메모와, 그 주 소식으로 만들어진 카드(다음 날 아침 생성)
DIGEST_SQL = """SELECT m.id AS memo_id, m.title, m.content, m.created_at, ti.type::text AS item_type, ti.price_threshold,
       tu.id AS upd_id, tu.type::text AS upd_type, tu.title AS upd_title, tu.summary, tu.created_at AS upd_at,
       (SELECT array_agg(coalesce('news:' || us.news_id::text, 'disc:' || us.disclosure_rcept_no))
          FROM update_sources us WHERE us.update_id = tu.id) AS refs
FROM memos m
LEFT JOIN tracking_items ti ON ti.memo_id = m.id
LEFT JOIN tracking_updates tu ON tu.tracking_item_id = ti.id AND tu.created_at >= :cs AND tu.created_at < :ce
WHERE m.user_id = :u AND m.symbol = :s AND m.deleted_at IS NULL AND m.ai_linked AND m.kind = 'note'
  AND m.created_at < :me                                   -- 그 주가 끝나기 전에 쓴 메모만
ORDER BY m.id, tu.created_at"""
NEWS_SNIP_SQL = """SELECT a.id, a.summary,
       (SELECT l.lead_text FROM news_article_leads l WHERE l.news_id = a.id) AS lead,
       (SELECT nc.chunk_text FROM news_chunks nc WHERE nc.news_id = a.id ORDER BY nc.chunk_index LIMIT 1) AS chunk
FROM news_articles a WHERE a.id = ANY(:ids)"""
DISC_SNIP_SQL = """SELECT rcept_no, string_agg(chunk_text, ' ' ORDER BY chunk_index) AS text FROM (
  SELECT rcept_no, chunk_index, chunk_text FROM disclosure_chunks WHERE rcept_no = ANY(:ids) AND chunk_index < 2) c
GROUP BY rcept_no"""
FUND_SQL = """SELECT basis_trade_date, per, pbr, eps, bps, w52_high, w52_low, market_cap FROM stock_fundamentals_snapshot
WHERE symbol = :s AND basis_trade_date <= :d ORDER BY basis_trade_date DESC LIMIT 1"""
QUARTER_SQL = """SELECT period_end, quarter, fs_div, revenue, operating_income, net_income FROM financials_quarterly
WHERE symbol = :s AND period_end <= :d ORDER BY period_end DESC, (fs_div = 'consolidated') DESC LIMIT 12"""
INDEX_SQL = """SELECT trade_date AS day, close AS value FROM market_indices
WHERE code = :c AND trade_date BETWEEN :since AND :fri ORDER BY trade_date"""
OBS_SQL = """SELECT observation_date AS day, value FROM economic_observations
WHERE indicator_code = :c AND value IS NOT NULL AND observation_date BETWEEN :since AND :fri ORDER BY observation_date"""


def _rows(db, sql: str, **params) -> list[dict]:
    return [dict(r) for r in db.execute(text(sql), params).mappings().all()]


def _memo_links(db, user_id: int, symbol: str, window: dict) -> list[MemoLink]:
    links: dict[int, MemoLink] = {}
    items: dict[int, MemoLink] = {}
    for r in _rows(db, MEMO_SQL, u=user_id, s=symbol):
        m = links.get(r["memo_id"])
        if m is None:
            title = (r["title"] or "").strip() or next((ln.strip() for ln in (r["content"] or "").splitlines() if ln.strip()), "")[:40]
            m = links[r["memo_id"]] = MemoLink(r["memo_id"], title or "제목 없는 메모", r["created_at"])
        if r["type"] in ("price_below", "price_above") and r["price_threshold"] is not None:
            m.prices.append((r["type"], float(r["price_threshold"])))
        else:
            m.topics.append((r["item_id"], r["description"]))
        items[r["item_id"]] = m
    if items:
        desc = {iid: d for m in links.values() for iid, d in m.topics}
        for r in _rows(db, LINKED_SQL, ids=list(items), **window):
            m = items[r["item_id"]]
            if r["news_id"] is not None:
                it = Item("뉴스", r["published_at"].astimezone(SEOUL).date(), r["news_title"] or "", r["source"] or "",
                          f"news:{r['news_id']}", r["news_url"])
            else:
                it = Item("공시", r["rcept_dt"], clean_disclosure_title(r["disc_title"]), "DART", f"disc:{r['rcept_no']}", r["source_url"])
            it.linked = True
            m.linked.setdefault(it.ref, it)
            if r["item_id"] in desc and desc[r["item_id"]] not in m.linked_topics:
                m.linked_topics.append(desc[r["item_id"]])
    return list(links.values())


def _change(rows: list[dict], monday: date) -> float | None:
    week = [r for r in rows if r["day"] >= monday]
    before = [r for r in rows if r["day"] < monday]
    if not week or not before:
        return None
    return round((float(week[-1]["value"]) - float(before[-1]["value"])) / float(before[-1]["value"]) * 100, 1)


def market_block(db, monday: date, friday: date) -> list[dict]:
    since = monday - timedelta(days=10)
    out = []
    for name, sql, code in (("코스피", INDEX_SQL, "KOSPI"), ("코스닥", INDEX_SQL, "KOSDAQ"), ("원/달러", OBS_SQL, "USD_KRW")):
        rows = _rows(db, sql, c=code, since=since, fri=friday)
        pct = _change(rows, monday)
        if pct is not None:
            week = [r for r in rows if r["day"] >= monday]
            out.append({"name": name, "value": f"{float(week[-1]['value']):,.2f}", "pct": pct, "as_of": week[-1]["day"].isoformat()})
    return out


def money(v) -> str:
    """원 단위 금액 → '195.3조원' / '8,345억원' (화면 표기, 코드 계산)."""
    if v is None:
        return ""
    v = float(v)
    return f"{v / 1e12:,.1f}조원" if abs(v) >= 1e12 else f"{v / 1e8:,.0f}억원"


def valuation(db, symbol: str, as_of: date, close: float) -> dict | None:
    """PER·PBR·EPS·시가총액·52주 위치 (stock_fundamentals_snapshot, 그 날 이전 마지막 값)."""
    r = next(iter(_rows(db, FUND_SQL, s=symbol, d=as_of)), None)
    if r is None:
        return None
    hi, lo = r["w52_high"], r["w52_low"]
    pos = round((close - float(lo)) / (float(hi) - float(lo)) * 100) if hi and lo and float(hi) > float(lo) else None
    f = lambda v, d=2: None if v is None else round(float(v), d)
    return {"basis": r["basis_trade_date"].isoformat(), "per": f(r["per"]), "pbr": f(r["pbr"]), "eps": f(r["eps"], 0),
            "market_cap": money(r["market_cap"]), "w52_high": f(hi, 0), "w52_low": f(lo, 0), "w52_pos": pos}


def quarter_block(db, symbol: str, as_of: date) -> dict | None:
    """최근 분기 매출·영업이익·순이익과 전년 같은 분기 대비 (연결 우선)."""
    rows = _rows(db, QUARTER_SQL, s=symbol, d=as_of)
    if not rows:
        return None
    fs = "consolidated" if any(r["fs_div"] == "consolidated" for r in rows) else rows[0]["fs_div"]
    rows = [r for r in rows if r["fs_div"] == fs]
    cur = rows[0]
    pe = cur["period_end"]
    prev = next((r for r in rows if r["period_end"].year == pe.year - 1 and r["period_end"].month == pe.month), None)
    yoy = lambda k: (round((float(cur[k]) - float(prev[k])) / abs(float(prev[k])) * 100, 1)
                     if prev and cur[k] is not None and prev[k] not in (None, 0) else None)
    return {"label": f"{pe.year}년 {cur['quarter']}분기" if cur.get("quarter") else f"{pe:%Y.%m}", "basis": "연결" if fs == "consolidated" else "별도",
            "revenue": money(cur["revenue"]), "operating_income": money(cur["operating_income"]), "net_income": money(cur["net_income"]),
            "revenue_yoy": yoy("revenue"), "op_yoy": yoy("operating_income")}


def add_snippets(db, items: list[Item]) -> None:
    news = [int(i.ref.split(":")[1]) for i in items if i.ref.startswith("news:")]
    discs = [i.ref.split(":")[1] for i in items if i.ref.startswith("disc:")]
    snip: dict[str, str] = {}
    if news:
        for r in _rows(db, NEWS_SNIP_SQL, ids=news):
            t = (r["summary"] or "").strip()
            snip[f"news:{r['id']}"] = t if len(t) >= 40 else (r["lead"] or r["chunk"] or t or "")
    if discs:
        for r in _rows(db, DISC_SNIP_SQL, ids=discs):
            snip[f"disc:{r['rcept_no']}"] = r["text"] or ""
    for i in items:
        # 정기보고서 첫 청크는 작성 기준 같은 상투 문구라 넣지 않는다 (제목만으로 충분)
        if i.kind == "공시" and re.search(r"(분기|반기|사업)보고서", i.title):
            i.snippet = ""
            continue
        i.snippet = re.sub(r"\s+", " ", snip.get(i.ref, "")).strip()[:300]


def company_names(name: str, symbol: str) -> list[str]:
    """뉴스 제목 필터용 이름: 종목 이름 + configs/stock_aliases.yaml + 판정 사전 별칭."""
    from pipelines.tracking.lexicon import load_lexicon
    from pipelines.updates.candidates import company_terms, load_symbol_aliases
    names = company_terms(name, symbol, None, load_symbol_aliases())
    try:
        names += [a for a, s in load_lexicon().aliases if s == symbol and len(a) >= 2]
    except Exception:
        pass
    return list(dict.fromkeys(names))


def build_report(db, user_id: int, codes: list[str] | None = None, today: date | None = None,
                 market: bool = True, now: datetime | None = None,
                 llm=None) -> dict[str, Any]:
    """보고서 content. codes가 없으면 내 종목 전부. llm(메시지→dict)을 주면 흐름 문장을 LLM으로 쓴다(2단계), 없으면 코드 문장."""
    today = today or datetime.now(SEOUL).date()
    monday, friday = last_week(today)
    now = now or datetime.now(SEOUL)
    start, end, partial = news_window(monday, now if today == now.astimezone(SEOUL).date() else
                                      datetime.combine(today, time.max, SEOUL))
    news_last = (end - timedelta(microseconds=1)).date()          # 소식 마지막 날 (보통 일요일)
    window = {"start": start, "end": end, "mon": monday, "fri": news_last}
    mine = _rows(db, STOCK_SQL, u=user_id)
    stocks = [s for s in mine if not codes or s["code"] in codes]
    warnings: list[str] = []
    sections, all_items = [], []
    for s in stocks:
        p = price_block(_rows(db, PRICES_SQL, s=s["code"], since=monday - timedelta(days=10), until=friday), monday, friday)
        if p is None:
            warnings.append(f"{s['name']}: 그 주 시세가 없어 뺐어요")
            continue
        # 금요일 시세가 아직 없는 건 정상이다 (2026-11-23 확인). 머리·지수는 종목의 실제 마지막 거래일에 맞춘다
        items = pick_disclosures(_rows(db, DISC_SQL, s=s["code"], mon=monday, fri=news_last))
        ctx_news = pick_news(_rows(db, NEWS_SQL, s=s["code"], start=start, end=end), company_names(s["name"], s["code"]), limit=10, per_day=2)
        shown = {i.ref for i in sorted(ctx_news, key=lambda i: -i.score)[:NEWS_PER_STOCK]}
        for i in ctx_news:
            i.show = i.ref in shown                       # 화면 목록은 3건, 나머지는 이슈 정리 근거
        items += ctx_news
        links = _memo_links(db, user_id, s["code"], window)
        refs = {i.ref for i in items}
        for m in links:                                   # 메모 카드 근거가 목록에 없으면 더한다
            for it in m.linked.values():
                if it.ref not in refs:
                    items.append(it)
                    refs.add(it.ref)
                else:
                    same = next(i for i in items if i.ref == it.ref)
                    same.linked = same.show = True
        items.sort(key=lambda i: (i.day, i.kind != "공시"))
        if llm is not None:
            add_snippets(db, items)
        all_items += items
        sections.append({"s": s, "p": p, "items": items, "links": links})
    # 출처 번호: 보고서 전체에서 날짜순 (공시 먼저)
    order = {id(sec): k for k, sec in enumerate(sections)}
    numbered = sorted(((it, sec) for sec in sections for it in sec["items"]),
                      key=lambda x: (not x[0].show, x[0].day, x[0].kind != "공시", order[id(x[1])]))   # 화면 목록 먼저, 이슈 근거는 뒤 번호
    sources = []
    for n, (it, sec) in enumerate(numbered, 1):
        it.no = n
        sources.append({"no": n, "text": f"[{n}] {it.src or '뉴스'} · {sec['s']['name']} {it.title} · {it.day:%Y.%m.%d}",
                        "code": sec["s"]["code"], "ref": it.ref, "url": it.url})
    out_stocks = []
    story_meta = {"llm_calls": 0, "usage": {"input": 0, "output": 0}, "fallbacks": []}
    for sec in sections:
        s, p, items, links = sec["s"], sec["p"], sec["items"], sec["links"]
        shown_items = [i for i in items if i.show]
        story, issues, source = code_story(p, shown_items), "", "code"
        suggest: list[dict] = []
        if llm is not None:
            from .story import llm_stock
            tracked = [t for m in links for _, t in m.topics] + [f"{won_short(th)} {'아래' if k == 'price_below' else '위'}" for m in links for k, th in m.prices]
            extra = ["[이미 추적 중인 메모] " + " / ".join(tracked)] if tracked else None
            story, issues, meta = llm_stock(s["name"], p, items, llm, story, extra=extra)
            suggest = meta.get("suggest") or []
            source = meta["source"]
            story_meta["llm_calls"] += meta["tries"]
            for k in story_meta["usage"]:
                story_meta["usage"][k] += meta["usage"][k]
            if meta["problems"]:
                story_meta["fallbacks"].append({"name": s["name"], "problems": meta["problems"]})
            if meta.get("removed"):
                story_meta.setdefault("removed", []).append({"name": s["name"], "sentences": meta["removed"]})
        for m in links:                                    # 번호가 붙은 뒤 같은 객체로 맞춘다
            m.linked = {ref: next(i for i in items if i.ref == ref) for ref in m.linked}
        dates = p["trade_dates"]
        numbers = {i.ref: i.no for i in items}
        memos = memo_digest_rows(_rows(db, DIGEST_SQL, u=user_id, s=s["code"], cs=start, ce=end + timedelta(days=1), me=end),
                                 numbers, p["close"], dates[-1])
        digest = digest_code_line(memos) if memos else ""
        if memos and llm is not None:
            from .story import llm_memo_digest
            digest, dmeta = llm_memo_digest(s["name"], memos, llm, digest)
            story_meta["llm_calls"] += dmeta["tries"]
            for k in story_meta["usage"]:
                story_meta["usage"][k] += dmeta["usage"][k]
            if dmeta["problems"]:
                story_meta["fallbacks"].append({"name": s["name"] + " 메모 정리", "problems": dmeta["problems"]})
        out_stocks.append({
            "stock_code": s["code"], "name": s["name"], "own": "보유" if s["status"] == "holding" else "관심",
            "pct": p["pct"], "close": p["close"], "prev": p["prev"], "closes": p["closes"], "yr": p["yr"],
            "hi": p["hi"], "lo": p["lo"], "vol": p["vol"], "trade_dates": [d.isoformat() for d in dates],
            "events": [[it.day.weekday(), it.no, "g" if it.kind == "공시" else "n"] for it in shown_items if monday <= it.day <= friday and it.day.weekday() < 5],   # 차트 점은 거래일만 (주말 소식은 목록에만)
            "counts": {"공시": sum(1 for i in shown_items if i.kind == "공시"), "뉴스": sum(1 for i in shown_items if i.kind == "뉴스")},
            "story": story, "story_source": source, "issues": issues,
            "items": [{"no": i.no, "kind": i.kind, "date": md(i.day), "title": i.title, "src": i.src, "ref": i.ref,
                       "url": i.url, "linked": i.linked} for i in shown_items],
            "issue_refs": [i.no for i in items if not i.show],
            "valuation": valuation(db, s["code"], dates[-1], p["close"]),
            "quarter": (qb := quarter_block(db, s["code"], dates[-1])),
            "memo": memo_section(links),
            "memos": memos, "memo_digest": digest,          # 이번 주 내 메모 정리 (2026-11-24, 메모 없으면 빈 목록)
            "watch": watch_lines(links, p["close"], dates[-1], bool(shown_items), code=s["code"], items=items,
                                 lo=p.get("lo_num"), suggest=suggest, name=s["name"], quarter=qb),
        })
    week, title = week_label(monday)
    last_day = max((date.fromisoformat(x["trade_dates"][-1]) for x in out_stocks), default=friday)
    n_days = max((len(x["trade_dates"]) for x in out_stocks), default=0)
    days = [monday + timedelta(days=k) for k in range(5)]
    mk = None
    if market:
        from .market import market_section
        mk = market_section(db, monday, last_day, start, end, llm, first_no=len(sources) + 1)
        for i in mk["items"]:
            sources.append({"no": i["no"], "text": f"[{i['no']}] {i['src'] or '뉴스'} · {i['title']} · {i['day']:%Y.%m.%d}",
                            "code": "", "ref": i["ref"], "url": i["url"]})
        story_meta["llm_calls"] += mk["meta"]["tries"]
        for k in story_meta["usage"]:
            story_meta["usage"][k] += mk["meta"]["usage"][k]
        if mk["meta"]["problems"]:
            story_meta["fallbacks"].append({"name": "국내 증시", "problems": mk["meta"]["problems"]})
        if mk["meta"].get("removed"):
            story_meta.setdefault("removed", []).append({"name": "국내 증시", "sentences": mk["meta"]["removed"]})
    return {
        "period_start": monday.isoformat(), "period_end": news_last.isoformat(), "partial_week": partial,
        "week": week, "title": title,
        "range": f"{md(monday)}({WEEKDAYS[0]}) ~ {md(news_last)}({WEEKDAYS[news_last.weekday()]})",   # 소식 기간 (주말 포함)
        "trade_days": n_days, "as_of": last_day.isoformat(),
        "days": [f"{md(d)} {WEEKDAYS[d.weekday()]}" for d in days], "days_short": list(WEEKDAYS[:5]),
        "made_at": now.astimezone(SEOUL).strftime("%m.%d %H:%M"),
        "market": mk["cells"] if mk else [],                              # 종목과 같은 날 기준
        "market_summary": mk["summary"] if mk else "", "flow": mk["flow"] if mk else [],
        "stocks": out_stocks, "sources": sources,
        "source_note": "시세는 KIS, 공시는 DART 원문을 바탕으로 정리했어요. 뉴스는 제목·언론사·날짜만 쓰고 원문 링크로 연결해요.",
        "warnings": warnings, "story_meta": story_meta,
    }
