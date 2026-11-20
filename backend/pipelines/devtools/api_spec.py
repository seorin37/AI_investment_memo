"""docs/api-spec.md 생성기 (api_gap.py --write-spec 이 부른다).

입력
- OpenAPI(JSON): 테스트 서버(worktree 8020)의 /openapi.json — 요청 파라미터·본문, 응답 스키마, 설명
- backend/app/**/routes.py (ast): 인증(get_current_user) 여부, 라우트·헬퍼에서 던지는 HTTPException 코드
- frontend/src/api/{real,board,stocks}.ts: 프론트 함수 ↔ 경로, index.ts MOCK_ONLY
- frontend/src/api/types.ts · src/types/models.ts: 응답 형식(mock 함수 기준) 필드표·예시

사람이 채우는 칸: 현황표의 '담당'·'비고'. 다시 생성하면 기존 문서의 같은 (메서드, 경로) 행에서 값을 가져온다.
경로가 사라졌는데 사람이 적은 값이 있으면 상태 '목록에서 빠짐'으로 남긴다(값을 잃지 않게).
"""

from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[3]
APP_DIR = REPO / "backend" / "app"
FRONT_API = REPO / "frontend" / "src" / "api"
FRONT_MODELS = REPO / "frontend" / "src" / "types" / "models.ts"
API_PREFIX = "/api/v1"

TABLE_START = "<!-- api-table:start (담당·비고 칸만 손으로 고치세요. 나머지 칸은 다시 생성하면 덮어씁니다) -->"
TABLE_END = "<!-- api-table:end -->"
COLUMNS = ["영역", "메서드", "경로", "프론트 함수", "상태", "담당", "비고"]
HUMAN = ("담당", "비고")

TAG_AREA = {
    "auth": "인증", "stocks": "종목", "memo-board": "메모 보드", "ai-updates": "AI 업데이트",
    "credits": "크레딧", "account": "계정·설정", "marketdata": "시세·뉴스·기업", "trash": "휴지통", "home": "홈 위젯",
}
SEGMENT_AREA = {
    "journal": "투자 기록", "insights": "인사이트", "calendar": "캘린더", "data": "데이터", "feedback": "피드백",
    "mcp": "MCP", "files": "파일", "ai": "AI 통계", "memos": "메모 보드", "updates": "AI 업데이트",
    "checklist-items": "홈 위젯", "price-conditions": "홈 위젯", "settings": "계정·설정", "me": "계정·설정",
    "home": "계정·설정", "trash": "휴지통", "news": "시세·뉴스·기업", "market": "시세·뉴스·기업", "stocks": "종목",
}
AREA_ORDER = ["인증", "계정·설정", "종목", "시세·뉴스·기업", "메모 보드", "AI 업데이트", "홈 위젯", "휴지통", "크레딧",
              "투자 기록", "캘린더", "인사이트", "AI 통계", "데이터", "피드백", "MCP", "파일", "기타"]
ERROR_TEXT = {
    400: "잘못된 요청", 401: "인증 필요 · 토큰 만료/폐기 (프론트는 /auth/refresh 를 한 번 시도)",
    403: "권한 없음 · 쿠키 세션의 쓰기 요청에서 CSRF 불일치", 404: "대상 없음 (다른 사용자 것 포함)",
    409: "지금 상태와 충돌", 422: "요청 검증 실패 (FastAPI 형식 detail 배열)", 503: "서버 설정·의존 서비스 문제",
}


# ─────────────────────────────────────────────── 백엔드 소스 (ast)
@dataclass
class RouteMeta:
    auth: bool = False
    codes: set[int] = field(default_factory=set)
    module: str = ""


def scan_routes() -> dict[str, RouteMeta]:
    """라우트 함수 이름 → 인증 여부·에러 코드. 같은 모듈의 헬퍼(_not_found 등)가 던지는 코드도 한 단계 따라간다."""
    out: dict[str, RouteMeta] = {}
    for path in sorted(APP_DIR.rglob("routes.py")):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        funcs = {n.name: n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}

        def codes_of(node: ast.AST, seen: set[str]) -> set[int]:
            text = ast.get_source_segment(source, node) or ""
            found = {int(c) for c in re.findall(r"HTTPException\(\s*(\d{3})", text)}
            found |= {int(c) for c in re.findall(r"status_code\s*=\s*(\d{3})", text) if int(c) >= 400}
            for call in ast.walk(node):
                if isinstance(call, ast.Call) and isinstance(call.func, ast.Name):
                    name = call.func.id
                    if name in funcs and name not in seen and funcs[name] is not node:
                        found |= codes_of(funcs[name], seen | {name})
            return found

        for name, node in funcs.items():
            if not any(isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute)
                       and d.func.attr in {"get", "post", "put", "patch", "delete", "api_route"}
                       for d in node.decorator_list):
                continue
            text = ast.get_source_segment(source, node) or ""
            meta = out.setdefault(name, RouteMeta(module=str(path.relative_to(REPO))))
            meta.auth = meta.auth or "get_current_user" in text
            meta.codes |= codes_of(node, {name})
    return out


# ─────────────────────────────────────────────── 프론트 타입 (TypeScript, 단순 파서)
def _strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"//[^\n]*", "", text)


def _match_brace(text: str, start: int) -> int:
    depth = 0
    for i in range(start, len(text)):
        if text[i] in "{<([":
            depth += 1
        elif text[i] in "}>)]":
            depth -= 1
            if depth == 0:
                return i
    return len(text) - 1


def _split_top(text: str, seps: str) -> list[str]:
    parts, depth, cur = [], 0, []
    for ch in text:
        if ch in "{<([":
            depth += 1
        elif ch in "}>)]":
            depth -= 1
        if depth == 0 and ch in seps:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    parts.append("".join(cur))
    return [p.strip() for p in parts if p.strip()]


@dataclass
class TsField:
    name: str
    type: str
    optional: bool


class TsTypes:
    def __init__(self, *files: Path) -> None:
        self.interfaces: dict[str, tuple[list[str], list[TsField]]] = {}
        self.aliases: dict[str, str] = {}
        for f in files:
            self._parse(_strip_comments(f.read_text(encoding="utf-8")))

    def _parse(self, text: str) -> None:
        for m in re.finditer(r"export\s+interface\s+(\w+)(?:<[^>{]*>)?(?:\s+extends\s+([^{]+))?\s*\{", text):
            end = _match_brace(text, m.end() - 1)
            parents = [p.strip() for p in (m.group(2) or "").split(",") if p.strip()]
            self.interfaces[m.group(1)] = (parents, self.fields(text[m.end():end]))
        for m in re.finditer(r"export\s+type\s+(\w+)(?:<[^>=]*>)?\s*=", text):
            i, depth = m.end(), 0
            while i < len(text):
                ch = text[i]
                if ch in "{<([":
                    depth += 1
                elif ch in "}>)]":
                    depth -= 1
                elif ch == ";" and depth == 0:
                    break
                i += 1
            self.aliases[m.group(1)] = " ".join(text[m.end():i].split())

    @staticmethod
    def fields(body: str) -> list[TsField]:
        out = []
        for part in _split_top(body, ";\n"):
            m = re.match(r"(\w+)(\?)?\s*:\s*(.+)$", part, re.S)
            if m:
                out.append(TsField(m.group(1), " ".join(m.group(3).split()).rstrip(","), bool(m.group(2))))
        return out

    def interface_fields(self, name: str) -> list[TsField] | None:
        if name not in self.interfaces:
            return None
        parents, own = self.interfaces[name]
        merged: dict[str, TsField] = {}
        for parent in parents:
            for f in self.interface_fields(parent.split("<")[0]) or []:
                merged[f.name] = f
        for f in own:
            merged[f.name] = f
        return list(merged.values())

    def resolve_fields(self, type_text: str) -> tuple[str, list[TsField]] | None:
        """응답 타입에서 필드표를 만들 대상 (배열·Partial·Pick 등을 벗겨 이름 하나로)."""
        t = type_text.strip()
        t = re.sub(r"\[\]$", "", t)
        while True:
            m = re.match(r"(?:Partial|Required|Readonly|NonNullable|DeepPartial)<(.+)>$", t)
            if not m:
                break
            t = m.group(1).strip()
        m = re.match(r"(?:Pick|Omit)<\s*(\w+)\s*,", t)
        if m:
            t = m.group(1)
        if t.startswith("{"):
            return "(익명 객체)", self.fields(t[1:-1])
        if "&" in t:
            name = t.split("&")[0].strip()
            extra = re.search(r"\{(.*)\}", t)
            base = self.interface_fields(name) or []
            return t, base + (self.fields(extra.group(1)) if extra else [])
        fields = self.interface_fields(t)
        if fields is not None:
            return t, fields
        if t in self.aliases:
            alias = self.aliases[t]
            if alias.startswith("{") or "&" in alias:
                return self.resolve_fields(alias)
        return None

    def example(self, type_text: str, depth: int = 0) -> Any:
        t = " ".join(type_text.split()).strip()
        if depth > 3:
            return "…"
        parts = _split_top(t, "|")
        if len(parts) > 1:
            non_null = [p for p in parts if p not in ("null", "undefined")]
            return self.example(non_null[0] if non_null else "null", depth)
        if t.endswith("[]"):
            return [self.example(t[:-2], depth + 1)]
        m = re.match(r"(?:Array|ReadonlyArray)<(.+)>$", t)
        if m:
            return [self.example(m.group(1), depth + 1)]
        m = re.match(r"Record<\s*([^,]+),\s*(.+)>$", t)
        if m:
            key = self.example(m.group(1), depth + 1)
            return {str(key) if not isinstance(key, (dict, list)) else "key": self.example(m.group(2), depth + 1)}
        m = re.match(r"(?:Partial|Required|Readonly|NonNullable|DeepPartial|Pick|Omit)<\s*(\w+)", t)
        if m:
            t = m.group(1)
        if re.match(r"^'.*'$|^\".*\"$", t):
            return t[1:-1]
        if re.match(r"^-?\d+(\.\d+)?$", t):
            return float(t) if "." in t else int(t)
        prim = {"string": "string", "number": 0, "boolean": False, "null": None, "undefined": None,
                "ISODate": "2026-11-20T09:00:00+09:00", "unknown": None, "any": None, "Blob": "(file)", "void": None}
        if t in prim:
            return prim[t]
        if t.startswith("{"):
            return {f.name: self.example(f.type, depth + 1) for f in self.fields(t[1:-1])}
        fields = self.interface_fields(t)
        if fields is not None:
            return {f.name: self.example(f.type, depth + 1) for f in fields}
        if t in self.aliases:
            return self.example(self.aliases[t], depth)
        return t


def api_signatures() -> dict[str, tuple[str, str]]:
    """Api 인터페이스: 함수 이름 → (시그니처, 응답 타입)."""
    text = _strip_comments((FRONT_API / "types.ts").read_text(encoding="utf-8"))
    m = re.search(r"export\s+interface\s+Api\s*\{", text)
    body = text[m.end():_match_brace(text, m.end() - 1)] if m else ""
    out = {}
    for line in body.splitlines():
        mm = re.match(r"\s*(\w+)\((.*)\):\s*Promise<(.+)>;\s*$", line)
        if mm:
            out[mm.group(1)] = (f"{mm.group(1)}({mm.group(2)}): Promise<{mm.group(3)}>", mm.group(3).strip())
    return out


# ─────────────────────────────────────────────── OpenAPI
def _ref_name(ref: str) -> str:
    return ref.rsplit("/", 1)[-1]


class OpenApi:
    def __init__(self, spec: dict) -> None:
        self.spec = spec
        self.schemas = spec.get("components", {}).get("schemas", {})

    def resolve(self, schema: dict | None) -> dict:
        """$ref 를 따라가고, `X | null` (anyOf/oneOf) 이면 null 이 아닌 첫 갈래를 쓴다."""
        schema = schema or {}
        for _ in range(10):
            if "$ref" in schema:
                schema = self.schemas.get(_ref_name(schema["$ref"]), {})
                continue
            variants = schema.get("anyOf") or schema.get("oneOf")
            non_null = [v for v in variants or [] if v.get("type") != "null"]
            if len(non_null) == 1:
                schema = non_null[0]
                continue
            break
        return schema

    def type_text(self, schema: dict | None) -> str:
        schema = schema or {}
        if "$ref" in schema:
            return _ref_name(schema["$ref"])
        for key in ("anyOf", "oneOf"):
            if key in schema:
                return " | ".join(self.type_text(s) for s in schema[key])
        if "const" in schema:
            return json.dumps(schema["const"], ensure_ascii=False)
        if "enum" in schema:
            return " | ".join(json.dumps(v, ensure_ascii=False) for v in schema["enum"])
        t = schema.get("type")
        if t == "array":
            return f"{self.type_text(schema.get('items'))}[]"
        if t == "object" and "additionalProperties" in schema and isinstance(schema["additionalProperties"], dict):
            return f"object<string, {self.type_text(schema['additionalProperties'])}>"
        if t == "string" and schema.get("format"):
            return f"string({schema['format']})"
        return t or "any"

    @staticmethod
    def constraints(schema: dict) -> str:
        bits = []
        for key, label in (("minLength", "최소 길이"), ("maxLength", "최대 길이"), ("minimum", "≥"), ("maximum", "≤"),
                           ("exclusiveMinimum", ">"), ("exclusiveMaximum", "<"), ("minItems", "최소 개수"),
                           ("maxItems", "최대 개수"), ("pattern", "형식")):
            if key in schema:
                bits.append(f"{label} `{schema[key]}`" if key == "pattern" else f"{label} {schema[key]}")
        if "default" in schema:
            bits.append(f"기본 `{json.dumps(schema['default'], ensure_ascii=False)}`")
        for sub in schema.get("anyOf", []):
            nested = OpenApi.constraints(sub)
            if nested:
                bits.append(nested)
        return ", ".join(bits)

    def property_rows(self, schema: dict | None, prefix: str = "", depth: int = 0) -> list[list[str]]:
        schema = self.resolve(schema)
        rows: list[list[str]] = []
        required = set(schema.get("required", []))
        for name, prop in schema.get("properties", {}).items():
            rows.append([f"`{prefix}{name}`", f"`{self.type_text(prop)}`", "예" if name in required else "",
                         " ".join(filter(None, [prop.get("description", ""), self.constraints(prop)]))])
            target = prop
            if "anyOf" in prop:
                target = next((s for s in prop["anyOf"] if s.get("type") != "null"), prop)
            if target.get("type") == "array":
                target = target.get("items", {})
            if "$ref" in target and depth < 2:
                rows += self.property_rows(target, f"{prefix}{name}.", depth + 1)
        return rows


# ─────────────────────────────────────────────── 현황표 행
@dataclass
class Row:
    area: str
    method: str
    path: str                     # 사람용 (/stocks/{code}/quote)
    shape: str                    # 비교용 (/stocks/{}/quote)
    funcs: list[str] = field(default_factory=list)       # "getQuote (real.ts)"
    func_names: list[str] = field(default_factory=list)
    calls: list[str] = field(default_factory=list)       # 프론트 호출 코드
    status: str = ""
    op: dict | None = None
    owner: str = ""
    note: str = ""


def _code(text: str) -> str:
    """인라인 코드. 내용에 백틱(템플릿 문자열)이 있으면 더 긴 백틱으로 감싼다."""
    longest = max((len(m) for m in re.findall(r"`+", text)), default=0)
    fence = "`" * (longest + 1)
    return f"{fence} {text} {fence}" if longest else f"`{text}`"


def _shape(path: str) -> str:
    return re.sub(r"\{[^}]*\}", "{}", path)


def _escape(cell: str) -> str:
    return cell.replace("|", "\\|").replace("\n", " ")


def _unescape(cell: str) -> str:
    return cell.replace("\\|", "|").strip()


def read_human_cells(path: Path) -> dict[tuple[str, str], dict[str, str]]:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    start, end = text.find(TABLE_START), text.find(TABLE_END)
    if start < 0 or end < 0:
        return {}
    out: dict[tuple[str, str], dict[str, str]] = {}
    for line in text[start + len(TABLE_START):end].splitlines():
        line = line.strip()
        if not line.startswith("|") or set(line) <= set("|-: "):
            continue
        cells = [_unescape(c) for c in re.split(r"(?<!\\)\|", line.strip("|"))]
        if len(cells) != len(COLUMNS) or cells[0] == COLUMNS[0]:
            continue
        row = dict(zip(COLUMNS, cells))
        path_cell = row["경로"].strip("`")
        out[(row["메서드"], _shape(path_cell))] = {k: row[k] for k in HUMAN} | {"_area": row["영역"], "_path": path_cell}
    return out


def build_rows(spec: dict, calls, mock_only: set[str], human: dict) -> list[Row]:
    rows: dict[tuple[str, str], Row] = {}
    for path, ops in spec.get("paths", {}).items():
        if not path.startswith(API_PREFIX):
            continue
        rel = path[len(API_PREFIX):] or "/"
        for method, op in ops.items():
            tag = (op.get("tags") or [""])[0]
            area = TAG_AREA.get(tag) or SEGMENT_AREA.get(rel.strip("/").split("/")[0], "기타")
            rows[(method.upper(), _shape(rel))] = Row(area, method.upper(), rel, _shape(rel), op=op)
    for call in calls:
        key = (call.method, call.path)
        row = rows.get(key)
        if row is None:
            area = SEGMENT_AREA.get(call.display_path.strip("/").split("/")[0], "기타")
            row = rows[key] = Row(area, call.method, call.display_path, call.path)
        label = f"{call.func} ({call.source})"
        if label not in row.funcs:
            row.funcs.append(label)
            row.func_names.append(call.func)
            row.calls.append(f"{call.source}:{call.lineno} {_code(call.line)}")
    for row in rows.values():
        if row.func_names and any(f in mock_only for f in row.func_names):
            row.status = "mock" + (" (백엔드에도 있음)" if row.op else "")
        elif row.func_names and row.op:
            row.status = "구현됨"
        elif row.func_names:
            row.status = "없음"
        else:
            row.status = "백엔드만 있음"
        kept = human.get((row.method, row.shape), {})
        row.owner, row.note = kept.get("담당", ""), kept.get("비고", "")
    for key, kept in human.items():                         # 사라진 경로라도 사람이 적은 값은 남긴다
        if key not in rows and (kept.get("담당") or kept.get("비고")):
            rows[key] = Row(kept.get("_area") or "기타", key[0], kept["_path"], key[1], status="목록에서 빠짐",
                            owner=kept.get("담당", ""), note=kept.get("비고", ""))
    order = {a: i for i, a in enumerate(AREA_ORDER)}
    return sorted(rows.values(), key=lambda r: (order.get(r.area, len(order)), r.path, r.method))


# ─────────────────────────────────────────────── 렌더링
def _table(header: list[str], rows: list[list[str]]) -> list[str]:
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    out += ["| " + " | ".join(_escape(c) for c in r) + " |" for r in rows]
    return out


def _anchor(row: Row) -> str:
    return re.sub(r"[^a-z0-9가-힣-]", "", f"{row.method}-{row.path}".lower().replace("/", "-").replace("{", "").replace("}", ""))


STATUS_HELP = {
    "구현됨": "프론트가 부르고 백엔드에 있음",
    "mock": "백엔드 미구현 — frontend/src/api/index.ts MOCK_ONLY 로 USE_MOCK=false 에서도 mock 응답",
    "백엔드만 있음": "백엔드에는 있지만 프론트 real.ts 가 아직 부르지 않음",
    "없음": "프론트가 부르는데 백엔드도 mock 연결도 없음 (실제 서버로 가면 404)",
    "목록에서 빠짐": "예전 문서에 담당·비고가 적혀 있던 경로인데 지금은 프론트·백엔드 어디에도 없음",
}


def render(rows: list[Row], spec: dict, openapi_source: str) -> str:
    oa = OpenApi(spec)
    routes = scan_routes()
    ts = TsTypes(FRONT_MODELS, FRONT_API / "types.ts")
    sigs = api_signatures()
    counts: dict[str, int] = {}
    for r in rows:
        counts[r.status.split(" ")[0]] = counts.get(r.status.split(" ")[0], 0) + 1

    L: list[str] = [
        "# API 명세서",
        "",
        "> **자동 생성 문서입니다.** 현황표의 `담당`·`비고` 칸만 손으로 고치고, 나머지는 아래 명령으로 다시 만드세요.",
        "> 다시 만들어도 담당·비고는 (메서드, 경로)가 같은 행에서 그대로 옮겨집니다.",
        ">",
        "> ```bash",
        "> # 1) worktree 에서 테스트 서버를 띄운다 (공개 서버 8010 이 아니라 8020)",
        "> PYTHONPATH=backend uvicorn app.main:app --host 127.0.0.1 --port 8020 --env-file <.env 경로>",
        "> # 2) backend 폴더에서 생성",
        "> python -m pipelines.devtools.api_gap --openapi-url http://127.0.0.1:8020/openapi.json --write-spec",
        "> ```",
        ">",
        f"> 입력: OpenAPI `{openapi_source}` · 프론트 `frontend/src/api/{{real,board,stocks,index,types}}.ts` · "
        "`frontend/src/types/models.ts` · 라우트 소스 `backend/app/**/routes.py` · 생성기 `backend/pipelines/devtools/api_spec.py`",
        "",
        "## 목차",
        "1. [공통 규칙](#1-공통-규칙)",
        "2. [현황표](#2-현황표)",
        "3. [API별 상세](#3-api별-상세)",
        "",
        "## 1. 공통 규칙",
        "",
        "### 기본 주소",
        "- 모든 API는 **`/api/v1`** 아래에 있다. 이 문서의 경로는 `/api/v1`을 뺀 나머지다 (`/stocks` = `/api/v1/stocks`).",
        "- 웹(같은 주소 빌드, `npm run export:web:same-origin`): 상대 경로 `/api/v1`. 웹 빌드는 FastAPI가 `/api` 이외 경로에서 서빙한다.",
        "- 앱·개발: `EXPO_PUBLIC_API_BASE_URL` (예: `https://<서버>/api/v1`, 안드로이드 에뮬레이터 `http://10.0.2.2:8000/api/v1`).",
        "",
        "### 인증",
        "| 클라이언트 | 로그인 | 요청 인증 | 갱신 |",
        "|---|---|---|---|",
        "| 웹 | `GET /auth/{provider}/start?client=web&return_to=<origin>/auth/callback` → 콜백이 쿠키를 심고 return_to 로 돌아감 | HttpOnly 쿠키 `memos_access` (15분) | `POST /auth/refresh` 본문 `{}` — 쿠키 `memos_refresh`(path `/api/v1/auth`, 14일) 사용 |",
        "| 앱 | 같은 start 를 `client=mobile&code_challenge=` 로 열고, 받은 일회용 code 를 `POST /auth/mobile/exchange` (PKCE) | `Authorization: Bearer <access_token>` | `POST /auth/refresh` 본문 `{\"refresh_token\": ...}` |",
        "",
        "- **CSRF (웹 쿠키 세션)**: POST·PUT·PATCH·DELETE 에 `memos_access`/`memos_refresh` 쿠키가 실리고 `Authorization` 헤더가 없으면, "
        "`X-CSRF-Token` 헤더가 `memos_csrf` 쿠키 값과 같아야 한다(double-submit). 다르면 `403 {\"detail\": \"CSRF 검증에 실패했습니다.\"}`. "
        "프론트 `http.ts`가 `document.cookie`에서 읽어 넣으므로 **웹은 API와 같은 주소에서 열어야 한다** (다른 주소면 쿠키를 못 읽어 403).",
        "- `401`을 받으면 프론트(`http.ts`)가 `/auth/refresh`를 한 번 시도하고 원래 요청을 다시 보낸다.",
        "- 인증이 필요한 API는 아래 상세의 `인증` 줄에 표시한다 (라우트가 `get_current_user`에 의존하는지로 판단).",
        "",
        "### 에러 형식",
        "- 모든 에러 본문은 `{\"detail\": \"사람이 읽는 메시지\"}`.",
        "- 요청 검증 실패(422)는 FastAPI 기본 형식 `{\"detail\": [{\"loc\": [...], \"msg\": \"...\", \"type\": \"...\"}]}` — 프론트는 첫 `msg`를 보여 준다.",
        "",
        "| 코드 | 뜻 |",
        "|---|---|",
        *[f"| {code} | {text} |" for code, text in ERROR_TEXT.items()],
        "",
        "### 응답 형식",
        "- **기준은 `frontend/src/api/mock/`의 같은 함수가 돌려주는 모양과 필드 이름**이다 (타입: `frontend/src/types/models.ts`, `frontend/src/api/types.ts`의 `Api`).",
        "- 백엔드는 그 필드를 모두 채우고, 필요하면 필드를 덧붙일 수 있다 (예: 뉴스 `summary`, AI 업데이트 `card`·`sources`). 필드를 빼거나 이름을 바꾸지 않는다.",
        "- ID는 문자열, 시각은 ISO 8601 (`2026-11-20T09:00:00+09:00`), 날짜는 `YYYY-MM-DD`, 금액은 원 단위 숫자.",
        "- 본문이 없는 성공은 `204 No Content` (프론트는 `undefined`로 받음).",
        "- `상태 = mock`인 API는 백엔드가 없어서 `frontend/src/api/index.ts`의 `MOCK_ONLY` 목록으로 `USE_MOCK=false`에서도 mock 응답을 쓴다. "
        "백엔드를 만들면 그 목록에서 함수 이름을 빼면 된다.",
        "",
        "## 2. 현황표",
        "",
        "상태: " + " · ".join(f"**{k}** {counts.get(k, 0)}개 ({v})" for k, v in STATUS_HELP.items() if counts.get(k)),
        "",
        TABLE_START,
        *_table(COLUMNS, [[r.area, r.method, f"`{r.path}`", ", ".join(r.funcs), r.status, r.owner, r.note] for r in rows]),
        TABLE_END,
        "",
        "## 3. API별 상세",
        "",
    ]

    current_area = None
    for row in rows:
        if row.status == "목록에서 빠짐":
            continue
        if row.area != current_area:
            current_area = row.area
            L += [f"### {row.area}", ""]
        L += [f"<a id=\"{_anchor(row)}\"></a>", f"#### `{row.method} {row.path}`", ""]
        op = row.op or {}
        func_name = op.get("operationId", "").split("_api_v1")[0] if op else ""
        meta = routes.get(func_name)
        # summary 는 FastAPI 가 함수 이름으로 자동으로 만든 것("Get Quote")이라 쓰지 않고, 라우트 독스트링(description)만
        if op.get("description"):
            L += [" ".join(op["description"].split()), ""]
        L.append(f"- 상태: **{row.status}**" + (f" · 담당: {row.owner}" if row.owner else ""))
        if meta:
            L.append(f"- 인증: {'필요' if meta.auth else '불필요'} · 구현: `{meta.module}` `{func_name}`")
        elif not op:
            L.append("- 인증: (백엔드 미구현) · 응답은 `frontend/src/api/mock/index.ts`의 같은 함수가 기준")
        for fn, call in zip(row.func_names, row.calls):
            sig = sigs.get(fn)
            L.append(f"- 프론트: {_code(sig[0])}" if sig else f"- 프론트: `{fn}`")
            L.append(f"  - 호출: {call}")
        L.append("")

        params = op.get("parameters", [])
        if params:
            L += ["**요청 파라미터**", ""]
            L += _table(["이름", "위치", "타입", "필수", "설명·제약"], [
                [f"`{p['name']}`", {"path": "경로", "query": "쿼리", "header": "헤더", "cookie": "쿠키"}.get(p["in"], p["in"]),
                 f"`{oa.type_text(p.get('schema'))}`", "예" if p.get("required") else "",
                 " ".join(filter(None, [p.get("description", ""), oa.constraints(p.get("schema", {}))]))]
                for p in params])
            L.append("")
        body = (op.get("requestBody") or {}).get("content", {}).get("application/json", {}).get("schema")
        if body:
            L += [f"**요청 본문** `{oa.type_text(body)}`" + (" (필수)" if op["requestBody"].get("required") else ""), ""]
            body_rows = oa.property_rows(body)
            L += (_table(["필드", "타입", "필수", "설명·제약"], body_rows) if body_rows else ["(스키마 없음)"])
            L.append("")
        form = (op.get("requestBody") or {}).get("content", {}).get("multipart/form-data")
        if form:
            L += ["**요청 본문** multipart/form-data", ""]

        responses = op.get("responses", {})
        ok_codes = [c for c in responses if c.startswith("2")]
        if ok_codes:
            code = ok_codes[0]
            schema = responses[code].get("content", {}).get("application/json", {}).get("schema")
            L.append(f"**응답** `{code}`" + (" 본문 없음" if code == "204" else ""))
            L.append("")
            if schema and (schema.get("$ref") or schema.get("properties") or schema.get("items") or schema.get("anyOf")):
                L += [f"OpenAPI 응답 스키마 `{oa.type_text(schema)}`", ""]
                target = schema.get("items", schema)
                variants = target.get("anyOf") or target.get("oneOf") or [target]
                for variant in variants:
                    prop_rows = oa.property_rows(variant)
                    if prop_rows:
                        if len(variants) > 1:
                            L += [f"- `{oa.type_text(variant)}`", ""]
                        L += _table(["필드", "타입", "필수", "설명·제약"], prop_rows) + [""]
        sig = next((sigs[f] for f in row.func_names if f in sigs), None)
        if sig and sig[1] != "void":
            resolved = ts.resolve_fields(sig[1])
            L += [f"프론트 타입 (mock 기준) `{sig[1]}`", ""]
            if resolved:
                L += _table(["필드", "타입", "필수"], [[f"`{f.name}`", f"`{f.type}`", "" if f.optional else "예"]
                                                     for f in resolved[1]]) + [""]
            example = ts.example(sig[1])
            L += ["<details><summary>예시</summary>", "", "```json",
                  json.dumps(example, ensure_ascii=False, indent=2), "```", "", "</details>", ""]

        codes = set(meta.codes) if meta else set()
        if meta and meta.auth:
            codes.add(401)
        if "422" in responses:
            codes.add(422)
        if row.method in {"POST", "PUT", "PATCH", "DELETE"} and meta and meta.auth:
            codes.add(403)
        if codes:
            L += ["**에러**: " + " · ".join(f"`{c}` {ERROR_TEXT.get(c, '')}".strip() for c in sorted(codes)), ""]
    return "\n".join(L).rstrip() + "\n"


def write_spec(spec: dict, calls, mock_only: set[str], path: Path, openapi_source: str = "") -> Path:
    path = path if path.is_absolute() else (Path.cwd() / path)
    human = read_human_cells(path)
    rows = build_rows(spec, calls, mock_only, human)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(rows, spec, openapi_source), encoding="utf-8")
    return path
