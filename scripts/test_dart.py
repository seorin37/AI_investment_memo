"""DART API 연결 테스트: 삼성전자 최근 공시 목록 조회."""

import os
from datetime import date, timedelta

import requests
from dotenv import load_dotenv

load_dotenv()

key = os.getenv("DART_API_KEY")
if not key:
    raise SystemExit(".env에 DART_API_KEY가 비어 있어요.")

today = date.today()
params = {
    "crtfc_key": key,
    "corp_code": "00126380",  # 삼성전자
    "bgn_de": (today - timedelta(days=30)).strftime("%Y%m%d"),
    "end_de": today.strftime("%Y%m%d"),
    "page_count": 5,
}
res = requests.get("https://opendart.fss.or.kr/api/list.json", params=params, timeout=10)
data = res.json()

print("status:", data.get("status"), "/", data.get("message"))
for item in data.get("list", []):
    print(item["rcept_dt"], item["report_nm"])
