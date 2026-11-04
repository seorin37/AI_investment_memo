"""Cross-platform file locks used by long-running pipeline processes."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from filelock import FileLock, Timeout


class LockUnavailable(RuntimeError):
    """Raised when a non-blocking lock is already held by another process."""


def acquire_file_lock(path: str | Path, *, timeout: float = -1) -> FileLock:
    """Acquire *path* and return the held lock.

    ``timeout=0`` is non-blocking.  The caller must retain the returned object
    for as long as the lock is required and release it when finished.
    """

    lock_path = Path(path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock = FileLock(str(lock_path))
    try:
        lock.acquire(timeout=timeout)
    except Timeout as exc:
        raise LockUnavailable(str(lock_path)) from exc
    return lock


@contextmanager
def file_lock(path: str | Path, *, timeout: float = -1) -> Iterator[None]:
    """Hold a cross-platform file lock for the duration of the context."""

    lock = acquire_file_lock(path, timeout=timeout)
    try:
        yield
    finally:
        lock.release()
