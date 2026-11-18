"""BGE-M3 임베딩 (GPU · fp16 · 토큰 길이 정렬 배치 · CUDA OOM 시 배치 절반 재시도).

FlagEmbedding의 `encode()`는 호출마다 첫 배치를 OOM 탐색용으로 한 번 더 추론하므로 쓰지 않고,
같은 모델(`BGEM3FlagModel.model`)과 토크나이저로 배치 루프를 직접 돌린다. dense는 모델 출력(CLS,
정규화)을 float32로 다시 L2 정규화하고, sparse는 FlagEmbedding과 같은 방식(토큰별 최대 가중치,
특수 토큰 제외, w > 0)으로 만든다. 토큰 ID는 BGE-M3 원래 값(문자열 키)이다.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Sequence

import numpy as np

from ..common.logging import get_logger


log = get_logger("disclosures.embedder")


class ModelRevisionError(RuntimeError):
    pass


class DeviceError(RuntimeError):
    pass


class EmbeddingQualityError(RuntimeError):
    pass


# ── 모델 로딩 ─────────────────────────────────────────
MODEL_IGNORE_PATTERNS = ["onnx/*", "*.onnx", "*.onnx_data", "imgs/*", "*.jpg", "*.png"]
_PATCHED = False


def patch_transformers_dtype() -> None:
    """transformers `from_pretrained(dtype=…)` 호환 패치 (scripts/test_bge.py 방식). 여러 번 불러도 한 번만 적용."""
    global _PATCHED
    if _PATCHED:
        return
    from transformers import AutoModel

    original = AutoModel.from_pretrained

    def compatible_from_pretrained(*args, **kwargs):
        if "dtype" in kwargs:
            kwargs["torch_dtype"] = kwargs.pop("dtype")
        return original(*args, **kwargs)

    AutoModel.from_pretrained = compatible_from_pretrained
    _PATCHED = True


def set_offline(offline: bool) -> None:
    """--offline이면 HF 허브 접속을 막는다. huggingface_hub를 import하기 전에 불러야 한다."""
    if offline:
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"


def resolve_model_path(name: str, revision: str, offline: bool) -> Path:
    """고정 revision 스냅샷 경로를 받는다. 받은 스냅샷 revision이 다르면 중단한다."""
    from huggingface_hub import snapshot_download

    path = Path(
        snapshot_download(
            repo_id=name,
            revision=revision,
            local_files_only=offline,
            ignore_patterns=MODEL_IGNORE_PATTERNS,  # 쓰지 않는 ONNX(약 2.2GB)·이미지는 받지 않는다
        )
    )
    if path.name != revision:
        raise ModelRevisionError(f"모델 revision이 다릅니다: 기대 {revision}, 실제 {path.name}")
    return path


def select_device(devices: Sequence[str], allow_cpu: bool) -> str:
    import torch

    if torch.cuda.is_available():
        device = devices[0] if devices else "cuda:0"
        if len(devices) > 1:
            log.warning("멀티 GPU는 지원하지 않습니다. %s만 사용합니다.", device)
        index = torch.device(device).index or 0
        props = torch.cuda.get_device_properties(index)
        log.info("GPU: %s, 메모리 %.1f GiB", props.name, props.total_memory / 2**30)
        return device
    if allow_cpu:
        log.warning("CUDA를 쓸 수 없어 CPU로 실행합니다 (--allow-cpu).")
        return "cpu"
    raise DeviceError("CUDA를 쓸 수 없습니다. CPU로 실행하려면 --allow-cpu를 주세요.")


def load_tokenizer(model_path: Path):
    from transformers import AutoTokenizer

    return AutoTokenizer.from_pretrained(str(model_path))


# ── 배치 실행 (모델과 무관한 부분, 테스트 대상) ────────────────
def is_cuda_oom(exc: BaseException) -> bool:
    try:
        import torch

        if isinstance(exc, torch.cuda.OutOfMemoryError):
            return True
    except ImportError:  # pragma: no cover
        pass
    return isinstance(exc, RuntimeError) and "out of memory" in str(exc).lower()


def _empty_cuda_cache() -> None:
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:  # pragma: no cover
        pass


@dataclass
class BatchRunner:
    """길이 내림차순으로 묶어 forward를 돌리고 결과를 원래 순서로 돌려준다.

    OOM이면 캐시를 비우고 배치를 절반(최소 1)으로 줄여 같은 배치를 다시 시도한다. 줄어든 크기는 유지한다.
    """

    forward: Callable[[list[str]], list]
    batch_size: int
    is_oom: Callable[[BaseException], bool] = is_cuda_oom
    clear_cache: Callable[[], None] = _empty_cuda_cache
    oom_events: int = 0

    def run(
        self,
        texts: Sequence[str],
        lengths: Sequence[int],
        on_batch: Callable[[list[int], list], None] | None = None,
        keep_results: bool = True,
    ) -> list:
        """keep_results=False면 결과를 on_batch로만 넘기고 모아 두지 않는다 (대량 실행 메모리 절약)."""
        order = sorted(range(len(texts)), key=lambda i: (-lengths[i], i))
        results: list = [None] * len(texts) if keep_results else []
        position = 0
        while position < len(order):
            indices = order[position : position + self.batch_size]
            oom = False
            try:
                outputs = self.forward([texts[i] for i in indices])
            except Exception as exc:
                if not self.is_oom(exc) or self.batch_size <= 1:
                    raise
                oom = True
            if oom:
                # except 블록 밖에서 비워야 실패한 배치의 텐서를 잡고 있던 traceback이 풀린다.
                self.oom_events += 1
                self.clear_cache()
                self.batch_size = max(1, self.batch_size // 2)
                log.warning("CUDA OOM → 배치 크기 %d로 줄여 재시도", self.batch_size)
                continue
            if keep_results:
                for index, output in zip(indices, outputs):
                    results[index] = output
            if on_batch is not None:
                on_batch(indices, outputs)
            position += len(indices)
        return results


def check_dense(vectors: np.ndarray, tolerance: float = 0.01) -> None:
    """NaN/Inf가 있거나 노름이 1±tolerance 밖이면 EmbeddingQualityError."""
    if not np.isfinite(vectors).all():
        raise EmbeddingQualityError("임베딩에 NaN/Inf가 있습니다.")
    norms = np.linalg.norm(vectors.astype(np.float64), axis=1)
    if norms.size and (norms.min() < 1 - tolerance or norms.max() > 1 + tolerance):
        raise EmbeddingQualityError(f"임베딩 노름 범위 밖: {norms.min():.4f}~{norms.max():.4f}")


def check_sparse(rows: Sequence[dict[str, float] | None]) -> None:
    """Sparse 토큰 ID와 가중치가 DB에 안전하게 저장 가능한지 검사한다."""
    for row in rows:
        if row is None:
            raise EmbeddingQualityError("sparse 임베딩이 생성되지 않았습니다.")
        for token, weight in row.items():
            try:
                token_id = int(token)
                value = float(weight)
            except (TypeError, ValueError):
                raise EmbeddingQualityError(f"잘못된 sparse 값: {token!r}={weight!r}") from None
            if token_id < 0 or str(token_id) != str(token) or not np.isfinite(value) or value <= 0:
                raise EmbeddingQualityError(f"잘못된 sparse 값: {token!r}={weight!r}")


def l2_normalize(vectors: np.ndarray) -> np.ndarray:
    vectors = np.asarray(vectors, dtype=np.float32)
    return vectors / np.linalg.norm(vectors, axis=1, keepdims=True).clip(min=1e-12)


@dataclass
class Encoded:
    dense: np.ndarray  # float32 (1024,), L2 정규화
    sparse: dict[str, float] | None = None
    colbert: np.ndarray | None = None  # float16 (토큰 수, 1024), CLS·패딩 제외, 토큰별 L2 정규화


def colbert_score(query_vecs: np.ndarray, doc_vecs: np.ndarray) -> float:
    """BGE-M3 ColBERT 점수: 질의 토큰마다 문서 토큰과의 최대 내적을 구해 평균 (BGEM3FlagModel.colbert_score와 같은 식)."""
    q = np.asarray(query_vecs, dtype=np.float32)
    d = np.asarray(doc_vecs, dtype=np.float32)
    if q.shape[0] == 0 or d.shape[0] == 0:
        return 0.0
    return float((q @ d.T).max(axis=1).sum() / q.shape[0])


@dataclass
class EncodeStats:
    truncated: int = 0
    oom_events: int = 0
    batch_size: int = 0
    seconds: float = 0.0
    items: int = 0
    max_memory_bytes: int = 0
    extra: dict = field(default_factory=dict)


class M3Encoder:
    """BGEM3FlagModel을 감싼 인코더. 문서·질의 모두 같은 모델·revision·fp16·정규화를 쓴다."""

    def __init__(self, flag_model, device: str, batch_size: int, max_length: int, query_max_length: int):
        self.flag_model = flag_model
        self.tokenizer = flag_model.tokenizer
        self.device = device
        self.batch_size = batch_size
        self.max_length = max_length
        self.query_max_length = query_max_length
        self.unused_token_ids = self._unused_token_ids()
        model = flag_model.model
        if device == "cpu":
            model.float()
        model.to(device)
        model.eval()

    def _unused_token_ids(self) -> set[int]:
        ids = set()
        for name in ("cls_token", "eos_token", "pad_token", "unk_token"):
            if name in self.tokenizer.special_tokens_map:
                ids.add(self.tokenizer.convert_tokens_to_ids(self.tokenizer.special_tokens_map[name]))
        return ids

    def token_lengths(self, texts: Sequence[str]) -> list[int]:
        """특수 토큰 포함, 잘리기 전 길이."""
        encoded = self.tokenizer(list(texts), add_special_tokens=True, truncation=False)
        return [len(ids) for ids in encoded["input_ids"]]

    def _forward(self, texts: list[str], max_length: int, sparse: bool, colbert: bool = False) -> list[Encoded]:
        import torch

        inputs = self.tokenizer(texts, padding=True, truncation=True, max_length=max_length, return_tensors="pt").to(self.device)
        with torch.inference_mode():
            outputs = self.flag_model.model(inputs, return_dense=True, return_sparse=sparse, return_colbert_vecs=colbert)
            dense = l2_normalize(outputs["dense_vecs"].float().cpu().numpy())
            weights = outputs["sparse_vecs"].squeeze(-1).float().cpu().numpy() if sparse else None
            # FlagEmbedding과 같은 후처리: CLS 다음 토큰부터, 실제 토큰 수 - 1개만 (패딩 제외)
            multi = outputs["colbert_vecs"].half().cpu().numpy() if colbert else None
        input_ids = inputs["input_ids"].cpu().numpy()
        token_counts = inputs["attention_mask"].sum(dim=1).cpu().numpy() if colbert else None
        results: list[Encoded] = []
        for row in range(len(texts)):
            lexical = None
            if sparse:
                lexical = {}
                for weight, token_id in zip(weights[row], input_ids[row]):
                    token_id = int(token_id)
                    if token_id in self.unused_token_ids or weight <= 0:
                        continue
                    key = str(token_id)
                    value = float(str(np.float32(weight)))  # float32를 그대로 복원하는 최단 10진 표기
                    if value > lexical.get(key, 0.0):
                        lexical[key] = value
            vecs = multi[row][: int(token_counts[row]) - 1] if colbert else None
            results.append(Encoded(dense=dense[row], sparse=lexical, colbert=vecs))
        return results

    def encode_documents(
        self,
        texts: Sequence[str],
        sparse: bool,
        on_batch: Callable[[list[int], list[Encoded]], None] | None = None,
        keep_results: bool = True,
    ) -> tuple[list[Encoded], EncodeStats]:
        """문서 청크 인코딩. 품질 검사(check_dense)는 on_batch 쪽에서 배치 단위로 한다."""
        import torch

        lengths = self.token_lengths(texts)
        truncated = sum(1 for length in lengths if length > self.max_length)
        if truncated:
            log.warning("max_length %d를 넘어 잘린 청크 %d개", self.max_length, truncated)
        runner = BatchRunner(lambda batch: self._forward(batch, self.max_length, sparse), self.batch_size)
        if self.device.startswith("cuda"):
            torch.cuda.reset_peak_memory_stats(self.device)
        started = time.perf_counter()
        results = runner.run(texts, lengths, on_batch, keep_results)
        stats = EncodeStats(
            truncated=truncated,
            oom_events=runner.oom_events,
            batch_size=runner.batch_size,
            seconds=time.perf_counter() - started,
            items=len(texts),
            max_memory_bytes=torch.cuda.max_memory_allocated(self.device) if self.device.startswith("cuda") else 0,
        )
        self.batch_size = runner.batch_size  # 줄어든 배치 크기는 이후에도 유지
        return results, stats

    def encode_query(self, query: str, sparse: bool, colbert: bool = False) -> Encoded:
        """질의: prefix 없음, max_length=query_max_length."""
        encoded = self._forward([query], self.query_max_length, sparse, colbert)[0]
        check_dense(encoded.dense[None, :])
        return encoded

    def encode_colbert_documents(self, texts: Sequence[str]) -> list[np.ndarray]:
        """문서 ColBERT 벡터 (인덱싱과 같은 텍스트·max_length). 길이 정렬 배치·OOM 시 배치 절반은 BatchRunner 그대로."""
        if not texts:
            return []
        runner = BatchRunner(lambda batch: self._forward(batch, self.max_length, sparse=False, colbert=True), self.batch_size)
        results = runner.run(texts, self.token_lengths(texts))
        self.batch_size = runner.batch_size
        return [r.colbert for r in results]


def load_encoder(model_config: dict, offline: bool, allow_cpu: bool) -> tuple[M3Encoder, dict]:
    """설정대로 BGE-M3를 올린다. (encoder, 환경 정보) 반환."""
    set_offline(offline)
    device = select_device(model_config.get("devices") or ["cuda:0"], allow_cpu)
    path = resolve_model_path(model_config["name"], model_config["revision"], offline)
    patch_transformers_dtype()
    from FlagEmbedding import BGEM3FlagModel

    use_fp16 = bool(model_config.get("use_fp16", True)) and device != "cpu"
    flag_model = BGEM3FlagModel(str(path), use_fp16=use_fp16, devices=[device])
    encoder = M3Encoder(
        flag_model,
        device,
        batch_size=int(model_config.get("batch_size", 16)),
        max_length=int(model_config.get("max_length", 1024)),
        query_max_length=int(model_config.get("query_max_length", 512)),
    )
    encoder.cache_namespace = f"{model_config['name']}@{model_config['revision']}"
    return encoder, {"model_path": str(path), "device": device, "dtype": "float16" if use_fp16 else "float32"}


def environment_info() -> dict:
    import platform

    info = {"python": platform.python_version()}
    try:
        import torch

        info["torch"] = torch.__version__
        info["cuda"] = torch.version.cuda
        info["gpu"] = torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
    except ImportError:  # pragma: no cover
        pass
    from importlib.metadata import PackageNotFoundError, version

    for package in ("transformers", "FlagEmbedding", "numpy", "SQLAlchemy", "psycopg", "pgvector", "lxml"):
        try:
            info[package] = version(package)
        except PackageNotFoundError:
            info[package] = None
    return info


# ── DB 임베딩 단계 ────────────────────────────────────
@dataclass
class EmbedReport:
    pending: int = 0
    embedded: int = 0
    failed: int = 0
    stats: EncodeStats | None = None


def embed_pending(
    begin: Callable,
    encoder: M3Encoder,
    rcept_nos: Sequence[str],
    *,
    model_name: str = "unknown",
    model_revision: str = "unknown",
    config_hash: str = "unknown",
    commit_every: int = 256,
    progress_every_sec: float = 10.0,
) -> EmbedReport:
    """dense/sparse가 없거나 현재 모델 설정과 다른 청크를 함께 임베딩한다.

    begin: 트랜잭션 컨텍스트를 돌려주는 함수(보통 engine.begin). commit_every행마다 executemany UPDATE + commit.
    dense와 sparse 및 생성 메타데이터는 같은 UPDATE/트랜잭션으로 확정한다. DB가 유일한 체크포인트다.
    NaN/Inf·노름 이상 배치는 저장하지 않고 실패로 센다(NULL로 남아 validate가 잡는다).
    """
    from sqlalchemy import bindparam, text

    from .search import vector_literal

    rcept_nos = sorted(set(rcept_nos))
    with begin() as conn:
        rows = conn.execute(
            text(
                "SELECT id, rcept_no, chunk_index, chunk_text,"
                " dense_embedding IS NULL OR sparse_embedding IS NULL OR embedding_model IS DISTINCT FROM :model"
                " OR embedding_revision IS DISTINCT FROM :revision OR embedding_config_hash IS DISTINCT FROM :config_hash AS pending"
                " FROM disclosure_chunks"
                " WHERE rcept_no IN :rs ORDER BY rcept_no, chunk_index"
            ).bindparams(bindparam("rs", expanding=True)),
            {"rs": rcept_nos, "model": model_name, "revision": model_revision, "config_hash": config_hash},
        ).all() if rcept_nos else []
    work = [r for r in rows if r[4]]
    report = EmbedReport(pending=len(work))
    if not work:
        log.info("임베딩할 청크가 없습니다.")
        return report

    buffer: list[tuple[int, str, int, Encoded]] = []
    started = time.perf_counter()
    last_log = [started]

    def flush() -> None:
        if not buffer:
            return
        embedded_at = datetime.now(timezone.utc)
        with begin() as conn:
            conn.execute(
                text(
                    "UPDATE disclosure_chunks SET dense_embedding = CAST(:dense AS vector),"
                    " sparse_embedding = CAST(:sparse AS jsonb), embedding_model = :model,"
                    " embedding_revision = :revision, embedding_config_hash = :config_hash, embedded_at = :embedded_at"
                    " WHERE id = :id"
                ),
                [
                    {
                        "id": chunk_id,
                        "dense": vector_literal(encoded.dense),
                        "sparse": json.dumps(encoded.sparse, separators=(",", ":"), sort_keys=True),
                        "model": model_name,
                        "revision": model_revision,
                        "config_hash": config_hash,
                        "embedded_at": embedded_at,
                    }
                    for chunk_id, _, _, encoded in buffer
                ],
            )
        report.embedded += len(buffer)
        buffer.clear()

    def on_batch(indices: list[int], outputs: list[Encoded]) -> None:
        try:
            check_dense(np.stack([o.dense for o in outputs]))
            check_sparse([o.sparse for o in outputs])
        except EmbeddingQualityError as exc:
            report.failed += len(indices)
            log.error("배치 품질 검사 실패 → 저장하지 않음 (%d개): %s", len(indices), exc)
            return
        for index, output in zip(indices, outputs):
            row = work[index]
            buffer.append((row[0], row[1], row[2], output))
        if len(buffer) >= commit_every:
            flush()
        now = time.perf_counter()
        if now - last_log[0] >= progress_every_sec:
            last_log[0] = now
            done = report.embedded + len(buffer) + report.failed
            rate = done / max(now - started, 1e-9)
            eta = (len(work) - done) / rate if rate > 0 else float("inf")
            log.info("진행 %d/%d청크, %.1f청크/초, 남은 시간 약 %.0f초 (배치 %d)", done, len(work), rate, eta, encoder.batch_size)

    _, stats = encoder.encode_documents([r[3] for r in work], sparse=True, on_batch=on_batch, keep_results=False)
    flush()
    report.stats = stats
    log.info(
        "임베딩 완료: %d청크, %.1f초, %.1f청크/초, 최대 GPU 메모리 %.2f GiB, 실패 %d, 잘림 %d",
        report.embedded,
        stats.seconds,
        report.embedded / max(stats.seconds, 1e-9),
        stats.max_memory_bytes / 2**30,
        report.failed,
        stats.truncated,
    )
    return report
