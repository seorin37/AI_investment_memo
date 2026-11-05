"""수시공시 원문 → "항목 경로: 값" 목록 (run_events 2단계).

원문 형식은 두 가지이고, 둘 다 표 하나(또는 몇 개)에 항목과 값이 들어 있다.
- 거래소·기타 공시 (잠정실적, 배당, 공급계약 …): HTML. 값 칸은 `<span class="xforms_input">`.
- 주요사항보고서 (자사주, 유상증자 …): DART XML (정기보고서와 같은 형식). 값 칸은 `<TE>`·`<TU>`,
  `<TE ACODE="ACQ_OSTK">`처럼 항목 코드가 붙어 있다.

표를 rowspan·colspan을 펼친 격자로 바꾼 뒤, 값 칸마다
  경로 = 같은 행 왼쪽의 항목명들 (+ 한 행에 값이 여럿이면 위쪽 열 제목들)
을 만든다. 예) 배당: "3. 1주당 배당금(원) > 보통주식" → "160"
             잠정실적: "매출액 > 당해실적 > 당기실적" → "1,877,789"
"""

from __future__ import annotations

import re
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

from lxml import html as lxml_html

from .parser import _parse_tree, normalize_text


PARSER_VERSION = "events-1"  # 파서·항목 규칙을 바꾸면 올린다 (run_events가 이전 버전 행을 다시 처리)
VALUE_TAGS_XML = {"te", "tu"}
CELL_TAGS = {"td", "th", "te", "tu"}
LABEL_RE = re.compile(r"[0-9A-Za-z가-힣]")
PATH_SEP = " > "


class EventParseError(Exception):
    pass


@dataclass(frozen=True)
class Pair:
    path: str
    value: str
    acode: str = ""  # XML 값 칸의 항목 코드 (HTML은 빈 값)
    table: int = 0  # 문서 안 몇 번째 표인지 (0부터)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ParsedEvent:
    doc_format: str  # html | xml
    document_title: str
    pairs: list[Pair]
    text: str  # 본문 전체 텍스트 (청크·임베딩용)
    warnings: list[str] = field(default_factory=list)


@dataclass
class _Cell:
    text: str
    is_value: bool
    acode: str
    row: int  # 시작 행
    col: int  # 시작 열


def _tag(element) -> str:
    tag = element.tag
    return tag.lower() if isinstance(tag, str) else ""


def _hidden(element) -> bool:
    style = (element.get("style") or "").replace(" ", "").lower()
    return "display:none" in style


def _text(element) -> str:
    """숨김(display:none) 노드와 주석을 뺀 글자. <br>·칸 경계는 공백으로."""
    parts: list[str] = []

    def walk(node) -> None:
        if not isinstance(node.tag, str) or _hidden(node):
            return
        if node.text:
            parts.append(node.text)
        for child in node:
            walk(child)
            if child.tail:
                parts.append(child.tail)

    walk(element)
    return normalize_text(" ".join(parts))


def _is_value_cell(cell, doc_format: str) -> bool:
    if doc_format == "xml":
        return _tag(cell) in VALUE_TAGS_XML
    return any("xforms_input" in (node.get("class") or "") for node in cell.iter())


def _own_rows(table) -> list:
    """이 표에 직접 속한 행만 (안쪽 표의 행 제외)."""
    rows = []
    for node in table.iter():
        if _tag(node) != "tr":
            continue
        parent = node.getparent()
        while parent is not None and _tag(parent) != "table":
            parent = parent.getparent()
        if parent is table:
            rows.append(node)
    return rows


def _int_attr(element, name: str) -> int:
    for key in (name, name.upper(), name.lower()):
        value = element.get(key)
        if value:
            try:
                return max(1, int(value))
            except ValueError:
                return 1
    return 1


def build_grid(table, doc_format: str) -> list[list[_Cell | None]]:
    """rowspan·colspan을 펼친 격자. 같은 칸이 여러 위치에 같은 _Cell 객체로 들어간다."""
    grid: list[list[_Cell | None]] = []
    for r, row in enumerate(_own_rows(table)):
        while len(grid) <= r:
            grid.append([])
        c = 0
        for cell in row:
            if _tag(cell) not in CELL_TAGS or _hidden(cell):
                continue
            while c < len(grid[r]) and grid[r][c] is not None:
                c += 1
            info = _Cell(_text(cell), _is_value_cell(cell, doc_format), cell.get("ACODE", "") or "", r, c)
            rowspan, colspan = _int_attr(cell, "rowspan"), _int_attr(cell, "colspan")
            for dr in range(rowspan):
                while len(grid) <= r + dr:
                    grid.append([])
                target = grid[r + dr]
                while len(target) < c + colspan:
                    target.append(None)
                for dc in range(colspan):
                    target[c + dc] = info
            c += colspan
    return grid


def mark_rightmost_values(grid: list[list[_Cell | None]]) -> None:
    """값 칸 표시가 없는 문서용: 칸이 둘 이상인 행의 맨 오른쪽 칸(그 행에서 시작한 칸)을 값으로 본다.

    자회사 주요사항보고서를 모회사가 일반 HTML로 옮겨 올린 문서가 이렇다. 한 행에 값이 여럿인
    표(자기주식 보유현황 등)는 맨 오른쪽 값만 잡히지만, 카드에 쓰는 주요 항목은 대부분 "항목 | 값" 행이다.
    """
    for r, row in enumerate(grid):
        distinct: list[_Cell] = []
        for cell in row:
            if cell is not None and (not distinct or distinct[-1] is not cell):
                distinct.append(cell)
        if len(distinct) >= 2 and distinct[-1].row == r and distinct[-1].text:
            distinct[-1].is_value = True


def _is_label(cell: _Cell | None) -> bool:
    return cell is not None and not cell.is_value and bool(LABEL_RE.search(cell.text))


def _clean_label(text: str) -> str:
    return re.sub(r"^[-ㆍ·]\s*", "", text).strip()


def table_pairs(table, doc_format: str, table_index: int = 0, rightmost: bool = False) -> list[Pair]:
    grid = build_grid(table, doc_format)
    if rightmost:
        mark_rightmost_values(grid)
    pairs: list[Pair] = []
    done: set[int] = set()
    for r, row in enumerate(grid):
        value_cols = [c for c, cell in enumerate(row) if cell is not None and cell.is_value]
        if not value_cols:
            continue
        distinct_values = {id(row[c]) for c in value_cols}
        first_value_col = value_cols[0]
        for c in value_cols:
            cell = row[c]
            if id(cell) in done or cell.row != r:
                continue
            if c != cell.col:  # colspan으로 펼친 자리
                continue
            done.add(id(cell))
            labels: list[str] = []
            seen: set[int] = set()
            for left in row[:c]:
                if _is_label(left) and id(left) not in seen:
                    seen.add(id(left))
                    labels.append(_clean_label(left.text))
            headers: list[str] = []
            if len(distinct_values) > 1:
                for up in range(r - 1, -1, -1):
                    above = grid[up][c] if c < len(grid[up]) else None
                    if above is None or above.is_value:
                        continue
                    if above.col < first_value_col:
                        break
                    if _is_label(above) and id(above) not in seen:
                        seen.add(id(above))
                        headers.insert(0, _clean_label(above.text))
            if not labels and not headers:
                # 표 전체 폭의 설명 칸: 바로 위 행의 항목명("9. 기타 투자판단과 관련한 중요사항")을 쓴다.
                for up in range(r - 1, -1, -1):
                    above = grid[up][c] if c < len(grid[up]) else None
                    if above is not None and above.is_value:
                        break
                    if _is_label(above):
                        headers.append(_clean_label(above.text))
                        break
            path = PATH_SEP.join(labels + headers)
            pairs.append(Pair(path=path, value=cell.text, acode=cell.acode, table=table_index))
    return pairs


def _dedupe_paths(pairs: list[Pair]) -> list[Pair]:
    """같은 경로가 또 나오면 뒤의 것에 #2, #3 … 을 붙인다 (기간 '2026-07-01 ~ 2026-09-30' 같은 경우)."""
    counts: dict[str, int] = {}
    result = []
    for pair in pairs:
        counts[pair.path] = counts.get(pair.path, 0) + 1
        if counts[pair.path] > 1:
            pair = Pair(f"{pair.path}#{counts[pair.path]}", pair.value, pair.acode, pair.table)
        result.append(pair)
    return result


def _decode_html(raw: bytes) -> str:
    for encoding in ("utf-8", "cp949"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def detect_format(raw: bytes) -> str:
    head = raw[:500].lstrip().lower()
    if head.startswith(b"<?xml") or b"<document" in head:
        return "xml"
    return "html"


def parse_event_document(raw: bytes) -> ParsedEvent:
    doc_format = detect_format(raw)
    warnings: list[str] = []
    if doc_format == "xml":
        root, _, errors = _parse_tree(raw)
        if root is None:
            raise EventParseError("XML을 읽을 수 없습니다.")
        warnings.extend(errors[:5])
        name = root.find(".//DOCUMENT-NAME")
        title = normalize_text(name.text or "") if name is not None else ""
        body = root.find("BODY")
        text_root = body if body is not None else root
    else:
        root = lxml_html.document_fromstring(_decode_html(raw))
        title_node = root.find(".//title")
        title = normalize_text(title_node.text_content()) if title_node is not None else ""
        text_root = root.find("body")
        if text_root is None:
            text_root = root
    tables = [node for node in text_root.iter() if _tag(node) == "table"]
    pairs: list[Pair] = []
    for index, table in enumerate(tables):
        pairs.extend(table_pairs(table, doc_format, index))
    if not pairs and tables:
        pairs = [pair for index, table in enumerate(tables) for pair in table_pairs(table, doc_format, index, rightmost=True)]
        if pairs:
            doc_format = f"{doc_format}_plain"
            warnings.append("값 칸 표시가 없어 각 행의 맨 오른쪽 칸을 값으로 읽었습니다.")
    if not pairs:
        raise EventParseError("값 칸이 있는 표를 찾지 못했습니다.")
    return ParsedEvent(doc_format, title, _dedupe_paths(pairs), _text(text_root), warnings)


def read_event_zip(zip_path: Path, rcept_no: str) -> bytes:
    """원문 ZIP에서 본문 파일을 읽는다. `{rcept_no}.xml`이 없으면 첫 파일."""
    with zipfile.ZipFile(zip_path) as archive:
        names = archive.namelist()
        if not names:
            raise EventParseError(f"{zip_path.name}: 빈 ZIP입니다.")
        name = f"{rcept_no}.xml" if f"{rcept_no}.xml" in names else names[0]
        return archive.read(name)


def parse_event_zip(zip_path: Path, rcept_no: str) -> ParsedEvent:
    return parse_event_document(read_event_zip(zip_path, rcept_no))


def dump_pairs(pairs: list[Pair]) -> str:
    return "\n".join(f"[{p.table}] {p.path} = {p.value}" + (f"  ({p.acode})" if p.acode else "") for p in pairs)
