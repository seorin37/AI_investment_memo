"""1시간 회차(fulltext_hourly) 테스트. 네트워크·DB·모델 없이 가짜 응답·가짜 저장소로 확인한다."""
import json
from datetime import datetime
from zoneinfo import ZoneInfo

from backend.pipelines.common.file_lock import acquire_file_lock
from backend.pipelines.news import fulltext as ft
from backend.pipelines.news import fulltext_hourly as fh
from backend.pipelines.news.tests.test_fulltext import PAGE, Resp, cfg, http
from backend.pipelines.news.tests.test_fulltext_load import FakeStore

KST = ZoneInfo("Asia/Seoul")
NOW = datetime(2026, 11, 8, 10, 0, tzinfo=KST)
EMPTY = "<html><body><div id='b'> </div></body></html>"


def art(i, hour, title="삼성 HBM4 공급"):
    return ft.ArticleRow(i, "hankyung", f"https://www.hankyung.com/article/{i}", title,
                         datetime(2026, 11, 8, hour, 0, tzinfo=KST).isoformat())


class Run:
    """같은 가짜 DB(news_articles·적재 저장소)로 회차를 여러 번 돌린다."""

    def __init__(self, tmp_path, rows, routes):
        self.tmp, self.rows, self.routes = tmp_path, rows, routes
        self.store = FakeStore({r.news_id: r.url for r in rows})
        self.loaded_batches = []

    def load_fn(self, todo, store):
        ids = [r.news_id for r in todo]
        self.loaded_batches.append(ids)
        store.loaded.update(ids)
        return {"status": "loaded", "articles": len(ids), "chunks": 2 * len(ids), "bad": [], "news_ids": ids}

    def once(self, hours=6):
        get = http(dict(self.routes))
        summary = fh.run_once(
            hours, read_rows=lambda start, end, codes: [r for r in self.rows if start <= datetime.fromisoformat(
                r.published_at) < end], http_get=get, config=cfg(), store=self.store, load_fn=self.load_fn,
            raw_dir=self.tmp, codes=["hankyung"], sleep=lambda s: None, now=NOW)
        return summary, get


def test_run_once_collects_new_articles_and_loads_them(tmp_path):
    rows = [art(1, 9), art(2, 8), art(3, 9, title="[포토] 코스피"), art(4, 2)]       # 4는 6시간 밖 (02시)
    run = Run(tmp_path, rows, {})
    summary, get = run.once()
    assert summary["collect"]["rows"] == 3 and summary["collect"]["ok"] == 2 and summary["collect"]["skipped"] == 1
    assert summary["load"]["todo"] == 2 and summary["load"]["articles"] == 2 and summary["load"]["chunks"] == 4
    assert run.loaded_batches == [[1, 2]] and (tmp_path / "2026-11-08.jsonl").exists()
    assert "https://www.hankyung.com/article/4" not in get.calls
    assert summary["window"][1].startswith("2026-11-08T01:00")                        # UTC로 남긴다 (10시 KST)
    assert {"collect_seconds", "load_seconds", "total_seconds"} <= summary.keys()
    # 다음 회차: 받은 기사는 요청하지 않고, 적재된 기사는 다시 넣지 않는다
    again, get2 = run.once()
    assert again["collect"]["already"] == 3 and again["collect"]["ok"] == 0
    assert again["load"]["already"] == 2 and again["load"]["status"] == "nothing"
    assert [u for u in get2.calls if not u.endswith("robots.txt")] == [] and len(run.loaded_batches) == 1


def test_empty_body_is_retried_each_run_then_given_up(tmp_path):                 # 속보: 본문이 나중에 채워진다
    run = Run(tmp_path, [art(1, 9, title="[속보] 다우 3% 급등"), art(2, 9)],
              {"https://www.hankyung.com/article/1": Resp(200, EMPTY)})
    for _ in range(3):                                                          # fulltext_max_runs = 3
        summary, _ = run.once()
        assert summary["collect"]["failed"] == 1 and summary["collect"]["gave_up"] == 0
    summary, get = run.once()
    assert summary["collect"]["gave_up"] == 1 and "https://www.hankyung.com/article/1" not in get.calls
    # 2회차에 본문이 채워졌다면: 그 회차에 ok로 받아 적재된다
    run2 = Run(tmp_path / "b", [art(1, 9, title="[속보] 다우 3% 급등")],
               {"https://www.hankyung.com/article/1": [Resp(200, EMPTY)]})
    run2.once()
    run2.routes = {"https://www.hankyung.com/article/1": Resp(200, PAGE)}
    summary, _ = run2.once()
    assert summary["collect"]["ok"] == 1 and run2.loaded_batches == [[1]]


def test_load_retries_articles_left_unloaded(tmp_path):                         # 지난 회차에 GPU 부족으로 적재를 미룸
    run = Run(tmp_path, [art(1, 9)], {})
    busy = {"status": "gpu_busy", "gpu_free_gb": 1.2, "articles": 0, "chunks": 0, "bad": []}
    summary = fh.run_once(6, read_rows=lambda s, e, c: run.rows, http_get=http({}), config=cfg(), store=run.store,
                          load_fn=lambda todo, store: busy, raw_dir=tmp_path, codes=["hankyung"],
                          sleep=lambda s: None, now=NOW)
    assert summary["collect"]["ok"] == 1 and summary["load"]["status"] == "gpu_busy"
    summary, _ = run.once()
    assert summary["collect"]["already"] == 1 and summary["load"]["articles"] == 1 and run.loaded_batches == [[1]]


def test_tag_fn_runs_after_load_only_when_given(tmp_path):
    run = Run(tmp_path, [art(1, 9)], {})
    summary, _ = run.once()
    assert "tag" not in summary                                                     # 기본은 태그하지 않는다
    calls = []
    summary = fh.run_once(6, read_rows=lambda s, e, c: run.rows, http_get=http({}), config=cfg(), store=run.store,
                          load_fn=run.load_fn, raw_dir=tmp_path, codes=["hankyung"], sleep=lambda s: None, now=NOW,
                          tag_fn=lambda s, e: calls.append((s, e)) or {"new_links": 2})
    assert summary["tag"] == {"new_links": 2} and calls[0][1].isoformat().startswith("2026-11-08T01:00")


def test_blocked_source_is_reported(tmp_path):
    run = Run(tmp_path, [art(1, 9), art(2, 9)], {"https://www.hankyung.com/article/1": Resp(429)})
    summary, _ = run.once()
    assert summary["collect"]["blocked"] == ["hankyung"] and summary["collect"]["stopped"] == 1


def test_main_stops_on_target_mismatch_and_skips_when_locked(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@192.168.0.105:15432/memos")
    log_file = tmp_path / "hourly.log"
    common = ["--raw-dir", str(tmp_path), "--log-file", str(log_file)]
    assert fh.main(["--target", "127.0.0.1:5433", *common]) == 3 and not log_file.exists()
    lock = acquire_file_lock(tmp_path / fh.LOCK_NAME, timeout=0)                 # 이전 회차가 돌고 있다
    try:
        assert fh.main(["--target", "192.168.0.105:15432", *common]) == 0
    finally:
        lock.release()
    line = json.loads(log_file.read_text(encoding="utf-8").splitlines()[-1])
    assert line["skipped"].startswith("이전 회차")


def test_gpu_check_error_is_not_memory_shortage(tmp_path, monkeypatch):
    from backend.pipelines.news import fulltext_load as fl
    monkeypatch.setattr(fl, "gpu_free_check", lambda: (None, "nvidia-smi 실행 실패: FileNotFoundError"))
    lines = []
    result = fl.embed_and_load([], FakeStore({}), {}, None, out=lines.append)          # 모델을 올리기 전에 멈춘다
    assert result["status"] == "gpu_check_failed" and "FileNotFoundError" in result["error"]
    assert "확인 오류" in lines[0]
    run = Run(tmp_path, [art(1, 9)], {})
    summary = fh.run_once(6, read_rows=lambda s, e, c: run.rows, http_get=http({}), config=cfg(), store=run.store,
                          load_fn=lambda todo, store: result, raw_dir=tmp_path, codes=["hankyung"],
                          sleep=lambda s: None, now=NOW)
    assert summary["load"]["status"] == "gpu_check_failed" and "FileNotFoundError" in summary["load"]["error"]
    assert fh.exit_code(summary) == 5                                                  # 오류로 끝낸다 (gpu_busy는 0)
    busy = {**summary, "load": {**summary["load"], "status": "gpu_busy"}}
    assert fh.exit_code(busy) == 0


def test_gpu_free_check_reports_missing_nvidia_smi(monkeypatch):
    from backend.pipelines.news import fulltext_bench as fb

    def missing(*a, **k):
        raise FileNotFoundError("nvidia-smi")
    monkeypatch.setattr(fb.subprocess, "run", missing)
    free, error = fb.gpu_free_check()
    assert free is None and "FileNotFoundError" in error and fb.gpu_free_gb() == 0.0
