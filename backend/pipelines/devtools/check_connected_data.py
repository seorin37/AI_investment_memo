"""화면에 연결된 시세·지수·거시·기업정보·뉴스 API 가 DB 원본과 같은 값을 주는지 대조 (읽기 전용).

API 는 앱 안에서 직접 부른다(TestClient, 인증만 가짜 사용자로 바꿈) — 서버를 띄우거나 공개하지 않는다.
비교 기준은 API 코드가 아니라 DB 테이블을 따로 읽은 값이다.

    cd backend
    python -m pipelines.devtools.check_connected_data            # 내 종목 + 코스피 시총 상위 50
    python -m pipelines.devtools.check_connected_data --top 100

화면 ↔ API (docs/api-inventory.md '연결 1단계')
- 홈 시장 지수 · 앱 지수 자세히  GET /market/overview
- 내 종목 목록 · 추가 후보       GET /quotes
- 보드 종목 머리                 GET /stocks/{code}/quote
- 기업정보                       GET /stocks/{code}/profile · quote · candles · financials
- 스튜디오 실험실 변수           GET /market/macro
- 홈 뉴스                        GET /news/home
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from datetime import date
from decimal import Decimal
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(REPO_ROOT / ".env")

import psycopg  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.auth.routes import get_current_user  # noqa: E402
from app.main import app  # noqa: E402
from pipelines.common.db import get_read_dsn  # noqa: E402

COMPANY_SAMPLES = ["005930", "000660", "105560", "005935"]  # 일반 · 일반 · 금융사 · 우선주
INDEX_SOURCES = {"KOSPI": ("index", "KOSPI"), "KOSDAQ": ("index", "KOSDAQ"), "USDKRW": ("observation", "USD_KRW")}


class Report:
    def __init__(self) -> None:
        self.rows: list[tuple[str, str, str]] = []

    def add(self, area: str, ok: bool | None, msg: str) -> None:
        self.rows.append((area, "OK" if ok else ("확인" if ok is None else "틀림"), msg))

    def print(self) -> int:
        bad = 0
        for area, mark, msg in self.rows:
            bad += mark == "틀림"
            print(f"[{mark:^4}] {area:<14} {msg}")
        counts = Counter(m for _, m, _ in self.rows)
        print(f"\n합계: OK {counts['OK']} · 확인 {counts['확인']} · 틀림 {counts['틀림']}")
        return 1 if bad else 0


def same(a, b) -> bool:
    if a is None or b is None:
        return a is b
    return abs(Decimal(str(a)) - Decimal(str(b))) < Decimal("0.01")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--top", type=int, default=50, help="코스피 시총 상위 몇 종목을 볼지 (내 종목은 항상 포함)")
    args = parser.parse_args()

    app.dependency_overrides[get_current_user] = lambda: {"id": "0"}
    api = TestClient(app)
    rep = Report()

    with psycopg.connect(get_read_dsn(), connect_timeout=5) as db:
        q = lambda sql, *p: db.execute(sql, p).fetchall()  # noqa: E731

        # ── 데이터 신선도
        latest_px = q("SELECT max(trade_date) FROM prices_daily")[0][0]
        print(f"오늘 {date.today()} · 주가 최신 거래일 {latest_px}\n")

        # ── 대상 종목: 사용자들이 담은 종목 + 코스피 시총 상위
        mine = [r[0] for r in q("SELECT DISTINCT btrim(symbol) FROM user_stocks WHERE deleted_at IS NULL")]
        top = [r[0] for r in q(
            """SELECT btrim(p.symbol) FROM prices_daily p JOIN stocks s ON s.symbol = p.symbol
               WHERE p.trade_date = %s AND s.market::text = 'KOSPI'
               ORDER BY p.market_cap DESC NULLS LAST LIMIT %s""", latest_px, args.top)]
        codes = list(dict.fromkeys(mine + top))

        # ── GET /quotes (내 종목 목록) · /stocks/{code}/quote (보드 머리)
        got: dict[str, dict] = {}
        missing_api: list[str] = []
        for i in range(0, len(codes), 50):
            r = api.get("/api/v1/quotes", params={"codes": ",".join(codes[i:i + 50])})
            if r.status_code != 200:
                rep.add("시세 /quotes", False, f"HTTP {r.status_code} {r.text[:80]}")
                continue
            body = r.json()
            got.update({x["code"]: x for x in body["quotes"]})
            missing_api += body["missing"]
        wrong, stale = [], []
        for code in codes:
            px = q("SELECT trade_date, close FROM prices_daily WHERE symbol = %s ORDER BY trade_date DESC LIMIT 2", code)
            if not px:
                if code not in missing_api:
                    wrong.append(f"{code}: DB 시세 없는데 API 가 값을 줌")
                continue
            a = got.get(code)
            if not a:
                wrong.append(f"{code}: DB 시세 있는데 API missing")
                continue
            change = px[0][1] - px[1][1] if len(px) > 1 else Decimal(0)
            if not same(a["price"], px[0][1]) or not same(a["change"], change) or a["trade_date"] != px[0][0].isoformat():
                wrong.append(f"{code}: API {a['price']}/{a['change']}/{a['trade_date']} ≠ DB {px[0][1]}/{change}/{px[0][0]}")
            if px[0][0] < latest_px:
                stale.append(f"{code}({px[0][0]})")
        rep.add("시세 /quotes", not wrong, f"{len(codes)}종목(내 종목 {len(mine)}) 중 값·등락·날짜 불일치 {len(wrong)}" + (f": {wrong[:3]}" if wrong else ""))
        rep.add("시세 /quotes", None if missing_api else True, f"시세 없는 종목 {len(missing_api)}: {missing_api[:10]}")
        rep.add("시세 /quotes", None if stale else True, f"최신 거래일({latest_px})보다 오래된 종목 {len(stale)}: {stale[:10]}")
        diff_single = []
        for code in mine[:20] or codes[:5]:
            one = api.get(f"/api/v1/stocks/{code}/quote")
            if one.status_code == 200 and got.get(code) and one.json() != got[code]:
                diff_single.append(code)
        rep.add("보드 /quote", not diff_single, f"/stocks/{{code}}/quote 와 /quotes 한 줄이 다른 종목 {len(diff_single)} {diff_single[:5]}")

        # ── GET /market/overview (홈 지수)
        r = api.get("/api/v1/market/overview")
        if r.status_code != 200:
            rep.add("지수 /overview", False, f"HTTP {r.status_code}")
        else:
            idx = {x["key"]: x for x in r.json()["indices"]}
            for key, (src, code) in INDEX_SOURCES.items():
                sql = ("SELECT trade_date, close FROM market_indices WHERE code = %s ORDER BY trade_date DESC LIMIT 2" if src == "index"
                       else "SELECT observation_date, value FROM economic_observations WHERE indicator_code = %s AND value IS NOT NULL ORDER BY observation_date DESC LIMIT 2")
                d = q(sql, code)
                a = idx.get(key)
                if not d or not a:
                    rep.add("지수 /overview", False, f"{key}: API {'없음' if not a else '있음'} · DB {'없음' if not d else '있음'}")
                    continue
                ok = same(a["value"], d[0][1]) and a["trade_date"] == d[0][0].isoformat() and same(a["change"], d[0][1] - d[1][1])
                lens = len(a["dates"]) == len(a["series"]["1Y"])
                rep.add("지수 /overview", ok and lens, f"{key}: {a['value']} ({a['change']:+}) {a['trade_date']} · DB {d[0][1]} {d[0][0]} · 날짜축 길이 {'맞음' if lens else '다름'}")

        # ── GET /market/macro (실험실 변수)
        r = api.get("/api/v1/market/macro")
        if r.status_code != 200:
            rep.add("거시 /macro", False, f"HTTP {r.status_code}")
        else:
            body = r.json()
            for x in body["indicators"]:
                if x["key"] == "GOLD":
                    d = q("SELECT trade_date, close FROM commodity_prices_daily WHERE product_code = '04020000' ORDER BY trade_date DESC LIMIT 1")
                else:
                    d = q("SELECT observation_date, value FROM economic_observations WHERE indicator_code = %s AND value IS NOT NULL ORDER BY observation_date DESC LIMIT 1", x["key"])
                ok = bool(d) and same(x["value"], d[0][1]) and x["observed_date"] == d[0][0].isoformat()
                age = (date.today() - date.fromisoformat(x["observed_date"])).days
                rep.add("거시 /macro", ok if age <= 7 or not ok else None,
                        f"{x['label']}: {x['value']}{x['unit']} ({x['observed_date']}, {age}일 전)" + ("" if ok else f" ≠ DB {d[0] if d else '없음'}"))
            if body["missing"]:
                rep.add("거시 /macro", None, f"값 없는 지표: {body['missing']}")

        # ── 기업정보 (profile · candles · financials)
        for code in COMPANY_SAMPLES:
            p = api.get(f"/api/v1/stocks/{code}/profile")
            c = api.get(f"/api/v1/stocks/{code}/candles", params={"range": "1M"})
            f = api.get(f"/api/v1/stocks/{code}/financials")
            if p.status_code != 200 or c.status_code != 200 or f.status_code != 200:
                rep.add("기업정보", False, f"{code}: profile {p.status_code} · candles {c.status_code} · financials {f.status_code}")
                continue
            last_c = c.json()[-1]
            dbl = q("SELECT max(trade_date) FROM prices_daily WHERE symbol = %s", code)[0][0]
            fin = f.json()
            ok = last_c["date"] == dbl.isoformat()
            rep.add("기업정보", ok, f"{code} {p.json().get('name')}: 차트 끝 {last_c['date']}(DB {dbl}) · 분기 {len(fin['quarters'])}개"
                    f" · 금융사 {fin['financial']} · 준비중 {fin['preparing']} · PER {p.json().get('per')}")

        # ── 뉴스 (홈)
        r = api.get("/api/v1/news/home")
        b = r.json()
        dup = len(b["items"]) - len({x["title"] for x in b["items"]})
        newest = q("SELECT max(published_at) FROM news_articles a WHERE EXISTS (SELECT 1 FROM news_stocks ns WHERE ns.news_id = a.id)")[0][0]
        ok = r.status_code == 200 and dup == 0 and b["items"] and b["items"][0]["at"][:16] == newest.astimezone().isoformat()[:16]
        rep.add("뉴스 /news/home", bool(ok) or None, f"{b['day']} · {b['day_total']}건 · 기사 {len(b['items'])} · 제목 중복 {dup} · 최신 {b['items'][0]['at'] if b['items'] else '-'} (DB {newest})")

    return rep.print()


if __name__ == "__main__":
    sys.exit(main())
