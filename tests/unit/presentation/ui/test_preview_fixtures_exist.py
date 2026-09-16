"""
Guard test for UI Preview Convention (BOT-031).

Enforces the architectural rule:
1. Every screen package in `src/presentation/ui/screens/` and the `src/support/ui_kit/sidebar/`
   component must provide a `preview.py` file exposing a `build_preview() -> QWidget` function.
2. Every discovered `build_preview()` can be executed cleanly in offscreen mode with zero exceptions
   and zero QML syntax/runtime errors.
"""

from __future__ import annotations

import ast
import os
from pathlib import Path

from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.scripts.preview_qml import discover_previews
from Sagittarius_Elite_Warrior.src.support.ui_kit.theme_bootstrap import (
    seed_app_theme,
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_REPO_ROOT = Path(__file__).resolve().parents[4]
_SCREENS_DIR = _REPO_ROOT / "src" / "presentation" / "ui" / "screens"
#: `support/ui_kit/sidebar` since `EPIC-025` PR 1.6d. The convention is about
#: the widget, not the directory it currently sits in.
_SIDEBAR_DIR = _REPO_ROOT / "src" / "support" / "ui_kit" / "sidebar"


def test_every_screen_and_sidebar_has_preview_file():
    """
    AST/filesystem check:
    Asserts every screen directory and the sidebar directory has a `preview.py`
    declaring a `build_preview` function.
    """
    targets: list[Path] = [
        d
        for d in _SCREENS_DIR.iterdir()
        if d.is_dir() and not d.name.startswith(("_", "."))
    ]
    if _SIDEBAR_DIR.is_dir():
        targets.append(_SIDEBAR_DIR)

    missing_previews: list[str] = []
    missing_build_fn: list[str] = []

    for target in targets:
        preview_file = target / "preview.py"
        if not preview_file.is_file():
            missing_previews.append(f"{target.name}/preview.py")
            continue

        tree = ast.parse(
            preview_file.read_text(encoding="utf-8"), filename=str(preview_file)
        )
        func_names = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        if "build_preview" not in func_names:
            missing_build_fn.append(
                f"{target.name}/preview.py (missing build_preview())"
            )

    assert not missing_previews, (
        "The following UI packages are missing preview.py (BOT-031 convention):\n"
        + "\n".join(f"  - {m}" for m in missing_previews)
    )
    assert not missing_build_fn, (
        "The following preview.py files do not declare build_preview():\n"
        + "\n".join(f"  - {m}" for m in missing_build_fn)
    )


def test_discover_previews_finds_all_targets():
    """
    Asserts discover_previews() auto-discovers all screen keys.
    """
    previews = discover_previews()
    expected_keys = {"sidebar", "settings", "data_management", "dashboard", "backtest"}
    assert expected_keys.issubset(set(previews.keys())), (
        f"discover_previews() missing expected keys. Found: {list(previews.keys())}"
    )


def test_all_discovered_previews_build_cleanly(qapp):
    """
    Constructs every discovered preview in offscreen Qt mode and asserts 0 QML errors.
    """
    # Idempotent, and the session fixture in `tests/conftest.py` has already
    # run it — kept because a preview is the one thing here that loads QML
    # from a bare build function, and `seed_app_theme()` is what makes the
    # engine's QML factory usable (`BOT-132` turned its absence into a hard
    # failure). One call, not the engine pair spelled out again (`BOT-133`).
    seed_app_theme()
    previews = discover_previews()
    assert len(previews) > 0, "No previews discovered"

    for name, build_fn in previews.items():
        widget = build_fn()
        assert isinstance(widget, QWidget), (
            f"Preview for '{name}' did not return a QWidget"
        )

        if hasattr(widget, "errors"):
            errors = widget.errors()
            assert errors == [], f"QML errors in preview for '{name}': {errors}"

        for child_qw in widget.findChildren(QQuickWidget):
            errors = child_qw.errors()
            assert errors == [], (
                f"QML errors in child QQuickWidget of '{name}': {errors}"
            )

        widget.deleteLater()
        qapp.processEvents()


def test_no_preview_uses_a_relative_import():
    """`preview.py` is loaded **by path** by `scripts/preview_qml.py`, never as
    part of its package, so a relative import raises `ImportError: attempted
    relative import with no known parent package` — at discovery time, for
    every preview, not just the one that was edited.

    `EPIC-025` PR 1.6d is why this exists. Moving `sidebar/` into
    `support/ui_kit` rewrote its preview's imports to absolute, a follow-up
    pass restored intra-package imports to relative form (right for every
    other file in the package), and this one broke. Nothing but the preview
    tests would have said so, and they say it as an `ImportError` rather than
    as the rule that was violated.
    """
    offenders: list[str] = []
    for root in ("src/presentation/ui", "src/support/ui_kit"):
        for preview in sorted((_REPO_ROOT / root).rglob("preview.py")):
            tree = ast.parse(preview.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.level:
                    offenders.append(
                        f"{preview.relative_to(_REPO_ROOT).as_posix()}:{node.lineno}: "
                        f"from {'.' * node.level}{node.module or ''} import ..."
                    )

    assert offenders == [], (
        "a `preview.py` uses a relative import. It is imported by path, not as "
        "part of its package, so the relative form cannot resolve — write the "
        "full dotted path:\n" + "\n".join(offenders)
    )
