"""Unit tests for the file and identity guards in the overview loader."""

from __future__ import annotations

import csv
import importlib.util
import sys
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "load_company_overviews.py"
SPEC = importlib.util.spec_from_file_location("load_company_overviews", SCRIPT)
assert SPEC and SPEC.loader
loader = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = loader
SPEC.loader.exec_module(loader)


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=("symbol", "name", "description", "verdict")
        )
        writer.writeheader()
        writer.writerows(rows)


def good_rows() -> list[dict[str, str]]:
    return [
        {
            "symbol": "000001",
            "name": "테스트회사",
            "description": "테스트회사는 원문에 있는 제품을 제조하고 국내외 고객에게 공급하는 회사예요. 관련 부품과 유지보수 서비스도 함께 제공하며 여러 산업의 고객사와 거래해요.",
            "verdict": "fixed",
        },
        {"symbol": "000002", "name": "빈회사", "description": "", "verdict": "blank"},
    ]


def test_load_rows_accepts_reviewed_and_blank_rows(tmp_path):
    path = tmp_path / "input.csv"
    write_csv(path, good_rows())
    rows = loader.load_rows(path, expected_rows=2)
    assert [row.symbol for row in rows] == ["000001", "000002"]
    assert rows[1].is_blank


@pytest.mark.parametrize("mutation,match", [
    (lambda rows: rows.append(dict(rows[0])), "중복"),
    (lambda rows: rows[0].update(description="짧아요"), "길이"),
    (lambda rows: rows[0].update(description=""), "비어"),
    (lambda rows: rows[1].update(description="설명이 남음"), "blank"),
])
def test_load_rows_rejects_unsafe_input(tmp_path, mutation, match):
    rows = good_rows()
    mutation(rows)
    path = tmp_path / "input.csv"
    write_csv(path, rows)
    with pytest.raises(ValueError, match=match):
        loader.load_rows(path, expected_rows=len(rows))


def test_build_plan_skips_blank_and_detects_changes():
    rows = [
        loader.OverviewRow("000001", "회사1", "가" * 80, "ok"),
        loader.OverviewRow("000002", "회사2", "", "blank"),
        loader.OverviewRow("000003", "회사3", "다" * 80, "fixed"),
    ]
    stocks = {
        "000001": {"name": "회사1", "description": "가" * 80},
        "000002": {"name": "회사2", "description": "기존"},
        "000003": {"name": "회사3", "description": "이전"},
    }
    changes, counts = loader.build_plan(rows, stocks)
    assert [row.symbol for row in changes] == ["000003"]
    assert counts == {
        "input_rows": 3,
        "db_matched_rows": 3,
        "blank_skipped": 1,
        "already_unchanged": 1,
        "update_candidates": 1,
    }


def test_build_plan_rejects_missing_symbol_and_name_mismatch():
    row = loader.OverviewRow("000001", "CSV회사", "가" * 80, "ok")
    with pytest.raises(ValueError, match="없는 종목코드"):
        loader.build_plan([row], {})
    with pytest.raises(ValueError, match="회사명 불일치"):
        loader.build_plan(
            [row], {"000001": {"name": "DB회사", "description": None}}
        )
