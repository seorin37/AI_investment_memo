"""메모 생성 파이프라인 공통 도구 — 경로·설정·.env·파일 입출력·페르소나 로드·안내 출력.

모든 명령은 레포 루트에서 `python -m eval.memo_personas.<모듈>`로 실행한다.
Windows+WSL2에서도 같은 결과가 나오도록 경로는 pathlib, 파일은 UTF-8로만 읽고 쓴다.
비밀값(.env의 LLM_API_KEY·DATABASE_URL)은 프로그램 안에서만 쓰고 화면·파일에 남기지 않는다.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import sys
from pathlib import Path

PKG_DIR = Path(__file__).resolve().parent
REPO_ROOT = PKG_DIR.parents[1]
CONFIG_PATH = PKG_DIR / "config.yaml"
ENV_PATH = REPO_ROOT / ".env"
ENV_KEYS = ("LLM_API_KEY", "LLM_MODEL", "DATABASE_URL")

COMPANIES = ["삼성전자", "SK하이닉스", "NAVER", "KB금융"]
# 메모 속 기업 언급 판정용 별명 (소문자로 비교). 페르소나 nickname(sample_personas.NICKNAME)을 모두 포함한다.
ALIASES = {
    "삼성전자": ["삼성전자", "삼전", "삼성"],
    "SK하이닉스": ["sk하이닉스", "하이닉스", "하닉"],
    "NAVER": ["naver", "네이버", "넵"],
    "KB금융": ["kb금융", "kb국민", "국민은행", "kb"],
}
# 다른 종목 언급 판정용 (B10·C3). 0002 시드 종목 + 메모에 자주 나오는 해외 종목
OTHER_STOCKS = [
    "LG에너지솔루션", "엘지에너지솔루션", "LG엔솔", "엔솔", "삼성바이오로직스", "삼성바이오", "삼바", "현대차", "현대자동차", "기아",
    "셀트리온", "카카오", "POSCO홀딩스", "포스코홀딩스", "포스코", "LG화학", "삼성SDI", "삼성물산", "현대모비스", "한국전력", "한전",
    "크래프톤", "엔씨소프트", "엔씨", "하이브", "SK이노베이션", "대한항공", "아모레퍼시픽", "두산에너빌리티", "신한지주", "신한금융",
    "하나금융지주", "하나금융", "삼성생명", "우리금융", "엔비디아", "테슬라", "애플", "마이크론", "TSMC", "구글", "알파벳", "메타",
]


def setup_console() -> None:
    """Windows 콘솔·WSL2에서 한글·이모지가 깨지지 않게 UTF-8로 출력한다."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass


def load_env() -> None:
    """레포 루트 .env를 읽는다. 이미 있는 환경변수는 덮어쓰지 않는다."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(ENV_PATH, override=False, encoding="utf-8")


def env_value(name: str) -> str | None:
    v = os.environ.get(name)
    return v.strip() if v and v.strip() else None


def load_config(path: Path | None = None) -> dict:
    """config.yaml을 읽는다. MEMO_CONFIG 환경변수는 개발·테스트 전용(맥북 점검용 설정 파일)."""
    import yaml

    path = Path(path or os.environ.get("MEMO_CONFIG") or CONFIG_PATH)
    if not path.is_absolute():
        path = REPO_ROOT / path
    with path.open(encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    cfg["_path"] = str(path)
    return cfg


def rpath(p: str | Path) -> Path:
    p = Path(p)
    return p if p.is_absolute() else REPO_ROOT / p


def company_codes(cfg: dict) -> dict[str, str]:
    return {name: str(code).zfill(6) for name, code in cfg["companies"].items()}


# ── 파일 입출력 (UTF-8, 중간에 끊겨도 반쯤 쓴 파일이 남지 않게 임시 파일 → 교체) ──
def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    os.replace(tmp, path)


def write_json(path: Path, data) -> None:
    write_text(path, json.dumps(data, ensure_ascii=False, indent=1, default=str) + "\n")


def read_json(path: Path):
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def write_jsonl(path: Path, rows) -> None:
    write_text(path, "".join(json.dumps(r, ensure_ascii=False, default=str) + "\n" for r in rows))


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ── 페르소나 (3단계 결과 그대로) ──
def load_personas(cfg: dict) -> list[dict]:
    """personas.jsonl + slot_plan.csv → 사람별 dict (slots: [{slot, company, role, status}])."""
    d = rpath(cfg["paths"]["personas_dir"])
    people = read_jsonl(d / "personas.jsonl")
    slots: dict[str, list[dict]] = {}
    with (d / "slot_plan.csv").open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            slots.setdefault(r["persona_id"], []).append(
                {"slot": int(r["slot"]), "company": r["company"], "role": r["role"], "status": r["status"]})
    for p in people:
        p["slots"] = sorted(slots.get(p["persona_id"], []), key=lambda s: s["slot"])
    return people


# ── 안내 출력 ──
OK, FAIL, WARN = "✅", "❌", "⚠️"


def say(mark: str, title: str, detail: str = "", fix: str = "") -> None:
    print(f"{mark} {title}" + (f" — {detail}" if detail else ""))
    if fix:
        for line in fix.strip().splitlines():
            print(f"     ↳ {line}")
