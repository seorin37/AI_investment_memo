"""KRX Open API로 주요 KOSPI 종목의 최근 일봉(OHLCV)을 수집한다.

KRX API는 종목별이 아니라 기준일의 시장 전체 시세를 반환한다. 따라서
거래일별로 KOSPI 전체 시세를 한 번 요청한 뒤 필요한 종목만 남긴다.

사용법:
    python scripts/collect_prices2.py

결과:
    data/sample/prices2.csv
"""

import csv
import os
import time
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

BASE = "https://data-dbg.krx.co.kr/svc/apis/sto"
ENDPOINTS = {
    "KOSPI": "stk_bydd_trd",
}
OUT = ROOT / "data" / "sample" / "prices2.csv"
TARGET_BARS = 260  # 종목별 최근 약 1년치 거래일
MAX_LOOKBACK_DAYS = 550
REQUEST_INTERVAL = 0.05
KST = ZoneInfo("Asia/Seoul")

SYMBOLS = {
    "005930": "삼성전자", "000660": "SK하이닉스", "373220": "LG에너지솔루션",
    "207940": "삼성바이오로직스", "005380": "현대차", "000270": "기아",
    "068270": "셀트리온", "105560": "KB금융", "035420": "NAVER",
    "035720": "카카오", "005490": "POSCO홀딩스", "006400": "삼성SDI",
    "051910": "LG화학", "055550": "신한지주", "028260": "삼성물산",
    "012330": "현대모비스", "086790": "하나금융지주", "012450": "한화에어로스페이스",
    "034020": "두산에너빌리티", "329180": "HD현대중공업", "032830": "삼성생명",
    "009150": "삼성전기", "138040": "메리츠금융지주", "259960": "크래프톤",
    "066570": "LG전자", "042700": "한미반도체", "011200": "HMM",
}


def parse_number(value):
    """KRX 숫자 문자열의 쉼표를 제거한다."""
    text = str(value or "").replace(",", "").strip()
    return text if text not in {"", "-"} else None


def get_daily_market(session, api_key, market, date):
    """한 시장의 기준일 전체 일별매매정보를 가져온다."""
    url = f"{BASE}/{ENDPOINTS[market]}"
    params = {"basDd": date.strftime("%Y%m%d")}

    for attempt in range(5):
        response = session.get(
            url,
            headers={"AUTH_KEY": api_key},
            params=params,
            timeout=20,
        )

        if response.status_code in {429, 500, 502, 503, 504}:
            wait = float(response.headers.get("Retry-After", 2 ** attempt))
            time.sleep(wait)
            continue

        if response.status_code in {401, 403}:
            raise RuntimeError(
                f"{market} API 인증/권한 오류(HTTP {response.status_code}). "
                "KRX Data Marketplace에서 해당 일별매매정보 API의 활용 승인을 확인하세요."
            )

        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or "OutBlock_1" not in payload:
            raise RuntimeError(
                f"{market} API 응답 형식이 예상과 다릅니다: {str(payload)[:200]}"
            )
        return payload["OutBlock_1"] or []

    raise RuntimeError(f"{market} API가 반복해서 일시 오류를 반환했습니다.")


def collect_prices(api_key):
    """오늘부터 과거 방향으로 조회하여 종목마다 정확히 260개를 모은다."""
    rows_by_symbol = defaultdict(list)
    target_symbols = set(SYMBOLS)
    session = requests.Session()
    today = datetime.now(KST).date()

    for offset in range(MAX_LOOKBACK_DAYS + 1):
        date = today - timedelta(days=offset)
        if date.weekday() >= 5:
            continue

        found_today = 0
        for market in ENDPOINTS:
            market_rows = get_daily_market(session, api_key, market, date)
            for item in market_rows:
                symbol = str(item.get("ISU_CD", "")).strip()
                if symbol not in target_symbols or len(rows_by_symbol[symbol]) >= TARGET_BARS:
                    continue

                values = [
                    parse_number(item.get("TDD_OPNPRC")),
                    parse_number(item.get("TDD_HGPRC")),
                    parse_number(item.get("TDD_LWPRC")),
                    parse_number(item.get("TDD_CLSPRC")),
                    parse_number(item.get("ACC_TRDVOL")),
                ]
                if any(value is None for value in values):
                    continue

                bas_dd = str(item.get("BAS_DD") or params_date(date))
                rows_by_symbol[symbol].append(
                    [symbol, format_date(bas_dd), *values]
                )
                found_today += 1

            time.sleep(REQUEST_INTERVAL)

        if found_today and min(len(rows_by_symbol[s]) for s in target_symbols) % 20 == 0:
            minimum = min(len(rows_by_symbol[s]) for s in target_symbols)
            print(f"[수집 중] {date}: 종목별 최소 {minimum}/{TARGET_BARS}개")

        if all(len(rows_by_symbol[s]) >= TARGET_BARS for s in target_symbols):
            break

    return rows_by_symbol


def params_date(date):
    return date.strftime("%Y%m%d")


def format_date(value):
    return datetime.strptime(value, "%Y%m%d").date().isoformat()


def write_csv(rows_by_symbol):
    rows = []
    for symbol in SYMBOLS:
        rows.extend(rows_by_symbol[symbol][:TARGET_BARS])
    rows.sort(key=lambda row: (row[0], row[1]))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["symbol", "date", "open", "high", "low", "close", "volume"])
        writer.writerows(rows)
    return rows


def main():
    api_key = os.getenv("KRX_API_KEY")
    if not api_key:
        raise SystemExit(".env에 KRX_API_KEY가 비어 있어요.")

    try:
        rows_by_symbol = collect_prices(api_key)
    except requests.RequestException as error:
        raise SystemExit(f"KRX API 요청 실패: {error}") from error
    except RuntimeError as error:
        raise SystemExit(str(error)) from error

    incomplete = {
        f"{symbol} {SYMBOLS[symbol]}": len(rows_by_symbol[symbol])
        for symbol in SYMBOLS
        if len(rows_by_symbol[symbol]) < TARGET_BARS
    }
    rows = write_csv(rows_by_symbol)

    print(f"저장: {OUT.relative_to(ROOT)} ({len(rows)}행)")
    if incomplete:
        print(f"{TARGET_BARS}개를 채우지 못한 종목: {incomplete}")
        raise SystemExit(1)
    print(f"완료: {len(SYMBOLS)}개 종목 × {TARGET_BARS}거래일")


if __name__ == "__main__":
    main()
