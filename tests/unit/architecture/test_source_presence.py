"""Regression for `BUG-198`: a directory left behind by a deleted package (bytecode caches
only) is not a package. The guards that discover their subjects by listing directories
(`test_every_support_package_is_in_the_catalog.py`, `test_module_declarations.py`) failed
on every checkout that had ever held the deleted package, and passed on a clean CI one.

Retire when: the guards discover packages from git (`git_tracked_paths.py`) instead.
"""

from __future__ import annotations

from pathlib import Path

from Sagittarius_Elite_Warrior.tests.unit.architecture.capability_catalog_checks import (
    unit_directories,
)
from Sagittarius_Elite_Warrior.tests.unit.architecture.source_presence import (
    holds_python_source,
)
from Sagittarius_Elite_Warrior.tests.unit.architecture.test_module_declarations import (
    _packages_on_disk,
)


def _stale_shell(parent: Path) -> None:
    """What `git pull` leaves of a deleted package: caches and empty folders only."""
    (parent / "__pycache__").mkdir(parents=True)
    (parent / "__pycache__" / "gone.cpython-313.pyc").write_bytes(b"\0")
    (parent / "sub" / "__pycache__").mkdir(parents=True)


def _package(parent: Path, *, nested: bool = False) -> None:
    where = parent / "inner" if nested else parent
    where.mkdir(parents=True)
    (where / "__init__.py").write_text('"""A package."""\n', encoding="utf-8")


def test_a_directory_of_bytecode_caches_holds_no_source(tmp_path: Path) -> None:
    _stale_shell(tmp_path / "gone")
    assert not holds_python_source(tmp_path / "gone")


def test_a_package_and_a_package_below_a_folder_hold_source(tmp_path: Path) -> None:
    _package(tmp_path / "direct")
    _package(tmp_path / "nested", nested=True)
    assert holds_python_source(tmp_path / "direct")
    assert holds_python_source(tmp_path / "nested")


def test_a_stale_shell_is_not_a_support_unit(tmp_path: Path) -> None:
    support = tmp_path / "support"
    _package(support / "real")
    _stale_shell(support / "gone")
    assert unit_directories(support) == [support / "real"]


def test_a_stale_shell_is_not_a_module_package(tmp_path: Path) -> None:
    _package(tmp_path / "real")
    _stale_shell(tmp_path / "gone")
    assert _packages_on_disk(tmp_path) == {"real"}
