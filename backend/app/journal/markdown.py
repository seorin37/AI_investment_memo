"""블록 → Markdown (journal_entries.body, 검색·LLM용). 원본은 blocks 이고 이 변환은 한 방향이다."""

from __future__ import annotations

from typing import Any


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\r", "").replace("\n", "<br>").strip()


def _table(rows: list[list[str]]) -> str:
    rows = [list(r) for r in rows if r]
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    lines = ["| " + " | ".join(_cell(c) for c in rows[0]) + " |", "|" + "|".join("---" for _ in range(width)) + "|"]
    lines += ["| " + " | ".join(_cell(c) for c in r) + " |" for r in rows[1:]]
    return "\n".join(lines)


def _mark(text: str, highlight: bool | None) -> str:
    text = text.strip("\n")
    return f"=={text}==" if highlight and text.strip() else text


def blocks_to_markdown(blocks: list[dict[str, Any]]) -> str:
    """문단 = 그대로, 제목 = '## ', 체크 = '- [ ] / - [x]', 표 = Markdown 표, 첨부 = [이름](주소), 강조 = ==글자==.
    블록 사이는 빈 줄, 이어진 체크 항목은 한 목록으로 붙인다. 빈 문단은 건너뛴다."""
    parts: list[str] = []
    prev = None
    for b in blocks:
        kind = b.get("type")
        if kind == "paragraph":
            text = _mark(b.get("text") or "", b.get("highlight"))
            if not text.strip():
                prev = kind
                continue
            parts.append(text)
        elif kind == "heading":
            text = _mark((b.get("text") or "").replace("\n", " "), b.get("highlight"))
            if text.strip():
                parts.append(f"## {text}")
        elif kind == "checklist":
            line = f"- [{'x' if b.get('checked') else ' '}] {(b.get('text') or '').replace(chr(10), ' ').strip()}"
            if prev == "checklist" and parts:
                parts[-1] += "\n" + line
            else:
                parts.append(line)
        elif kind == "table":
            table = _table(b.get("rows") or [])
            if table:
                parts.append(table)
        elif kind == "attachment":
            name = (b.get("name") or "첨부").replace("]", "\\]")
            parts.append(f"[{name}]({b.get('url') or ''})")
        prev = kind
    return "\n\n".join(parts)
