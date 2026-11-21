"""DB 행 → 프론트 Quote / Candle / NewsHeadline / StockProfile / Financials / MarketOverview 모양."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from .repository import MarketDataRepository

KST = ZoneInfo("Asia/Seoul")
MARKET_CLOSE = time(15, 30)

# mock/index.ts getCandles 와 같은 개수
RANGE_SIZES = {"1W": 5, "1M": 22, "3M": 64, "1Y": 250}
SPARK_SIZE = 24
YEAR_DAYS = 250
# 홈 뉴스: 같은 제목을 거르고도 limit 개를 채우려고 더 받는 배수 (속보는 보통 2~3곳)
HOME_NEWS_FETCH_FACTOR = 3
HOME_NEWS_FETCH_MAX = 150
ANNUAL_YEARS = 7
QUARTERS = 12           # 기업정보 분기 재무: 화면 8 + 전년 동기 비교 4 (UI v2)

# 시장 개요 지수 그래프. 장중 데이터가 없어 1D 는 전일·최근 종가 두 점이다.
INDEX_SERIES_SIZES = {"1D": 2, "1W": 5, "1M": 22, "1Y": 250}

# (key, label, flag, 읽을 곳, 코드)
INDICES = [
    ("KOSPI", "코스피", "kr", "index", "KOSPI"),
    ("KOSDAQ", "코스닥", "kr", "index", "KOSDAQ"),
    ("USDKRW", "원/달러", "us", "observation", "USD_KRW"),
]
# (key, label, unit, 읽을 곳, 코드)
MACROS = [
    ("BASE_RATE", "기준금리", "%", "observation", "KR_POLICY_RATE"),
    ("KR3Y", "국고채 3년", "%", "observation", "KR_GOV_3Y"),
    ("US10Y", "미 국채 10년", "%", "observation", "US_TREASURY_10Y"),
    ("GOLD", "금", "원/g", "commodity", "04020000"),           # KRX 금 99.99K, 1g 원화 가격
    ("WTI", "WTI 유가", "$", "observation", "WTI_SPOT"),
]

# 거시 API (GET /market/macro). (key, label, unit, 읽을 곳, 코드). 값은 수집된 원천값 그대로(가공·예측 없음)
MACRO_INDICATORS = [
    ("USD_KRW", "원/달러 환율", "원", "observation", "USD_KRW"),
    ("KR_POLICY_RATE", "한국 기준금리", "%", "observation", "KR_POLICY_RATE"),
    ("KR_GOV_3Y", "국고채 3년", "%", "observation", "KR_GOV_3Y"),
    ("KR_GOV_10Y", "국고채 10년", "%", "observation", "KR_GOV_10Y"),
    ("KR_GOV_30Y", "국고채 30년", "%", "observation", "KR_GOV_30Y"),
    ("US_TREASURY_2Y", "미국 국채 2년", "%", "observation", "US_TREASURY_2Y"),
    ("US_TREASURY_10Y", "미국 국채 10년", "%", "observation", "US_TREASURY_10Y"),
    ("US_TREASURY_30Y", "미국 국채 30년", "%", "observation", "US_TREASURY_30Y"),
    ("WTI_SPOT", "WTI 유가", "달러/배럴", "observation", "WTI_SPOT"),
    ("GOLD", "금 99.99K", "원/g", "commodity", "04020000"),
]

QUOTES_MAX = 50  # GET /quotes 한 번에 받는 종목 수

DEFAULT_OVERVIEW_TEXT = "기업 개요를 준비 중이에요."


class PriceDataNotFoundError(LookupError):
    pass


class StockNotFoundError(LookupError):
    pass


class FinancialsNotFoundError(LookupError):
    pass


def num(value: Any) -> int | float | None:
    """numeric 은 정수면 int, 아니면 float 로."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    return value


def _round(value: Any, digits: int) -> float | None:
    return None if value is None else round(float(value), digits)


def _ratio(part: Any, whole: Any) -> float | None:
    if part is None or not whole:
        return None
    return round(float(Decimal(part) / Decimal(whole) * 100), 1)


def _eok(value: Any) -> int | None:
    """원 → 억원 (반올림 정수). 화면 CompanyQuarter 단위."""
    return None if value is None else int(round(float(value) / 1e8))


def _kis(value: Any) -> Any:
    """KIS 투자지표는 값이 없을 때 0을 준다(리츠·인프라펀드 등) → None."""
    return None if value in (None, 0) else value


def _iso(value: Any) -> Any:
    return value.isoformat() if hasattr(value, "isoformat") else value


def _close_time(day: date) -> str:
    return datetime.combine(day, MARKET_CLOSE, tzinfo=KST).isoformat()


def candle(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "date": row["trade_date"].isoformat(),
        "open": num(row["open"]),
        "high": num(row["high"]),
        "low": num(row["low"]),
        "close": num(row["close"]),
        "volume": int(row["volume"]),
    }


class MarketDataService:
    def __init__(self, repo: MarketDataRepository) -> None:
        self.repo = repo

    # ─── 시세 (A)
    def quote(self, code: str) -> dict[str, Any]:
        rows = self.repo.recent_prices(code, SPARK_SIZE)
        if not rows:
            raise PriceDataNotFoundError(code)
        return self._quote(code, rows)

    def quotes(self, codes: list[str]) -> dict[str, Any]:
        """여러 종목 시세를 한 번에 (보드·사이드바·내 종목 목록). 현재가·등락은 원시 종가. 시세가 없는 종목은 missing."""
        by_code = self.repo.recent_prices_many(codes, SPARK_SIZE)
        quotes = [self._quote(code, by_code[code]) for code in codes if by_code.get(code)]
        return {"quotes": quotes, "missing": [code for code in codes if not by_code.get(code)]}

    @staticmethod
    def _quote(code: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
        """rows: 날짜 오름차순 prices_daily 행 (원시 종가)."""
        last = rows[-1]
        price = Decimal(last["close"])
        prev = Decimal(rows[-2]["close"]) if len(rows) >= 2 else price
        change = price - prev
        change_pct = float(round(change / prev * 100, 2)) if prev else 0.0
        return {
            "code": code,
            "price": num(price),
            "change": num(change),
            "change_pct": change_pct,
            "as_of": _close_time(last["trade_date"]),
            "trade_date": last["trade_date"].isoformat(),
            "spark": [num(row["close"]) for row in rows],
        }

    def candles(self, code: str, range_: str, adjusted: bool = True) -> list[dict[str, Any]]:
        """차트는 기본이 수정주가(분할·병합으로 끊기지 않게). 현재가·전일비(quote·profile)는 원시 주가."""
        rows = self.repo.recent_candles(code, RANGE_SIZES[range_], adjusted=adjusted)
        if not rows:
            raise PriceDataNotFoundError(code)
        return [candle(row) for row in rows]

    def headlines(self, limit: int) -> list[dict[str, Any]]:
        return [
            {
                "id": str(row["id"]),
                "title": row["title"],
                # 프론트 NewsHeadline 에는 없는 추가 필드(화면은 무시해도 됨)
                "summary": row["summary"],
                "source": row["source"],
                "url": row["url"],
                "published_at": _iso(row["published_at"]),
                # 덧붙인 필드: 연결된 종목 코드 (관련성 점수 높은 순)
                "stock_codes": list(row.get("stock_codes") or []),
            }
            for row in self.repo.latest_news(limit)
        ]

    def home_news(self, limit: int) -> dict[str, Any]:
        """홈 뉴스 위젯 (UI v2 HomeNewsItem 모양).

        - items: 종목과 연결된 최신 기사. at 은 한국 시간 ISO (화면이 앞 10자리로 날짜를 비교한다)
        - day: 가장 새 기사의 한국 날짜. 기사가 없으면 null
        - day_total: 그 날짜(0시~24시 KST)에 나온 종목 연결 기사 수 (같은 제목은 한 번)
        - 같은 제목(속보를 여러 언론사가 몇 분 간격으로 냄)은 가장 새 기사 하나만.
          걸러진 만큼 모자라지 않게 넉넉히 받아서 자른다
        """
        rows = []
        seen: set[str] = set()
        for row in self.repo.latest_news(min(limit * HOME_NEWS_FETCH_FACTOR, HOME_NEWS_FETCH_MAX)):
            key = " ".join(row["title"].split())
            if key in seen:
                continue
            seen.add(key)
            rows.append(row)
            if len(rows) == limit:
                break
        if not rows:
            return {"day": None, "day_total": 0, "items": []}
        items = [
            {
                "id": str(row["id"]),
                "title": row["title"],
                "src": row["source"],
                "at": row["published_at"].astimezone(KST).isoformat(),
                "url": row["url"],
                "stock_codes": list(row.get("stock_codes") or []),
            }
            for row in rows
        ]
        day = rows[0]["published_at"].astimezone(KST).date()
        start = datetime.combine(day, time.min, tzinfo=KST)
        total = self.repo.linked_news_count(start, start + timedelta(days=1))
        return {"day": day.isoformat(), "day_total": total, "items": items}

    # ─── 기업 정보 (B)
    def profile(self, code: str) -> dict[str, Any]:
        stock = self.repo.stock(code)
        if not stock:
            raise StockNotFoundError(code)
        prices = self.repo.recent_prices(code, YEAR_DAYS)
        if not prices:
            raise PriceDataNotFoundError(code)
        snap = self.repo.latest_snapshot(code) or {}
        last = prices[-1]
        prev = prices[-2] if len(prices) >= 2 else last
        close = Decimal(last["close"])
        shares = snap.get("listed_shares") or last.get("listed_shares") or stock.get("shares_outstanding")
        market_cap = (
            snap.get("market_cap")
            or last.get("market_cap")
            or (close * shares if shares else None)
        )
        trading_value = last.get("trade_value") or close * int(last["volume"])
        week52_low = snap.get("w52_low") or min(Decimal(p["low"]) for p in prices)
        week52_high = snap.get("w52_high") or max(Decimal(p["high"]) for p in prices)
        return {
            "code": stock["code"],
            "name": stock["name"],
            "market": stock["market"],
            "overview": (stock.get("description") or "").strip() or DEFAULT_OVERVIEW_TEXT,
            "prev_close": num(prev["close"]),
            "open": num(last["open"]),
            "high": num(last["high"]),
            "low": num(last["low"]),
            "volume": int(last["volume"]),
            "trading_value": num(Decimal(trading_value).quantize(Decimal(1))),
            # PER·PBR·EPS·BPS는 KIS 값 그대로(직전 사업연도 기준, 2026-11-21 팀 결정). KIS는 값이 없으면 0을 줘서 null로
            "per": _round(_kis(snap.get("per")), 2),
            "pbr": _round(_kis(snap.get("pbr")), 2),
            "eps": num(_kis(snap.get("eps"))),
            "bps": num(_kis(snap.get("bps"))),
            "market_cap": num(Decimal(market_cap).quantize(Decimal(1))) if market_cap is not None else None,
            "shares_outstanding": int(shares) if shares else None,
            "week52_low": num(week52_low),
            "week52_high": num(week52_high),
        }

    def financials(self, code: str) -> dict[str, Any]:
        """기업정보 재무 (UI v2 CompanyInfo 모양, 2026-11-21 · docs/company-page-data-gaps-plan.md 11-21 결정).

        - quarters: 분기 단독 최대 12개(화면 8 + 전년 동기 4), 오래된 → 최근, 금액 억원. 적으면 있는 만큼(⑤)
        - 라벨은 period_end의 달력 분기 '26.3Q'(④). ROA는 보내지 않는다(③)
        - 금융사(sector='financial'): 매출·이익률·유동·당좌·이자보상은 null, 영업이익은 보낸다(①, 11-16 결정)
        - 자본총계 0 이하인 분기의 ROE는 null(⑦). 우선주는 본주 재무(⑧)
        - 분기 재무가 하나도 없으면 404 대신 preparing=true (리츠·인프라펀드 등, ⑥). 모르는 종목만 404
        """
        fp = self.repo.financial_profile(code)
        if not fp:
            raise StockNotFoundError(code)
        src = fp["source_code"]
        financial = fp.get("sector") == "financial"
        rows = self.repo.quarterly_financials(src, QUARTERS)
        metrics = self.repo.latest_metrics(src) or {}
        quarters = [self._quarter(r, financial) for r in rows]
        basis_row = rows[-1] if rows else metrics
        basis_end = basis_row.get("period_end") if basis_row else None
        fs_label = "별도재무제표" if (basis_row or {}).get("fs_div") == "separate" else "연결재무제표"
        hide = {"current", "quick", "interest"} if financial else set()
        health = {
            key: (None if key in hide else _round(metrics.get(col), 1))
            for key, col in (("debt", "debt_ratio"), ("current", "current_ratio"), ("quick", "quick_ratio"),
                             ("interest", "interest_coverage"), ("reserve", "reserve_ratio"))
        }
        as_of = metrics.get("period_end")
        return {
            "code": code,
            "source_code": src,                       # 우선주면 재무를 읽은 본주 코드
            "sector": fp.get("sector") or "general",
            "fin_type": fp.get("fin_type"),
            "financial": financial,
            "preparing": not quarters,
            "basis": f"{basis_end.year}년 {basis_end.month:02d}월 기준 · {fs_label}" if basis_end else "",
            "quarters": quarters,
            "health": health,
            "health_as_of": as_of.isoformat() if as_of else None,
            "interest_coverage_basis": None if financial else metrics.get("interest_coverage_basis"),
        }

    @staticmethod
    def _quarter(r: dict[str, Any], financial: bool) -> dict[str, Any]:
        end: date = r["period_end"]
        qn = (end.month - 1) // 3 + 1
        equity = r.get("total_equity")
        return {
            "period_end": end.isoformat(),
            "q": f"{end.year % 100:02d}.{qn}Q",
            "label": f"{end.year}년 {qn}분기",
            "revenue": None if financial else _eok(r.get("revenue")),
            "op": _eok(r.get("operating_income")),
            "net": _eok(r.get("net_income")),
            "op_margin": None if financial else _round(r.get("operating_margin"), 1),
            "net_margin": None if financial else _round(r.get("net_margin"), 1),
            "roe": None if (equity is not None and equity <= 0) else _round(r.get("roe"), 1),
        }

    # ─── 시장 개요 (B)
    def _series(self, source: str, code: str, limit: int) -> list[dict[str, Any]]:
        if source == "index":
            return self.repo.index_closes(code, limit)
        if source == "commodity":
            return self.repo.commodity_closes(code, limit)
        return self.repo.observations(code, limit)

    def overview(self) -> dict[str, Any]:
        longest = max(INDEX_SERIES_SIZES.values())
        latest_days: list[date] = []
        indices = []
        for key, label, flag, source, code in INDICES:
            rows = self._series(source, code, longest)
            if not rows:
                continue
            values = [Decimal(r["value"]) for r in rows]
            last = values[-1]
            prev = values[-2] if len(values) >= 2 else last
            change = last - prev
            latest_days.append(rows[-1]["day"])
            indices.append(
                {
                    "key": key,
                    "label": label,
                    "flag": flag,
                    "value": float(round(last, 2)),
                    "change": float(round(change, 2)),
                    "change_pct": float(round(change / prev * 100, 2)) if prev else 0.0,
                    "series": {
                        name: [float(round(v, 2)) for v in values[-size:]]
                        for name, size in INDEX_SERIES_SIZES.items()
                    },
                    # C-16: 지수별 기준일과 series['1Y'] 와 같은 길이의 날짜 (다른 기간은 뒤에서 같은 개수)
                    "trade_date": rows[-1]["day"].isoformat(),
                    "dates": [r["day"].isoformat() for r in rows[-INDEX_SERIES_SIZES["1Y"]:]],
                }
            )
        macro = []
        for key, label, unit, source, code in MACROS:
            rows = self._series(source, code, 2)
            if not rows:
                continue
            last = Decimal(rows[-1]["value"])
            prev = Decimal(rows[-2]["value"]) if len(rows) >= 2 else last
            # 화면(MarketWidgets)과 mock 의 약속: 단위가 % 인 지표는 %p 차이, 그 밖(원/g·$)은 등락률(%)
            if unit == "%":
                change = float(round(last - prev, 2))
            else:
                change = float(round((last - prev) / prev * 100, 2)) if prev else 0.0
            macro.append(
                {
                    "key": key,
                    "label": label,
                    "value": float(round(last, 2)),
                    "unit": unit,
                    "change": change,
                }
            )
        as_of = _close_time(max(latest_days)) if latest_days else datetime.now(KST).isoformat()
        return {"indices": indices, "macro": macro, "as_of": as_of}

    # ─── 거시 지표 (GET /market/macro)
    def macro(self) -> dict[str, Any]:
        """지표별 최신값·직전값·관측일·출처. economic_observations(ECOS·FRED) + commodity_prices_daily(KRX 금).

        - 값은 원천값 그대로(소수 4자리 반올림만). change = 최신 − 직전 (단위가 % 면 %p), change_pct = 등락률
        - 관측값이 없는 지표는 indicators 에서 빼고 missing 에 키를 넣는다
        """
        obs_codes = [code for _, _, _, source, code in MACRO_INDICATORS if source == "observation"]
        obs = self.repo.latest_observations(obs_codes, 2)
        indicators: list[dict[str, Any]] = []
        missing: list[str] = []
        for key, label, unit, source, code in MACRO_INDICATORS:
            rows = obs.get(code, []) if source == "observation" else self.repo.latest_commodity(code, 2)
            if not rows:
                missing.append(key)
                continue
            last, prev = rows[-1], (rows[-2] if len(rows) >= 2 else None)
            value = Decimal(last["value"])
            prev_value = Decimal(prev["value"]) if prev else None
            change = value - prev_value if prev_value is not None else None
            indicators.append(
                {
                    "key": key,
                    "label": label,
                    "unit": unit,
                    "value": _round(value, 4),
                    "prev_value": _round(prev_value, 4),
                    "change": _round(change, 4),
                    "change_pct": float(round(change / prev_value * 100, 2)) if change is not None and prev_value else None,
                    "observed_date": last["day"].isoformat(),
                    "prev_date": prev["day"].isoformat() if prev else None,
                    "source": last.get("source"),
                    "series_code": last.get("series_code"),
                }
            )
        as_of = max((i["observed_date"] for i in indicators), default=None)
        return {"indicators": indicators, "missing": missing, "as_of": as_of}
