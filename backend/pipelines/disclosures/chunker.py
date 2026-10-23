"""파싱 블록을 BGE-M3 토큰 기준 청크로 나눈다.

- 본문: 목표 700토큰, 오버랩 100토큰, 최대 1000토큰. 문장 경계를 우선해서 자른다.
- 표: 최대 토큰 이하면 한 청크. 넘으면 행 경계에서 나누고 조각마다 표 제목·단위·열 헤더를 반복한다.
  같은 섹션의 작은 표가 이어지면 목표 토큰까지 한 청크로 묶는다.
- 토큰 수는 헤더(`[기업명 연도 보고서 | 섹션]`)를 포함한 chunk_text 전체 기준이며 max_tokens를 넘지 않는다.
- 입력과 토크나이저가 같으면 결과(index·텍스트·해시·fingerprint)가 항상 같다.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from typing import Protocol

from .parser import PARSER_VERSION, Block, section_label


CHUNKER_VERSION = "1.1"

_SENTENCE_RE = re.compile(r"(?<=[.!?。])\s+")
PERIOD_LABELS = {3: "1분기", 6: "반기", 9: "3분기", 12: "사업보고서"}


class TokenCounter(Protocol):
    def count(self, text: str) -> int: ...

    def offsets(self, text: str) -> list[tuple[int, int]]: ...


class HFTokenCounter:
    """transformers fast 토크나이저 래퍼 (특수 토큰 제외 길이)."""

    def __init__(self, tokenizer):
        # 길이만 세므로 잘라내지 않는다. 긴 표 전체를 셀 때 나오는 길이 경고를 끈다.
        tokenizer.model_max_length = 10**9
        self.tokenizer = tokenizer
        self._cache: dict[str, int] = {}

    def count(self, text: str) -> int:
        cached = self._cache.get(text)
        if cached is None:
            cached = len(self.tokenizer(text, add_special_tokens=False)["input_ids"])
            if len(self._cache) < 200_000:
                self._cache[text] = cached
        return cached

    def offsets(self, text: str) -> list[tuple[int, int]]:
        encoded = self.tokenizer(text, add_special_tokens=False, return_offsets_mapping=True)
        return [tuple(pair) for pair in encoded["offset_mapping"]]


@dataclass
class ChunkSettings:
    target_tokens: int = 700
    overlap_tokens: int = 100
    max_tokens: int = 1000

    @classmethod
    def from_config(cls, config: dict) -> "ChunkSettings":
        chunk = config.get("chunk", {})
        return cls(
            target_tokens=int(chunk.get("target_tokens", 700)),
            overlap_tokens=int(chunk.get("overlap_tokens", 100)),
            max_tokens=int(chunk.get("max_tokens", 1000)),
        )


@dataclass
class Chunk:
    rcept_no: str
    chunk_index: int
    section: str
    block_type: str
    chunk_text: str
    token_count: int
    chunk_hash: str

    def manifest_row(self) -> dict:
        return {
            "rcept_no": self.rcept_no,
            "chunk_index": self.chunk_index,
            "section": self.section,
            "token_count": self.token_count,
            "chunk_hash": self.chunk_hash,
            "block_type": self.block_type,
            "parser_version": PARSER_VERSION,
            "chunker_version": CHUNKER_VERSION,
        }

    def to_dict(self) -> dict:
        return asdict(self)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def doc_fingerprint(chunk_hashes: list[str]) -> str:
    """청크 해시를 순서대로 이은 값의 sha256."""
    return sha256_text("".join(chunk_hashes))


def period_label(period_end: str) -> str:
    return PERIOD_LABELS[int(period_end[5:7])]


def chunk_header(company: str, period_end: str, section: str) -> str:
    return f"[{company} {period_end[:4]} {period_label(period_end)} | {section}]\n"


# ── 분할 도구 ─────────────────────────────────────────
def _hard_split(text: str, limit: int, tokens: TokenCounter) -> list[str]:
    """토큰 경계에서 limit 토큰 이하 조각으로 자른다 (원문 문자를 바꾸지 않는다)."""
    offsets = tokens.offsets(text)
    if len(offsets) <= limit:
        return [text]
    pieces: list[str] = []
    start_char = 0
    for index in range(limit, len(offsets), limit):
        cut = offsets[index][0]
        piece = text[start_char:cut].strip()
        if piece:
            pieces.append(piece)
        start_char = cut
    tail = text[start_char:].strip()
    if tail:
        pieces.append(tail)
    # 조각을 다시 토큰화하면 경계 근처에서 길이가 달라질 수 있어 한 번 더 확인한다.
    result: list[str] = []
    for piece in pieces:
        if tokens.count(piece) > limit and limit > 1:
            result.extend(_hard_split(piece, max(1, limit * 9 // 10), tokens))
        else:
            result.append(piece)
    return result


def _sentences(paragraph: str) -> list[str]:
    return [part for part in _SENTENCE_RE.split(paragraph) if part]


@dataclass
class _Unit:
    text: str
    tokens: int
    new_paragraph: bool


def _join_units(units: list[_Unit]) -> str:
    out = ""
    for position, unit in enumerate(units):
        if position:
            out += "\n" if unit.new_paragraph else " "
        out += unit.text
    return out


def _pack_text(paragraphs: list[str], budget_target: int, budget_max: int, overlap: int, tokens: TokenCounter) -> list[str]:
    units: list[_Unit] = []
    for paragraph in paragraphs:
        first = True
        for sentence in _sentences(paragraph):
            for piece in _hard_split(sentence, budget_target, tokens) if tokens.count(sentence) > budget_target else [sentence]:
                units.append(_Unit(piece, tokens.count(piece), first))
                first = False

    bodies: list[str] = []
    current: list[_Unit] = []
    current_tokens = 0
    for unit in units:
        if current and current_tokens + unit.tokens > budget_target:
            bodies.append(_join_units(current))
            carried: list[_Unit] = []
            carried_tokens = 0
            for previous in reversed(current[1:]):  # 직전 청크 전체를 다시 넣지는 않는다
                if carried_tokens + previous.tokens > overlap:
                    break
                carried.insert(0, previous)
                carried_tokens += previous.tokens
            current, current_tokens = carried, carried_tokens
        current.append(unit)
        current_tokens += unit.tokens
    if current:
        bodies.append(_join_units(current))
    # 문장 이어붙이기로 토큰 수가 늘어난 경우를 대비해 최종 길이를 확인한다.
    result: list[str] = []
    for body in bodies:
        result.extend(_hard_split(body, budget_max, tokens) if tokens.count(body) > budget_max else [body])
    return result


def _table_prefix(block: Block) -> list[str]:
    lines = []
    if block.caption:
        lines.append(f"[표] {block.caption}")
    else:
        lines.append("[표]")
    if block.unit:
        lines.append(block.unit)
    if block.header:
        lines.append("열: " + " | ".join(block.header))
    return lines


def _table_bodies(block: Block, budget_target: int, budget_max: int, tokens: TokenCounter) -> list[str]:
    prefix = _table_prefix(block)
    whole = "\n".join(prefix + block.rows)
    if tokens.count(whole) <= budget_max:
        return [whole]
    prefix_text = "\n".join(prefix)
    prefix_tokens = tokens.count(prefix_text)
    if prefix_tokens > budget_target // 2:
        # 열 헤더는 각 행의 `헤더: 값`에 이미 들어 있으므로 머리말이 너무 길면 먼저 뺀다.
        prefix = [line for line in prefix if not line.startswith("열: ")]
        prefix_text = "\n".join(prefix)
        prefix_tokens = tokens.count(prefix_text)
    if prefix_tokens > budget_target // 2:
        # 그래도 길면 표 제목 줄을 앞부분만 남긴다 (단위 줄은 유지).
        caption_line, rest = prefix[0], prefix[1:]
        caption_line = _hard_split(caption_line, max(1, budget_target // 4), tokens)[0]
        prefix_text = "\n".join([caption_line] + rest)
        prefix_tokens = tokens.count(prefix_text)
    row_budget = max(1, budget_target - prefix_tokens)
    rows: list[str] = []
    for row in block.rows:
        if tokens.count(row) > row_budget:
            rows.extend(_hard_split(row, row_budget, tokens))
        else:
            rows.append(row)
    bodies: list[str] = []
    current: list[str] = []
    current_tokens = 0
    for row in rows:
        row_tokens = tokens.count(row)
        if current and current_tokens + row_tokens > row_budget:
            bodies.append("\n".join([prefix_text] + current))
            current, current_tokens = [], 0
        current.append(row)
        current_tokens += row_tokens
    if current:
        bodies.append("\n".join([prefix_text] + current))
    result: list[str] = []
    for body in bodies:
        result.extend(_hard_split(body, budget_max, tokens) if tokens.count(body) > budget_max else [body])
    return result


# ── 문서 청킹 ─────────────────────────────────────────
def chunk_blocks(
    rcept_no: str,
    blocks: list[Block],
    company: str,
    period_end: str,
    tokens: TokenCounter,
    settings: ChunkSettings,
) -> list[Chunk]:
    # 1) 같은 섹션의 연속 문단은 하나의 본문 묶음, 표는 각각 하나의 표 묶음
    groups: list[tuple[str, str, list[Block]]] = []
    for block in blocks:
        section = section_label(block.section)
        if block.block_type == "text" and groups and groups[-1][0] == section and groups[-1][1] == "text":
            groups[-1][2].append(block)
        else:
            groups.append((section, block.block_type, [block]))

    # 2) 묶음별 청크 본문 생성
    pieces: list[tuple[str, str, str]] = []  # (section, block_type, body)
    for section, block_type, members in groups:
        header_tokens = tokens.count(chunk_header(company, period_end, section))
        budget_max = settings.max_tokens - header_tokens
        budget_target = min(settings.target_tokens, budget_max)
        if budget_target < 50:
            raise ValueError(f"섹션 헤더가 너무 깁니다 ({header_tokens}토큰): {section}")
        if block_type == "text":
            bodies = _pack_text([b.text for b in members], budget_target, budget_max, settings.overlap_tokens, tokens)
            pieces.extend((section, "text", body) for body in bodies)
            continue
        bodies = _table_bodies(members[0], budget_target, budget_max, tokens)
        # 같은 섹션의 작은 표가 이어지면 목표 토큰까지 합친다.
        if (
            len(bodies) == 1
            and pieces
            and pieces[-1][0] == section
            and pieces[-1][1] == "table"
            and tokens.count(pieces[-1][2] + "\n\n" + bodies[0]) <= budget_target
        ):
            pieces[-1] = (section, "table", pieces[-1][2] + "\n\n" + bodies[0])
        else:
            pieces.extend((section, "table", body) for body in bodies)

    # 3) 헤더를 붙이고 번호·해시를 매긴다
    chunks: list[Chunk] = []
    for section, block_type, body in pieces:
        text = chunk_header(company, period_end, section) + body
        count = tokens.count(text)
        if count > settings.max_tokens:
            raise ValueError(f"{rcept_no}: 청크가 최대 토큰을 넘습니다 ({count} > {settings.max_tokens}): {section}")
        chunks.append(
            Chunk(
                rcept_no=rcept_no,
                chunk_index=len(chunks),
                section=section,
                block_type=block_type,
                chunk_text=text,
                token_count=count,
                chunk_hash=sha256_text(text),
            )
        )
    return chunks
