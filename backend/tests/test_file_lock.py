from __future__ import annotations

import pytest

from pipelines.common.file_lock import LockUnavailable, acquire_file_lock, file_lock


def test_nonblocking_lock_reports_contention(tmp_path):
    path = tmp_path / "pipeline.lock"
    first = acquire_file_lock(path, timeout=0)
    try:
        with pytest.raises(LockUnavailable):
            acquire_file_lock(path, timeout=0)
    finally:
        first.release()


def test_context_lock_is_released(tmp_path):
    path = tmp_path / "cache.lock"
    with file_lock(path):
        with pytest.raises(LockUnavailable):
            acquire_file_lock(path, timeout=0)

    second = acquire_file_lock(path, timeout=0)
    second.release()
