"""What mypy skips only shrinks, and every override reaches a module (`EPIC-032A`).

**Why this guard exists.** `code/quality.md` §1 gates typing on mypy, but two
parts of `pyproject.toml`'s `[tool.mypy]` decide what that gate sees, and
neither was checked:

* **`exclude`** — 69 path patterns mypy never reads. Nothing stopped a 70th.
* **`[[tool.mypy.overrides]]`** — the strict settings for Domain and
  Application targeted `src.domain.*` and `src.application.*`, which `EPIC-025`
  moved under `src/modules/*/`. For months they matched nothing and the strict
  check covered no file; mypy reports an unused section only as a note, and
  only under `warn_unused_configs`, so the gate stayed green.

**The ratchets.** `baseline_mypy_excludes.txt` holds the patterns as found: a
pattern not listed fails, a listed one no longer in `pyproject.toml` fails, and
a pattern that matches no file fails. Every first-party override must match at
least one module of `src` or `scripts`, and `warn_unused_configs` stays on.

Retire when: the `exclude` list is empty, and mypy itself fails on an unused
override section.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest
from mypy.options import Options

_REPO_ROOT = Path(__file__).resolve().parents[3]
_BASELINE_FILE = Path(__file__).with_name("baseline_mypy_excludes.txt")
_PACKAGE = _REPO_ROOT.name
_FIRST_PARTY = f"{_PACKAGE}."
_SCANNED = ("src", "scripts")
_COMMENT = "#"


def _mypy_config() -> dict[str, object]:
    config = tomllib.loads((_REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    mypy: dict[str, object] = config["tool"]["mypy"]
    return mypy


def _excludes() -> list[str]:
    patterns = _mypy_config().get("exclude", [])
    assert isinstance(patterns, list)
    return [str(p) for p in patterns]


def _read_baseline() -> list[str]:
    entries: list[str] = []
    for raw in _BASELINE_FILE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith(_COMMENT):
            entries.append(line)
    return entries


def _python_files() -> list[Path]:
    files: list[Path] = []
    for tree in _SCANNED:
        root = _REPO_ROOT / tree
        if not root.is_dir():
            raise FileNotFoundError(f"{root} does not exist; retarget this guard")
        files.extend(p for p in root.rglob("*.py") if "__pycache__" not in p.parts)
    return files


def _mypy_paths() -> list[str]:
    """Each file as mypy sees it: run from the workspace root, prefixed by the package."""
    return [
        f"{_PACKAGE}/{p.relative_to(_REPO_ROOT).as_posix()}" for p in _python_files()
    ]


def module_names(paths: list[str]) -> set[str]:
    """Dotted module names for `.py` paths, packages under their own name."""
    names: set[str] = set()
    for path in paths:
        parts = path.removesuffix(".py").split("/")
        if parts[-1] == "__init__":
            parts = parts[:-1]
        names.add(".".join(parts))
    return names


def override_pattern(module: str) -> re.Pattern[str]:
    """The regex mypy itself compiles for an override's `module` glob.

    mypy's own compiler, not a copy: a `.*` matches zero or more sections,
    in the middle of a pattern as at its end (PR #330 review).
    """
    return Options().compile_glob(module)


def unmatched_overrides(overrides: list[str], modules: set[str]) -> list[str]:
    return [
        module
        for module in overrides
        if not any(override_pattern(module).match(name) for name in modules)
    ]


def _first_party_overrides() -> list[str]:
    sections = _mypy_config().get("overrides", [])
    assert isinstance(sections, list)
    modules: list[str] = []
    for section in sections:
        listed = section["module"]
        modules.extend([listed] if isinstance(listed, str) else listed)
    return [m for m in modules if m.startswith(_FIRST_PARTY)]


def test_the_scan_has_a_subject() -> None:
    assert _excludes(), "pyproject.toml lost [tool.mypy] exclude; retarget this guard"
    assert _first_party_overrides()


def test_no_exclude_was_added() -> None:
    added = sorted(set(_excludes()) - set(_read_baseline()))
    assert not added, (
        "mypy exclude patterns not in the baseline; type the file instead:\n"
        + "\n".join(f"  - {a}" for a in added)
    )


def test_the_baseline_has_not_gone_stale() -> None:
    stale = sorted(set(_read_baseline()) - set(_excludes()))
    assert not stale, "baseline lines with no pattern left; remove them:\n" + "\n".join(
        f"  - {s}" for s in stale
    )


def test_every_exclude_still_matches_a_file() -> None:
    paths = _mypy_paths()
    dead = [p for p in _excludes() if not any(re.search(p, path) for path in paths)]
    assert not dead, "exclude patterns that match no file; delete them:\n" + "\n".join(
        f"  - {d}" for d in dead
    )


def test_every_first_party_override_matches_a_module() -> None:
    dead = unmatched_overrides(_first_party_overrides(), module_names(_mypy_paths()))
    assert not dead, (
        "mypy overrides that match no module; retarget them:\n"
        + "\n".join(f"  - {d}" for d in dead)
    )


def test_unused_configs_are_reported() -> None:
    assert _mypy_config().get("warn_unused_configs") is True


@pytest.mark.parametrize(
    ("pattern", "module", "matches"),
    [
        ("pkg.src.modules.*.domain.*", "pkg.src.modules.bots.domain", True),
        ("pkg.src.modules.*.domain.*", "pkg.src.modules.bots.domain.grid.level", True),
        ("pkg.src.modules.*.domain.*", "pkg.src.modules.domain", True),
        ("pkg.src.domain.*", "pkg.src.modules.bots.domain", False),
        ("pkg.src.a.b", "pkg.src.a.b", True),
        ("pkg.src.a.b", "pkg.src.a.bc", False),
    ],
)
def test_override_patterns_match_like_mypy(
    pattern: str, module: str, matches: bool
) -> None:
    assert bool(override_pattern(pattern).match(module)) is matches


def test_a_moved_tree_leaves_its_override_unmatched() -> None:
    modules = {"pkg.src.modules.bots.domain.grid"}
    assert unmatched_overrides(["pkg.src.domain.*"], modules) == ["pkg.src.domain.*"]
