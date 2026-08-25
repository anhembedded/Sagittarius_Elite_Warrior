"""
Sanity tier — the declared Python floor is true, not merely written down.

`pyproject.toml` says `requires-python = ">=3.12"`. Nothing normally checks
that: a developer on 3.13 can use 3.13-only syntax, every test passes on their
machine, and the declaration quietly becomes false. The failure only surfaces
for whoever installs on the floor version — which is exactly the shape of
BUG-044, where a published package could not be imported at all while its own
CI was green.

`ast.parse(..., feature_version=...)` re-parses each module as the floor
interpreter would, so this holds on any interpreter the suite happens to run on.
It is a syntax check only — it cannot see a 3.13-only standard-library call —
but syntax is the class that breaks import outright, and import is what this
tier exists to prove.

Belongs here rather than in unit tests for the reason the tier exists: whether
the application can come into existence at all, on the platform it claims to
support. See `Tasks/epics/EPIC-009_sanity_tier_redesign/`.
"""

from __future__ import annotations

import ast
import re
import sys
import tomllib
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FIRST_PARTY_DIRS = ("src", "scripts", "tests")


def _declared_floor() -> tuple[int, int]:
    """The floor from `pyproject.toml`, so this guard cannot drift from it."""
    config = tomllib.loads((_REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    spec = config["project"]["requires-python"]

    match = re.fullmatch(r">=\s*(\d+)\.(\d+)", spec.strip())
    assert match, (
        f"requires-python is {spec!r}; this guard only understands a simple "
        f">=MAJOR.MINOR floor. Widen the parser deliberately rather than "
        f"loosening the check."
    )
    return int(match[1]), int(match[2])


def test_the_declared_floor_is_one_this_interpreter_can_check() -> None:
    """`feature_version` cannot validate syntax newer than the running
    interpreter, so a run below the floor would silently under-check."""
    floor = _declared_floor()
    assert sys.version_info[:2] >= floor, (
        f"Running on {sys.version_info.major}.{sys.version_info.minor}, below "
        f"the declared floor {floor[0]}.{floor[1]} — the whole suite is being "
        f"run on an unsupported interpreter."
    )


def test_every_first_party_module_parses_at_the_declared_floor() -> None:
    """No first-party file may use syntax newer than `requires-python` claims.

    Scans rather than lists, so a new directory or module is covered the moment
    it exists.
    """
    floor = _declared_floor()

    offenders: list[str] = []
    checked = 0
    for directory in _FIRST_PARTY_DIRS:
        for path in sorted((_REPO_ROOT / directory).rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            checked += 1
            source = path.read_text(encoding="utf-8")
            try:
                ast.parse(source, filename=str(path), feature_version=floor)
            except SyntaxError as exc:
                offenders.append(
                    f"{path.relative_to(_REPO_ROOT)}:{exc.lineno} — {exc.msg}"
                )

    assert checked > 0, (
        "Scanned the first-party directories and found no Python files — the "
        "scan is broken, which would make this guard silently vacuous."
    )
    assert offenders == [], (
        f"{len(offenders)} of {checked} first-party file(s) use syntax newer "
        f"than the declared floor {floor[0]}.{floor[1]}. Either lower the "
        f"syntax or raise `requires-python` deliberately:\n  " + "\n  ".join(offenders)
    )


@pytest.mark.parametrize("directory", _FIRST_PARTY_DIRS)
def test_first_party_directory_exists(directory: str) -> None:
    """Guards the scan above: a renamed directory would otherwise make it check
    less and still pass."""
    assert (_REPO_ROOT / directory).is_dir(), (
        f"`{directory}/` does not exist — test_every_first_party_module_parses_"
        f"at_the_declared_floor is scanning a stale directory list."
    )
