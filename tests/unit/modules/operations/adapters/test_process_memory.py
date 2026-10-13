"""Resident memory for the health line (`EPIC-038D`)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.process_memory import (
    ProcfsProcessMemory,
    UnknownProcessMemory,
    WindowsProcessMemory,
    default_process_memory,
)

_MB = 1024 * 1024


def test_resident_pages_times_the_page_size_in_whole_megabytes(tmp_path: Path) -> None:
    statm = tmp_path / "statm"
    statm.write_text("123456 2560 800 4 0 9000 0\n", encoding="ascii")  # 2560 pages

    assert (
        ProcfsProcessMemory(statm, page_size=4096).resident_mb() == 10
    )  # 10 485 760 B


def test_a_partial_megabyte_is_not_rounded_up(tmp_path: Path) -> None:
    statm = tmp_path / "statm"
    statm.write_text(f"1 {(3 * _MB - 1) // 4096} 0 0 0 0 0", encoding="ascii")

    assert ProcfsProcessMemory(statm, page_size=4096).resident_mb() == 2


@pytest.mark.parametrize("content", ["", "1", "1 many 0", "\x00"])
def test_a_statm_that_cannot_be_read_is_unknown_not_zero(
    tmp_path: Path, content: str
) -> None:
    statm = tmp_path / "statm"
    statm.write_text(content, encoding="ascii")

    assert ProcfsProcessMemory(statm, page_size=4096).resident_mb() is None


def test_a_missing_statm_is_unknown(tmp_path: Path) -> None:
    assert ProcfsProcessMemory(tmp_path / "nope", page_size=4096).resident_mb() is None


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="reads /proc")
def test_this_process_has_some_resident_memory_on_linux() -> None:
    resident = default_process_memory().resident_mb()

    assert resident is not None
    assert resident > 0


def test_the_platform_picks_its_reader() -> None:
    assert isinstance(default_process_memory("linux"), ProcfsProcessMemory)
    assert isinstance(default_process_memory("win32"), WindowsProcessMemory)
    assert isinstance(default_process_memory("plan9"), UnknownProcessMemory)


@pytest.mark.skipif(
    sys.platform == "win32", reason="checks the guard that keeps other platforms safe"
)
def test_windows_memory_off_windows_is_unknown_not_a_crash() -> None:
    assert WindowsProcessMemory().resident_mb() is None
