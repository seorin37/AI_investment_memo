"""BGE-M3 sparse(lexical) 가중치 파일 저장소와 메모리 역색인.

파일: `{sparse_dir}/{rcept_no}.jsonl`, 한 줄 = {"rcept_no","chunk_index","weights":{"<token_id>": float32}}.
DB 스키마를 바꾸지 않기 위해 sparse는 파일에만 둔다. 같은 키가 여러 번 있으면 마지막 줄을 쓴다
(중단 후 재실행으로 생길 수 있음). compact()로 정렬·중복 제거한다.
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Iterable

import numpy as np


Key = tuple[str, int]


def sparse_path(sparse_dir: Path, rcept_no: str) -> Path:
    return Path(sparse_dir) / f"{rcept_no}.jsonl"


def _line(rcept_no: str, chunk_index: int, weights: dict[str, float]) -> str:
    return json.dumps({"rcept_no": rcept_no, "chunk_index": chunk_index, "weights": weights}, ensure_ascii=False, separators=(",", ":"))


def append(sparse_dir: Path, rows: Iterable[tuple[str, int, dict[str, float]]]) -> None:
    """(rcept_no, chunk_index, weights) 행을 문서별 파일에 덧붙이고 디스크에 확정한다."""
    grouped: dict[str, list[str]] = defaultdict(list)
    for rcept_no, chunk_index, weights in rows:
        grouped[rcept_no].append(_line(rcept_no, chunk_index, weights))
    Path(sparse_dir).mkdir(parents=True, exist_ok=True)
    for rcept_no, lines in grouped.items():
        with sparse_path(sparse_dir, rcept_no).open("a", encoding="utf-8", newline="\n") as handle:
            handle.write("\n".join(lines) + "\n")
            handle.flush()
            os.fsync(handle.fileno())


def read(sparse_dir: Path, rcept_no: str) -> dict[int, dict[str, float]]:
    path = sparse_path(sparse_dir, rcept_no)
    rows: dict[int, dict[str, float]] = {}
    if not path.exists():
        return rows
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                row = json.loads(line)
                if row["rcept_no"] != rcept_no:
                    raise ValueError(f"{path.name}: 다른 문서의 행이 있습니다 ({row['rcept_no']})")
                rows[int(row["chunk_index"])] = row["weights"]
    return rows


def keys(sparse_dir: Path, rcept_nos: Iterable[str]) -> set[Key]:
    return {(rcept_no, index) for rcept_no in rcept_nos for index in read(sparse_dir, rcept_no)}


def compact(sparse_dir: Path, rcept_no: str, valid_indices: set[int] | None = None) -> int:
    """chunk_index 순으로 정렬·중복 제거해 다시 쓴다. valid_indices가 있으면 그 밖의 행은 버린다. 남은 행 수 반환."""
    rows = read(sparse_dir, rcept_no)
    if valid_indices is not None:
        rows = {index: weights for index, weights in rows.items() if index in valid_indices}
    path = sparse_path(sparse_dir, rcept_no)
    if not rows:
        path.unlink(missing_ok=True)
        return 0
    temp = path.with_suffix(".jsonl.tmp")
    with temp.open("w", encoding="utf-8", newline="\n") as handle:
        for index in sorted(rows):
            handle.write(_line(rcept_no, index, rows[index]) + "\n")
    os.replace(temp, path)
    return len(rows)


def remove(sparse_dir: Path, rcept_no: str) -> None:
    sparse_path(sparse_dir, rcept_no).unlink(missing_ok=True)


def lexical_score(query: dict[str, float], document: dict[str, float]) -> float:
    """Σ q_w × d_w (공통 토큰만)."""
    if len(query) > len(document):
        query, document = document, query
    return float(sum(weight * document[token] for token, weight in query.items() if token in document))


class SparseIndex:
    """sparse 파일로 만드는 메모리 역색인 (numpy 배열, 문서당 dict를 들고 있지 않는다)."""

    def __init__(self, entries: dict[Key, dict[str, float]] | Iterable[tuple[Key, dict[str, float]]]):
        """entries: {키: 가중치} 또는 (키, 가중치) 스트림. 키 순으로 정렬해 쌓는다."""
        items = sorted(entries.items()) if isinstance(entries, dict) else entries
        self.keys: list[Key] = []
        doc_ids, token_ids, weights, offsets = [], [], [], [0]
        for i, (key, row) in enumerate(items):
            if self.keys and key <= self.keys[-1]:
                raise ValueError(f"키가 정렬되어 있지 않거나 중복입니다: {key}")
            self.keys.append(key)
            tokens = np.fromiter((int(t) for t in row), dtype=np.int64, count=len(row))
            values = np.fromiter(row.values(), dtype=np.float32, count=len(row))
            order = np.argsort(tokens, kind="stable")
            token_ids.append(tokens[order])
            weights.append(values[order])
            doc_ids.append(np.full(len(row), i, dtype=np.int32))
            offsets.append(offsets[-1] + len(row))
        self.position = {key: i for i, key in enumerate(self.keys)}
        self.key_rcepts = np.array([key[0] for key in self.keys], dtype=object)
        empty_i, empty_f = np.zeros(0, np.int64), np.zeros(0, np.float32)
        # 문서 순 (정방향): 특정 문서 점수 계산용
        self.fwd_tokens = np.concatenate(token_ids) if token_ids else empty_i
        self.fwd_weights = np.concatenate(weights) if weights else empty_f
        self.fwd_offsets = np.asarray(offsets, dtype=np.int64)
        # 토큰 순 (역색인): 후보 검색용
        docs = np.concatenate(doc_ids) if doc_ids else np.zeros(0, np.int32)
        order = np.argsort(self.fwd_tokens, kind="stable")
        self.inv_tokens = self.fwd_tokens[order]
        self.inv_docs = docs[order]
        self.inv_weights = self.fwd_weights[order]

    @classmethod
    def from_dir(cls, sparse_dir: Path, rcept_nos: Iterable[str]) -> "SparseIndex":
        """문서 파일을 하나씩 읽어 쌓는다 (전체 dict를 한꺼번에 들고 있지 않는다)."""

        def stream():
            for rcept_no in sorted(set(rcept_nos)):
                rows = read(sparse_dir, rcept_no)
                for index in sorted(rows):
                    yield (rcept_no, index), rows[index]

        return cls(stream())

    def __len__(self) -> int:
        return len(self.keys)

    def _scores(self, query: dict[str, float]) -> np.ndarray:
        scores = np.zeros(len(self.keys), dtype=np.float64)
        for token, weight in query.items():
            token_id = int(token)
            lo = np.searchsorted(self.inv_tokens, token_id, side="left")
            hi = np.searchsorted(self.inv_tokens, token_id, side="right")
            if hi > lo:
                np.add.at(scores, self.inv_docs[lo:hi], weight * self.inv_weights[lo:hi].astype(np.float64))
        return scores

    def top(self, query: dict[str, float], k: int, allowed: set[str] | None = None) -> list[tuple[Key, float]]:
        """점수 > 0인 문서 중 상위 k개. allowed가 있으면 그 접수번호만."""
        if not self.keys or not query:
            return []
        scores = self._scores(query)
        if allowed is not None:
            scores = np.where(np.isin(self.key_rcepts, list(allowed)), scores, 0.0)
        candidates = np.flatnonzero(scores > 0)
        # 키가 정렬돼 있으므로 안정 정렬이면 동점은 키 순서가 된다.
        ranked = candidates[np.argsort(-scores[candidates], kind="stable")][:k]
        return [(self.keys[i], float(scores[i])) for i in ranked.tolist()]

    def score(self, query: dict[str, float], key: Key) -> float | None:
        """한 문서의 실제 sparse 점수. 인덱스에 없는 키면 None."""
        i = self.position.get(key)
        if i is None:
            return None
        lo, hi = self.fwd_offsets[i], self.fwd_offsets[i + 1]
        tokens, weights = self.fwd_tokens[lo:hi], self.fwd_weights[lo:hi]
        total = 0.0
        for token, weight in query.items():
            j = np.searchsorted(tokens, int(token))
            if j < len(tokens) and tokens[j] == int(token):
                total += weight * float(weights[j])
        return total
