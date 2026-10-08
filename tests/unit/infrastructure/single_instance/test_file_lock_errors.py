"""`EPIC-035H` review — only "someone holds it" reads as another copy.

Any other failure of the lock call (a filesystem without `flock`, say) is still
refused, which is the safe side, but it is logged with its errno instead of
being worded as another copy running.
"""

from __future__ import annotations

import errno
import logging
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.infrastructure.single_instance import file_lock
from Sagittarius_Elite_Warrior.src.infrastructure.single_instance.instance_access import (
    InstanceAccess,
)

pytestmark = pytest.mark.skipif(
    not hasattr(file_lock, "fcntl"), reason="the POSIX lock call"
)


def _failing_flock(code: int):  # type: ignore[no-untyped-def]
    def flock(fd: int, operation: int) -> None:
        raise OSError(code, "injected")

    return flock


def test_a_taken_lock_is_quietly_another_copy(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(file_lock.fcntl, "flock", _failing_flock(errno.EAGAIN))

    with caplog.at_level(logging.WARNING, logger="App.Instance"):
        access = InstanceAccess.acquire(tmp_path / "instance.lock")

    assert access.read_only is True
    assert caplog.records == []


def test_any_other_error_is_refused_and_logged_with_its_errno(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(file_lock.fcntl, "flock", _failing_flock(errno.ENOLCK))

    with caplog.at_level(logging.WARNING, logger="App.Instance"):
        access = InstanceAccess.acquire(tmp_path / "instance.lock")

    assert access.read_only is True
    assert any(
        "ENOLCK" in r.getMessage() or str(errno.ENOLCK) in r.getMessage()
        for r in caplog.records
    )
