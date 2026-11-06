"""뉴스 원문 수집 (1단계). RSS 수집분(news_articles)을 읽기만 해서 원문을 받고, 정제한 본문을 파일에 쓴다.

  python -m backend.pipelines.news.fulltext --dry-run              # 대상 건수만 (DB 읽기만, 요청 없음)
  python -m backend.pipelines.news.fulltext                        # 어제(KST) 발행분
  python -m backend.pipelines.news.fulltext --date 2026-11-05 --limit 20 --sources mk,yonhap

- DB에는 쓰지 않는다 (읽기 전용 접속 + read_only 세션, SELECT만). 결과는 data/news_raw/<발행일>.jsonl.
- 매체별 설정은 lead_sources.yaml 그대로다 (선택자·drop·유료/모음/포토 제외·본문 최소 글자 수·URL 패턴).
  fulltext_enabled: false인 매체, selector가 없는 매체는 원문을 요청하지 않는다.
- 요청 규칙은 리드 보충(lead_fetcher)과 같다: 수집기 User-Agent, robots.txt, 같은 호스트 사이 request_interval_seconds,
  타임아웃 REQUEST_TIMEOUT. 매체마다 스레드 하나로 동시에 돌린다 (같은 호스트에는 한 번에 하나).
- 재시도: 타임아웃·연결 오류·5xx는 같은 실행 안에서 max_attempts회까지 (간격을 늘려 가며). 403·429를 받으면
  그 매체는 이번 실행에서 멈춘다.
- 이미 받은 기사는 건너뛴다: data/news_raw/*.jsonl에 status ok/skipped로 남은 URL(정규화 기준). failed는 다음 실행에서
  max_attempts까지 다시 시도한다.
- 한 줄 = 기사 1건. 필드는 나중에 0015 news_article_bodies로 옮길 수 있게 맞춘다 (news_id, source_code, fetch_method,
  subtitle, body, body_hash, extractor_version, fetched_at) + 수집 기록(status, reason, http_status, attempts).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Iterable
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from . import lead_fetcher as lf
from .rss import normalize_url

log = logging.getLogger("fulltext")

KST = ZoneInfo("Asia/Seoul")
OUT_DIR = Path("data/news_raw")
FETCH_METHOD = "link"
DONE = ("ok", "skipped")          # 다시 받지 않는 상태

ARTICLES_SQL = """
SELECT a.id, s.code, a.url, a.title, a.published_at
FROM news_articles a JOIN news_sources s ON s.id = a.source_id
WHERE a.published_at >= %(start)s AND a.published_at < %(end)s AND s.code = ANY(%(codes)s)
ORDER BY a.published_at, a.id
"""


@dataclass(frozen=True)
class ArticleRow:
    news_id: int
    source_code: str
    url: str
    title: str
    published_at: str          # ISO 8601


@dataclass
class BodyRecord:
    news_id: int
    url: str
    source_code: str
    fetch_method: str
    title: str
    published_at: str
    status: str                # ok / skipped / failed
    reason: str | None = None  # skipped·failed 이유 (유료·포토·모음·본문 짧음·robots·HTTP …)
    subtitle: str | None = None
    body: str | None = None
    body_chars: int = 0
    body_hash: str | None = None
    extractor_version: str = ""
    http_status: int | None = None
    attempts: int = 0
    fetched_at: str = ""


def extractor_version(src: lf.SourceConfig) -> str:
    """본문 추출에 영향을 주는 설정의 해시 (설정이 바뀌면 다시 뽑을 대상을 알 수 있게)."""
    keys = ("selector", "drop_selectors", "paywall_selectors", "paywall_text", "skip_paywalled", "drop_text_patterns",
            "skip_section_patterns", "skip_title_patterns", "url_patterns", "subtitle_selector", "domains")
    payload = json.dumps({k: getattr(src, k) for k in keys}, ensure_ascii=False, sort_keys=True)
    return f"{src.code}-{hashlib.sha256(payload.encode()).hexdigest()[:12]}"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_done(out_dir: Path) -> dict[str, tuple[str, int]]:
    """이미 남긴 기록: 정규화 URL → (마지막 status, 지금까지 시도 횟수 합)."""
    done: dict[str, tuple[str, int]] = {}
    for path in sorted(out_dir.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            key = normalize_url(row["url"])
            attempts = done.get(key, ("", 0))[1] + int(row.get("attempts") or 0)
            done[key] = (row["status"], attempts)
    return done


def fetch_one(row: ArticleRow, src: lf.SourceConfig, config: lf.LeadConfig, http_get: lf.HttpGet,
              robots: lf.RobotsCache, throttle: lf.Throttle, version: str, prior_attempts: int = 0,
              sleep: Callable[[float], None] = time.sleep, now: Callable[[], datetime] = lambda: datetime.now(KST)
              ) -> BodyRecord:
    """기사 1건. 요청하지 않고 끝낼 수 있는 것(URL·제목 규칙, robots)은 먼저 거른다."""
    rec = BodyRecord(row.news_id, row.url, row.source_code, FETCH_METHOD, row.title, row.published_at, "skipped",
                     extractor_version=version)

    def done(status: str, reason: str | None = None, **fields) -> BodyRecord:
        rec.status, rec.reason, rec.fetched_at = status, reason, now().isoformat(timespec="seconds")
        for key, value in fields.items():
            setattr(rec, key, value)
        return rec

    if not lf._url_accepted(row.url, src):
        return done("skipped", "URL 패턴·도메인 제외 (사진 기사·다른 서브도메인)")
    reason = lf.title_skip_reason(row.title, src)
    if reason:
        return done("skipped", reason)
    allowed = robots.allowed(row.url)
    if allowed is None:
        return done("failed", "robots.txt 확인 실패", attempts=1)
    if not allowed:
        return done("skipped", f"robots.txt 불허: {urlsplit(row.url).path}")

    host = urlsplit(row.url).netloc.lower()
    resp, error = None, None
    attempts = 0
    for attempt in range(1, max(1, config.max_attempts - prior_attempts) + 1):
        attempts = attempt
        throttle.wait(host)
        try:
            resp = http_get(row.url)
        except Exception as exc:                      # 타임아웃·연결 오류: 간격을 늘려 다시
            resp, error = None, f"요청 실패: {type(exc).__name__}"
        else:
            if resp.status_code in lf.STOP_STATUSES or resp.status_code < 500:
                break
            error = f"HTTP {resp.status_code}"
        if attempt < config.max_attempts - prior_attempts:
            sleep(config.interval * attempt)
    if resp is None or resp.status_code >= 500:
        return done("failed", error, http_status=getattr(resp, "status_code", None), attempts=attempts)
    code = resp.status_code
    if code in lf.STOP_STATUSES:
        return done("failed", f"HTTP {code} (이 매체 이번 실행 중단)", http_status=code, attempts=attempts)
    if code != 200:
        return done("skipped", f"HTTP {code}", http_status=code, attempts=attempts)
    html = resp.text
    if not (lf.source_body_text(html, src) or ""):
        # 속보는 본문이 나중에 채워진다 (2026-11-06 매경 [속보] 0자). skipped로 끝내지 않고 다음 실행에서 다시 받는다
        return done("failed", "본문 비어 있음 (속보 등, 다음 실행에서 다시)", http_status=code, attempts=attempts)
    reason = lf.page_skip_reason(html, src) or lf.short_body_reason(html, src, config.min_body_chars)
    if reason:
        return done("skipped", reason, http_status=code, attempts=attempts)
    body = lf.source_body_text(html, src)
    if not body or len(body) < max(config.min_chars, config.min_body_chars):
        return done("failed", "본문 추출 실패 (선택자 확인 필요)", http_status=code, attempts=attempts)
    return done("ok", None, subtitle=lf.extract_subtitle(html, src.subtitle_selector), body=body, body_chars=len(body),
                body_hash=sha256_text(body), http_status=code, attempts=attempts)


def collect(rows: Iterable[ArticleRow], config: lf.LeadConfig, http_get: lf.HttpGet, out_dir: Path,
            done: dict[str, tuple[str, int]] | None = None, sleep=time.sleep, clock=time.monotonic,
            workers: int = 4) -> dict[str, Counter]:
    """매체별로 받아 data/news_raw/<발행일 KST>.jsonl에 덧붙인다. 매체별 집계를 돌려준다."""
    done = done if done is not None else load_done(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    lock = threading.Lock()
    by_source: dict[str, list[ArticleRow]] = {}
    stats: dict[str, Counter] = {}
    for row in rows:
        stat = stats.setdefault(row.source_code, Counter())
        key = normalize_url(row.url)
        status, prior = done.get(key, ("", 0))
        if status in DONE:
            stat["already"] += 1
            continue
        if status == "queued":                            # 이번 목록 안에서 같은 링크(정규화 기준)가 또 나옴
            stat["dup_link"] += 1
            continue
        if status == "failed" and prior >= config.max_attempts:
            stat["gave_up"] += 1
            continue
        done[key] = ("queued", prior)                     # 같은 실행 안의 같은 링크 중복 제거
        by_source.setdefault(row.source_code, []).append(row)

    def write(rec: BodyRecord) -> None:
        day = datetime.fromisoformat(rec.published_at).astimezone(KST).date().isoformat()
        with lock, (out_dir / f"{day}.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(rec), ensure_ascii=False) + "\n")

    def run_source(code: str) -> None:
        src, stat = config.sources.get(code), stats[code]
        items = by_source.get(code, [])
        if src is None or not src.can_probe or not src.selector:
            stat["not_ready"] += len(items)
            log.warning("%s: 원문 수집이 꺼져 있거나 selector가 없어 건너뜁니다 (%d건)", code, len(items))
            return
        throttle = lf.Throttle(config.interval, sleep, clock)
        robots = lf.RobotsCache(http_get, config.user_agent, throttle)
        version = extractor_version(src)
        for i, row in enumerate(items, 1):
            rec = fetch_one(row, src, config, http_get, robots, throttle, version,
                            done.get(normalize_url(row.url), ("", 0))[1], sleep)
            write(rec)
            stat[rec.status] += 1
            if rec.status == "ok":
                stat["body_chars"] += rec.body_chars
            elif rec.reason:
                stat["reason:" + rec.reason.split(" (")[0].split(":")[0]] += 1
            if i % 100 == 0:
                log.info("%s %d/%d (ok %d)", code, i, len(items), stat["ok"])
            if rec.http_status in lf.STOP_STATUSES:
                stat["stopped"] += len(items) - i
                log.warning("%s: HTTP %s를 받아 이번 실행에서 멈춥니다 (남은 %d건)", code, rec.http_status, len(items) - i)
                break

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        list(pool.map(run_source, list(by_source)))
    return stats


def day_window(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, datetime.min.time(), tzinfo=KST)
    return start.astimezone(timezone.utc), (start + timedelta(days=1)).astimezone(timezone.utc)


def read_rows(dsn: str, start: datetime, end: datetime, codes: list[str], limit: int | None) -> list[ArticleRow]:
    """news_articles를 읽기만 한다 (read_only 세션). limit은 매체당 건수."""
    import psycopg

    with psycopg.connect(dsn) as conn:
        conn.read_only = True                      # 쓰기를 시도하면 DB가 거부한다
        with conn.cursor() as cur:
            cur.execute(ARTICLES_SQL, {"start": start, "end": end, "codes": codes})
            fetched = cur.fetchall()
    rows, per = [], Counter()
    for news_id, code, url, title, published in fetched:
        if limit and per[code] >= limit:
            continue
        per[code] += 1
        rows.append(ArticleRow(news_id, code, url, title, published.isoformat()))
    return rows


def report(stats: dict[str, Counter]) -> str:
    lines = ["매체      대상  이미받음  성공  제외  실패  미준비  평균본문  제외·실패 이유"]
    for code, s in sorted(stats.items()):
        target = sum(s[k] for k in ("ok", "skipped", "failed", "not_ready", "stopped"))
        avg = round(s["body_chars"] / s["ok"]) if s["ok"] else 0
        reasons = ", ".join(f"{k[7:]} {v}" for k, v in s.most_common() if k.startswith("reason:"))
        lines.append(f"{code:9} {target:5} {s['already']:8} {s['ok']:5} {s['skipped']:5} {s['failed']:5} "
                     f"{s['not_ready'] + s['stopped']:6} {avg:8}자  {reasons}")
    return "\n".join(lines)


def main(argv=None) -> int:
    from ..common.db import get_read_dsn, load_env

    ap = argparse.ArgumentParser(description="뉴스 원문 수집 → data/news_raw/*.jsonl (DB 읽기만)")
    ap.add_argument("--date", help="발행일 YYYY-MM-DD (KST, 기본: 어제)")
    ap.add_argument("--sources", default="sedaily,hankyung,mk,yonhap")
    ap.add_argument("--limit", type=int, help="매체당 최대 건수 (시험용)")
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    ap.add_argument("--dry-run", action="store_true", help="요청 없이 대상 건수만 출력")
    ap.add_argument("--yes", action="store_true", help="요청 전 확인 질문을 건너뜀")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    load_env()
    dsn = get_read_dsn()
    if not dsn:
        log.error("DB 접속 정보가 없습니다. .env의 READONLY_DATABASE_URL 또는 DATABASE_URL을 확인하세요.")
        return 1
    config = lf.load_config()
    day = date.fromisoformat(args.date) if args.date else datetime.now(KST).date() - timedelta(days=1)
    start, end = day_window(day)
    codes = [c.strip() for c in args.sources.split(",") if c.strip()]
    rows = read_rows(dsn, start, end, codes, args.limit)
    done = load_done(args.out)
    pending = Counter(r.source_code for r in rows if done.get(normalize_url(r.url), ("", 0))[0] not in DONE)
    per_host = max(pending.values(), default=0)
    print(f"{day} 발행분 {len(rows)}건, 새로 받을 대상 {dict(pending)} — 매체별 동시, 같은 호스트 {config.interval:g}초 간격 "
          f"(가장 많은 매체 기준 최소 약 {per_host * config.interval / 60:.0f}분). User-Agent: {config.user_agent}")
    if args.dry_run:
        return 0
    if not args.yes and input("계속할까요? [y/N] ").strip().lower() != "y":
        print("취소했습니다.")
        return 1
    started = time.monotonic()
    stats = collect(rows, config, lf._requests_get(config.user_agent), args.out, done)
    print(report(stats))
    print(f"\n{(time.monotonic() - started) / 60:.1f}분, 결과: {args.out}/{day}.jsonl — DB에는 아무것도 쓰지 않았습니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
