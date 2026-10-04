"""Every presenter package ships a `preview.py` (`ui-presentation-rule.md`,
the `BOT-031` preview convention).

**Why this guard exists** (`EPIC-030G`). The convention's static check lived
in `tests/unit/presentation/ui/test_preview_fixtures_exist.py` and listed
its targets from `src/presentation/ui/screens/` — a directory `EPIC-025`
deleted. It fell back to `[]` when the root was missing, so for every screen
that moved into `modules/*/ui` or `shell/` it checked nothing and stayed
green. The 2026-10-04 audit found four presenter packages without a preview
and no test that could have said so.

**The rule.** A directory holding a `*_presenter.py` anywhere under `src/`
except `src/support/` holds a `preview.py` that defines
`build_preview` (checked with `ast`; nothing is imported), unless it is listed
in `baseline_presenter_packages_without_preview.txt`, which only shrinks.
Separately, no `preview.py` anywhere under `src/` uses a relative import:
`scripts/preview_qml.py` loads each one by path, with no parent package, so
the relative form raises at discovery time for every preview at once.

`src/support/` is left out because a support package holds shared bases, never
a screen (`support/ui_kit/options_section_presenter.py` is the base every
Options page builds on). Scanning the rest of `src/` keeps a future presenter
in `shell/` or `presentation/` covered without a root to remember: the shell
held none once `EPIC-033E` deleted the Settings screen.

A scanned root that does not exist fails loudly — the silent `[]` fallback is
the defect this file replaces.

Stdlib only: no Qt. Building each preview is
`test_preview_fixtures_exist.py`'s job.

Retire when: presenters stop being the unit a preview is written for (the
convention moves to another seam), or the preview convention is dropped from
`ui-presentation-rule.md`.
"""

from __future__ import annotations

import ast
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SRC_ROOT = _REPO_ROOT / "src"
_SUPPORT_ROOT = _REPO_ROOT / "src" / "support"
_BASELINE_FILE = Path(__file__).with_name(
    "baseline_presenter_packages_without_preview.txt"
)

_PREVIEW_FILE = "preview.py"
_BUILD_FUNCTION = "build_preview"
_COMMENT = "#"

#: Measured 2026-10-04: 12 presenter packages, 10 `preview.py` files. Floors
#: that catch a lost subject, not churn.
_MIN_PRESENTER_PACKAGES = 8
_MIN_PREVIEW_FILES = 5


# --------------------------------------------------------------------------- #
# Pure helpers                                                                #
# --------------------------------------------------------------------------- #


def defines_build_preview(source: str) -> bool:
    """`True` when `source` defines a module-level `build_preview`."""
    return any(
        isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        and node.name == _BUILD_FUNCTION
        for node in ast.parse(source).body
    )


def relative_imports(source: str) -> list[tuple[int, str]]:
    """`(line, rendered import)` for every relative import in `source`."""
    return [
        (node.lineno, f"from {'.' * node.level}{node.module or ''} import ...")
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ImportFrom) and node.level
    ]


def _read_baseline() -> list[str]:
    entries: list[str] = []
    for raw in _BASELINE_FILE.read_text(encoding="utf-8").splitlines():
        line = raw.split(_COMMENT, 1)[0].strip()
        if line:
            entries.append(line)
    return entries


# --------------------------------------------------------------------------- #
# The tree                                                                    #
# --------------------------------------------------------------------------- #


def _require_root(root: Path) -> Path:
    if not root.is_dir():
        raise FileNotFoundError(
            f"{root} does not exist — the presenter tree moved; retarget this "
            "guard rather than letting it scan nothing"
        )
    return root


def _presenter_packages() -> list[Path]:
    """Every directory that holds a `*_presenter.py`."""
    _require_root(_SRC_ROOT)
    presenters = (
        path
        for path in _SRC_ROOT.rglob("*_presenter.py")
        if "__pycache__" not in path.parts and _SUPPORT_ROOT not in path.parents
    )
    return sorted({path.parent for path in presenters})


def _packages_without_a_preview() -> list[str]:
    missing: list[str] = []
    for package in _presenter_packages():
        preview = package / _PREVIEW_FILE
        if not preview.is_file() or not defines_build_preview(
            preview.read_text(encoding="utf-8")
        ):
            missing.append(package.relative_to(_REPO_ROOT).as_posix())
    return missing


def _preview_files() -> list[Path]:
    _require_root(_SRC_ROOT)
    return sorted(
        p for p in _SRC_ROOT.rglob("preview.py") if "__pycache__" not in p.parts
    )


def test_the_scan_has_a_subject() -> None:
    packages = _presenter_packages()
    assert len(packages) >= _MIN_PRESENTER_PACKAGES, packages
    assert len(_preview_files()) >= _MIN_PREVIEW_FILES


def test_a_missing_root_fails_loudly(tmp_path: Path) -> None:
    missing = tmp_path / "gone"
    try:
        _require_root(missing)
    except FileNotFoundError as error:
        assert str(missing) in str(error)
    else:
        raise AssertionError("a missing scan root was accepted silently")


def test_every_presenter_package_has_a_preview() -> None:
    recorded = set(_read_baseline())
    new = [
        package for package in _packages_without_a_preview() if package not in recorded
    ]
    assert new == [], (
        "a presenter package has no preview.py defining build_preview() "
        "(ui-presentation-rule.md, BOT-031). Add one — it must build the view "
        "with no container and no engine boot:\n"
        + "\n".join(f"  - {package}" for package in new)
    )


def test_the_baseline_has_not_gone_stale() -> None:
    stale = sorted(set(_read_baseline()) - set(_packages_without_a_preview()))
    assert stale == [], (
        "these packages now have a preview (or no longer hold a presenter) — "
        "delete them from the baseline:\n" + "\n".join(f"  - {s}" for s in stale)
    )


def test_the_baseline_has_no_duplicate_entries() -> None:
    entries = _read_baseline()
    assert len(entries) == len(set(entries)), "duplicate lines in the baseline"


def test_no_preview_uses_a_relative_import() -> None:
    """`preview.py` is loaded **by path** by `scripts/preview_qml.py`, never as
    part of its package, so a relative import raises `ImportError: attempted
    relative import with no known parent package` — at discovery time, for
    every preview (`EPIC-025` PR 1.6d broke the sidebar's this way). Every
    `preview.py` under `src/`, not only the legacy UI tree the earlier
    version of this check scanned."""
    offenders = [
        f"  {preview.relative_to(_REPO_ROOT).as_posix()}:{line}: {rendered}"
        for preview in _preview_files()
        for line, rendered in relative_imports(preview.read_text(encoding="utf-8"))
    ]
    assert offenders == [], (
        "a `preview.py` uses a relative import. It is imported by path, not as "
        "part of its package — write the full dotted path:\n" + "\n".join(offenders)
    )


# --------------------------------------------------------------------------- #
# Probes: the guard can fail                                                  #
# --------------------------------------------------------------------------- #


def test_a_preview_without_build_preview_does_not_count() -> None:
    assert defines_build_preview("def build_other():\n    pass\n") is False
    assert (
        defines_build_preview("class P:\n    def build_preview(self):\n        pass\n")
        is False
    )
    assert defines_build_preview("def build_preview():\n    pass\n") is True


def test_a_relative_import_is_seen() -> None:
    source = "from .watchlist_view import WatchlistView\nfrom .. import x\n"
    assert relative_imports(source) == [
        (1, "from .watchlist_view import ..."),
        (2, "from .. import ..."),
    ]


def test_an_absolute_import_is_not_flagged() -> None:
    source = "from Sagittarius_Elite_Warrior.src.shell.welcome.x import X\n"
    assert relative_imports(source) == []
