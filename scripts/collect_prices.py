"""토스증권 Open API로 일봉(OHLCV)을 받아 CSV로 저장한다.

허용 IP로 등록된 환경에서만 동작한다. 사용: python scripts/collect_prices.py
"""

import csv
import os
import time

import requests
from dotenv import load_dotenv

load_dotenv()

BASE = "https://openapi.tossinvest.com"
OUT = "data/sample/prices.csv"
TARGET_BARS = 260  # 약 1년치 거래일

SYMBOLS = {
    "005930": "삼성전자", "000660": "SK하이닉스", "373220": "LG에너지솔루션",
    "207940": "삼성바이오로직스", "005380": "현대차", "000270": "기아",
    "068270": "셀트리온", "105560": "KB금융", "035420": "NAVER",
    "035720": "카카오", "005490": "POSCO홀딩스", "006400": "삼성SDI",
    "051910": "LG화학", "055550": "신한지주", "028260": "삼성물산",
    "012330": "현대모비스", "086790": "하나금융지주", "012450": "한화에어로스페이스",
    "034020": "두산에너빌리티", "329180": "HD현대중공업", "032830": "삼성생명",
    "009150": "삼성전기", "138040": "메리츠금융지주", "259960": "크래프톤",
    "066570": "LG전자", "247540": "에코프로비엠", "086520": "에코프로",
    "196170": "알테오젠", "042700": "한미반도체", "011200": "HMM",
}


def get_token():
    cid, secret = os.getenv("TOSS_CLIENT_ID"), os.getenv("TOSS_CLIENT_SECRET")
    if not cid or not secret:
        raise SystemExit(".env에 TOSS_CLIENT_ID / TOSS_CLIENT_SECRET이 비어 있어요.")
    res = requests.post(
        f"{BASE}/oauth2/token",
        data={"grant_type": "client_credentials", "client_id": cid, "client_secret": secret},
        timeout=10,
    )
    if res.status_code != 200:
        raise SystemExit(f"토큰 발급 실패 {res.status_code}: {res.text[:200]}")
    return res.json()["access_token"]


def get_json(token, params):
    """429(한도 초과)면 잠깐 기다렸다가 다시 시도한다."""
    for _ in range(5):
        res = requests.get(
            f"{BASE}/api/v1/candles",
            headers={"Authorization": f"Bearer {token}"},
            params=params,
            timeout=10,
        )
        if res.status_code == 429:
            time.sleep(float(res.headers.get("Retry-After", 1)) + 0.5)
            continue
        res.raise_for_status()
        return res.json()["result"]
    raise RuntimeError("429가 계속 나와요.")


def fetch_symbol(token, symbol):
    bars, before = [], None
    while len(bars) < TARGET_BARS:
        params = {"symbol": symbol, "interval": "1d", "count": 200}
        if before:
            params["before"] = before
        result = get_json(token, params)
        bars += result["candles"]
        before = result.get("nextBefore")
        time.sleep(0.3)
        if not before:
            break
    return bars


def main():
    token = get_token()
    rows, failed = [], []
    for symbol, name in SYMBOLS.items():
        try:
            bars = fetch_symbol(token, symbol)
        except Exception as e:
            failed.append(symbol)
            print(f"[실패] {symbol} {name}: {e}")
            continue
        for c in bars:
            rows.append([symbol, c["timestamp"][:10], c["openPrice"], c["highPrice"],
                         c["lowPrice"], c["closePrice"], c["volume"]])
        print(f"[완료] {symbol} {name}: {len(bars)}개")

    rows = sorted({tuple(r) for r in rows}, key=lambda r: (r[0], r[1]))
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["symbol", "date", "open", "high", "low", "close", "volume"])
        w.writerows(rows)
    print(f"저장: {OUT} ({len(rows)}행), 실패 종목: {failed or '없음'}")


if __name__ == "__main__":
    main()
