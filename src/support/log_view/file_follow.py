"""Read a file to its end, and optionally keep reading as it grows (`tail -f`).

The clock is injected as `sleep` and the stop condition as `keep_going`, so a test
drives a growing file without waiting. A last line without its newline is held back
until the newline arrives. A file that shrinks (copytruncate) or is replaced
(rotation) is read again from its start.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO


@dataclass(frozen=True, slots=True)
class FollowTiming:
    poll_seconds: float
    sleep: Callable[[float], None]
    keep_going: Callable[[], bool]


def read_lines(path: Path, timing: FollowTiming | None) -> Iterator[str]:
    """Every line of `path`, terminators kept; with `timing`, waits for more."""
    handle = path.open("r", encoding="utf-8", errors="surrogateescape", newline="")
    held = ""
    try:
        identity = os.fstat(handle.fileno()).st_ino
        while True:
            chunk = handle.readline()
            if chunk:
                held += chunk
                if held.endswith("\n"):
                    yield held
                    held = ""
                continue
            if timing is None or not timing.keep_going():
                if held:
                    yield held
                return
            timing.sleep(timing.poll_seconds)
            if _was_rotated(path, handle, identity):
                if held:
                    yield held
                handle.close()
                handle = path.open(
                    "r", encoding="utf-8", errors="surrogateescape", newline=""
                )
                identity = os.fstat(handle.fileno()).st_ino
                held = ""
    finally:
        handle.close()


def _was_rotated(path: Path, handle: TextIO, identity: int) -> bool:
    try:
        stat = path.stat()
        position = handle.tell()
    except OSError:
        return False
    return stat.st_ino != identity or stat.st_size < position
