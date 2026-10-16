"""토스증권 Open API 연결 테스트: 삼성전자 일봉 5개 조회."""

import os

import requests
from dotenv import load_dotenv

load_dotenv()

BASE = "https://openapi.tossinvest.com"
cid = os.getenv("TOSS_CLIENT_ID")
secret = os.getenv("TOSS_CLIENT_SECRET")
if not cid or not secret:
    raise SystemExit(".env에 TOSS_CLIENT_ID / TOSS_CLIENT_SECRET이 비어 있어요.")

# 1) 토큰 발급
tok = requests.post(
    f"{BASE}/oauth2/token",
    data={"grant_type": "client_credentials", "client_id": cid, "client_secret": secret},
    timeout=10,
)
print("토큰 발급 HTTP", tok.status_code)
if tok.status_code != 200:
    print(tok.text[:300])
    raise SystemExit(1)
token = tok.json()["access_token"]

# 2) 일봉 조회
res = requests.get(
    f"{BASE}/api/v1/candles",
    headers={"Authorization": f"Bearer {token}"},
    params={"symbol": "005930", "interval": "1d", "count": 5},
    timeout=10,
)
print("캔들 조회 HTTP", res.status_code)
if res.status_code != 200:
    print(res.text[:300])
    raise SystemExit(1)

for c in res.json()["result"]["candles"]:
    print(c["timestamp"], c["openPrice"], c["highPrice"], c["lowPrice"], c["closePrice"], c["volume"])
