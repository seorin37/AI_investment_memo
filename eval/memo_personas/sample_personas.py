"""
MemoStock 평가용 페르소나 확정 도구 (Step 3)
------------------------------------------------
뼈대 : nvidia/Nemotron-Personas-Korea (CC BY 4.0, 100만 레코드)
       revision ada0f5b53a38bb5a30cce09358adde883c1ab63a → data/nemotron_ko
목표 : 한국예탁결제원 「2025년 12월 결산 상장법인 주식 소유자 현황」(2026.03.18 발표) 분포를
       참고한 평가용 표본 (만 20세 이상)
산출 : <out>/personas.csv    속성표
       <out>/personas.jsonl  속성 + Nemotron 원문 서술 (수정하지 않고 그대로)
       <out>/slot_plan.csv   인당 10슬롯의 기업 배정
       <out>/meta.json       출처·가정·규칙·교체/수정 기록·검증 결과
       <out>/review.md       검수용 요약

사용법
  # 로직 확인 (가짜 데이터) → results/memo_personas/personas_100_mock
  python eval/memo_personas/sample_personas.py --mock
  # 실제 데이터 → results/memo_personas/personas_100
  python eval/memo_personas/sample_personas.py --data data/nemotron_ko

검증이 하나라도 실패하면 <out>은 건드리지 않고 <out>_failed/meta.json에 실패 내역만 남긴 뒤
종료 코드 1로 끝난다. 외부 API·DB는 호출하지 않는다.
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

TOOL = "eval/memo_personas/sample_personas.py"
DEFAULT_SEED = 2026
DEFAULT_N = 100
Q_PER_PERSONA = 10
MIN_AGE = 20

DATASET = "nvidia/Nemotron-Personas-Korea"
DATASET_REVISION = "ada0f5b53a38bb5a30cce09358adde883c1ab63a"
SAMPLE_LABEL = "공식 통계 분포를 참고한 평가용 표본"
STAT_SOURCE = "한국예탁결제원 「2025년 12월 결산 상장법인 주식 소유자 현황」(2026.03.18 발표)"

# ─────────────────────────────────────────────────────────────
# 1. 목표 분포 (100명 기준 인원수, 다른 N은 최대잉여법으로 비례 축소·확대)
# ─────────────────────────────────────────────────────────────
# [통계] 개인 소유자 연령 분포. 70대+ 13명은 잔여값이라 '임시 테스트 배분'
AGE_TARGET = {"20대": 9, "30대": 18, "40대": 22, "50대": 23, "60대": 15, "70대+": 13}
# [통계] 개인 소유자 성별 남 742만 / 여 700만
SEX_TARGET = {"남자": 52, "여자": 48}
# [통계+가정] 경기·서울·부산은 지역별 소유자 수, 기타는 잔여 → '임시 테스트 배분'
REGION_TARGET = {"경기": 26, "서울": 24, "부산": 6, "기타": 44}
QUOTA_REGIONS = ("서울", "경기", "부산")  # province 값이 이 셋이면 그대로, 나머지는 기타
TEMP_ALLOCATION = {
    "70대+": "개인 소유자 연령 분포의 잔여값(100 − 87.1)으로 잡은 임시 테스트 배분",
    "지역": "경기·서울·부산은 지역별 소유자 수 비율, 기타는 잔여로 잡은 임시 테스트 배분",
}

# 표시용 정식 명칭. 원본 province는 그대로 두고 province_full 컬럼으로만 추가한다.
PROVINCE_FULL = {
    "강원": "강원특별자치도", "경기": "경기도", "경상남": "경상남도", "경상북": "경상북도",
    "광주": "광주광역시", "대구": "대구광역시", "대전": "대전광역시", "부산": "부산광역시",
    "서울": "서울특별시", "세종": "세종특별자치시", "울산": "울산광역시", "인천": "인천광역시",
    "전라남": "전라남도", "전북": "전북특별자치도", "제주": "제주특별자치도",
    "충청남": "충청남도", "충청북": "충청북도",
}

# 대표 종목은 기업별 동일 인원, 슬롯도 기업별 동일 — 평가용 배분이며 실제 투자자 비중이 아니다.
COMPANIES = ["삼성전자", "SK하이닉스", "NAVER", "KB금융"]
PRIMARY_SLOTS = (5, 7)          # 관심 종목이 있을 때 대표 종목 슬롯 범위
INTEREST_COUNT = {0: 30, 1: 45, 2: 25}  # 관심 종목 수 (1인 최대 3종목)
SLOT_MAX_ATTEMPTS = 200

# ─────────────────────────────────────────────────────────────
# 2. 실제 스키마 (2단계 확인 결과)
# ─────────────────────────────────────────────────────────────
DEMO_COLS = ["sex", "age", "province", "district", "occupation", "education_level",
             "marital_status", "family_type", "housing_type", "bachelors_field"]
TEXT_COLS = ["persona", "professional_persona", "sports_persona", "arts_persona",
             "travel_persona", "culinary_persona", "family_persona", "cultural_background",
             "skills_and_expertise", "skills_and_expertise_list", "hobbies_and_interests",
             "hobbies_and_interests_list", "career_goals_and_ambitions"]
JOBLESS = "무직"

# 서술 단서. housing_type은 건물 유형(아파트·단독주택…)뿐이라 점유 형태(자가·임차)는 서술에서 찾는다.
RE_OWN = re.compile(r"(?<![가-힣])자가(?=\s?(주택|아파트|단독|빌라|집|를|에서|에\s|로\s|보유|소유))"
                    r"|내 집 마련에 성공|집을 소유")
RE_RENT = re.compile(r"전세(?!계)|월세|전·월세|전월세|임대(주택|아파트)|셋방|고시원|하숙")
RE_AVERSE = re.compile(r"무리한 투자|(?<![가-힣])투기|무모한 (투자|도박)|도박적인|원금 손실")  # 격투기 제외
RE_REJECT = re.compile(r"(주식|투자|재테크|증권)[^.]{0,15}(관심(이|을|조차)?\s?(없|두지\s?않)"
                       r"|손(을)?\s?대지|하지\s?않|멀리|꺼려|불신)")
RE_LEFT_JOB = re.compile(r"퇴직|퇴사|실직|은퇴|그만두|정년")
UNEMPLOYED_CUES = {
    "은퇴": re.compile(r"은퇴|퇴직|정년"),
    "주부": re.compile(r"전업주부|주부|살림|집안일|가사 ?(노동|일)|육아"),
    "구직": re.compile(r"구직|취업 준비|취업을 준비|취준|재취업|일자리를 (찾|구)|이직 준비"
                     r"|공무원 시험|시험 준비|대학생|대학원생|재학 ?중|재학생|휴학 ?중|휴학생"),  # 이름(김재학 등) 제외
}

# ─────────────────────────────────────────────────────────────
# 3. 투자 속성 — 전부 [가정]. 연령대 가중치는 확률만 바꾸고 0인 칸은 없다(나이만으로 금지하지 않음).
#    원본 속성·서술과 명백히 충돌하는 값만 규칙(RULES)으로 막는다.
# ─────────────────────────────────────────────────────────────
EXPERIENCE = {
    "young":  {"1년 미만": 25, "1~2년": 35, "3~4년": 25, "5~9년": 12, "10년 이상": 3},
    "mid":    {"1년 미만": 10, "1~2년": 20, "3~4년": 20, "5~9년": 25, "10년 이상": 25},
    "senior": {"1년 미만": 8, "1~2년": 12, "3~4년": 15, "5~9년": 25, "10년 이상": 40},
}
EXPERIENCE_YEARS = {"1년 미만": (0, 0), "1~2년": (1, 2), "3~4년": (3, 4), "5~9년": (5, 9), "10년 이상": (10, 40)}

STYLE = {
    "young":  {"단타·스윙": 30, "성장주 장기": 30, "적립식": 25, "배당": 5, "남 따라 삼": 10, "목돈 분할매수": 5},
    "mid":    {"단타·스윙": 20, "성장주 장기": 30, "적립식": 20, "배당": 20, "남 따라 삼": 10, "목돈 분할매수": 10},
    "senior": {"단타·스윙": 10, "성장주 장기": 20, "적립식": 10, "배당": 45, "남 따라 삼": 15, "목돈 분할매수": 15},
}
# 투자 방식별로 말이 되는 투자 기간·성향만 둔다 (R11)
STYLE_HORIZON = {
    "단타·스윙": {"단기(1년 미만)": 1},
    "성장주 장기": {"중기(1~3년)": 30, "장기(3년 이상)": 70},
    "적립식": {"중기(1~3년)": 40, "장기(3년 이상)": 60},
    "배당": {"중기(1~3년)": 30, "장기(3년 이상)": 70},
    "남 따라 삼": {"단기(1년 미만)": 50, "중기(1~3년)": 50},
    "목돈 분할매수": {"중기(1~3년)": 50, "장기(3년 이상)": 50},
}
STYLE_RISK = {
    "단타·스윙": {"공격형": 70, "중립형": 30},
    "성장주 장기": {"공격형": 40, "중립형": 50, "안정형": 10},
    "적립식": {"공격형": 10, "중립형": 50, "안정형": 40},
    "배당": {"중립형": 40, "안정형": 60},
    "남 따라 삼": {"공격형": 30, "중립형": 50, "안정형": 20},
    "목돈 분할매수": {"공격형": 10, "중립형": 50, "안정형": 40},
}
HOUSING = "주거 자금"  # 뽑은 뒤 점유 형태로 꼬리표를 붙인다 (R03)
HOUSING_BUY = "주거 자금(내 집 마련)"         # 자가 미상·임차·혼재
HOUSING_MOVE = "주거 자금(갈아타기·대출 상환)"  # 서술로 자가가 확인된 사람만
FUND_PURPOSE = {
    "young":  {"목돈 마련": 30, HOUSING: 30, "결혼 자금": 10, "여유자금 운용": 15, "노후 자금": 5,
               "자녀 교육비": 5, "생활비 보탬": 5},
    "mid":    {"목돈 마련": 15, HOUSING: 19, "결혼 자금": 3, "여유자금 운용": 15, "노후 자금": 25,
               "자녀 교육비": 20, "생활비 보탬": 3},
    "senior": {"목돈 마련": 5, HOUSING: 8, "결혼 자금": 2, "여유자금 운용": 20, "노후 자금": 30,
               "자녀 교육비": 5, "생활비 보탬": 30},
}
RENTER_HOUSING_BOOST = 2.0  # 임차로 확인되면 주거 자금을 우선
RETIRE_DEFAULT_AGE = 65     # 이 나이 이상 무직은 은퇴가 기본값

SPOUSE_FUNDS = "가계 여유자금(배우자 소득)"
FUND_SOURCE_EMPLOYED = {"근로·사업소득 적립": 55, "예금·저축 목돈": 30, "상여금·부수입": 15}
FUND_SOURCE_JOBLESS = {  # 무직은 소득 기반이 아니라 자산 기반
    "은퇴": {"퇴직금": 35, "연금": 30, "예금·저축 목돈": 35},
    "주부": {"예금·저축 목돈": 60, SPOUSE_FUNDS: 40},
    "구직": {"예금·저축 목돈": 80, "퇴직금": 20},
}
ASSET_BASED = {"예금·저축 목돈", "퇴직금", "연금", SPOUSE_FUNDS}

INFO_SOURCE = {
    "young":  {"유튜브": 30, "종토방·커뮤니티": 30, "증권앱 뉴스": 20, "공시 직접": 8, "지인": 5,
               "직장 동료": 5, "신문·방송": 2},
    "mid":    {"유튜브": 22, "종토방·커뮤니티": 18, "증권앱 뉴스": 25, "공시 직접": 12, "지인": 8,
               "직장 동료": 7, "신문·방송": 8},
    "senior": {"유튜브": 28, "종토방·커뮤니티": 8, "증권앱 뉴스": 20, "공시 직접": 8, "지인": 18,
               "직장 동료": 3, "신문·방송": 15},
}
COMPANY_TOPIC = {"삼성전자": "반도체 업황(메모리·파운드리)", "SK하이닉스": "HBM·AI 반도체 수요",
                 "NAVER": "플랫폼·AI 사업 구조", "KB금융": "금리와 은행 이익·주주환원"}
GENERAL_TOPICS = {"재무제표 읽기": 20, "공시 읽는 법": 15, "배당 정책": 15, "차트·수급 기초": 20,
                  "세금(배당소득세·양도세)": 10, "환율·거시 지표": 10, "매매 원칙 세우기": 10}
NICKNAME = {"삼성전자": ["삼전", "삼성", "삼성전자"], "SK하이닉스": ["하닉", "하이닉스", "sk하이닉스"],
            "NAVER": ["네이버", "naver", "넵"], "KB금융": ["kb", "국민은행", "KB금융"]}
PRIMARY_STATUS = {"보유": 55, "관심": 20, "관찰": 15, "다시 보기": 10}
INTEREST_STATUS = {"보유": 30, "관심": 50, "관찰": 20}

WRITING = {  # 표현 선호(글버릇)
    "young":  dict(banmal=0.65, laugh=0.45, typo=(0.0, 0.03, 0.06), short=0.55, ellipsis=0.10),
    "mid":    dict(banmal=0.40, laugh=0.20, typo=(0.0, 0.02, 0.04), short=0.45, ellipsis=0.20),
    "senior": dict(banmal=0.25, laugh=0.05, typo=(0.01, 0.03, 0.07), short=0.35, ellipsis=0.45),
}

RULES = {
    "R01": "투자 경력(년) ≤ 나이 − 20",
    "R02": "자금 목적 '자녀 교육비'는 family_type에 자녀가 포함될 때만 (손자녀만 있는 경우 제외)",
    "R03": f"자금 목적 '주거 자금'은 점유 형태로 꼬리표를 붙인다: 서술로 자가가 확인되면 '{HOUSING_MOVE}'"
           f"(사유 기록), 자가 미상·임차·혼재면 '{HOUSING_BUY}'",
    "R04": "자금 목적 '결혼 자금'은 marital_status가 배우자있음이면 불가",
    "R05": "occupation이 무직이면 투자 방식 '적립식'(소득 기반) 불가, 자금 원천은 자산 기반(예금·퇴직금·연금 등)",
    "R06": "occupation이 무직이면 무직 유형(은퇴·주부·구직) 필수, 무직이 아니면 무직 유형·household_role 비움",
    "R07": f"자금 원천 '{SPOUSE_FUNDS}'는 marital_status가 배우자있음일 때만",
    "R08": "자금 원천 '퇴직금'은 서술에 퇴직·퇴사·실직 단서가 있거나, 무직 유형 은퇴이면서 살림 담당(household_role)이 아닐 때만",
    "R09": "정보 출처 '직장 동료'는 무직이 아닐 때만",
    "R10": "서술에 무리한 투자·투기 회피 단서가 있으면 성향 '공격형'·투자 방식 '단타·스윙' 불가",
    "R11": "투자 방식과 투자 기간·성향이 서로 맞을 것 (단타·스윙=단기, 안정형≠단타·스윙 등)",
    "R12": "서술에 주식·투자 거부가 명시되면 같은 셀(연령×성별×지역)의 다음 후보로 교체",
}


# ─────────────────────────────────────────────────────────────
# 4. 유틸
# ─────────────────────────────────────────────────────────────
def largest_remainder(weights: dict, total: int) -> dict:
    """비율 dict → 합이 정확히 total인 정수 배분 (최대잉여법)."""
    s = sum(weights.values())
    raw = {k: v / s * total for k, v in weights.items()}
    out = {k: int(np.floor(v)) for k, v in raw.items()}
    rest = total - sum(out.values())
    for k in sorted(raw, key=lambda k: raw[k] - out[k], reverse=True)[:rest]:
        out[k] += 1
    return out


def controlled_round(rows: dict, cols: dict) -> dict:
    """행·열 합계를 정확히 지키는 2차원 정수 배분. 비례 기대값의 내림에서 출발해
    남은 인원을 소수부가 큰 칸부터 채운다 (같은 칸 반복은 마지막 수단)."""
    n = sum(rows.values())
    assert n == sum(cols.values()), "행·열 합계 불일치"
    raw = {(r, c): rows[r] * cols[c] / n for r in rows for c in cols}
    out = {k: int(np.floor(v)) for k, v in raw.items()}
    r_left = {r: rows[r] - sum(out[r, c] for c in cols) for r in rows}
    c_left = {c: cols[c] - sum(out[r, c] for r in rows) for c in cols}
    order = sorted(raw, key=lambda k: raw[k] - out[k], reverse=True)
    while sum(r_left.values()):
        k = next(k for k in order if r_left[k[0]] > 0 and c_left[k[1]] > 0)
        out[k] += 1
        r_left[k[0]] -= 1
        c_left[k[1]] -= 1
        order.remove(k)
        order.append(k)
    return out


def age_bucket(age: int):
    if age < MIN_AGE:
        return None
    if age >= 70:
        return "70대+"
    return f"{(age // 10) * 10}대"


def age_group3(age: int) -> str:
    return "young" if age < 40 else "mid" if age < 60 else "senior"


def pick(rng, table: dict):
    keys = list(table)
    p = np.array([table[k] for k in keys], float)
    return keys[rng.choice(len(keys), p=p / p.sum())]


def snippet(m: re.Match, width: int = 12) -> str:
    s = m.string
    return s[max(0, m.start() - width): m.end() + width].replace("\n", " ")


def narrative(texts: dict) -> str:
    return " ".join(str(texts.get(c) or "") for c in TEXT_COLS)


def has_child(family_type: str) -> bool:
    return "자녀" in str(family_type).replace("손자녀", "")


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ─────────────────────────────────────────────────────────────
# 5. 데이터 (인구통계 컬럼만 먼저 → 후보로 뽑힌 사람만 원문 서술 로드)
# ─────────────────────────────────────────────────────────────
class Source:
    """모집단 인구통계 + 원문 서술 캐시(uuid → {컬럼: 텍스트})."""

    def __init__(self, demo: pd.DataFrame, text_loader, info: dict):
        self.demo = demo
        self.info = info
        self._loader = text_loader
        self._texts: dict = {}

    def texts(self, uuids) -> dict:
        missing = [u for u in uuids if u not in self._texts]
        if missing:
            self._texts.update(self._loader(missing))
        return {u: self._texts[u] for u in uuids}


def load_source(data_dir: str) -> Source:
    import pyarrow.dataset as ds

    files = sorted(glob.glob(os.path.join(data_dir, "**", "*.parquet"), recursive=True))
    if not files:
        raise FileNotFoundError(f"{data_dir} 아래에 parquet 파일이 없습니다.")
    dset = ds.dataset(files, format="parquet")
    names = dset.schema.names
    missing = [c for c in ["uuid"] + DEMO_COLS + TEXT_COLS if c not in names]
    if missing:
        raise ValueError(f"없는 컬럼: {missing}  ← 실제 스키마: {names}")
    demo = dset.to_table(columns=["uuid"] + DEMO_COLS).to_pandas()

    def load_texts(uuids):
        tbl = dset.to_table(columns=["uuid"] + TEXT_COLS, filter=ds.field("uuid").isin(uuids))
        return {r["uuid"]: {c: r[c] for c in TEXT_COLS} for r in tbl.to_pylist()}

    manifest = os.path.join(data_dir, "MANIFEST.txt")
    info = {
        "mode": "real",
        "dataset": DATASET,
        "revision": DATASET_REVISION,
        "license": "CC BY 4.0",
        "data_dir": data_dir,
        "parquet_files": [os.path.relpath(f, data_dir) for f in files],
        "manifest_sha256": sha256_file(manifest) if os.path.exists(manifest) else None,
        "population_rows": len(demo),
    }
    if info["manifest_sha256"] is None:
        print("[경고] MANIFEST.txt가 없어 입력 파일 해시를 기록하지 못했습니다.")
    else:
        with open(manifest, encoding="utf-8") as f:
            rev = next((l.split(":", 1)[1].strip() for l in f if l.startswith("# revision:")), None)
        if rev != DATASET_REVISION:
            raise ValueError(f"MANIFEST revision {rev} ≠ 고정 revision {DATASET_REVISION}")
    return Source(demo, load_texts, info)


MOCK_PROVINCES = {"서울": 18, "경기": 26, "부산": 6, "인천": 6, "대구": 5, "대전": 3, "광주": 3, "울산": 2,
                  "세종": 1, "강원": 3, "충청북": 3, "충청남": 4, "전북": 3, "전라남": 3, "경상북": 5,
                  "경상남": 6, "제주": 1.3}
MOCK_TAILS = ["은퇴 후 텃밭을 가꾸며 조용히 지내고 싶어 합니다.",
              "취업 준비를 마치고 안정적인 일자리를 찾고 싶어 합니다.",
              "살림을 꾸리며 가족의 건강을 챙기는 데 집중합니다.",
              "무리한 투자보다는 꾸준한 저축으로 자산을 지키려 합니다.",
              "지금 하는 일에서 전문성을 더 쌓고 싶어 합니다.",
              "회사를 그만두고 다음 진로를 고민하고 있습니다."]
MOCK_HOMES = ["자가 아파트에서", "전세 아파트에서", "월세방에서", "오래된 집에서"]


def make_mock_source(seed: int, n: int = 200_000) -> Source:
    """로직 검증용 가짜 모집단. 컬럼명·값 표기는 실제 스키마와 같게 맞춘다."""
    rng = np.random.default_rng(seed)
    provs = list(MOCK_PROVINCES)
    pw = np.array(list(MOCK_PROVINCES.values()), float)
    province = rng.choice(provs, n, p=pw / pw.sum())
    jobs = ["무직", "회계 사무원", "건물 청소원", "응용 소프트웨어 개발자", "초등학교 교사", "한식 조리사",
            "택시 운전원", "그 외 일반 영업원", "간호사", "행정 사무원"]
    jw = np.array([37, 8, 7, 6, 6, 6, 7, 8, 6, 9], float)
    families = ["배우자·자녀와 거주", "배우자와 거주", "혼자 거주", "부모와 동거", "자녀와 거주 (한부모)",
                "배우자·손자녀와 거주", "기타3세대"]
    fw = np.array([27, 21, 14, 9, 3, 1, 3], float)
    demo = pd.DataFrame({
        "uuid": [f"mock{i:06d}" for i in range(n)],
        "sex": rng.choice(["남자", "여자"], n),
        "age": rng.integers(19, 95, n),
        "province": province,
        "district": [f"{p}-가상구{int(k)}" for p, k in zip(province, rng.integers(1, 6, n))],
        "occupation": rng.choice(jobs, n, p=jw / jw.sum()),
        "education_level": rng.choice(["고등학교", "4년제 대학교", "2~3년제 전문대학", "대학원", "중학교"], n),
        "marital_status": rng.choice(["배우자있음", "미혼", "사별", "이혼"], n, p=[0.59, 0.26, 0.09, 0.06]),
        "family_type": rng.choice(families, n, p=fw / fw.sum()),
        "housing_type": rng.choice(["아파트", "단독주택", "다세대주택", "주택 이외의 거처"], n),
        "bachelors_field": rng.choice(["해당없음", "공학·제조·건설", "경영·행정·법", "예술·인문"], n),
    })
    by_id = demo.set_index("uuid")

    def load_texts(uuids):
        out = {}
        for u in uuids:
            r = by_id.loc[u]
            g = np.random.default_rng(int(u[4:]) + seed)
            name = f"가상인물{u[4:]}"
            tail = MOCK_TAILS[g.integers(len(MOCK_TAILS))]
            if g.random() < 0.03:
                tail = "주식 투자에는 전혀 관심이 없고 예금만 고집합니다."
            texts = {c: f"{name} 씨의 {c} 서술입니다." for c in TEXT_COLS}
            texts["persona"] = f"{name} 씨는 {r.district}에 사는 {r.age}세 {r.occupation}입니다. {tail}"
            texts["family_persona"] = f"{name} 씨는 {MOCK_HOMES[g.integers(len(MOCK_HOMES))]} {r.family_type} 지냅니다."
            out[u] = texts
        return out

    info = {"mode": "mock", "dataset": "mock (make_mock_source)", "revision": None, "license": None,
            "population_rows": n, "mock_seed": seed}
    return Source(demo, load_texts, info)


def prepare_population(demo: pd.DataFrame) -> pd.DataFrame:
    df = demo[demo["age"] >= MIN_AGE].copy()
    df["age"] = df["age"].astype(int)
    unknown_prov = sorted(set(df["province"]) - set(PROVINCE_FULL))
    unknown_sex = sorted(set(df["sex"]) - set(SEX_TARGET))
    if unknown_prov or unknown_sex:
        raise ValueError(f"매핑에 없는 값 — province: {unknown_prov}, sex: {unknown_sex}")
    df["age_bucket"] = df["age"].map(age_bucket)
    df["region_quota"] = np.where(df["province"].isin(QUOTA_REGIONS), df["province"], "기타")
    return df.reset_index(drop=True)


# ─────────────────────────────────────────────────────────────
# 6. 층화 샘플링: 연령×성별×지역 3차원 정수 쿼터 (세 주변합을 정확히 맞춤)
# ─────────────────────────────────────────────────────────────
def make_quotas(n: int) -> dict:
    return {"age": largest_remainder(AGE_TARGET, n), "sex": largest_remainder(SEX_TARGET, n),
            "region": largest_remainder(REGION_TARGET, n)}


def sample_people(src: Source, pop: pd.DataFrame, quotas: dict, rng):
    age_sex = controlled_round(quotas["age"], quotas["sex"])
    cells = controlled_round({k: v for k, v in age_sex.items()}, quotas["region"])
    groups = pop.groupby(["age_bucket", "sex", "region_quota"], sort=False).indices

    chosen, replacements = [], []
    for a in quotas["age"]:
        for s in quotas["sex"]:
            for r in quotas["region"]:
                k = cells[(a, s), r]
                if k == 0:
                    continue
                idx = groups.get((a, s, r), np.array([], int))
                queue = rng.permutation(idx)
                pending, taken, pos = [], 0, 0
                while taken < k:
                    if pos >= len(queue):
                        raise RuntimeError(f"셀 {a}/{s}/{r} 후보 부족 (필요 {k})")
                    batch = queue[pos: pos + k + 5]
                    texts = src.texts(pop.loc[batch, "uuid"].tolist())
                    for i in batch:
                        pos += 1
                        u = pop.at[i, "uuid"]
                        m = RE_REJECT.search(narrative(texts[u]))
                        if m:
                            pending.append({"cell": f"{a}/{s}/{r}", "removed_uuid": u, "rule": "R12",
                                            "reason": f"서술에 주식·투자 거부 명시: '{snippet(m)}'"})
                            continue
                        for rep in pending:  # 걸러진 후보 자리는 같은 셀의 다음 통과자가 채운다
                            rep["replaced_by"] = u
                        replacements += pending
                        pending = []
                        chosen.append(i)
                        taken += 1
                        if taken == k:
                            break
    return pop.loc[chosen].reset_index(drop=True), replacements, cells


# ─────────────────────────────────────────────────────────────
# 7. 모순 규칙 — 배정과 최종 검증이 같은 함수를 쓴다
# ─────────────────────────────────────────────────────────────
def field_violations(field: str, v, rec: dict, ctx: dict) -> list:
    out = []
    if field == "experience_years" and v > ctx["age"] - MIN_AGE:
        out.append(("R01", f"경력 {v}년 > 나이 {ctx['age']} − 20"))
    if field == "fund_purpose":
        if v == "자녀 교육비" and not ctx["has_child"]:
            out.append(("R02", f"family_type '{ctx['family_type']}'에 자녀 없음"))
        if v == HOUSING_BUY and ctx["tenure"] == "자가":
            out.append(("R03", f"서술상 자가 보유 ({ctx['tenure_basis']}) — 갈아타기·대출 상환이어야 함"))
        if v == HOUSING_MOVE and ctx["tenure"] != "자가":
            out.append(("R03", f"자가 확인 안 됨(점유 {ctx['tenure']}) — 내 집 마련이어야 함"))
        if v == "결혼 자금" and ctx["marital_status"] == "배우자있음":
            out.append(("R04", "marital_status 배우자있음"))
    if field == "invest_style":
        if v == "적립식" and ctx["jobless"]:
            out.append(("R05", "무직 — 소득 기반 적립식 불가"))
        if v == "단타·스윙" and ctx["averse"]:
            out.append(("R10", f"서술상 투자 위험 회피 ({ctx['averse_basis']})"))
    if field == "fund_source":
        if ctx["jobless"] and v not in ASSET_BASED:
            out.append(("R05", "무직 — 자산 기반 자금 원천이어야 함"))
        if v == SPOUSE_FUNDS and ctx["marital_status"] != "배우자있음":
            out.append(("R07", f"marital_status '{ctx['marital_status']}'"))
        role = rec.get("household_role")
        retired = rec.get("unemployed_type") == "은퇴" and (role is None or role != role)  # 저장된 표에선 빈칸이 NaN
        if v == "퇴직금" and not retired and not ctx["left_job"]:
            out.append(("R08", "서술에 퇴직·퇴사 단서가 없고 은퇴(살림 담당 아님) 유형도 아님"))
    if field == "unemployed_type" and ctx["jobless"] != (v is not None):
        out.append(("R06", "무직 여부와 무직 유형 불일치"))
    if field == "household_role" and v is not None and not ctx["jobless"]:
        out.append(("R06", "무직이 아닌데 household_role 있음"))
    if field == "info_source" and v == "직장 동료" and ctx["jobless"]:
        out.append(("R09", "무직 — 직장 동료 없음"))
    if field == "risk_profile":
        if v == "공격형" and ctx["averse"]:
            out.append(("R10", f"서술상 투자 위험 회피 ({ctx['averse_basis']})"))
        if v not in STYLE_RISK[rec["invest_style"]]:
            out.append(("R11", f"투자 방식 '{rec['invest_style']}'와 성향 불일치"))
    if field == "investment_horizon" and v not in STYLE_HORIZON[rec["invest_style"]]:
        out.append(("R11", f"투자 방식 '{rec['invest_style']}'와 투자 기간 불일치"))
    return out


CHECKED_FIELDS = ["experience_years", "unemployed_type", "household_role", "invest_style", "investment_horizon",
                  "risk_profile", "fund_purpose", "fund_source", "info_source"]


def draw_checked(rng, table: dict, field: str, rec: dict, ctx: dict, log: list):
    """기본 분포에서 뽑고, 원본 속성·서술과 충돌하면 허용 값 안에서 다시 뽑아 기록한다."""
    v = pick(rng, table)
    bad = field_violations(field, v, rec, ctx)
    if bad:
        allowed = {k: w for k, w in table.items() if not field_violations(field, k, rec, ctx)}
        if not allowed:
            raise RuntimeError(f"{ctx['uuid']} {field}: 허용 값 없음 {bad}")
        new = pick(rng, allowed)
        log.append({"persona_id": ctx["persona_id"], "uuid": ctx["uuid"], "field": field, "before": v,
                    "after": new, "rule": ",".join(r for r, _ in bad), "reason": "; ".join(m for _, m in bad)})
        v = new
    return v


def detect_tenure(text: str):
    own = [snippet(m) for m in RE_OWN.finditer(text)]
    rent = [snippet(m) for m in RE_RENT.finditer(text)]
    if own and rent:
        return "혼재", f"자가 '{own[0]}' / 임차 '{rent[0]}'"
    if own:
        return "자가", f"'{own[0]}'"
    if rent:
        return "임차", f"'{rent[0]}'"
    return "미상", "서술에 점유 단서 없음"


def unemployed_cues(text: str):
    scores = {k: sum(1 for _ in p.finditer(text)) for k, p in UNEMPLOYED_CUES.items()}
    hits = {k: [snippet(m, 6) for m in p.finditer(text)][:2] for k, p in UNEMPLOYED_CUES.items()}
    return scores, hits


def classify_unemployed(age: int, text: str):
    """무직 유형과 보조 필드 household_role.
    65세 이상은 은퇴가 기본값(서술에 구직 단서가 은퇴 단서보다 많을 때만 구직), 65세 미만은 기존 규칙.
    살림 단서는 나이와 관계없이 household_role(살림 담당)로 따로 남긴다."""
    scores, hits = unemployed_cues(text)
    role = "살림 담당" if scores["주부"] else None
    if age < RETIRE_DEFAULT_AGE:
        return (*classify_unemployed_legacy(age, text), role)
    cue = ", ".join(f"{k} {scores[k]}" for k in scores if scores[k]) or "없음"
    if scores["구직"] > scores["은퇴"]:
        return "구직", f"{RETIRE_DEFAULT_AGE}세 이상이지만 구직 단서가 더 많음(단서: {cue}) 예: {hits['구직']}", role
    return "은퇴", f"{RETIRE_DEFAULT_AGE}세 이상 기본값({age}세, 단서: {cue})", role


def classify_unemployed_legacy(age: int, text: str):
    """3단계 첫 버전 규칙 (65세 미만은 지금도 이 규칙). 서술 단서 개수로 고르고, 단서가 없거나 동점이면 나이로 정한다."""
    scores, hits = unemployed_cues(text)
    top = max(scores.values())
    if top == 0:
        t = "은퇴" if age >= 60 else "구직"
        return t, f"서술 단서 없음 → 나이 기준({age}세)"
    tied = [k for k, v in scores.items() if v == top]
    if len(tied) == 1:
        t = tied[0]
    elif "은퇴" in tied and age >= 55:
        t = "은퇴"
    else:
        t = next(k for k in ("주부", "구직", "은퇴") if k in tied)
    cue = ", ".join(f"{k} {scores[k]}" for k in scores if scores[k])
    return t, f"서술 단서({cue}) 예: {hits[t]}" + (" · 동점은 나이로 결정" if len(tied) > 1 else "")


def assign_attrs(people: pd.DataFrame, texts: dict, rng):
    rows, corrections, notes, type_changes = [], [], [], []
    for _, r in people.iterrows():
        text = narrative(texts[r.uuid])
        jobless = r.occupation == JOBLESS
        tenure, tenure_basis = detect_tenure(text)
        averse = RE_AVERSE.search(text)
        ctx = {"persona_id": r.persona_id, "uuid": r.uuid, "age": int(r.age), "family_type": r.family_type,
               "marital_status": r.marital_status, "has_child": has_child(r.family_type), "jobless": jobless,
               "tenure": tenure, "tenure_basis": tenure_basis, "averse": bool(averse),
               "averse_basis": f"'{snippet(averse)}'" if averse else None,
               "left_job": bool(RE_LEFT_JOB.search(text))}
        g = age_group3(int(r.age))
        rec = {"tenure": tenure, "tenure_basis": tenure_basis, "risk_averse_cue": ctx["averse_basis"]}

        if jobless:
            rec["unemployed_type"], rec["unemployed_basis"], rec["household_role"] = \
                classify_unemployed(int(r.age), text)
            legacy = classify_unemployed_legacy(int(r.age), text)[0]
            if legacy != rec["unemployed_type"]:
                type_changes.append({"persona_id": r.persona_id, "uuid": r.uuid, "age": int(r.age), "sex": r.sex,
                                     "before": legacy, "after": rec["unemployed_type"],
                                     "household_role": rec["household_role"], "basis": rec["unemployed_basis"]})
        else:
            rec["unemployed_type"], rec["unemployed_basis"], rec["household_role"] = None, None, None

        cap = int(r.age) - MIN_AGE
        bands = {b: w for b, w in EXPERIENCE[g].items() if EXPERIENCE_YEARS[b][0] <= cap}
        band = pick(rng, bands)
        lo, hi = EXPERIENCE_YEARS[band]
        rec["experience_band"] = band
        rec["experience_years"] = int(rng.integers(lo, min(hi, cap) + 1))

        rec["invest_style"] = draw_checked(rng, STYLE[g], "invest_style", rec, ctx, corrections)
        rec["investment_horizon"] = draw_checked(rng, STYLE_HORIZON[rec["invest_style"]], "investment_horizon",
                                                 rec, ctx, corrections)
        rec["risk_profile"] = draw_checked(rng, STYLE_RISK[rec["invest_style"]], "risk_profile", rec, ctx,
                                           corrections)

        purposes = dict(FUND_PURPOSE[g])
        if tenure == "임차":
            purposes[HOUSING] *= RENTER_HOUSING_BOOST
        purpose = draw_checked(rng, purposes, "fund_purpose", rec, ctx, corrections)
        if purpose == HOUSING:
            purpose = HOUSING_MOVE if tenure == "자가" else HOUSING_BUY
        rec["fund_purpose"] = purpose
        rec["fund_purpose_note"] = None
        if rec["fund_purpose"] == HOUSING_MOVE and tenure == "자가":
            rec["fund_purpose_note"] = f"자가 보유({tenure_basis})지만 갈아타기·대출 상환 목적이라 허용"
            notes.append({"persona_id": r.persona_id, "uuid": r.uuid, "field": "fund_purpose",
                          "value": HOUSING_MOVE, "rule": "R03", "reason": rec["fund_purpose_note"]})

        sources = FUND_SOURCE_JOBLESS[rec["unemployed_type"]] if jobless else FUND_SOURCE_EMPLOYED
        rec["fund_source"] = draw_checked(rng, sources, "fund_source", rec, ctx, corrections)
        rec["info_source"] = draw_checked(rng, INFO_SOURCE[g], "info_source", rec, ctx, corrections)

        topics = dict(GENERAL_TOPICS)
        first = COMPANY_TOPIC[r.primary_company] if rng.random() < 0.5 else pick(rng, topics)
        topics.pop(first, None)
        rec["learning_interest"] = first if rng.random() < 0.4 else f"{first}|{pick(rng, topics)}"

        w = WRITING[g]
        rec.update({
            "nickname": str(rng.choice(NICKNAME[r.primary_company])),
            "w_banmal": bool(rng.random() < w["banmal"]),
            "w_laugh": bool(rng.random() < w["laugh"]),
            "w_ellipsis": bool(rng.random() < w["ellipsis"]),
            "w_typo_rate": float(rng.choice(w["typo"])),
            "w_length": "짧게" if rng.random() < w["short"] else str(rng.choice(["보통", "길게"], p=[0.7, 0.3])),
        })
        rows.append(rec)
    return pd.DataFrame(rows), corrections, notes, type_changes


def rule_context(r: pd.Series, texts: dict) -> dict:
    """검증용: 저장된 값과 원본 서술만으로 규칙 판단 근거를 다시 만든다."""
    text = narrative(texts[r.uuid])
    tenure, tenure_basis = detect_tenure(text)
    averse = RE_AVERSE.search(text)
    return {"persona_id": r.persona_id, "uuid": r.uuid, "age": int(r.age), "family_type": r.family_type,
            "marital_status": r.marital_status, "has_child": has_child(r.family_type),
            "jobless": r.occupation == JOBLESS, "tenure": tenure, "tenure_basis": tenure_basis,
            "averse": bool(averse), "averse_basis": f"'{snippet(averse)}'" if averse else None,
            "left_job": bool(RE_LEFT_JOB.search(text)), "reject": bool(RE_REJECT.search(text))}


# ─────────────────────────────────────────────────────────────
# 8. 기업·슬롯: 대표 종목 기업별 n/4명, 기업별 슬롯 n×10/4개를 정수계획으로 정확히 맞춘다
# ─────────────────────────────────────────────────────────────
def solve_slot_milp(primary: list, interests: list, tp: list, tx: list, per_company: int):
    """변수: 대표 슬롯 p_i ∈ [5,7] (관심 없으면 10), 관심 슬롯 x_ic ≥ 1.
    제약: 인당 합 10, 기업별 합 per_company. 목적: 무작위로 뽑은 목표 배분과의 차이 최소."""
    from scipy.optimize import Bounds, LinearConstraint, milp

    var, target, lb, ub = [], [], [], []
    for i, S in enumerate(interests):
        var.append((i, primary[i]))
        target.append(tp[i])
        lb.append(PRIMARY_SLOTS[0] if S else Q_PER_PERSONA)
        ub.append(PRIMARY_SLOTS[1] if S else Q_PER_PERSONA)
        for c, t in zip(S, tx[i]):
            var.append((i, c))
            target.append(t)
            lb.append(1)
            ub.append(Q_PER_PERSONA - PRIMARY_SLOTS[0])
    m = len(var)
    A, b = [], []
    for i in range(len(primary)):
        A.append([1.0 if v[0] == i else 0.0 for v in var] + [0.0] * 2 * m)
        b.append(Q_PER_PERSONA)
    for c in COMPANIES:
        A.append([1.0 if v[1] == c else 0.0 for v in var] + [0.0] * 2 * m)
        b.append(per_company)
    for j in range(m):  # v_j − d⁺_j + d⁻_j = target_j
        row = np.zeros(3 * m)
        row[j], row[m + j], row[2 * m + j] = 1, -1, 1
        A.append(row.tolist())
        b.append(target[j])
    res = milp(c=np.r_[np.zeros(m), np.ones(2 * m)],
               constraints=LinearConstraint(np.array(A), b, b),
               integrality=np.r_[np.ones(m), np.zeros(2 * m)],
               bounds=Bounds(np.r_[lb, np.zeros(2 * m)], np.r_[ub, np.full(2 * m, np.inf)]))
    if res.status != 0:
        return None
    vals = np.rint(res.x[:m]).astype(int)
    M = np.zeros((len(primary), len(COMPANIES)), int)
    for (i, c), v in zip(var, vals):
        M[i, COMPANIES.index(c)] += v
    return M


def assign_slots(people: pd.DataFrame, rng, n: int):
    per_company = n * Q_PER_PERSONA // len(COMPANIES)
    primary = people["primary_company"].tolist()
    for attempt in range(1, SLOT_MAX_ATTEMPTS + 1):
        interests, tp, tx = [], [], []
        for c0 in primary:
            k = pick(rng, INTEREST_COUNT)
            others = [c for c in COMPANIES if c != c0]
            S = sorted(rng.choice(others, size=k, replace=False).tolist(), key=COMPANIES.index) if k else []
            p = int(rng.integers(PRIMARY_SLOTS[0], PRIMARY_SLOTS[1] + 1)) if k else Q_PER_PERSONA
            rest = Q_PER_PERSONA - p
            split = []
            if k == 1:
                split = [rest]
            elif k == 2:
                a = int(rng.integers(1, rest))
                split = [a, rest - a]
            interests.append(S)
            tp.append(p)
            tx.append(split)
        M = solve_slot_milp(primary, interests, tp, tx, per_company)
        if M is not None:
            return M, interests, attempt
    raise RuntimeError(f"{SLOT_MAX_ATTEMPTS}회 시도 안에 기업별 {per_company}슬롯을 맞추지 못했습니다.")


# ─────────────────────────────────────────────────────────────
# 9. 전체 조립
# ─────────────────────────────────────────────────────────────
def build(src: Source, pop: pd.DataFrame, n: int, seed: int) -> dict:
    rng = np.random.default_rng(seed)
    quotas = make_quotas(n)
    people, replacements, cells = sample_people(src, pop, quotas, rng)
    people = people.sample(frac=1, random_state=int(rng.integers(2**31))).reset_index(drop=True)
    people.insert(0, "persona_id", [f"P{i + 1:03d}" for i in range(len(people))])
    people["province_full"] = people["province"].map(PROVINCE_FULL)
    people["primary_company"] = rng.permutation(np.repeat(COMPANIES, n // len(COMPANIES)))
    texts = src.texts(people["uuid"].tolist())

    attrs, corrections, notes, type_changes = assign_attrs(people, texts, rng)
    p = pd.concat([people, attrs], axis=1)

    M, interests, attempts = assign_slots(p, rng, n)
    for j, c in enumerate(COMPANIES):
        p[f"q_{c}"] = M[:, j]
    p["primary_slots"] = [M[i, COMPANIES.index(c)] for i, c in enumerate(p["primary_company"])]
    p["interest_companies"] = ["|".join(S) for S in interests]
    p["primary_status"] = [pick(rng, PRIMARY_STATUS) for _ in range(n)]
    p["interest_statuses"] = ["|".join(f"{c}:{pick(rng, INTEREST_STATUS)}" for c in S) for S in interests]

    plan = []
    for i, r in p.iterrows():
        status = {r.primary_company: r.primary_status}
        status.update(dict(s.split(":") for s in r.interest_statuses.split("|") if s))
        seq = [c for c in COMPANIES for _ in range(M[i, COMPANIES.index(c)])]
        for k, j in enumerate(rng.permutation(len(seq))):
            c = seq[j]
            plan.append({"persona_id": r.persona_id, "slot": k + 1, "company": c,
                         "role": "대표" if c == r.primary_company else "관심", "status": status[c]})

    cols = ["persona_id", "uuid", "sex", "age", "age_bucket", "province", "province_full", "region_quota",
            "district", "occupation", "education_level", "bachelors_field", "marital_status", "family_type",
            "housing_type", "tenure", "tenure_basis", "unemployed_type", "unemployed_basis", "household_role",
            "primary_company", "primary_status", "primary_slots", "interest_companies", "interest_statuses"] \
        + [f"q_{c}" for c in COMPANIES] \
        + ["experience_band", "experience_years", "investment_horizon", "invest_style", "risk_profile",
           "fund_purpose", "fund_purpose_note", "fund_source", "info_source", "learning_interest",
           "risk_averse_cue", "nickname", "w_banmal", "w_laugh", "w_ellipsis", "w_typo_rate", "w_length"]
    return {"personas": p[cols], "slot_plan": pd.DataFrame(plan), "texts": texts, "quotas": quotas,
            "cells": {f"{a}/{s}/{r}": v for ((a, s), r), v in cells.items() if v},
            "replacements": replacements, "corrections": corrections, "notes": notes,
            "unemployed_type_changes": type_changes, "slot_attempts": attempts}


def digest(res: dict) -> str:
    payload = {"personas": res["personas"].to_dict("records"), "slot_plan": res["slot_plan"].to_dict("records"),
               "replacements": res["replacements"], "corrections": res["corrections"], "notes": res["notes"],
               "unemployed_type_changes": res["unemployed_type_changes"]}
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()


# ─────────────────────────────────────────────────────────────
# 10. 검증 — 하나라도 실패하면 성공으로 저장하지 않는다
# ─────────────────────────────────────────────────────────────
def validate(res: dict, n: int, src: Source) -> list:
    p, plan, q = res["personas"], res["slot_plan"], res["quotas"]
    per_company = n * Q_PER_PERSONA // len(COMPANIES)
    checks = []

    def check(name, ok, detail=""):
        checks.append({"check": name, "ok": bool(ok), "detail": detail})

    def same(actual: pd.Series, target: dict):
        a = actual.value_counts().to_dict()
        return all(a.get(k, 0) == v for k, v in target.items()) and set(a) <= set(target), a

    check("인원 수", len(p) == n, f"{len(p)}명")
    check("uuid 중복 0", p["uuid"].is_unique, f"중복 {p['uuid'].duplicated().sum()}건")
    check("만 20세 이상", p["age"].min() >= MIN_AGE, f"최소 {p['age'].min()}세")
    for name, col in (("연령", "age_bucket"), ("성별", "sex"), ("지역", "region_quota")):
        ok, a = same(p[col], q[{"연령": "age", "성별": "sex", "지역": "region"}[name]])
        check(f"{name} 쿼터 일치", ok, json.dumps(a, ensure_ascii=False))
    check("province_full 매핑", p["province_full"].notna().all() and
          (p["province_full"] == p["province"].map(PROVINCE_FULL)).all())
    ok, a = same(p["primary_company"], {c: n // len(COMPANIES) for c in COMPANIES})
    check(f"대표 종목 기업별 {n // len(COMPANIES)}명", ok, json.dumps(a, ensure_ascii=False))

    per_persona = plan.groupby("persona_id").size()
    check("인당 10슬롯", len(per_persona) == n and (per_persona == Q_PER_PERSONA).all())
    by_company = plan["company"].value_counts().to_dict()
    check(f"기업별 {per_company}슬롯", all(by_company.get(c, 0) == per_company for c in COMPANIES),
          json.dumps(by_company, ensure_ascii=False))
    qsum = p[[f"q_{c}" for c in COMPANIES]].sum(axis=1)
    check("속성표 슬롯 합 = 10", (qsum == Q_PER_PERSONA).all())
    n_int = p["interest_companies"].map(lambda s: len([c for c in s.split("|") if c]))
    check("관심 종목 0~2개", n_int.between(0, 2).all(), json.dumps(n_int.value_counts().sort_index().to_dict()))
    prim = p["primary_slots"]
    check("대표 종목 슬롯 ≥ 5", (prim >= PRIMARY_SLOTS[0]).all(), f"최소 {prim.min()}")
    check("관심 있으면 대표 5~7, 없으면 10",
          ((n_int == 0) & (prim == Q_PER_PERSONA) | (n_int > 0) & prim.between(*PRIMARY_SLOTS)).all())
    role_ok = all(
        ((plan.persona_id == r.persona_id) & (plan.company == r.primary_company) & (plan.role == "대표")).sum()
        == r.primary_slots for r in p.itertuples())
    check("slot_plan 대표 슬롯 = 속성표", role_ok)
    int_ok = all(r[f"q_{c}"] >= 1 for _, r in p.iterrows() for c in r.interest_companies.split("|") if c)
    check("관심 종목마다 1슬롯 이상", int_ok)

    violations = []
    texts = src.texts(p["uuid"].tolist())
    for _, r in p.iterrows():
        ctx = rule_context(r, texts)
        rec = r.to_dict()
        if ctx["reject"]:
            violations.append(f"{r.persona_id} R12 서술상 투자 거부")
        for f in CHECKED_FIELDS:
            v = rec[f]
            v = None if (f in ("unemployed_type", "household_role") and pd.isna(v)) else v
            violations += [f"{r.persona_id} {rule} {f}={v}: {m}" for rule, m in field_violations(f, v, rec, ctx)]
        if r.tenure != ctx["tenure"]:
            violations.append(f"{r.persona_id} 점유 형태 재계산 불일치")
    check("모순 검사 위반 0건", not violations, "; ".join(violations[:10]))
    check("원문 서술 보존", all(res["texts"][u] == texts[u] for u in p["uuid"]))
    return checks


# ─────────────────────────────────────────────────────────────
# 11. 저장
# ─────────────────────────────────────────────────────────────
def dist_table(actual: pd.Series, target: dict) -> pd.DataFrame:
    a = actual.value_counts()
    return pd.DataFrame({"목표": pd.Series(target), "실제": a.reindex(list(target)).fillna(0).astype(int)})


def md_table(df: pd.DataFrame) -> str:
    cols = [df.index.name or ""] + [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for idx, row in df.iterrows():
        lines.append("| " + " | ".join([str(idx)] + [str(v) for v in row]) + " |")
    return "\n".join(lines)


def build_meta(res: dict, args, src: Source, checks: list, status: str) -> dict:
    n = args.n_personas
    return {
        "tool": TOOL,
        "status": status,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sample_description": SAMPLE_LABEL,
        "mode": src.info["mode"],
        "seed": args.seed,
        "n_personas": n,
        "source": {**src.info, "age_filter": f"age ≥ {MIN_AGE} (age는 만 나이로 간주)"},
        "targets": {
            "source": STAT_SOURCE,
            "age": res["quotas"]["age"], "sex": res["quotas"]["sex"], "region": res["quotas"]["region"],
            "region_rule": f"province가 {'/'.join(QUOTA_REGIONS)}이면 그대로, 나머지는 기타",
            "temporary_allocations": TEMP_ALLOCATION,
            "cells_age_sex_region": res.get("cells"),
        },
        "companies": {
            "list": COMPANIES,
            "primary_per_company": n // len(COMPANIES),
            "slots_per_company": n * Q_PER_PERSONA // len(COMPANIES),
            "slots_per_persona": Q_PER_PERSONA,
            "primary_slots": "관심 종목이 있으면 5~7, 없으면 10",
            "interest_companies": "0~2개 (1인 최대 3종목)",
            "note": "기업별 대표 종목 인원과 슬롯 수는 평가용 배분이며 실제 투자자 비중이 아니다.",
            "slot_solver": f"scipy.optimize.milp, 관심 종목 무작위 배정 {res.get('slot_attempts')}회째에 성공",
        },
        "attributes": {
            "fields": ["unemployed_type", "household_role", "experience_band", "experience_years", "fund_purpose",
                       "fund_source", "learning_interest",
                       "investment_horizon", "primary_status", "interest_statuses", "invest_style",
                       "risk_profile", "info_source", "nickname", "w_banmal", "w_laugh", "w_ellipsis",
                       "w_typo_rate", "w_length"],
            "note": "투자 속성은 전부 팀 가정. 연령대별 가중치는 확률만 바꾸며 나이만으로 금지·허용하지 않는다. "
                    "원본 속성·서술과 명백히 충돌하는 값만 규칙으로 막는다.",
        },
        "assumptions": [
            "housing_type은 건물 유형(아파트·단독주택 등)만 있고 점유 형태가 없어, 자가·임차는 원문 서술의 "
            "키워드(자가 주택/아파트, 전세, 월세 등)로 판단한다(tenure). 단서가 없으면 미상, 둘 다 있으면 혼재.",
            "family_type의 '자녀'는 손자녀만 있는 경우를 제외한다. 기타2세대·기타3세대·4세대이상은 자녀 포함으로 보지 않는다.",
            f"무직 유형(은퇴·주부·구직): {RETIRE_DEFAULT_AGE}세 이상은 은퇴가 기본값(서술의 구직 단서가 은퇴 단서보다 많을 때만 구직). "
            f"{RETIRE_DEFAULT_AGE}세 미만은 서술 단서 개수로 고르고, 단서가 없으면 60세 이상 은퇴·미만 구직으로 둔다. "
            "학생 단서는 구직으로 묶는다. 판단 근거는 unemployed_basis에 남긴다.",
            "살림 단서(살림·집안일·주부·육아 등)가 있는 무직자는 나이와 관계없이 household_role='살림 담당'으로 따로 남긴다.",
            "원문 서술(personas.jsonl의 nemotron)은 수정하지 않는다.",
        ],
        "rules": RULES,
        "province_full_map": PROVINCE_FULL,
        "replacements": res.get("replacements"),
        "corrections": res.get("corrections"),
        "allowed_with_reason": res.get("notes"),
        "unemployed_type_changes": res.get("unemployed_type_changes"),
        "validation": checks,
    }


def render_review(res: dict, meta: dict) -> str:
    p, q = res["personas"], res["quotas"]
    L = [f"# 평가용 페르소나 {len(p)}명 검수 ({meta['mode']})", "",
         f"{SAMPLE_LABEL}입니다. 목표 분포 출처: {STAT_SOURCE}.",
         "70대+ 인원과 지역 배분은 임시 테스트 배분입니다. 기업별 대표 종목 인원·슬롯은 평가용 배분이며 실제 투자자 비중이 아닙니다.",
         "", f"- 데이터: {meta['source'].get('dataset')} (revision {meta['source'].get('revision')})",
         f"- seed {meta['seed']}, 생성 {meta['generated_at']}", ""]
    for title, col, key in (("연령", "age_bucket", "age"), ("성별", "sex", "sex"), ("지역", "region_quota", "region")):
        t = dist_table(p[col], q[key])
        t.index.name = title
        L += [f"## {title}", "", md_table(t), ""]
    slots = res["slot_plan"].pivot_table(index="company", columns="role", values="slot", aggfunc="count",
                                         fill_value=0).reindex(COMPANIES)
    slots["합계"] = slots.sum(axis=1)
    slots.insert(0, "대표 종목 인원", p["primary_company"].value_counts().reindex(COMPANIES))
    slots.index.name = "기업"
    L += ["## 기업·슬롯", "", md_table(slots), ""]
    for title, col in (("무직 유형", "unemployed_type"), ("살림 담당(household_role)", "household_role"),
                       ("점유 형태(서술 기준)", "tenure"), ("자금 목적", "fund_purpose"),
                       ("자금 원천", "fund_source"), ("투자 방식", "invest_style"), ("성향", "risk_profile")):
        t = p[col].fillna("(무직 아님)").value_counts().to_frame("인원")
        t.index.name = title
        L += [f"## {title}", "", md_table(t), ""]
    L += ["## 교체 기록 (R12)", ""]
    L += [f"- {r['cell']}: {r['removed_uuid']} → {r['replaced_by']} — {r['reason']}" for r in res["replacements"]] \
        or ["- 없음"]
    L += ["", "## 수정 기록 (원본 속성·서술과 충돌해 다시 뽑은 값)", ""]
    L += [f"- {c['persona_id']} `{c['field']}` {c['before']} → {c['after']} ({c['rule']}: {c['reason']})"
          for c in res["corrections"]] or ["- 없음"]
    L += ["", "## 사유를 남기고 허용한 값", ""]
    L += [f"- {c['persona_id']} `{c['field']}` {c['value']} — {c['reason']}" for c in res["notes"]] or ["- 없음"]
    L += ["", f"## 무직 유형 규칙 변경으로 바뀐 사람 ({RETIRE_DEFAULT_AGE}세 이상 은퇴 기본값)", "",
          "이전 규칙(서술 단서 개수 우선)으로 정했을 때와 무직 유형이 달라진 사람입니다.", ""]
    L += [f"- {c['persona_id']} ({c['age']}세 {c['sex']}) {c['before']} → {c['after']}"
          f" · household_role {c['household_role'] or '-'} · {c['basis']}"
          for c in res["unemployed_type_changes"]] or ["- 없음"]
    L += ["", "## 검증", ""]
    L += [f"- {'통과' if c['ok'] else '실패'} · {c['check']}" + (f" — {c['detail']}" if c["detail"] else "")
          for c in meta["validation"]]
    L += ["", "## 전체 목록", "",
          "| ID | 나이 | 성별 | 지역 | 직업 | 무직 유형 | 대표 종목 | 슬롯 | 자금 목적 | 점유 |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for _, r in p.iterrows():
        alloc = " ".join(f"{c} {r[f'q_{c}']}" for c in COMPANIES if r[f"q_{c}"])
        L.append(f"| {r.persona_id} | {r.age} | {r.sex} | {r.province_full} {r.district.split('-', 1)[-1]} | "
                 f"{r.occupation} | {r.unemployed_type or '-'} | {r.primary_company} | {alloc} | "
                 f"{r.fund_purpose} | {r.tenure} |")
    return "\n".join(L) + "\n"


def render_source(meta: dict) -> str:
    src = meta["source"]
    if meta["mode"] == "mock":
        return ("# 출처\n\n로직 확인용 가짜 데이터(make_mock_source)로 만든 결과입니다. "
                "실제 인물·실제 데이터가 아니며 평가에 쓰지 않습니다.\n")
    return "\n".join([
        "# 출처와 이용 조건",
        "",
        f"- 원본 데이터: [{src['dataset']}](https://huggingface.co/datasets/{src['dataset']})",
        f"- revision: `{src['revision']}`",
        f"- 라이선스: {src['license']} — 재배포·수정 시 출처(NVIDIA, Nemotron-Personas-Korea)를 밝힙니다.",
        "- 합성 데이터입니다. 이름·서술은 생성된 가상 인물이며 실존 인물이 아닙니다.",
        f"- 원본 서술(personas.jsonl의 `nemotron`)은 수정하지 않았습니다. 이 폴더의 페르소나는 만 {MIN_AGE}세 이상 중에서 "
        f"{SAMPLE_LABEL}으로 뽑았습니다.",
        f"- 목표 분포 출처: {STAT_SOURCE}. 70대+ 인원과 지역 배분은 임시 테스트 배분입니다.",
        "- 투자 속성(경력·자금 목적·자금 원천·성향·정보 출처·보유 상태·표현 선호 등)과 무직 유형·점유 형태 추정은 "
        "평가용 가정이며 원본 데이터에 없는 값입니다. 기업별 대표 종목 인원·슬롯도 평가용 배분이며 실제 투자자 비중이 아닙니다.",
        f"- 생성 도구: `{TOOL}` (seed {meta['seed']})",
        "",
    ])


def save(res: dict, meta: dict, out: str):
    tmp = out + ".tmp"
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp)
    p = res["personas"]
    p.to_csv(f"{tmp}/personas.csv", index=False, encoding="utf-8-sig")
    res["slot_plan"].to_csv(f"{tmp}/slot_plan.csv", index=False, encoding="utf-8-sig")
    with open(f"{tmp}/personas.jsonl", "w", encoding="utf-8") as f:
        for _, r in p.iterrows():
            rec = {k: (v.item() if hasattr(v, "item") else (None if v is None or v != v else v))
                   for k, v in r.items()}
            for k in ("interest_companies",):
                rec[k] = [c for c in rec[k].split("|") if c]
            rec["interest_statuses"] = dict(s.split(":") for s in rec["interest_statuses"].split("|") if s)
            rec["learning_interest"] = rec["learning_interest"].split("|")
            rec["nemotron"] = res["texts"][r.uuid]
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    with open(f"{tmp}/review.md", "w", encoding="utf-8") as f:
        f.write(render_review(res, meta))
    with open(f"{tmp}/SOURCE.md", "w", encoding="utf-8") as f:
        f.write(render_source(meta))
    meta["files"] = {name: sha256_file(f"{tmp}/{name}")
                     for name in ("personas.csv", "personas.jsonl", "slot_plan.csv", "review.md", "SOURCE.md")}
    with open(f"{tmp}/meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1, default=str)
    if os.path.exists(out):
        with open(f"{out}/meta.json", encoding="utf-8") as f:
            if json.load(f).get("tool") != TOOL:
                raise RuntimeError(f"{out}은 이 도구가 만든 폴더가 아니라 덮어쓰지 않습니다.")
        shutil.rmtree(out)
    os.replace(tmp, out)


def print_report(res: dict):
    p, q = res["personas"], res["quotas"]
    for title, col, key in (("연령", "age_bucket", "age"), ("성별", "sex", "sex"), ("지역", "region_quota", "region")):
        print(f"\n[{title}]\n{dist_table(p[col], q[key]).to_string()}")
    print(f"\n[기업별 슬롯]\n{res['slot_plan'].groupby(['company', 'role']).size().unstack(fill_value=0).to_string()}")
    print(f"\n교체 {len(res['replacements'])}건 / 수정 {len(res['corrections'])}건 / 사유 기록 허용 {len(res['notes'])}건")


# ─────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/nemotron_ko", help="Nemotron parquet 폴더")
    ap.add_argument("--mock", action="store_true", help="가짜 데이터로 로직만 검증")
    ap.add_argument("--n-personas", type=int, default=DEFAULT_N)
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--out", help="기본: results/memo_personas/personas_<N>[_mock]")
    args = ap.parse_args()
    n = args.n_personas
    if n % len(COMPANIES):
        ap.error(f"--n-personas는 {len(COMPANIES)}의 배수여야 합니다 (기업별 대표 종목 인원 동일).")
    real_out = f"results/memo_personas/personas_{n}"
    args.out = args.out or (real_out + "_mock" if args.mock else real_out)
    if args.mock and os.path.normpath(args.out) == os.path.normpath(real_out):
        ap.error("mock 결과를 실제 결과 폴더에 쓸 수 없습니다.")

    src = make_mock_source(args.seed) if args.mock else load_source(args.data)
    pop = prepare_population(src.demo)
    print(f"모집단 {len(src.demo):,}명 로드 (만 {MIN_AGE}세 이상 {len(pop):,}명)")

    res = build(src, pop, n, args.seed)
    print_report(res)
    checks = validate(res, n, src)
    again = build(src, pop, n, args.seed)
    checks.append({"check": "시드 고정 재실행 동일", "ok": digest(res) == digest(again),
                   "detail": f"sha256 {digest(res)[:16]}… vs {digest(again)[:16]}…"})

    status = "success" if all(c["ok"] for c in checks) else "failed"
    meta = build_meta(res, args, src, checks, status)
    review = render_review(res, meta)
    banned = "대표 " + "표본"
    checks.append({"check": f"금지 표현 '{banned}' 없음",
                   "ok": banned not in review and banned not in json.dumps(meta, ensure_ascii=False), "detail": ""})
    status = "success" if all(c["ok"] for c in checks) else "failed"
    meta["status"] = status

    print("\n[검증]")
    for c in checks:
        print(f"  {'통과' if c['ok'] else '실패'}  {c['check']}" + (f" — {c['detail']}" if c["detail"] else ""))
    if status != "success":
        fail_dir = args.out + "_failed"
        os.makedirs(fail_dir, exist_ok=True)
        with open(f"{fail_dir}/meta.json", "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=1, default=str)
        print(f"\n검증 실패 → {args.out}는 그대로 두고 {fail_dir}/meta.json에 기록했습니다.")
        sys.exit(1)
    save(res, meta, args.out)
    print(f"\n저장 완료 → {args.out}/ (personas.csv, personas.jsonl, slot_plan.csv, meta.json, review.md, SOURCE.md)")


if __name__ == "__main__":
    main()
