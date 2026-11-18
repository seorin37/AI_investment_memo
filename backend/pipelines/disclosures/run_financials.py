"""DART 구조화 재무 수치 실행 진입점.

    PYTHONPATH=backend python -m pipelines.disclosures.run_financials \
        --config configs/common.yaml [--steps collect,load,bis,validate] [--symbols …] [--refresh] [--dry-run] [--root …]
"""

from .financials_pipeline import main


if __name__ == "__main__":
    raise SystemExit(main())
