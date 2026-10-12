"""`EPIC-038F` — the machine-level checks: disk, data root, Python floor."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.check_result import CheckStatus
from Sagittarius_Elite_Warrior.src.core.contracts.preflight_scope import (
    PreflightScope,
)
from Sagittarius_Elite_Warrior.src.core.repo_root import repo_root
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.data_root_writable_check import (
    DataRootWritableCheck,
)
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.disk_space_check import (
    GIB,
    MIB,
    DiskSpaceCheck,
    DiskUsage,
)
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.python_floor_check import (
    SUPPORTED_PYTHON_FLOOR,
    PythonFloorCheck,
)

_TOTAL = 100 * GIB


def _disk(free: int, total: int = _TOTAL) -> CheckStatus:
    check = DiskSpaceCheck(
        {"data root": Path("/data")}, lambda _p: DiskUsage(total, free)
    )
    return check.run(PreflightScope()).status


@pytest.mark.parametrize(
    ("free", "expected"),
    [
        (50 * GIB, CheckStatus.PASS),
        (11 * GIB, CheckStatus.PASS),
        (9 * GIB, CheckStatus.WARN),  # below 10 % of 100 GiB
        (GIB - 1, CheckStatus.WARN),
        (100 * MIB, CheckStatus.WARN),  # at the FAIL line is still a warning
        (100 * MIB - 1, CheckStatus.FAIL),
    ],
)
def test_disk_thresholds(free: int, expected: CheckStatus) -> None:
    assert _disk(free) is expected


def test_a_small_disk_with_plenty_free_in_bytes_still_warns_below_ten_percent() -> None:
    assert _disk(free=2 * GIB, total=50 * GIB) is CheckStatus.WARN


def test_every_target_gets_its_own_finding() -> None:
    check = DiskSpaceCheck(
        {"data root": Path("/a"), "log directory": Path("/b")},
        lambda _p: DiskUsage(_TOTAL, 50 * GIB),
    )

    findings = check.run(PreflightScope()).findings

    assert [f.subject for f in findings] == ["data root", "log directory"]


def test_a_directory_not_created_yet_is_measured_through_its_parent(
    tmp_path: Path,
) -> None:
    seen: list[Path] = []

    def read(path: Path) -> DiskUsage:
        seen.append(path)
        return DiskUsage(_TOTAL, 50 * GIB)

    DiskSpaceCheck({"log directory": tmp_path / "logs" / "deeper"}, read).run(
        PreflightScope()
    )

    assert seen == [tmp_path]


def test_an_unreadable_disk_is_a_fail() -> None:
    def read(_path: Path) -> DiskUsage:
        raise OSError("gone")

    check = DiskSpaceCheck({"data root": Path("/")}, read)

    assert check.run(PreflightScope()).status is CheckStatus.FAIL


def test_a_writable_data_root_passes_and_leaves_nothing_behind(tmp_path: Path) -> None:
    result = DataRootWritableCheck(tmp_path).run(PreflightScope())

    assert result.status is CheckStatus.PASS
    assert list(tmp_path.iterdir()) == []


def test_a_missing_data_root_fails(tmp_path: Path) -> None:
    assert (
        DataRootWritableCheck(tmp_path / "nope").run(PreflightScope()).status
        is CheckStatus.FAIL
    )


def test_a_data_root_that_is_a_file_fails(tmp_path: Path) -> None:
    file = tmp_path / "f"
    file.write_text("x")

    assert DataRootWritableCheck(file).run(PreflightScope()).status is CheckStatus.FAIL


def test_a_data_root_that_refuses_a_write_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(*_args: object, **_kwargs: object) -> None:
        raise PermissionError("read-only file system")

    monkeypatch.setattr(
        "Sagittarius_Elite_Warrior.src.modules.operations.adapters."
        "data_root_writable_check.tempfile.NamedTemporaryFile",
        refuse,
    )

    result = DataRootWritableCheck(tmp_path).run(PreflightScope())

    assert result.status is CheckStatus.FAIL
    assert "PermissionError" in result.findings[0].reason


@pytest.mark.parametrize(
    ("running", "expected"),
    [
        ((3, 11, 9), CheckStatus.FAIL),
        ((3, 12, 0), CheckStatus.PASS),
        ((3, 13, 1), CheckStatus.PASS),
        ((4, 0, 0), CheckStatus.PASS),
    ],
)
def test_the_python_floor(running: tuple[int, int, int], expected: CheckStatus) -> None:
    assert PythonFloorCheck(lambda: running).run(PreflightScope()).status is expected


def test_the_python_floor_matches_pyproject() -> None:
    data = tomllib.loads((repo_root() / "pyproject.toml").read_text(encoding="utf-8"))
    floor = ".".join(str(n) for n in SUPPORTED_PYTHON_FLOOR)

    assert data["project"]["requires-python"] == f">={floor}"
