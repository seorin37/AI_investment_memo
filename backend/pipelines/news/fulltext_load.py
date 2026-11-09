"""뉴스 원문 적재: data/news_raw/<날짜>.jsonl(status ok) → news_article_bodies + news_chunks (0015).

  # 기본은 dry-run: DB는 읽기만 하고 넣을 건수·예상 청크 수만 출력한다 (모델 없이 토크나이저만 올린다)
  python -m backend.pipelines.news.fulltext_load --date 2026-11-05
  # 실제 적재: --load와 함께 접속 대상(host:port)을 --target으로 적어야 한다. 다르면 쓰지 않고 멈춘다
  python -m backend.pipelines.news.fulltext_load --date 2026-11-05 --limit 50 --load --target 192.168.0.105:15432
  # 날짜 대신 최근 N시간 발행분 (그 발행일 파일만 읽고, 아직 DB에 없는 ok 기사만 넣는다)
  python -m backend.pipelines.news.fulltext_load --recent-hours 6 --load --target 192.168.0.105:15432

- news_id는 jsonl 값(= news_articles.id)을 쓴다. DB에 그 id가 없거나 URL이 다르면(다른 DB) 건너뛰고 센다.
- 여러 번 돌려도 안전하다: news_article_bodies에 이미 있는 news_id는 건너뛴다. 기사 묶음마다 본문과 그 청크를
  한 트랜잭션으로 넣어 본문만 있고 청크가 없는 기사가 생기지 않는다. ON CONFLICT DO NOTHING도 건다.
- 청크: fulltext_bench.chunk_article (embed_text 기준 목표 400 / 겹침 80 / 최대 512 토큰).
- 임베딩: disclosures.embedder.M3Encoder (dense + sparse, colbert는 만들지도 저장하지도 않는다).
  embedding_model / embedding_revision / embedding_config_hash는 disclosures와 같은 규칙
  (config_hash = sha256({name, revision, max_length})). max_length는 청크 최대 512라 공시(1024)와 해시가 다르다.
- GPU: 시작 전 남은 메모리(--min-free-gb)를 보고, 이 프로세스 사용량에 상한(--gpu-cap-gb)을 건다 (fulltext_bench와 같음).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Protocol
from urllib.parse import urlsplit

from .fulltext import OUT_DIR, recent_window, window_days
from .fulltext_bench import CHUNKER_VERSION, Article, Chunk, chunk_article, gpu_free_check, gpu_processes

log = logging.getLogger(__name__)

TARGET, OVERLAP, MAX_TOKENS = 400, 80, 512
CHUNKER_ID = f"{CHUNKER_VERSION}:{TARGET}/{OVERLAP}/{MAX_TOKENS}"

BODY_SQL = """INSERT INTO news_article_bodies
  (news_id, source_code, fetch_method, subtitle, body, body_hash, extractor_version, fetched_at)
  VALUES (%s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (news_id) DO NOTHING"""
CHUNK_SQL = """INSERT INTO news_chunks
  (news_id, chunk_index, chunk_text, embed_text, char_start, char_end, token_count, chunker_version,
   dense_embedding, sparse_embedding, embedding_model, embedding_revision, embedding_config_hash, embedded_at)
  VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::vector, %s::jsonb, %s, %s, %s, %s)
  ON CONFLICT (news_id, chunk_index) DO NOTHING"""


@dataclass
class Record:
    news_id: int
    url: str
    source_code: str
    fetch_method: str
    title: str
    published_at: str
    subtitle: str | None
    body: str
    body_hash: str
    extractor_version: str
    fetched_at: str


@dataclass(frozen=True)
class Identity:
    model: str
    revision: str
    config_hash: str


def embedding_identity(model_cfg: dict) -> Identity:
    """disclosures.run_events.embedding_identity와 같은 규칙."""
    keys = {key: model_cfg.get(key) for key in ("name", "revision", "max_length")}
    digest = hashlib.sha256(json.dumps(keys, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return Identity(str(model_cfg["name"]), str(model_cfg["revision"]), digest)


def read_ok_records(paths: Iterable[Path]) -> list[Record]:
    """status ok 행만. 같은 news_id가 여러 번 있으면(실패 뒤 재시도 성공 등) 마지막 ok 행을 쓴다."""
    latest: dict[int, Record] = {}
    for path in paths:
        for line in path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            if row.get("status") != "ok" or not row.get("body"):
                continue
            latest[int(row["news_id"])] = Record(
                int(row["news_id"]), row["url"], row["source_code"], row.get("fetch_method") or "link",
                row.get("title") or "", row.get("published_at") or "", row.get("subtitle"), row["body"],
                row["body_hash"], row["extractor_version"], row["fetched_at"])
    return sorted(latest.values(), key=lambda r: r.news_id)


def recent_records(raw_dir: Path, start: datetime, end: datetime) -> list[Record]:
    """[start, end) 발행분의 ok 행. 그 기간의 발행일 파일만 읽는다."""
    paths = [raw_dir / f"{d.isoformat()}.jsonl" for d in window_days(start, end)]
    records = read_ok_records(p for p in paths if p.is_file())
    return [r for r in records if r.published_at and start <= datetime.fromisoformat(r.published_at) < end]


class Store(Protocol):
    def article_urls(self, ids: list[int]) -> dict[int, str]: ...
    def loaded_ids(self, ids: list[int]) -> set[int]: ...
    def write(self, bodies: list[tuple], chunks: list[tuple]) -> None: ...


@dataclass
class Plan:
    todo: list[Record] = field(default_factory=list)
    already: int = 0
    missing: list[int] = field(default_factory=list)          # news_articles에 없는 id
    url_mismatch: list[int] = field(default_factory=list)     # id는 있는데 URL이 다름 (다른 DB)


def plan(records: list[Record], store: Store, limit: int | None = None) -> Plan:
    ids = [r.news_id for r in records]
    urls, loaded = store.article_urls(ids), store.loaded_ids(ids)
    out = Plan()
    for r in records:
        if r.news_id in loaded:
            out.already += 1
        elif r.news_id not in urls:
            out.missing.append(r.news_id)
        elif urls[r.news_id] != r.url:
            out.url_mismatch.append(r.news_id)
        elif limit is None or len(out.todo) < limit:
            out.todo.append(r)
    return out


def to_article(r: Record) -> Article:
    return Article(str(r.news_id), r.source_code, r.title, r.published_at[:10], r.subtitle, r.body)


def chunk_records(records: list[Record], tokens) -> tuple[list[tuple[Record, list[Chunk]]], list[int]]:
    """(기사, 청크) 목록과 청크 규칙(토큰 1~512, char_end > char_start)을 어긴 기사 id. 어긴 기사는 넣지 않는다."""
    good, bad = [], []
    for r in records:
        chunks = chunk_article(to_article(r), tokens, TARGET, OVERLAP, MAX_TOKENS)
        if chunks and all(1 <= c.token_count <= MAX_TOKENS and c.char_end > c.char_start for c in chunks):
            good.append((r, chunks))
        else:
            bad.append(r.news_id)
    return good, bad


def vector_literal(vector) -> str:
    from ..disclosures.search import vector_literal as literal

    return literal(vector)


def rows_for(record: Record, chunks: list[Chunk], encoded: list, ident: Identity, embedded_at: datetime):
    body = (record.news_id, record.source_code, record.fetch_method, record.subtitle, record.body,
            record.body_hash, record.extractor_version, record.fetched_at)
    rows = [(record.news_id, c.chunk_index, c.chunk_text, c.embed_text, c.char_start, c.char_end, c.token_count,
             CHUNKER_ID, vector_literal(e.dense), json.dumps(e.sparse, separators=(",", ":"), sort_keys=True),
             ident.model, ident.revision, ident.config_hash, embedded_at) for c, e in zip(chunks, encoded)]
    return body, rows


@dataclass
class LoadReport:
    articles: int = 0
    chunks: int = 0
    seconds: float = 0.0
    oom_events: int = 0
    batch_size: int = 0


def load(items: list[tuple[Record, list[Chunk]]], encode: Callable[[list[str]], list], store: Store,
         ident: Identity, group_size: int = 32, clock=time.perf_counter,
         now: Callable[[], datetime] = lambda: datetime.now(timezone.utc)) -> LoadReport:
    """기사 group_size개씩: 청크를 임베딩하고 본문+청크를 한 번에(한 트랜잭션) 쓴다."""
    from ..disclosures.embedder import check_dense, check_sparse
    import numpy as np

    report, started = LoadReport(), clock()
    for start in range(0, len(items), group_size):
        group = items[start:start + group_size]
        texts = [c.embed_text for _, chunks in group for c in chunks]
        encoded = encode(texts)
        check_dense(np.stack([e.dense for e in encoded]))
        check_sparse([e.sparse for e in encoded])
        embedded_at, bodies, chunk_rows, pos = now(), [], [], 0
        for record, chunks in group:
            body, rows = rows_for(record, chunks, encoded[pos:pos + len(chunks)], ident, embedded_at)
            pos += len(chunks)
            bodies.append(body)
            chunk_rows.extend(rows)
        store.write(bodies, chunk_rows)
        report.articles += len(group)
        report.chunks += len(chunk_rows)
        log.info("적재 %d/%d기사 (청크 %d)", report.articles, len(items), report.chunks)
    report.seconds = clock() - started
    return report


class PgStore:
    """psycopg 저장소. dry-run이면 세션을 읽기 전용으로 열어 쓰기를 DB가 거부하게 한다."""

    def __init__(self, dsn: str, read_only: bool):
        import psycopg

        self.conn = psycopg.connect(dsn)
        self.conn.read_only = read_only

    def article_urls(self, ids):
        with self.conn.cursor() as cur:
            cur.execute("SELECT id, url FROM news_articles WHERE id = ANY(%s)", (ids,))
            out = dict(cur.fetchall())
        self.conn.rollback()
        return out

    def loaded_ids(self, ids):
        with self.conn.cursor() as cur:
            cur.execute("SELECT news_id FROM news_article_bodies WHERE news_id = ANY(%s)", (ids,))
            out = {r[0] for r in cur.fetchall()}
        self.conn.rollback()
        return out

    def write(self, bodies, chunks):
        with self.conn.transaction(), self.conn.cursor() as cur:
            cur.executemany(BODY_SQL, bodies)
            cur.executemany(CHUNK_SQL, chunks)

    def counts(self, ids):
        with self.conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM news_article_bodies WHERE news_id = ANY(%s)", (ids,))
            bodies = cur.fetchone()[0]
            cur.execute("SELECT count(*), count(*) FILTER (WHERE dense_embedding IS NULL), max(token_count) "
                        "FROM news_chunks WHERE news_id = ANY(%s)", (ids,))
            chunks, no_dense, max_tokens = cur.fetchone()
        self.conn.rollback()
        return {"bodies": bodies, "chunks": chunks, "chunks_without_dense": no_dense, "max_token_count": max_tokens}


def dsn_target(dsn: str) -> str:
    """host:port/db (비밀번호·사용자 제외). key=value 형식 DSN도 처리한다."""
    if "://" in dsn:
        u = urlsplit(dsn)
        return f"{u.hostname}:{u.port or 5432}/{u.path.lstrip('/')}"
    from psycopg.conninfo import conninfo_to_dict

    d = conninfo_to_dict(dsn)
    return f"{d.get('host', 'localhost')}:{d.get('port', 5432)}/{d.get('dbname', '')}"


def model_config(device: str, batch_size: int) -> dict:
    from ..common.config import load_config as load_common

    cfg = dict(load_common("configs/common.yaml")["model"])
    cfg.update(batch_size=batch_size, max_length=MAX_TOKENS, devices=["cuda:0"] if device == "cuda" else ["cpu"])
    return cfg


def embed_and_load(todo: list[Record], store: Store, model_cfg: dict, ident: Identity, *, device: str = "cuda",
                   batch_size: int = 4, group_size: int = 32, gpu_cap_gb: float = 2.5, min_free_gb: float = 2.8,
                   out: Callable[[str], None] = print) -> dict:
    """GPU 여유 확인 → 모델 → 청크 → 임베딩 → 적재. 결과 요약을 돌려준다.
    status: loaded / gpu_busy(남은 메모리 부족) / gpu_check_failed(확인 자체가 실패, error에 이유)."""
    if device == "cpu":
        os.environ["CUDA_VISIBLE_DEVICES"] = ""
    else:
        free_gb, error = gpu_free_check()
        if free_gb is None:
            out(f"GPU 확인 실패: {error} — 메모리 부족이 아니라 확인 오류라 적재하지 않습니다.")
            return {"status": "gpu_check_failed", "error": error, "articles": 0, "chunks": 0, "bad": []}
        out(f"GPU 사용 현황: {gpu_processes()} / 남은 메모리 {free_gb:.2f}GB (필요 {min_free_gb}GB)")
        if free_gb < min_free_gb:
            out("남은 GPU 메모리가 부족해 시작하지 않습니다.")
            return {"status": "gpu_busy", "gpu_free_gb": round(free_gb, 2), "articles": 0, "chunks": 0, "bad": []}
        import torch
        total_gb = torch.cuda.get_device_properties(0).total_memory / 2**30
        torch.cuda.set_per_process_memory_fraction(min(1.0, gpu_cap_gb / total_gb), 0)

    from ..disclosures.chunker import HFTokenCounter
    from ..disclosures.embedder import BatchRunner, load_encoder

    encoder, info = load_encoder(model_cfg, offline=True, allow_cpu=device == "cpu")
    tokens = HFTokenCounter(encoder.tokenizer)
    items, bad = chunk_records(todo, tokens)
    if bad:
        out(f"청크 규칙 위반 기사 {len(bad)}건은 넣지 않습니다: {bad[:10]}")
    runner = BatchRunner(lambda batch: encoder._forward(batch, encoder.max_length, sparse=True), batch_size)
    report = load(items, lambda texts: runner.run(texts, encoder.token_lengths(texts)), store, ident, group_size)
    report.oom_events, report.batch_size = runner.oom_events, runner.batch_size
    peak = 0
    if encoder.device.startswith("cuda"):
        import torch
        peak = round(torch.cuda.max_memory_allocated(encoder.device) / 2**20)
    out(f"적재: 기사 {report.articles}, 청크 {report.chunks}, {report.seconds / 60:.1f}분, "
        f"{info['device']} {info['dtype']}, 배치 {batch_size}→{report.batch_size}, OOM {report.oom_events}, "
        f"최대 GPU {peak}MB")
    return {"status": "loaded", "articles": report.articles, "chunks": report.chunks, "bad": bad,
            "seconds": round(report.seconds, 1), "oom": report.oom_events, "gpu_peak_mb": peak,
            "news_ids": [r.news_id for r, _ in items]}


def main(argv=None) -> int:
    from ..common.db import get_dsn, load_env

    ap = argparse.ArgumentParser(description="뉴스 원문 jsonl → news_article_bodies·news_chunks (기본 dry-run)")
    when = ap.add_mutually_exclusive_group(required=True)
    when.add_argument("--date", help="data/news_raw/<날짜>.jsonl 의 날짜 YYYY-MM-DD")
    when.add_argument("--recent-hours", type=float, help="날짜 대신 최근 N시간 발행분 (그 발행일 파일들에서)")
    ap.add_argument("--raw-dir", type=Path, default=OUT_DIR)
    ap.add_argument("--limit", type=int, help="이번에 넣을 최대 기사 수 (시험용)")
    ap.add_argument("--load", action="store_true", help="실제로 DB에 쓴다 (없으면 dry-run)")
    ap.add_argument("--target", help="--load일 때 필수: 접속 대상 host:port. 실제 대상과 다르면 멈춘다")
    ap.add_argument("--device", choices=["cpu", "cuda"], default="cuda")
    ap.add_argument("--batch-size", type=int, default=4, help="시작 배치 크기 (OOM이면 절반씩 줄인다)")
    ap.add_argument("--group-size", type=int, default=32, help="이 기사 수마다 한 트랜잭션으로 쓴다")
    ap.add_argument("--gpu-cap-gb", type=float, default=2.5, help="--device cuda: 이 프로세스 GPU 메모리 상한")
    ap.add_argument("--min-free-gb", type=float, default=2.8, help="--device cuda: 남은 GPU 메모리가 이보다 적으면 시작 안 함")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    load_env()
    dsn = get_dsn()
    if not dsn:
        print("DATABASE_URL이 없습니다.")
        return 1
    target = dsn_target(dsn)
    print(f"접속 대상: {target}  ({'적재' if args.load else 'dry-run: DB 읽기만'})")
    if args.load and (not args.target or not target.startswith(args.target + "/")):
        print(f"--target({args.target})이 실제 접속 대상({target})과 달라 쓰지 않고 멈춥니다.")
        return 3
    if args.recent_hours:
        start, end = recent_window(args.recent_hours)
        source = f"{args.raw_dir}/{{{','.join(d.isoformat() for d in window_days(start, end))}}}.jsonl " \
                 f"(최근 {args.recent_hours:g}시간)"
        records = recent_records(args.raw_dir, start, end)
    else:
        path = args.raw_dir / f"{args.date}.jsonl"
        if not path.is_file():
            print(f"{path}가 없습니다.")
            return 1
        source, records = str(path), read_ok_records([path])

    model_cfg = model_config(args.device, args.batch_size)
    ident = embedding_identity(model_cfg)
    store = PgStore(dsn, read_only=not args.load)
    p = plan(records, store, args.limit)
    print(f"{source}: ok {len(records)}건 → 이미 적재 {p.already}, news_articles에 없음 {len(p.missing)}, "
          f"URL 불일치 {len(p.url_mismatch)}, 이번 대상 {len(p.todo)}" + (f" (--limit {args.limit})" if args.limit else ""))
    if p.missing:
        print(f"  없는 id 예: {p.missing[:10]}")
    if p.url_mismatch:
        print(f"  URL 불일치 id 예: {p.url_mismatch[:10]}  (다른 DB의 id일 수 있음)")
    dup = Counter(r.body_hash for r in p.todo)
    print(f"  같은 본문(body_hash) 중복: {sum(n - 1 for n in dup.values() if n > 1)}건 (그대로 넣는다)")
    print(f"  임베딩 식별: model={ident.model} revision={ident.revision[:12]} config_hash={ident.config_hash[:12]} "
          f"chunker={CHUNKER_ID}")
    if not p.todo:
        print("넣을 기사가 없습니다.")
        return 0

    if not args.load:
        from ..disclosures.chunker import HFTokenCounter
        from ..disclosures.embedder import load_tokenizer, resolve_model_path, set_offline

        set_offline(True)
        tokens = HFTokenCounter(load_tokenizer(resolve_model_path(model_cfg["name"], model_cfg["revision"], True)))
        items, bad = chunk_records(p.todo, tokens)
        n = sum(len(c) for _, c in items)
        print(f"  예상 청크 {n}개 (기사당 {n / max(1, len(items)):.2f}), 청크 규칙 위반 기사 {len(bad)}건 {bad[:10]}")
        print("dry-run이라 DB에 쓰지 않았습니다. 적재하려면 --load --target host:port 를 붙이세요.")
        return 0

    result = embed_and_load(p.todo, store, model_cfg, ident, device=args.device, batch_size=args.batch_size,
                            group_size=args.group_size, gpu_cap_gb=args.gpu_cap_gb, min_free_gb=args.min_free_gb)
    if result["status"] == "gpu_busy":
        return 2
    if result["status"] == "gpu_check_failed":
        return 5
    print(f"DB 확인 ({target}): {store.counts(result['news_ids'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
