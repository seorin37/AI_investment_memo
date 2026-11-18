"""도메인 단어 사전 — 공시 청크에 나오는 금융·산업 단어로, 종목명도 도메인 단어도 없는 문장을 API 없이 거른다.

사전은 `build_domain_vocab`로 DB의 공시 청크에서 만들어 `configs/tracking_domain_vocab.txt.gz`에 저장한다.
판정 때는 이 파일만 읽는다 (DB 불필요).

    PYTHONPATH=backend python -m pipelines.tracking.domain --min-df 3      # 사전 다시 만들기 (DB 읽기)
"""

from __future__ import annotations

import argparse
import collections
import gzip
import re
from functools import lru_cache
from pathlib import Path

from ..common.config import resolve_path

DEFAULT_PATH = "configs/tracking_domain_vocab.txt.gz"
_TOKEN = re.compile(r"[가-힣A-Za-z0-9]+")
# 어절 끝 조사를 떼서 어간도 사전에 넣는다 ("수율이랑" → "수율")
_JOSA = sorted("은 는 이 가 을 를 의 에 와 과 로 도 만 에서 에게 까지 부터 보다 처럼 이나 나 랑 이랑 으로 하고 께 서 이며 이고 이다 이라 라 인 적 들"
               .split(), key=len, reverse=True)


def stems(text: str) -> set[str]:
    out: set[str] = set()
    for word in _TOKEN.findall(text):
        word = word.lower()
        out.add(word)
        for josa in _JOSA:
            if word.endswith(josa) and len(word) - len(josa) >= 2:
                out.add(word[: -len(josa)])
                break
    return out


@lru_cache(maxsize=2)
def load_vocab(path: str = DEFAULT_PATH) -> frozenset[str]:
    file = resolve_path(path)
    if not file.exists():
        return frozenset()
    with gzip.open(file, "rt", encoding="utf-8") as handle:
        return frozenset(line.strip() for line in handle if line.strip())


def has_domain_word(text: str, vocab: frozenset[str]) -> bool:
    return any(s in vocab for s in stems(text) if len(s) >= 2)


def build(min_df: int, out: Path) -> int:
    from sqlalchemy import text

    from ..common.db import get_read_engine

    df: collections.Counter = collections.Counter()
    with get_read_engine().connect() as conn:
        for (chunk,) in conn.execute(text("SELECT chunk_text FROM disclosure_chunks")):
            df.update(stems(chunk))
    words = sorted(w for w, n in df.items() if n >= min_df and 2 <= len(w) <= 15)
    out.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(out, "wt", encoding="utf-8") as handle:
        handle.write("\n".join(words) + "\n")
    return len(words)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="공시 청크로 도메인 단어 사전 만들기 (DB 읽기 전용)")
    ap.add_argument("--min-df", type=int, default=3, help="이 수 이상의 청크에 나온 단어만")
    ap.add_argument("--out", default=DEFAULT_PATH)
    args = ap.parse_args(argv)
    n = build(args.min_df, resolve_path(args.out))
    print(f"도메인 단어 {n}개 → {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
