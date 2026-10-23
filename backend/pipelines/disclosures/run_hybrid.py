"""hybrid 모드 실행 진입점.

    PYTHONPATH=backend python -m pipelines.disclosures.run_hybrid \
        --config configs/common.yaml --mode-config configs/hybrid.yaml [--steps …] [--from-zip …] [--offline]
"""

from .pipeline import main


if __name__ == "__main__":
    raise SystemExit(main("hybrid"))
