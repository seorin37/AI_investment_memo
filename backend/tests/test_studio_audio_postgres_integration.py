"""AI 오디오 PostgreSQL 통합 시험: 메모·카드(가짜 자료) → collect_brief → run CLI(규칙 대본 + 가짜 음성) → 결과 파일.

    STUDIO_AUDIO_TEST_DATABASE_URL=postgresql://...@127.0.0.1:5433/memos_test STUDIO_AUDIO_TEST_ALLOW=1 \\
        python -m pytest backend/tests/test_studio_audio_postgres_integration.py
DB 이름이 _test로 끝나야 한다. 만든 행은 끝나고 지운다. LLM·Fish Audio는 부르지 않는다.
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta

import psycopg
import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.studio_audio.collect import collect_brief
from pipelines.studio_audio.seed_week import SEOUL, backdate_cards, load_seed, memo_time, pg_dsn, sa_url
from tests import studio_audio_fixtures as fx

URL = os.getenv("STUDIO_AUDIO_TEST_DATABASE_URL", "")
EMAIL = "studio-audio-it-test@example.invalid"
END = date(2026, 11, 22)
START = END - timedelta(days=6)
NOW = datetime(2026, 11, 23, 10, 0, tzinfo=SEOUL)


@pytest.fixture()
def seeded():
    if not URL or os.getenv("STUDIO_AUDIO_TEST_ALLOW") != "1":
        pytest.skip("explicit isolated PostgreSQL test database was not provided")
    if not (make_url(sa_url(URL)).database or "").endswith("_test"):
        pytest.fail("refusing to use a database whose name does not end with _test")
    conn = psycopg.connect(pg_dsn(URL))
    old = conn.execute("SELECT id FROM users WHERE email = %s", (EMAIL,)).fetchone()
    if old:
        conn.execute("DELETE FROM memos WHERE user_id = %s", (old[0],))
        conn.execute("DELETE FROM user_stocks WHERE user_id = %s", (old[0],))
        conn.execute("DELETE FROM users WHERE id = %s", (old[0],))
    uid = conn.execute("INSERT INTO users (email, display_name) VALUES (%s, 'audio it test') RETURNING id", (EMAIL,)).fetchone()[0]
    seed = load_seed()
    for sym, hold in seed["stocks"].items():
        conn.execute("INSERT INTO user_stocks (user_id, symbol, status) VALUES (%s, %s, %s)",
                     (uid, sym, "holding" if hold == "보유" else "watching"))
    created = {"user_id": uid, "period": {"start": START.isoformat(), "end": END.isoformat()}, "memos": {}, "memo_ids": []}
    for m in seed["memos"]:
        at = memo_time(START, m["day"])
        mid = conn.execute("""INSERT INTO memos (user_id, symbol, kind, title, content, ai_linked, ai_linked_at, created_at, updated_at)
            VALUES (%s, %s, 'note', %s, %s, true, %s, %s, %s) RETURNING id""",
                           (uid, m["symbol"], m["title"], m["body"], at, at, at)).fetchone()[0]
        created["memos"][m["key"]] = {"id": mid, "symbol": m["symbol"], "at": at}
        created["memo_ids"].append(mid)
    ids = fx.insert(conn, created)
    conn.commit()
    yield conn, created, ids
    fx.remove(conn, ids)
    conn.execute("DELETE FROM memos WHERE user_id = %s", (uid,))
    conn.execute("DELETE FROM user_stocks WHERE user_id = %s", (uid,))
    conn.execute("DELETE FROM market_indices WHERE code IN ('KOSPI', 'KOSDAQ') AND trade_date BETWEEN %s AND %s", (START, END))
    conn.execute("DELETE FROM economic_observations WHERE indicator_code = 'USD_KRW' AND observation_date BETWEEN %s AND %s",
                 (START, END))
    conn.execute("DELETE FROM users WHERE id = %s", (uid,))
    conn.commit()
    conn.close()


def test_backdate_then_collect_and_run(seeded, tmp_path):
    conn, created, ids = seeded
    memo_at = {v["id"]: v["at"] for v in created["memos"].values()}
    rows = backdate_cards(conn, created["memo_ids"], memo_at, NOW)
    conn.commit()
    assert len(rows) == len(fx.CARDS)
    for r in rows:                                           # 근거 다음 날 06:30, 메모를 쓴 뒤
        at = datetime.fromisoformat(r["created_at"])
        assert at.hour == 6 and at.minute == 30 and at > memo_at[r["memo_id"]]

    engine = create_engine(sa_url(URL))
    with Session(engine) as db:
        brief = collect_brief(db, created["user_id"], START, END, now=NOW)
    engine.dispose()
    names = [s.name for s in brief.stocks]
    assert names[-1] == "NAVER" and not brief.stocks[-1].cards          # 새 소식 없는 종목은 맨 뒤
    assert [c.uid for s in brief.stocks for c in s.cards] == [f"U{i}" for i in range(1, len(fx.CARDS) + 1)]
    hynix = brief.stock("000660")
    assert hynix.hold == "보유" and [c.kind for c in hynix.cards] == ["공시", "뉴스", "뉴스"]
    assert [c.data_date for c in hynix.cards] == sorted(c.data_date for c in hynix.cards)
    assert hynix.price.last_close == 180500 and hynix.price.change_pct == pytest.approx(6.18)
    assert [m.label for m in brief.market] == ["코스피", "코스닥", "원/달러 환율"]
    assert hynix.memos[0].title in {"HBM 수요 계속 확인", "환율 영향?"}

    from pipelines.studio_audio.run import main
    os.environ["TEST_DATABASE_URL"] = URL
    code = main(["--user-id", str(created["user_id"]), "--end", END.isoformat(), "--test-db", "--llm", "none",
                 "--tts", "fake", "--out-dir", str(tmp_path)])
    assert code == 0
    run = next(tmp_path.glob("run_*"))
    content = json.loads((run / "episode.json").read_text(encoding="utf-8"))
    assert content["source"] == "rules" and content["dur"] > 60 and len(content["sources"]) == len(fx.CARDS)
    assert (run / "player.html").exists() and ((run / "episode.mp3").exists() or (run / "episode.wav").exists())
    assert json.loads((run / "meta.json").read_text(encoding="utf-8")).get("fallback_warnings") is None
