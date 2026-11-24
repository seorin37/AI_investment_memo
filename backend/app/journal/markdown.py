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


def _style(text: str, b: dict[str, Any]) -> str:
    """줄 전체 서식: 굵게 **, 기울임 *, 취소선 ~~ (밑줄은 Markdown 에 없어 글자만)."""
    if not text.strip():
        return text
    if b.get("strike"):
        text = f"~~{text}~~"
    if b.get("italic"):
        text = f"*{text}*"
    if b.get("bold"):
        text = f"**{text}**"
    return text


_LIST_PREFIX = {"dot": "- ", "dash": "- ", "num": "1. ", "quote": "> "}


def blocks_to_markdown(blocks: list[dict[str, Any]]) -> str:
    """문단 = 그대로, 제목 = '## '(작은 제목 level 2 = '### '), 체크 = '- [ ] / - [x]', 표 = Markdown 표,
    첨부 = [이름](주소), 강조 = ==글자==, 목록 = '- ' · '1. ' · '> ', 굵게·기울임·취소선 = ** · * · ~~.
    블록 사이는 빈 줄, 이어진 체크 항목·같은 목록은 한 목록으로 붙인다. 빈 문단은 건너뛴다."""
    parts: list[str] = []
    prev = None
    for b in blocks:
        kind = b.get("type")
        if kind == "paragraph":
            text = _style(_mark(b.get("text") or "", b.get("highlight")), b)
            if not text.strip():
                prev = kind
                continue
            style = b.get("list_style")
            if style in _LIST_PREFIX:
                line = _LIST_PREFIX[style] + text.replace("\n", " ")
                if prev == f"list:{style}" and parts:
                    parts[-1] += "\n" + line
                else:
                    parts.append(line)
                prev = f"list:{style}"
                continue
            parts.append(text)
        elif kind == "heading":
            text = _style(_mark((b.get("text") or "").replace("\n", " "), b.get("highlight")), b)
            if text.strip():
                parts.append(f"{'###' if b.get('level') == 2 else '##'} {text}")
        elif kind == "checklist":
            item = _style((b.get("text") or "").replace(chr(10), " ").strip(), b)
            line = f"- [{'x' if b.get('checked') else ' '}] {item}"
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
