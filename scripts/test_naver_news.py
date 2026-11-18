"""NAVER API HUB 뉴스 검색 연결 테스트."""

import html
import os
import re

import requests
from dotenv import load_dotenv

load_dotenv()

cid = os.getenv("NAVER_CLIENT_ID")
secret = os.getenv("NAVER_CLIENT_SECRET")
if not cid or not secret:
    raise SystemExit(".env에 NAVER_CLIENT_ID / NAVER_CLIENT_SECRET이 비어 있어요.")

res = requests.get(
    "https://naverapihub.apigw.ntruss.com/search/v1/news",
    headers={"X-NCP-APIGW-API-KEY-ID": cid, "X-NCP-APIGW-API-KEY": secret},
    params={"query": "삼성전자 HBM", "display": 5, "sort": "date"},
    timeout=10,
)
print("HTTP", res.status_code)
if res.status_code != 200:
    print(res.text[:300])
    raise SystemExit(1)

data = res.json()
print("total:", data.get("total"))
for item in data.get("items", []):
    print(item["pubDate"], html.unescape(re.sub(r"<[^>]+>", "", item["title"])))
