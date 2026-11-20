"""API 명세서 생성기 (pipelines/devtools/api_spec.py): 상태 판정과 담당·비고 보존."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pipelines.devtools.api_gap import Call
from pipelines.devtools.api_spec import _code, build_rows, read_human_cells, write_spec

SPEC = {
    "openapi": "3.1.0",
    "paths": {
        "/api/v1/stocks/{code}/quote": {"get": {
            "tags": ["marketdata"], "operationId": "get_quote_api_v1_stocks__code__quote_get",
            "parameters": [{"name": "code", "in": "path", "required": True,
                            "schema": {"type": "string", "pattern": "^[0-9A-Z]{6}$"}}],
            "responses": {"200": {"content": {"application/json": {"schema": {}}}}, "422": {}}}},
        "/api/v1/me/usage": {"get": {"tags": ["credits"], "operationId": "get_my_usage_api_v1_me_usage_get",
                                     "responses": {"200": {}}}},
    },
}
CALLS = [
    Call("getQuote", "GET", "/stocks/{}/quote", "real.ts", "/stocks/{code}/quote", "getQuote: (code) => http.get(`/x`)", 25),
    Call("listJournal", "GET", "/journal", "real.ts", "/journal", "listJournal: () => http.get('/journal')", 44),
    Call("getAiStats", "GET", "/ai/stats", "real.ts", "/ai/stats", "getAiStats: () => http.get('/ai/stats')", 80),
]


class ApiSpecTest(unittest.TestCase):
    def test_status(self):
        rows = {(r.method, r.path): r for r in build_rows(SPEC, CALLS, {"listJournal"}, {})}
        self.assertEqual(rows[("GET", "/stocks/{code}/quote")].status, "구현됨")
        self.assertEqual(rows[("GET", "/me/usage")].status, "백엔드만 있음")
        self.assertEqual(rows[("GET", "/journal")].status, "mock")
        self.assertEqual(rows[("GET", "/ai/stats")].status, "없음")
        self.assertEqual(rows[("GET", "/stocks/{code}/quote")].area, "시세·뉴스·기업")
        self.assertEqual(rows[("GET", "/journal")].area, "투자 기록")

    def test_human_cells_survive_regeneration(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "api-spec.md"
            write_spec(SPEC, CALLS, {"listJournal"}, path, openapi_source="test")
            text = path.read_text(encoding="utf-8")
            # 사람이 담당·비고를 채운다 (비고에 | 도 넣어 본다)
            text = text.replace(
                "| 시세·뉴스·기업 | GET | `/stocks/{code}/quote` | getQuote (real.ts) | 구현됨 |  |  |",
                "| 시세·뉴스·기업 | GET | `/stocks/{code}/quote` | getQuote (real.ts) | 구현됨 | 서린 | 원시 주가 \\| 전일 기준 |",
            ).replace(
                "| 투자 기록 | GET | `/journal` | listJournal (real.ts) | mock |  |  |",
                "| 투자 기록 | GET | `/journal` | listJournal (real.ts) | mock | 민이 | blocks 컬럼 결정 대기 |",
            )
            path.write_text(text, encoding="utf-8")
            self.assertEqual(read_human_cells(path)[("GET", "/stocks/{}/quote")]["비고"], "원시 주가 | 전일 기준")

            # 다시 생성: /journal 은 프론트에서 사라졌다고 가정
            write_spec(SPEC, CALLS[:1] + CALLS[2:], set(), path, openapi_source="test")
            again = path.read_text(encoding="utf-8")
            self.assertIn("| 구현됨 | 서린 | 원시 주가 \\| 전일 기준 |", again)
            self.assertIn("| GET | `/journal` |  | 목록에서 빠짐 | 민이 | blocks 컬럼 결정 대기 |", again)
            self.assertIn("python -m pipelines.devtools.api_gap --openapi-url http://127.0.0.1:8020/openapi.json --write-spec",
                          "\n".join(again.splitlines()[:12]))           # 생성 명령은 문서 맨 위

    def test_code_span_with_backticks(self):
        self.assertEqual(_code("a"), "`a`")
        self.assertEqual(_code("http.get(`/x`)"), "`` http.get(`/x`) ``")


if __name__ == "__main__":
    unittest.main()
