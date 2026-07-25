"""Safe blocking file locks for private local-state transactions."""
from __future__ import annotations

import fcntl
import os
import stat
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


def sibling_lock_path(target: Path, *, operation: str) -> Path:
    safe_operation = "".join(
        character if character.isalnum() or character in {"-", "_"} else "_"
        for character in str(operation or "transaction")
    )
    return target.with_name(f".{target.name}.{safe_operation}.lock")


@contextmanager
def exclusive_local_state_lock(lock_path: Path) -> Iterator[None]:
    """Hold an advisory cross-process lock on a regular, non-symlink file."""

    path = lock_path.expanduser()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        path.parent.chmod(0o700)
    except OSError:
        pass

    flags = os.O_RDWR | os.O_CREAT
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o600)
    try:
        lock_stat = os.fstat(descriptor)
        if not stat.S_ISREG(lock_stat.st_mode):
            raise RuntimeError(f"Local-state lock must be a regular file: {path}")
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "a+", encoding="utf-8") as handle:
            descriptor = -1
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
