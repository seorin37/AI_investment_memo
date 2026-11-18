"""파이프라인 공용 설정 로더 (YAML 공통 설정 + 모드 설정 병합)."""

from __future__ import annotations

import copy
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[3]


def deep_merge(base: dict, override: dict) -> dict:
    """override의 값을 base 위에 재귀적으로 덮어쓴 새 dict를 반환한다."""
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def resolve_path(path: str | Path) -> Path:
    """상대 경로는 현재 디렉터리에 있으면 그대로, 없으면 저장소 루트 기준으로 해석한다."""
    candidate = Path(path)
    if candidate.is_absolute() or candidate.exists():
        return candidate.resolve()
    return (REPO_ROOT / candidate).resolve()


def load_config(common_path: str | Path, mode_path: str | Path | None = None) -> dict:
    with resolve_path(common_path).open(encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}
    if mode_path is not None:
        with resolve_path(mode_path).open(encoding="utf-8") as handle:
            config = deep_merge(config, yaml.safe_load(handle) or {})
    return config


def data_path(config: dict, key: str, root: Path = REPO_ROOT) -> Path:
    """config['paths'][key]를 root(기본: 저장소 루트) 기준 절대 경로로 반환한다."""
    path = Path(config["paths"][key])
    return path if path.is_absolute() else root / path
