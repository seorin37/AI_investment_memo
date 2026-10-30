"""맥북 점검용 임시 Postgres — pgserver로 띄우고 레포 Alembic 마이그레이션을 적용한 뒤 가짜 행을 넣는다.

    pip install -r eval/memo_personas/requirements-dev.txt
    python -m eval.memo_personas.devtools.fake_db --dir data/_e2e/pg   # 주소만 출력하고 끝나면 정지

팀 DB와는 전혀 상관없는 로컬 임시 DB다. 서린 PC에서는 쓰지 않는다.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from ..common import REPO_ROOT
from . import fake_data

DB_NAME = "memos_fake"


def start(root: Path, db: str = DB_NAME):
    """(서버, SQLAlchemy URL). 이미 DB가 있으면 지우고 새로 만든다(임시 DB 전용)."""
    import pgserver

    root.mkdir(parents=True, exist_ok=True)
    srv = pgserver.get_server(str(root), cleanup_mode="stop")
    srv.psql(f"DROP DATABASE IF EXISTS {db};")
    srv.psql(f"CREATE DATABASE {db};")
    url = srv.get_uri(db).replace("postgresql://", "postgresql+psycopg://", 1)
    return srv, url


def migrate(url: str) -> str:
    env = dict(os.environ, ALEMBIC_DATABASE_URL=url)
    r = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=REPO_ROOT, env=env,
                       capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        raise RuntimeError("alembic upgrade head 실패:\n" + r.stderr[-2000:])
    return r.stderr


def seed(url: str, seed_value: int = 7) -> dict:
    from sqlalchemy import create_engine, text

    data = fake_data.all_rows(seed_value)
    price_rows = [dict(row, source="KRX_OPEN_API") for row in data["prices"]]
    eng = create_engine(url)
    ins = {
        "prices_daily": (
            "symbol, trade_date, open, high, low, close, volume, source",
            price_rows,
        ),
        "disclosures": ("rcept_no, symbol, title, kind, period_end, rcept_dt, source_url", data["disclosures"]),
        "disclosure_chunks": ("id, rcept_no, chunk_index, section, chunk_text", data["chunks"]),
        "news_articles": ("id, source_id, url, title, summary, published_at", data["news"]),
        "news_stocks": ("news_id, symbol", data["news_stocks"]),
        "financials": ("symbol, period_end, period_type, fs_div, revenue, operating_income, net_income, total_liabilities, "
                       "total_equity", data["financials"]),
        "financials_fin": ("symbol, period_end, period_type, net_interest_income, fee_income, loan_loss_provision, "
                           "bis_ratio", data["financials_fin"]),
        "economic_observations": ("indicator_code, observation_date, value", data["macro"]),
    }
    casts = {"kind": "CAST(:kind AS disclosure_kind)", "period_type": "CAST(:period_type AS report_period)"}
    with eng.begin() as conn:
        for table, (cols, rows) in ins.items():
            names = [c.strip() for c in cols.split(",")]
            vals = ", ".join(casts.get(c, f":{c}") for c in names)
            conn.execute(text(f"INSERT INTO {table} ({cols}) VALUES ({vals})"), rows)
    eng.dispose()
    return {t: len(r) for t, (_, r) in ins.items()}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="data/_e2e/pg")
    args = ap.parse_args(argv)
    srv, url = start(REPO_ROOT / args.dir)
    try:
        migrate(url)
        print(seed(url))
        print("임시 DB 준비 완료 (프로그램이 끝나면 서버도 멈춥니다)")
    finally:
        srv.cleanup()
    return 0


if __name__ == "__main__":
    sys.exit(main())
