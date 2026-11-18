"""eval/memo_personas 테스트 공통 준비. 레포 루트에서 `python -m pytest eval/memo_personas/tests -q`로 실행한다."""

import copy
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from eval.memo_personas.common import load_config  # noqa: E402


@pytest.fixture(scope="session")
def base_cfg():
    return load_config(REPO / "eval/memo_personas/config.yaml")


@pytest.fixture(scope="session")
def fake_packs(base_cfg):
    from eval.memo_personas.devtools.fake_data import packs_without_db

    return packs_without_db(base_cfg)


@pytest.fixture
def cfg(base_cfg):
    return copy.deepcopy(base_cfg)
