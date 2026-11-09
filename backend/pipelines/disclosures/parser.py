"""DART 정기보고서 원문(dart4.xsd XML)을 섹션 경로가 붙은 블록 목록으로 바꾼다.

구조: BODY → SECTION-1/2/3(TITLE) → P / TABLE / TABLE-GROUP(TITLE) / LIBRARY(투명 래퍼)
- 섹션 제목은 하드코딩하지 않는다. 제외 여부는 설정의 TITLE 정규식으로만 판단한다.
- 1열짜리 TABLE은 레이아웃용(주석 본문 상자, 표 제목·단위 줄)으로 보고 안을 그대로 펼친다.
- 2열 이상 TABLE은 ROWSPAN·COLSPAN을 펼친 격자로 만들고 행마다 `열헤더: 값 | …` 텍스트로 만든다.

DART 원문은 본문의 `<`·`&`를 이스케이프하지 않은 채 오는 경우가 많다(예: `<당기말>`, `R&D`). 그대로 lxml 복구 모드로
읽으면 가짜 태그가 닫히지 않아 뒤의 섹션 전체가 TABLE·P 안으로 들어가거나 `&` 뒤 글자가 사라진다. 그래서 파싱 전에
sanitize_xml()로 정리하고, 파싱 후 구조 품질을 검사해 문제가 남은 문서는 ParseError로 실패시킨다(조용히 적재하지 않는다).
"""

from __future__ import annotations

import html.entities
import re
import unicodedata
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

from lxml import etree


PARSER_VERSION = "1.1"

SECTION_TAGS = {"SECTION-1", "SECTION-2", "SECTION-3"}
CELL_TAGS = {"TD", "TH", "TE", "TU"}
ROW_CONTAINERS = {"THEAD", "TBODY", "TFOOT"}
SKIP_TAGS = {"PGBRK", "IMAGE", "IMG", "IMG-CAPTION", "COLGROUP", "COL", "TITLE"}
FRONT_MATTER_TAGS = {"COVER"}
HIDDEN_ATTRS = {("HIDDEN", "Y"), ("VISIBLE", "N"), ("DISPLAY", "N"), ("ADISPLAY", "N")}

UNIT_RE = re.compile(r"단위\s*[:：]")
UNIT_PHRASE_RE = re.compile(r"\(?\s*단위\s*[:：][^)\n]*\)?")
_SPACE_RE = re.compile(r"\s+")

# dart4.xsd 문서에서 쓰는 요소 이름 (40건 원문 실측 + 표준 HTML형 표 요소). 이 밖의 `<`는 본문 글자로 본다.
DART_TAGS = frozenset(
    {
        "DOCUMENT", "DOCUMENT-NAME", "FORMULA-VERSION", "COMPANY-NAME", "SUMMARY", "EXTRACTION", "BODY", "COVER",
        "COVER-TITLE", "SECTION-1", "SECTION-2", "SECTION-3", "TITLE", "LIBRARY", "TABLE-GROUP", "TABLE", "COLGROUP",
        "COL", "THEAD", "TBODY", "TFOOT", "TR", "TD", "TH", "TE", "TU", "P", "SPAN", "A", "BR", "PGBRK", "IMAGE", "IMG",
        "IMG-CAPTION", "DIV", "CORRECTION",
    }
)
_TAG_ALT = b"|".join(re.escape(name.encode()) for name in sorted(DART_TAGS, key=len, reverse=True))
# 태그로 인정하는 `<`: DART 태그 이름 뒤에 `>`·`/>` 또는 속성(`이름=`)이 오는 경우만. `<A 등급>`·`<P 1>` 같은 본문은 글자로 본다.
_ATTR_START = rb"\s+[A-Za-z_][\w.:-]*\s*="
# 속성 없는 `<A>`도 글자로 본다. DART 링크는 늘 속성(REFNO·HREF)이 있고, 맨 `<A>`는 본문 글자다
# (SP삼화 제품 코드 `TP FLEX BLACK<A>#(KJ)…` — 닫히지 않은 링크로 읽으면 표 구조가 깨진다)
_STRAY_LT_RE = re.compile(rb"<(?=A\s*>)|<(?!(?:" + _TAG_ALT + rb")(?=\s*/?>|" + _ATTR_START + rb")|/(?:" + _TAG_ALT + rb")\s*>|[!?])")
_TAG_NAME_AT_RE = re.compile(rb"(/?)([A-Za-z][\w.:-]*)")
_CDATA_RE = re.compile(rb"(<!\[CDATA\[.*?\]\]>)", re.S)
_NAMED_ENTITY_RE = re.compile(rb"&([A-Za-z][A-Za-z0-9]*);")
_BARE_AMP_RE = re.compile(rb"&(?!#[0-9]+;|#x[0-9A-Fa-f]+;|(?:amp|lt|gt|quot|apos);)")
_START_TAG_RE = re.compile(rb"<(" + _TAG_ALT + rb")(\s[^<>]*?)(/?)>")
_WELL_FORMED_ATTRS_RE = re.compile(rb'(?:\s+[A-Za-z_][\w.:-]*\s*=\s*"[^"]*")*\s*')
_ATTR_RE = re.compile(rb'\s*([A-Za-z_][\w.:-]*)\s*=\s*"(.*?)"(?=\s+[A-Za-z_][\w.:-]*\s*=|\s*$)', re.S)
_XML_ENTITIES = {b"amp", b"lt", b"gt", b"quot", b"apos"}



class ParseError(Exception):
    """원문 구조를 해석할 수 없음. quality에 실패 시점까지의 품질 지표를 담는다."""

    def __init__(self, message: str, quality: dict | None = None):
        super().__init__(message)
        self.quality = quality or {}


@dataclass
class Block:
    section: list[str]
    block_type: str  # "text" | "table"
    text: str = ""
    caption: str = ""
    unit: str = ""
    header: list[str] = field(default_factory=list)
    rows: list[str] = field(default_factory=list)


@dataclass
class ParsedDocument:
    rcept_no: str
    document_name: str
    company_name: str
    corp_code: str
    period_from: str | None
    period_to: str | None
    blocks: list[Block]
    parser_version: str = PARSER_VERSION
    quality: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ParsedDocument":
        blocks = [Block(**block) for block in data["blocks"]]
        return cls(**{**data, "blocks": blocks})


def normalize_text(value: str) -> str:
    """NFC 정규화, 전각·특수 공백을 일반 공백으로, 반복 공백을 하나로 줄인다."""
    value = unicodedata.normalize("NFC", value)
    value = value.replace("　", " ").replace("\xa0", " ").replace("​", "")
    return _SPACE_RE.sub(" ", value).strip()


def _is_hidden(element) -> bool:
    return any(element.get(name) == value for name, value in HIDDEN_ATTRS)


def _text_of(element) -> str:
    return normalize_text("".join(element.itertext()))


def _title_of(element) -> str:
    title = element.find("TITLE")
    return _text_of(title) if title is not None else ""


class _Walker:
    def __init__(self, exclude_patterns: list[str], caption_max_chars: int, caption_max_blocks: int):
        self.exclude = [re.compile(pattern) for pattern in exclude_patterns]
        self.caption_max_chars = caption_max_chars
        self.caption_max_blocks = caption_max_blocks
        self.blocks: list[Block] = []

    def excluded(self, title: str) -> bool:
        return any(pattern.search(title) for pattern in self.exclude)

    def emit_text(self, path: list[str], text: str) -> None:
        if text:
            self.blocks.append(Block(section=list(path), block_type="text", text=text))

    def walk(self, element, path: list[str]) -> None:
        for child in element:
            tag = child.tag
            if not isinstance(tag, str) or tag in SKIP_TAGS or _is_hidden(child):
                continue
            if tag in FRONT_MATTER_TAGS:
                continue
            if tag in SECTION_TAGS or tag == "TABLE-GROUP":
                title = _title_of(child)
                if title and self.excluded(title):
                    continue
                self.walk(child, path + [title] if title else path)
            elif tag == "LIBRARY":
                self.walk(child, path)
            elif tag == "P":
                self.emit_text(path, _text_of(child))
            elif tag == "TABLE":
                self.table(child, path)
            elif child.find(".//P") is not None or child.find(".//TABLE") is not None:
                self.walk(child, path)
            else:
                self.emit_text(path, _text_of(child))

    # ── 표 ──────────────────────────────────────────────
    @staticmethod
    def _rows(table) -> list[tuple[object, bool]]:
        """(TR, 헤더 영역 여부) 목록. 중첩 TABLE의 행은 포함하지 않는다."""
        rows = []
        for child in table:
            if not isinstance(child.tag, str) or _is_hidden(child):
                continue
            if child.tag in ROW_CONTAINERS:
                rows.extend((tr, child.tag == "THEAD") for tr in child if tr.tag == "TR" and not _is_hidden(tr))
            elif child.tag == "TR":
                rows.append((child, False))
        return rows

    @staticmethod
    def _grid(rows) -> list[list[tuple[int, str, str] | None]]:
        """ROWSPAN·COLSPAN을 펼친 격자. 칸 = (원본 셀 id, 텍스트, 태그)."""
        grid: list[list] = []
        pending: dict[tuple[int, int], tuple[int, str, str]] = {}
        cell_id = 0
        for r, (tr, _) in enumerate(rows):
            line: list = []
            c = 0
            cells = [cell for cell in tr if isinstance(cell.tag, str) and cell.tag in CELL_TAGS and not _is_hidden(cell)]
            for cell in cells:
                while (r, c) in pending:
                    line.append(pending.pop((r, c)))
                    c += 1
                try:
                    rowspan = max(1, int(cell.get("ROWSPAN", "1")))
                    colspan = max(1, int(cell.get("COLSPAN", "1")))
                except ValueError:
                    rowspan = colspan = 1
                value = (cell_id, _text_of(cell), cell.tag)
                cell_id += 1
                for dc in range(colspan):
                    line.append(value)
                    for dr in range(1, rowspan):
                        pending[(r + dr, c + dc)] = value
                c += colspan
            while (r, c) in pending:
                line.append(pending.pop((r, c)))
                c += 1
            grid.append(line)
        width = max((len(line) for line in grid), default=0)
        return [line + [None] * (width - len(line)) for line in grid]

    def table(self, table, path: list[str]) -> None:
        rows = self._rows(table)
        if not rows:
            return
        grid = self._grid(rows)
        width = len(grid[0]) if grid else 0
        if width <= 1:
            # 레이아웃 표: 셀 안의 문단·중첩 표를 그대로 펼친다.
            for tr, _ in rows:
                for cell in tr:
                    if not isinstance(cell.tag, str) or cell.tag not in CELL_TAGS or _is_hidden(cell):
                        continue
                    if cell.find(".//P") is not None or cell.find(".//TABLE") is not None:
                        self.walk(cell, path)
                    else:
                        self.emit_text(path, _text_of(cell))
            return
        self.data_table(grid, [is_head for _, is_head in rows], path)

    def data_table(self, grid, head_flags: list[bool], path: list[str]) -> None:
        lead_lines: list[str] = []
        # 표 맨 위의 머리말 행(표 제목·단위)은 표 본문에서 뺀다:
        # 전폭 셀 하나짜리 행, 또는 셀 2개 이하에 그중 하나가 `단위 :` 문구인 행 (예: `당반기말 | (단위 : 백만원)`)
        while grid:
            texts: list[str] = []
            for cell in grid[0]:
                if cell is not None and cell[1] and (not texts or texts[-1] != cell[1]):
                    texts.append(cell[1])
            full_width = len({cell[0] for cell in grid[0] if cell is not None}) == 1 and len(texts) == 1
            unit_row = 1 <= len(texts) <= 2 and any(UNIT_RE.search(text) for text in texts)
            if not (full_width or unit_row):
                break
            lead_lines.extend(texts)
            grid, head_flags = grid[1:], head_flags[1:]
        if not grid:
            for line in lead_lines:
                self.emit_text(path, line)
            return

        head_count = 0
        if any(head_flags):
            while head_count < len(grid) and head_flags[head_count]:
                head_count += 1
        else:
            while head_count < len(grid) and all(cell is None or cell[2] == "TH" for cell in grid[head_count]):
                head_count += 1
            if head_count == len(grid):
                head_count = 0
        width = len(grid[0])
        header: list[str] = []
        for col in range(width):
            parts: list[str] = []
            for row in grid[:head_count]:
                cell = row[col]
                if cell is not None and cell[1] and (not parts or parts[-1] != cell[1]):
                    parts.append(cell[1])
            header.append(" / ".join(parts))

        rendered: list[str] = []
        for row in grid[head_count:]:
            parts = []
            previous_origin = None
            for col, cell in enumerate(row):
                if cell is None or cell[0] == previous_origin:
                    continue
                previous_origin = cell[0]
                if not cell[1]:
                    continue
                parts.append(f"{header[col]}: {cell[1]}" if header[col] else cell[1])
            if parts:
                rendered.append(" | ".join(parts))
        if not rendered:
            return

        caption_lines, unit = self._take_caption(path)
        for line in lead_lines:
            if UNIT_RE.search(line) and not unit:
                unit = line
            else:
                caption_lines.append(line)
        self.blocks.append(
            Block(
                section=list(path),
                block_type="table",
                caption=" / ".join(caption_lines),
                unit=unit,
                header=[h for h in header if h] if any(header) else [],
                rows=rendered,
            )
        )

    def _take_caption(self, path: list[str]) -> tuple[list[str], str]:
        """표 바로 앞의 짧은 문단(같은 섹션)을 표 제목·단위로 가져온다."""
        taken: list[str] = []
        unit = ""
        while (
            self.blocks
            and len(taken) < self.caption_max_blocks
            and self.blocks[-1].block_type == "text"
            and self.blocks[-1].section == path
            and len(self.blocks[-1].text) <= self.caption_max_chars
        ):
            taken.insert(0, self.blocks.pop().text)
        caption: list[str] = []
        for line in taken:
            if UNIT_RE.search(line) and not unit:
                unit = line
            else:
                caption.append(line)
        if not unit and self.blocks and self.blocks[-1].block_type == "text" and self.blocks[-1].section == path:
            # 긴 문단 끝에 붙은 단위 문구는 문단은 그대로 두고 단위만 가져온다.
            found = UNIT_PHRASE_RE.findall(self.blocks[-1].text)
            if found:
                unit = found[-1].strip()
        return caption, unit


def _document_meta(root) -> dict:
    period_from = period_to = None
    for element in root.iter("TU", "TD", "TE"):
        aunit = element.get("AUNIT")
        if aunit == "PERIODFROM" and period_from is None:
            period_from = element.get("AUNITVALUE")
        elif aunit == "PERIODTO" and period_to is None:
            period_to = element.get("AUNITVALUE")
        if period_from and period_to:
            break
    company = root.find("COMPANY-NAME")
    return {
        "document_name": _text_of(root.find("DOCUMENT-NAME")) if root.find("DOCUMENT-NAME") is not None else "",
        "company_name": _text_of(company) if company is not None else "",
        "corp_code": (company.get("AREGCIK") or "") if company is not None else "",
        "period_from": period_from,
        "period_to": period_to,
    }


def _sanitize_text_segment(segment: bytes, stats: dict, escaped_open: set, escaped_close: set) -> bytes:
    def named(match: re.Match) -> bytes:
        name = match.group(1)
        if name in _XML_ENTITIES:
            return match.group(0)
        stats["html_entities"] += 1
        chars = html.entities.html5.get(name.decode("ascii") + ";")
        return b"".join(b"&#%d;" % ord(c) for c in chars) if chars else b"&amp;" + name + b";"

    segment = _NAMED_ENTITY_RE.sub(named, segment)
    segment, count = _BARE_AMP_RE.subn(b"&amp;", segment)
    stats["bare_amp"] += count

    def stray(match: re.Match) -> bytes:
        stats["stray_lt"] += 1
        name = _TAG_NAME_AT_RE.match(segment, match.end())
        if name:  # 태그처럼 생긴 글자(`<KB 금융>`, `</B>` 등)는 이름을 남겨 둔다
            stats["stray_tag_like"] += 1
            (escaped_close if name.group(1) else escaped_open).add(name.group(2).decode("ascii", "replace"))
        return b"&lt;"

    segment = _STRAY_LT_RE.sub(stray, segment)

    def repair_tag(match: re.Match) -> bytes:
        attrs = match.group(2)
        if _WELL_FORMED_ATTRS_RE.fullmatch(attrs):
            return match.group(0)  # 따옴표 짝 수만 보면 `ENG="… CVA ("PD")"`처럼 짝수로 깨진 값을 놓친다
        body = attrs.rstrip()
        parts = list(_ATTR_RE.finditer(body))
        if not parts or b"".join(m.group(0) for m in parts) != body:
            return match.group(0)  # 해석할 수 없으면 손대지 않는다 (파싱 후 복구 오류로 잡힌다)
        if not any(b'"' in m.group(2) for m in parts):
            return match.group(0)  # 빈 값(ENG="") 등 정상 태그
        stats["broken_attrs"] += 1
        rebuilt = b"".join(b' %s="%s"' % (m.group(1), m.group(2).replace(b'"', b"&quot;")) for m in parts)
        return b"<" + match.group(1) + rebuilt + match.group(3) + b">"

    return _START_TAG_RE.sub(repair_tag, segment)


def sanitize_xml(xml_bytes: bytes) -> tuple[bytes, dict]:
    """DART 원문의 이스케이프되지 않은 글자를 XML로 읽을 수 있게 고친다. (정리된 바이트, 치환 통계) 반환.

    1) XML에 없는 HTML 이름 엔티티(&reg; 등)는 숫자 참조로, 모르는 이름은 글자 그대로(&amp;…)
    2) 엔티티가 아닌 `&`(R&D 등)는 `&amp;`
    3) DART 태그로 시작하지 않는 `<`(`<당기말>`, `<ACI 세미나>`, `<A 등급>` 등)는 `&lt;`
    4) 시작 태그 안 속성 값의 따옴표 짝이 깨졌으면(`ENG=""Snow…"`, `ENG="… "" HEIGHT=`) 값 안의 `"`를 `&quot;`로 바꿔 다시 쓴다
    CDATA 구간은 그대로 둔다. 통계의 unknown_markup은 글자로 바꾼 이름 중 닫는 태그(`</X>`)도 있는 것 —
    본문 글자가 아니라 화이트리스트에 없는 실제 마크업일 가능성이 높아 parse_xml이 문서를 실패시킨다.
    """
    stats = {"html_entities": 0, "bare_amp": 0, "broken_attrs": 0, "stray_lt": 0, "stray_tag_like": 0}
    escaped_open: set[str] = set()
    escaped_close: set[str] = set()
    parts = _CDATA_RE.split(xml_bytes)
    for i in range(0, len(parts), 2):  # 홀수 번째는 CDATA
        parts[i] = _sanitize_text_segment(parts[i], stats, escaped_open, escaped_close)
    stats["escaped_tag_names"] = sorted(escaped_open | escaped_close)
    stats["unknown_markup"] = sorted(escaped_close)
    return b"".join(parts), stats


def _parse_tree(xml_bytes: bytes):
    xml_bytes, stats = sanitize_xml(xml_bytes)
    parser = etree.XMLParser(recover=True, huge_tree=True, remove_comments=True, resolve_entities=False, no_network=True)
    root = etree.fromstring(xml_bytes, parser)
    return root, stats, [f"{e.line}: {e.message.strip()}" for e in parser.error_log]


def nested_section_count(root) -> int:
    """TABLE·P·셀 안에 들어간 SECTION 수 (원문 깨짐으로 섹션이 엉뚱한 곳에 들어간 신호)."""
    return sum(
        1
        for el in root.iter("SECTION-1", "SECTION-2", "SECTION-3")
        if any(a.tag in ("TABLE", "P", "TD", "TE", "TH", "TU") for a in el.iterancestors())
    )


def read_meta(xml_bytes: bytes) -> dict:
    """문서명·회사·기간만 읽는다 (품질 검사 없음). --from-zip 목록 구성용."""
    root, _, _ = _parse_tree(xml_bytes)
    if root is None:
        raise ParseError("XML을 해석할 수 없습니다.")
    return _document_meta(root)


def parse_xml(
    xml_bytes: bytes,
    rcept_no: str,
    exclude_patterns: list[str],
    caption_max_chars: int = 100,
    caption_max_blocks: int = 4,
    max_recover_errors: int | None = 0,
) -> ParsedDocument:
    """원문을 정리·파싱한다. 다음이면 ParseError(quality 포함): TABLE·P 안 섹션, 화이트리스트 밖 마크업(unknown_markup),
    복구 오류가 max_recover_errors 초과(None이면 오류 수 무시)."""
    root, stats, errors = _parse_tree(xml_bytes)
    if root is None:
        raise ParseError(f"{rcept_no}: XML을 해석할 수 없습니다.", stats)
    quality = {**stats, "recover_errors": len(errors), "recover_error_samples": errors[:5], "nested_sections": nested_section_count(root)}
    if quality["nested_sections"] or quality["unknown_markup"]:
        raise ParseError(
            f"{rcept_no}: XML 구조 이상 — TABLE·P 안 섹션 {quality['nested_sections']}개, "
            f"화이트리스트 밖 마크업 {quality['unknown_markup'][:5]} (첫 복구 오류: {errors[:2]})",
            quality,
        )
    if max_recover_errors is not None and len(errors) > max_recover_errors:
        raise ParseError(f"{rcept_no}: XML 복구 오류 {len(errors)}건 (허용 {max_recover_errors}): {errors[:3]}", quality)
    body = root.find("BODY")
    if body is None:
        raise ParseError(f"{rcept_no}: BODY 요소가 없습니다.", quality)
    walker = _Walker(exclude_patterns, caption_max_chars, caption_max_blocks)
    walker.walk(body, [])
    if not walker.blocks:
        raise ParseError(f"{rcept_no}: 추출된 본문이 없습니다.", quality)
    quality["max_block_chars"] = max(len(b.text) + sum(len(r) for r in b.rows) for b in walker.blocks)
    return ParsedDocument(rcept_no=rcept_no, blocks=walker.blocks, quality=quality, **_document_meta(root))


def read_main_xml(zip_path: Path, rcept_no: str) -> bytes:
    """ZIP에서 본문 XML(`{rcept_no}.xml`)만 읽는다. 첨부(감사보고서 등)는 쓰지 않는다."""
    with zipfile.ZipFile(zip_path) as archive:
        name = f"{rcept_no}.xml"
        if name not in archive.namelist():
            raise ParseError(f"{zip_path.name}에 본문 {name}이 없습니다.")
        return archive.read(name)


def section_label(path: list[str]) -> str:
    return " > ".join(path) if path else "(본문)"
