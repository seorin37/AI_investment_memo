"""프론트 real API 호출 경로 ↔ 백엔드 openapi.json 비교.

frontend/src/api/{real,board,stocks}.ts 의 http.get/post/put/patch/del/upload 호출을 모으고,
frontend/src/api/index.ts 의 MOCK_ONLY(C그룹) 함수는 따로 표시한다.

실행 (backend 폴더에서):
    python -m pipelines.devtools.api_gap --openapi-url http://127.0.0.1:8020/openapi.json
    python -m pipelines.devtools.api_gap --openapi-file openapi.json
    # API 명세서(docs/api-spec.md)도 다시 만들기 — 담당·비고 칸은 보존된다 (pipelines/devtools/api_spec.py)
    python -m pipelines.devtools.api_gap --openapi-url http://127.0.0.1:8020/openapi.json --write-spec
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
API_DIR = REPO / "frontend" / "src" / "api"
SOURCES = ("real.ts", "board.ts", "stocks.ts")
API_PREFIX = "/api/v1"

_METHODS = {"get": "GET", "post": "POST", "put": "PUT", "patch": "PATCH", "del": "DELETE", "upload": "POST"}
_CALL = re.compile(r"\bhttp\.(get|post|put|patch|del|upload)\s*(?:<[^>]*>)?\(\s*([`'\"])(.*?)\2")
_FUNC = re.compile(r"^\s*(?:async\s+)?([A-Za-z_]\w*)\s*(?::\s*(?:async\s*)?\(|\()")


@dataclass(frozen=True)
class Call:
    func: str
    method: str
    path: str                 # 비교용: 경로 변수는 {}
    source: str
    display_path: str = ""    # 사람용: ${code} → {code}
    line: str = ""            # 호출한 코드 한 줄
    lineno: int = 0


def _normalize(path: str) -> str:
    path = re.sub(r"\$\{[^}]+\}", "{}", path.split("?")[0])
    return "/" + path.strip("/")


def _display(path: str) -> str:
    path = re.sub(r"\$\{\s*([A-Za-z_]\w*)[^}]*\}", r"{\1}", path.split("?")[0])
    return "/" + path.strip("/")


def frontend_calls() -> list[Call]:
    calls: list[Call] = []
    for name in SOURCES:
        current = "?"
        for lineno, line in enumerate((API_DIR / name).read_text(encoding="utf-8").splitlines(), 1):
            func = _FUNC.match(line)
            if func and func.group(1) not in {"if", "for", "while", "return", "switch"}:
                current = func.group(1)
            for method, _quote, path in _CALL.findall(line):
                calls.append(Call(current, _METHODS[method], _normalize(path), name,
                                  _display(path), line.strip(), lineno))
    return calls


def mock_only_functions() -> set[str]:
    text = (API_DIR / "index.ts").read_text(encoding="utf-8")
    block = re.search(r"MOCK_ONLY\s*=\s*\[(.*?)\]", text, re.S)
    return set(re.findall(r"'(\w+)'", block.group(1))) if block else set()


def openapi_routes(spec: dict) -> set[tuple[str, str]]:
    routes = set()
    for path, ops in spec.get("paths", {}).items():
        if not path.startswith(API_PREFIX):
            continue
        shape = re.sub(r"\{[^}]+\}", "{}", path[len(API_PREFIX):]) or "/"
        for method in ops:
            routes.add((method.upper(), shape))
    return routes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--openapi-url")
    src.add_argument("--openapi-file", type=Path)
    parser.add_argument("--write-spec", nargs="?", const=REPO / "docs" / "api-spec.md", type=Path,
                        help="API 명세서 생성 (기본 docs/api-spec.md). 담당·비고 칸은 기존 문서에서 보존")
    args = parser.parse_args(argv)

    if args.openapi_url:
        with urllib.request.urlopen(args.openapi_url, timeout=10) as res:
            spec = json.load(res)
    else:
        spec = json.loads(args.openapi_file.read_text(encoding="utf-8"))

    backend = openapi_routes(spec)
    mock_only = mock_only_functions()
    unique: dict[tuple[str, str], Call] = {}
    for call in frontend_calls():
        unique.setdefault((call.method, call.path), call)

    rows = {"ok": [], "missing": [], "mock": []}
    for key, call in sorted(unique.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        group = "mock" if call.func in mock_only else ("ok" if key in backend else "missing")
        rows[group].append(call)

    labels = {"ok": "백엔드에 있음", "missing": "백엔드에 없음 (C그룹 아님)", "mock": "C그룹 (mock 연결)"}
    for group in ("missing", "ok", "mock"):
        print(f"\n## {labels[group]}: {len(rows[group])}")
        for call in rows[group]:
            mark = ""
            if group == "mock" and (call.method, call.path) in backend:
                mark = "  (백엔드에도 있음)"
            print(f"  {call.method:6} {call.path:45} {call.func}{mark}")
    print(f"\n총 {len(unique)}개 경로: 있음 {len(rows['ok'])}, 없음 {len(rows['missing'])}, C그룹 {len(rows['mock'])}")
    if args.write_spec:
        from .api_spec import write_spec

        source = args.openapi_url or str(args.openapi_file)
        path = write_spec(spec, frontend_calls(), mock_only, args.write_spec, openapi_source=source)
        print(f"\nAPI 명세서: {path}")
    return 1 if rows["missing"] else 0


if __name__ == "__main__":
    sys.exit(main())
