"""1) 사전 점검 — 메모 생성 전에 환경·데이터·DB·Gemini가 준비됐는지 항목마다 ✅/❌로 알려 준다.

    python -m eval.memo_personas.preflight

❌가 하나라도 있으면 종료 코드 1, 전부 ✅면 다음 명령을 보여 준다. ⚠️는 진행은 되지만 확인이 필요한 항목.
.env의 값(API 키·DB 주소)은 절대 화면에 출력하지 않는다. 있는지 없는지만 본다.
"""

from __future__ import annotations

import csv
import importlib
import sys

from .common import (ENV_KEYS, ENV_PATH, FAIL, OK, WARN, company_codes, env_value, load_config, load_env, read_json,
                     read_jsonl, rpath, say, setup_console)

PACKAGES = {"requests": "requests", "sqlalchemy": "sqlalchemy", "psycopg": "psycopg[binary]", "yaml": "PyYAML",
            "dotenv": "python-dotenv"}
INSTALL = "pip install -r eval/memo_personas/requirements.txt"

# 데이터 건수·날짜 범위 (테이블 근거는 export_evidence.REQUIRED_COLUMNS 주석과 같다)
SQL_COUNTS = {
    "주가": "SELECT count(*) AS n, min(trade_date) AS first, max(trade_date) AS last FROM prices_daily WHERE symbol = :s",
    "공시": "SELECT count(*) AS n, min(rcept_dt) AS first, max(rcept_dt) AS last FROM disclosures WHERE symbol = :s",
    "공시 청크": "SELECT count(*) AS n, NULL AS first, NULL AS last FROM disclosure_chunks c "
              "JOIN disclosures d ON d.rcept_no = c.rcept_no WHERE d.symbol = :s",
    "뉴스": "SELECT count(*) AS n, min(a.published_at)::date AS first, max(a.published_at)::date AS last "
          "FROM news_stocks ns JOIN news_articles a ON a.id = ns.news_id WHERE ns.symbol = :s",
    "재무": "SELECT count(*) AS n, min(period_end) AS first, max(period_end) AS last FROM financials WHERE symbol = :s",
}
SQL_MACRO_COUNTS = """
SELECT indicator_code, count(*) AS n, max(observation_date) AS last FROM economic_observations
WHERE indicator_code = ANY(:codes) GROUP BY indicator_code
"""


class Result:
    def __init__(self):
        self.fails = 0
        self.warns = 0

    def ok(self, title, detail=""):
        say(OK, title, detail)

    def fail(self, title, detail="", fix=""):
        self.fails += 1
        say(FAIL, title, detail, fix)

    def warn(self, title, detail="", fix=""):
        self.warns += 1
        say(WARN, title, detail, fix)


def check_python(r: Result):
    v = sys.version_info
    if v >= (3, 10):
        r.ok("Python 버전", f"{v.major}.{v.minor}.{v.micro}")
    else:
        r.fail("Python 버전", f"{v.major}.{v.minor} (3.10 이상 필요, 팀 환경은 3.11)",
               "conda activate ai_memo 로 팀 환경을 켠 뒤 다시 실행하세요.")


def check_packages(r: Result) -> bool:
    missing = []
    for mod, pkg in PACKAGES.items():
        try:
            importlib.import_module(mod)
        except ImportError:
            missing.append(pkg)
    if missing:
        r.fail("필요한 패키지", "없음: " + ", ".join(missing), INSTALL)
        return False
    r.ok("필요한 패키지", ", ".join(PACKAGES.values()))
    return True


def check_personas(r: Result, cfg: dict):
    d = rpath(cfg["paths"]["personas_dir"])
    need = ["personas.jsonl", "slot_plan.csv", "meta.json"]
    if not all((d / f).exists() for f in need):
        r.fail("페르소나 파일", f"{cfg['paths']['personas_dir']}에 {', '.join(need)} 중 빠진 파일이 있음",
               "git pull 로 feature/sanggue-next 브랜치를 받았는지 확인하세요 (git status, git log -1).")
        return
    people = read_jsonl(d / "personas.jsonl")
    with (d / "slot_plan.csv").open(encoding="utf-8-sig", newline="") as f:
        plan = list(csv.DictReader(f))
    by_company = {}
    for row in plan:
        by_company[row["company"]] = by_company.get(row["company"], 0) + 1
    per_person = {}
    for row in plan:
        per_person[row["persona_id"]] = per_person.get(row["persona_id"], 0) + 1
    meta = read_json(d / "meta.json")
    n = len(people)
    problems = []
    if n != 100:
        problems.append(f"{n}명(100명이어야 함)")
    if len(plan) != 1000:
        problems.append(f"슬롯 {len(plan)}개(1,000개여야 함)")
    if any(v != 250 for v in by_company.values()) or len(by_company) != 4:
        problems.append(f"기업별 슬롯 {by_company}(각 250이어야 함)")
    if any(v != 10 for v in per_person.values()):
        problems.append("인당 10슬롯이 아닌 사람이 있음")
    if meta.get("status") != "success":
        problems.append(f"meta.json status={meta.get('status')}")
    if problems:
        r.fail("페르소나 검증", "; ".join(problems), "페르소나 파일이 바뀌었습니다. git checkout -- results/memo_personas/personas_100 으로 되돌리세요.")
    else:
        r.ok("페르소나 검증", "100명 · 1,000슬롯 · 기업별 250")


def check_env(r: Result) -> dict:
    present = {k: bool(env_value(k)) for k in ENV_KEYS}
    if not ENV_PATH.exists() and not all(present.values()):
        r.fail(".env 파일", "레포 루트에 .env가 없음",
               "레포 루트에서 cp .env.example .env 로 만든 뒤 LLM_API_KEY, LLM_MODEL, DATABASE_URL 값을 채우세요.")
    for k, ok in present.items():
        if ok:
            r.ok(f".env {k}", "있음 (값은 표시하지 않음)")
        else:
            hint = {"LLM_API_KEY": "Gemini API 키를 LLM_API_KEY=... 한 줄로 넣으세요 (따옴표·공백 없이).",
                    "LLM_MODEL": "모델 이름을 LLM_MODEL=... 한 줄로 넣으세요. 상규가 카톡으로 알려 준 이름을 그대로 씁니다.",
                    "DATABASE_URL": "팀 DB 주소를 DATABASE_URL=postgresql+psycopg://사용자:비밀번호@localhost:포트/DB이름 형식으로 넣으세요."}[k]
            r.fail(f".env {k}", "없음", hint)
    return present


def db_fix(exc: Exception) -> str:
    msg = str(exc).lower()
    if "password" in msg or "authentication" in msg:
        return ".env DATABASE_URL의 사용자 이름·비밀번호를 확인하세요 (.env의 POSTGRES_USER·POSTGRES_PASSWORD와 같아야 함)."
    if "does not exist" in msg:
        return ".env DATABASE_URL 끝의 DB 이름을 확인하세요 (POSTGRES_DB와 같아야 함)."
    return ("DB가 켜져 있는지 확인하세요: docker compose ps (memos-db가 running이어야 함). 꺼져 있으면 docker compose up -d\n"
            "켜져 있는데도 안 되면 DATABASE_URL의 호스트(localhost)·포트(POSTGRES_PORT)를 확인하세요.")


def check_db(r: Result, cfg: dict):
    from .export_evidence import MACRO_CODES, check_schema, make_engine, q

    try:
        engine = make_engine(env_value("DATABASE_URL"))
        conn = engine.connect()
    except Exception as exc:  # noqa: BLE001
        r.fail("DB 연결", f"{type(exc).__name__} (주소·비밀번호는 표시하지 않음)", db_fix(exc))
        return
    with conn:
        ver = q(conn, "SHOW server_version")[0]["server_version"]
        r.ok("DB 연결", f"PostgreSQL {ver}, 읽기 전용으로 접속")
        missing = check_schema(conn)
        if missing:
            r.fail("필요한 테이블·컬럼", "; ".join(f"{t}: {', '.join(c)}" for t, c in missing.items()),
                   "팀 DB에 최신 마이그레이션이 적용됐는지 DB 담당자에게 확인하세요 (alembic current).")
            return
        r.ok("필요한 테이블·컬럼", "10개 테이블 확인")
        for name, symbol in company_codes(cfg).items():
            stats = {k: q(conn, sql, s=symbol)[0] for k, sql in SQL_COUNTS.items()}
            line = " · ".join(f"{k} {v['n']:,}건" + (f"({v['first']}~{v['last']})" if v["first"] else "")
                              for k, v in stats.items())
            if stats["주가"]["n"] == 0:
                r.fail(f"데이터 {name}({symbol})", line, "주가가 없으면 메모를 만들 수 없습니다. 상규에게 이 화면을 보내 주세요.")
            elif min(stats[k]["n"] for k in ("공시", "뉴스", "재무")) == 0:
                r.warn(f"데이터 {name}({symbol})", line, "비어 있는 근거 유형은 메모 생성 때 다른 유형으로 자동 조정됩니다.")
            else:
                r.ok(f"데이터 {name}({symbol})", line)
        macro = {x["indicator_code"]: x for x in q(conn, SQL_MACRO_COUNTS, codes=list(MACRO_CODES))}
        line = " · ".join(f"{ko} {macro[c]['n']:,}건(~{macro[c]['last']})" if c in macro else f"{ko} 없음"
                          for c, ko in MACRO_CODES.items())
        (r.ok if len(macro) == len(MACRO_CODES) else r.warn)("데이터 거시", line)
        conn.rollback()


def check_gemini(r: Result, cfg: dict):
    from .llm import PING_SCHEMA, APIError, BadResponse, DailyQuotaExceeded, RateLimited, make_client, parse_json

    try:
        client = make_client(cfg)
        res = client.generate('다음 JSON만 출력: {"ok": true}', PING_SCHEMA, max_output_tokens=1024)
        parse_json(res.text, PING_SCHEMA)
    except DailyQuotaExceeded as exc:
        r.fail("Gemini 테스트 호출", str(exc), "오늘 한도를 다 썼습니다. 내일 다시 preflight를 실행하세요.")
        return
    except RateLimited as exc:
        r.fail("Gemini 테스트 호출", str(exc), "1~2분 뒤 다시 실행하세요. 계속 429가 나면 상규에게 알려 주세요.")
        return
    except (APIError, BadResponse) as exc:
        r.fail("Gemini 테스트 호출", str(exc), getattr(exc, "guide", "") or "상규에게 이 화면을 보내 주세요.")
        return
    mode = " (목업 모드 — 실제 Gemini 아님)" if cfg["llm"].get("mock") else ""
    r.ok("Gemini 테스트 호출", f"모델 {res.model}{mode} · 토큰 입력 {res.usage.prompt_tokens} / 출력 {res.usage.output_tokens}"
         f" / thinking {res.usage.thinking_tokens}")


def main(argv=None) -> int:
    setup_console()
    load_env()
    r = Result()
    print("메모 생성 사전 점검\n")
    check_python(r)
    if not check_packages(r):
        print(f"\n❌ 패키지를 설치한 뒤 다시 실행하세요: {INSTALL}")
        return 1
    cfg = load_config()
    check_personas(r, cfg)
    present = check_env(r)
    if present["DATABASE_URL"]:
        check_db(r, cfg)
    else:
        r.fail("DB 연결", "DATABASE_URL이 없어 건너뜀")
    if present["LLM_API_KEY"] and present["LLM_MODEL"] or cfg["llm"].get("mock"):
        check_gemini(r, cfg)
    else:
        r.fail("Gemini 테스트 호출", "LLM_API_KEY·LLM_MODEL이 없어 건너뜀")
    print()
    if r.fails:
        print(f"❌ {r.fails}개 항목을 고친 뒤 다시 실행하세요: python -m eval.memo_personas.preflight")
        return 1
    print(("⚠️ 확인할 항목이 있지만 진행할 수 있습니다.\n" if r.warns else "✅ 모두 준비됐습니다.\n")
          + "다음 명령: python -m eval.memo_personas.export_evidence")
    return 0


if __name__ == "__main__":
    sys.exit(main())
