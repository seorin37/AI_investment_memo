"""뉴스 원문 청킹 + 로컬 BGE-M3 임베딩 속도 측정 (2단계). DB에 쓰지 않고 결과는 파일로만 남긴다.

  # CPU (수집기가 GPU를 쓰고 있어도 영향 없음)
  python -m backend.pipelines.news.fulltext_bench --device cpu
  # GPU: fp16. 시작 전에 남은 메모리를 확인하고(--min-free-gb), 이 프로세스 사용량에 상한(--gpu-cap-gb)을 건다.
  #   다른 프로세스(수집기)와 GPU를 나눠 쓸 때 OOM은 이쪽에서 나고, 배치를 절반씩 줄여 다시 시도한다
  python -m backend.pipelines.news.fulltext_bench --device cuda --batch-size 4

입력은 --probe로 받아 둔 samples/<매체>/*.html 이다 (네트워크 요청 없음). lead_sources.yaml의 매체별 설정
(선택자·drop·유료/모음/포토 제외·본문 최소 글자 수)을 그대로 적용한다.

- 청크: BGE-M3 토크나이저 기준, embed_text(헤더 포함) 목표 400 / 겹침 80 / 최대 512 토큰.
  chunk_text는 헤더 없는 본문 조각, embed_text = "[매체 날짜 | 제목]\\n부제: …\\n" + chunk_text.
  분할은 공시 청커(disclosures.chunker)의 문장 경계 분할을 재사용한다.
- 임베딩: disclosures.embedder.M3Encoder로 dense(1024)·sparse·colbert를 한 번에 만든다.
  colbert는 저장하지 않는 설계라(검색 때 상위 청크만 다시 인코딩) 결과 파일에도 남기지 않고 시간만 잰다.
- 검색 시연: 질의 몇 개로 dense+sparse 상위 K를 뽑고 그 청크만 colbert를 다시 계산해 0.4:0.2:0.4로 재정렬한다.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import subprocess
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from . import lead_fetcher as lf

NAMES = {"sedaily": "서울경제", "hankyung": "한국경제", "mk": "매일경제", "yonhap": "연합뉴스"}
WEIGHTS = {"dense": 0.4, "sparse": 0.2, "colbert": 0.4}
QUERIES = ["삼성전자 HBM 실적 전망", "코스피 급락 원인과 반대매매", "KB금융 배당과 주주환원", "SK하이닉스 메모리 가격"]
CHUNKER_VERSION = "news-1.0"


@dataclass
class Article:
    file: str
    source_code: str
    title: str
    published: str
    subtitle: str | None
    body: str


@dataclass
class Chunk:
    file: str
    source_code: str
    chunk_index: int
    chunk_text: str
    embed_text: str
    char_start: int
    char_end: int
    token_count: int


def _meta(html: str, prop: str) -> str:
    from bs4 import BeautifulSoup

    tag = BeautifulSoup(html, "lxml").find("meta", attrs={"property": prop})
    return (tag.get("content") or "").strip() if tag else ""


def load_articles(samples: Path, config: lf.LeadConfig) -> tuple[list[Article], dict]:
    """저장된 HTML에서 본문을 뽑는다. (기사, 매체별 집계)"""
    articles, counts = [], {}
    for code in NAMES:
        src = config.sources[code]
        stat = counts.setdefault(code, {"html": 0, "skipped": 0, "failed": 0, "ok": 0})
        for path in sorted(samples.glob(f"{code}/*.html"), key=lambda p: int(re.search(r"_(\d+)", p.name).group(1))):
            html = path.read_text(encoding="utf-8")
            stat["html"] += 1
            if lf.page_skip_reason(html, src) or lf.short_body_reason(html, src, config.min_body_chars):
                stat["skipped"] += 1
                continue
            body = lf.source_body_text(html, src) if src.selector else None
            if not body or len(body) < config.min_chars:
                stat["failed"] += 1
                continue
            stat["ok"] += 1
            title = re.sub(r"\s*\|\s*[^|]+$", "", lf.page_title(html))   # "제목 | 연합뉴스" → 제목
            published = _meta(html, "article:published_time")[:10]
            articles.append(Article(path.name, code, title, published, lf.extract_subtitle(html, src.subtitle_selector), body))
    return articles, counts


def header(article: Article) -> str:
    head = f"[{NAMES[article.source_code]} {article.published or '-'} | {article.title}]\n"
    return head + (f"부제: {article.subtitle}\n" if article.subtitle else "")


def chunk_article(article: Article, tokens, target: int, overlap: int, max_tokens: int) -> list[Chunk]:
    """embed_text(헤더 포함)가 max_tokens를 넘지 않게 본문 예산을 헤더만큼 줄여 나눈다."""
    from ..disclosures.chunker import _pack_text

    head = header(article)
    head_tokens = tokens.count(head)
    budget_target, budget_max = max(50, target - head_tokens), max(60, max_tokens - head_tokens)
    pieces = _pack_text([article.body], budget_target, budget_max, overlap, tokens)
    chunks, cursor = [], 0
    for index, piece in enumerate(pieces):
        start = article.body.find(piece[:30], max(0, cursor - 2000))
        start = start if start >= 0 else cursor
        end = start + len(piece)
        cursor = end
        text = head + piece
        chunks.append(Chunk(article.file, article.source_code, index, piece, text, start, end, tokens.count(text)))
    return chunks


def gpu_processes() -> str:
    try:
        out = subprocess.run(["nvidia-smi", "--query-compute-apps=pid,process_name,used_memory", "--format=csv,noheader"],
                             capture_output=True, text=True, timeout=10)
        mem = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.used,memory.total", "--format=csv,noheader"],
                             capture_output=True, text=True, timeout=10)
        return (mem.stdout.strip() + " | 프로세스: " + (out.stdout.strip().replace("\n", "; ") or "없음")).strip()
    except (OSError, subprocess.SubprocessError):
        return "nvidia-smi 없음"


def gpu_free_gb() -> float:
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=10)
        return float(out.stdout.split()[0]) / 1024
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        return 0.0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="뉴스 원문 청킹 + BGE-M3 임베딩 속도 측정 (파일만, DB 없음)")
    ap.add_argument("--samples", type=Path, default=Path("samples"))
    ap.add_argument("--out", type=Path, default=Path("samples/bench"))
    ap.add_argument("--device", choices=["cpu", "cuda"], default="cpu")
    ap.add_argument("--batch-size", type=int, default=8, help="시작 배치 크기 (OOM이면 절반씩 줄인다)")
    ap.add_argument("--target", type=int, default=400)
    ap.add_argument("--overlap", type=int, default=80)
    ap.add_argument("--max-tokens", type=int, default=512)
    ap.add_argument("--top-k", type=int, default=50, help="검색 시연: dense+sparse로 뽑아 colbert로 재정렬할 청크 수")
    ap.add_argument("--gpu-cap-gb", type=float, default=2.5,
                    help="--device cuda: 이 프로세스가 쓸 GPU 메모리 상한. 넘으면 수집기가 아니라 이쪽이 OOM 나고 배치를 줄인다")
    ap.add_argument("--min-free-gb", type=float, default=2.8, help="--device cuda: 남은 GPU 메모리가 이보다 적으면 시작하지 않는다")
    args = ap.parse_args(argv)
    if args.device == "cpu":
        os.environ["CUDA_VISIBLE_DEVICES"] = ""          # torch를 부르기 전에 GPU를 숨긴다 (수집기 GPU에 영향 없음)
    else:
        free_gb = gpu_free_gb()
        print(f"GPU 사용 현황: {gpu_processes()} / 남은 메모리 {free_gb:.2f}GB (필요 {args.min_free_gb}GB)")
        if free_gb < args.min_free_gb:
            print("남은 GPU 메모리가 부족해 시작하지 않습니다. 수집기를 잠깐 멈추거나 --device cpu로 측정하세요.")
            return 2
        import torch
        total_gb = torch.cuda.get_device_properties(0).total_memory / 2**30
        torch.cuda.set_per_process_memory_fraction(min(1.0, args.gpu_cap_gb / total_gb), 0)

    import numpy as np
    from ..common.config import load_config as load_common
    from ..disclosures.chunker import HFTokenCounter
    from ..disclosures.embedder import BatchRunner, check_dense, colbert_score, environment_info, load_encoder
    from ..disclosures.sparse_store import lexical_score

    gpu_before = gpu_processes()
    config = lf.load_config()
    articles, counts = load_articles(args.samples, config)
    model_cfg = dict(load_common("configs/common.yaml")["model"])
    model_cfg.update(batch_size=args.batch_size, max_length=args.max_tokens,
                     devices=["cuda:0"] if args.device == "cuda" else ["cpu"])
    started = time.perf_counter()
    encoder, model_info = load_encoder(model_cfg, offline=True, allow_cpu=args.device == "cpu")
    load_seconds = time.perf_counter() - started
    tokens = HFTokenCounter(encoder.tokenizer)

    t0 = time.perf_counter()
    chunks = [c for a in articles for c in chunk_article(a, tokens, args.target, args.overlap, args.max_tokens)]
    chunk_seconds = time.perf_counter() - t0
    texts = [c.embed_text for c in chunks]

    import torch
    if encoder.device.startswith("cuda"):
        torch.cuda.reset_peak_memory_stats(encoder.device)
    runner = BatchRunner(lambda batch: encoder._forward(batch, encoder.max_length, sparse=True, colbert=True),
                         args.batch_size)
    t0 = time.perf_counter()
    encoded = runner.run(texts, encoder.token_lengths(texts))
    embed_seconds = time.perf_counter() - t0
    dense = np.stack([e.dense for e in encoded])
    check_dense(dense)
    peak = torch.cuda.max_memory_allocated(encoder.device) if encoder.device.startswith("cuda") else 0

    # 검색 시연: dense+sparse 상위 K → 그 청크만 colbert 다시 인코딩(저장하지 않는 설계의 실제 비용) → 0.4:0.2:0.4
    demo, rerank_times = [], []
    for query in QUERIES:
        q = encoder.encode_query(query, sparse=True, colbert=True)
        d_scores = dense @ q.dense
        s_scores = np.array([lexical_score(q.sparse, e.sparse) for e in encoded])
        first = d_scores * (WEIGHTS["dense"] / (WEIGHTS["dense"] + WEIGHTS["sparse"])) + \
            s_scores * (WEIGHTS["sparse"] / (WEIGHTS["dense"] + WEIGHTS["sparse"]))
        top = list(np.argsort(-first)[: args.top_k])
        t1 = time.perf_counter()
        vecs = encoder.encode_colbert_documents([texts[i] for i in top])
        rerank_times.append(time.perf_counter() - t1)
        final = sorted(((WEIGHTS["dense"] * d_scores[i] + WEIGHTS["sparse"] * s_scores[i]
                         + WEIGHTS["colbert"] * colbert_score(q.colbert, v), i) for i, v in zip(top, vecs)), reverse=True)
        demo.append({"query": query, "top": [{"score": round(float(s), 4), "file": chunks[i].file,
                                              "chunk_index": chunks[i].chunk_index,
                                              "dense": round(float(d_scores[i]), 4), "sparse": round(float(s_scores[i]), 4),
                                              "text": chunks[i].chunk_text[:80]} for s, i in final[:3]]})

    per_article = [sum(1 for c in chunks if c.file == a.file) for a in articles]
    per_chunk = embed_seconds / max(1, len(chunks))
    avg_chunks = statistics.mean(per_article) if per_article else 0
    estimate = {f"{n}건": {"chunks": round(n * avg_chunks), "minutes": round(n * avg_chunks * per_chunk / 60, 1)}
                for n in (3000, 5000)}
    summary = {
        "run_at": datetime.now().isoformat(timespec="seconds"), "device": encoder.device, "dtype": model_info["dtype"],
        "gpu_before": gpu_before, "env": environment_info(), "batch_size_start": args.batch_size,
        "batch_size_end": runner.batch_size, "oom_events": runner.oom_events, "peak_gpu_mb": round(peak / 2**20),
        "chunk_settings": {"target": args.target, "overlap": args.overlap, "max": args.max_tokens, "version": CHUNKER_VERSION},
        "per_source": counts, "articles": len(articles), "chunks": len(chunks),
        "chunks_per_article": round(avg_chunks, 2), "chunk_tokens_avg": round(statistics.mean(c.token_count for c in chunks), 1),
        "chunk_tokens_max": max(c.token_count for c in chunks), "model_load_s": round(load_seconds, 1),
        "chunking_s": round(chunk_seconds, 2), "embed_s": round(embed_seconds, 2), "embed_s_per_chunk": round(per_chunk, 4),
        "rerank_colbert_s_per_query": round(statistics.mean(rerank_times), 3), "rerank_top_k": args.top_k,
        "daily_estimate": estimate, "search_demo": demo,
    }
    run_dir = args.out / f"{datetime.now():%Y%m%d_%H%M%S}_{encoder.device.replace(':', '')}"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    with (run_dir / "chunks.jsonl").open("w", encoding="utf-8") as handle:
        for c, e in zip(chunks, encoded):
            handle.write(json.dumps({**asdict(c), "chunker_version": CHUNKER_VERSION, "sparse": e.sparse},
                                    ensure_ascii=False) + "\n")
    np.save(run_dir / "dense.npy", dense.astype(np.float32))
    print(json.dumps({k: v for k, v in summary.items() if k not in ("env", "search_demo")}, ensure_ascii=False, indent=1))
    for d in demo:
        print(f"\n[질의] {d['query']}")
        for t in d["top"]:
            print(f"  {t['score']:.3f} (d {t['dense']:.3f} / s {t['sparse']:.3f}) {t['file']}#{t['chunk_index']} {t['text']}")
    print(f"\n결과 폴더: {run_dir}  (summary.json, chunks.jsonl, dense.npy) — DB에는 아무것도 쓰지 않았습니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
