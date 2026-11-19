"""Validate and merge the human/LLM-reviewed company overview artifacts.

This script only reads and writes files under the supplied artifact directory. It
does not connect to a database.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path


FORBIDDEN = (
    "당사",
    "1위",
    "최대",
    "최고",
    "선도",
    "대표적인",
    "독보적",
    "글로벌 리딩",
)
SENTENCE_END = re.compile(r"[.!?](?:\s|$)")


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def read_batch(path: Path) -> list[dict[str, object]]:
    with path.open(encoding="utf-8-sig") as handle:
        value = json.load(handle)
    if not isinstance(value, list):
        raise ValueError(f"{path}: expected a JSON array")
    return value


def description_issues(name: str, description: str) -> list[str]:
    issues: list[str] = []
    length = len(description)
    if not description:
        return ["empty description"]
    if not 80 <= length <= 180:
        issues.append(f"length={length}")
    if not description.startswith(name):
        issues.append("does not start with company name")
    if "\t" in description or "\n" in description or "\r" in description:
        issues.append("contains tab/newline")
    # A forbidden word may legitimately be part of the supplied company name
    # (for example, 선도전기). Check only the generated body after that prefix.
    body = description[len(name) :] if description.startswith(name) else description
    scan_body = body.replace("당사자", "")
    hits = [word for word in FORBIDDEN if word in scan_body]
    if hits:
        issues.append("forbidden=" + ",".join(hits))
    sentence_count = len(SENTENCE_END.findall(description))
    if sentence_count not in (2, 3):
        issues.append(f"sentence_count={sentence_count}")
    return issues


def validate(root: Path) -> int:
    problems: list[str] = []
    seen: list[str] = []
    total_expected = total_actual = 0

    for batch_no in range(1, 32):
        label = f"{batch_no:02d}"
        source_path = root / "batches" / f"batch_{label}.json"
        output_path = root / "out" / f"batch_{label}.tsv"
        source = read_batch(source_path)
        expected = [row for row in source if not row.get("pilot")]
        total_expected += len(expected)
        if not output_path.exists():
            problems.append(f"batch_{label}: missing output ({len(expected)} expected)")
            continue

        output = read_tsv(output_path)
        total_actual += len(output)
        expected_symbols = [str(row["symbol"]).zfill(6) for row in expected]
        actual_symbols = [str(row.get("symbol", "")).zfill(6) for row in output]
        seen.extend(actual_symbols)
        if actual_symbols != expected_symbols:
            missing = sorted(set(expected_symbols) - set(actual_symbols))
            extra = sorted(set(actual_symbols) - set(expected_symbols))
            problems.append(
                f"batch_{label}: symbol/order mismatch missing={missing} extra={extra}"
            )

        names = {str(row["symbol"]).zfill(6): str(row["name"]) for row in expected}
        for line_no, row in enumerate(output, start=2):
            symbol = str(row.get("symbol", "")).zfill(6)
            name = row.get("name", "")
            if names.get(symbol) != name:
                problems.append(f"batch_{label}:{line_no}: name mismatch for {symbol}")
            for issue in description_issues(name, row.get("description", "")):
                problems.append(f"batch_{label}:{line_no}:{symbol}: {issue}")

    duplicates = sorted(symbol for symbol, count in Counter(seen).items() if count > 1)
    if duplicates:
        problems.append(f"duplicate output symbols: {duplicates}")

    print(f"outputs: {total_actual}/{total_expected}")
    if problems:
        print(f"problems: {len(problems)}")
        for problem in problems:
            print(f"- {problem}")
        return 1
    print("problems: 0")
    return 0


def merge_verified(root: Path, destination: Path) -> int:
    rows: dict[str, dict[str, str]] = {}
    pilot_rows = read_tsv(root / "pilot_summaries.tsv")
    for row in pilot_rows:
        symbol = str(row["symbol"]).zfill(6)
        rows[symbol] = {
            "symbol": symbol,
            "name": row["name"],
            "description": row["description"],
            "verdict": "pilot",
            "issues": "",
        }

    missing_verify: list[str] = []
    for batch_no in range(1, 32):
        label = f"{batch_no:02d}"
        verify_path = root / "verify" / f"batch_{label}.tsv"
        if not verify_path.exists():
            missing_verify.append(label)
            continue
        for row in read_tsv(verify_path):
            symbol = str(row["symbol"]).zfill(6)
            rows[symbol] = {
                "symbol": symbol,
                "name": row["name"],
                "description": row["final_description"],
                "verdict": row["verdict"],
                "issues": row["issues"],
            }

    if missing_verify:
        print("missing verified batches: " + ", ".join(missing_verify))
        return 1
    if len(rows) != 825:
        print(f"merged rows: {len(rows)}/825; refusing to write")
        return 1

    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("symbol", "name", "description", "verdict", "issues"),
        )
        writer.writeheader()
        writer.writerows(rows[symbol] for symbol in sorted(rows))
    print(f"wrote {len(rows)} rows to {destination}")
    return 0


def validate_verified(root: Path) -> int:
    problems: list[str] = []
    total = 0
    verdicts: Counter[str] = Counter()
    for batch_no in range(1, 32):
        label = f"{batch_no:02d}"
        source = read_batch(root / "batches" / f"batch_{label}.json")
        verify_path = root / "verify" / f"batch_{label}.tsv"
        if not verify_path.exists():
            problems.append(f"batch_{label}: missing verification ({len(source)} expected)")
            continue
        rows = read_tsv(verify_path)
        total += len(rows)
        expected_symbols = [str(row["symbol"]).zfill(6) for row in source]
        actual_symbols = [str(row.get("symbol", "")).zfill(6) for row in rows]
        if actual_symbols != expected_symbols:
            missing = sorted(set(expected_symbols) - set(actual_symbols))
            extra = sorted(set(actual_symbols) - set(expected_symbols))
            problems.append(
                f"batch_{label}: symbol/order mismatch missing={missing} extra={extra}"
            )
        names = {str(row["symbol"]).zfill(6): str(row["name"]) for row in source}
        for line_no, row in enumerate(rows, start=2):
            symbol = str(row.get("symbol", "")).zfill(6)
            name = row.get("name", "")
            verdict = row.get("verdict", "")
            verdicts[verdict] += 1
            if verdict not in {"ok", "fixed", "blank"}:
                problems.append(f"batch_{label}:{line_no}:{symbol}: bad verdict={verdict!r}")
            if names.get(symbol) != name:
                problems.append(f"batch_{label}:{line_no}:{symbol}: name mismatch")
            description = row.get("final_description", "")
            if verdict == "blank":
                if description:
                    problems.append(f"batch_{label}:{line_no}:{symbol}: blank has description")
                if not row.get("issues", "").strip():
                    problems.append(f"batch_{label}:{line_no}:{symbol}: blank has no issue")
                continue
            for issue in description_issues(name, description):
                problems.append(f"batch_{label}:{line_no}:{symbol}: {issue}")

    print(f"verified: {total}/825")
    print("verdicts: " + ", ".join(f"{key}={value}" for key, value in sorted(verdicts.items())))
    if problems:
        print(f"problems: {len(problems)}")
        for problem in problems:
            print(f"- {problem}")
        return 1
    print("problems: 0")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("data/company_overview_20261115"),
        help="artifact directory",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("validate")
    subparsers.add_parser("validate-verified")
    merge = subparsers.add_parser("merge-verified")
    merge.add_argument(
        "--output",
        type=Path,
        default=Path("data/company_overview_20261115/company_overviews_verified.csv"),
    )
    args = parser.parse_args()
    if args.command == "validate":
        return validate(args.root)
    if args.command == "validate-verified":
        return validate_verified(args.root)
    return merge_verified(args.root, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
