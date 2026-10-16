"""Gemini API 연결 테스트: 메모와 뉴스 제목의 관련성을 한 줄로 판단시킨다."""

import os

import requests
from dotenv import load_dotenv

load_dotenv()

key = os.getenv("LLM_API_KEY")
if not key:
    raise SystemExit(".env에 LLM_API_KEY가 비어 있어요.")

BASE = "https://generativelanguage.googleapis.com/v1beta"
MODEL = os.getenv("LLM_MODEL", "gemini-3.1-flash-lite")
headers = {"x-goog-api-key": key}

prompt = (
    "투자 메모: 'HBM 실적 계속 보기'\n"
    "뉴스 제목: '삼성전자, HBM4 공급 확대 소식에 주가 상승'\n"
    "이 뉴스가 메모와 관련 있는지 '관련 있음' 또는 '관련 없음'으로 먼저 답하고, "
    "이유를 한 문장으로 설명해 줘."
)

res = requests.post(
    f"{BASE}/models/{MODEL}:generateContent",
    headers=headers,
    json={"contents": [{"parts": [{"text": prompt}]}]},
    timeout=30,
)
print("HTTP", res.status_code, "| 모델:", MODEL)

if res.status_code == 200:
    print(res.json()["candidates"][0]["content"]["parts"][0]["text"])
else:
    print(res.text[:300])
    models = requests.get(f"{BASE}/models", headers=headers, timeout=10)
    if models.status_code == 200:
        names = [m["name"].split("/")[-1] for m in models.json().get("models", [])]
        print("사용 가능한 모델 중 flash:", [n for n in names if "flash" in n][:10])
