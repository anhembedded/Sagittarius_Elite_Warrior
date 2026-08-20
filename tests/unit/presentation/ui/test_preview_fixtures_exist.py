"""
Guard test for UI Preview Convention (BOT-031).

Enforces the architectural rule:
1. Every screen package in `src/presentation/ui/screens/` and the `src/presentation/ui/components/sidebar/`
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
from Sagittarius_Elite_Warrior.src.presentation.ui.assets import (
    Palette,
    get_icon_loader,
)
from sagittarius_engine.extensions.pyside_mvc import configure_app_qml

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_REPO_ROOT = Path(__file__).resolve().parents[4]
_SCREENS_DIR = _REPO_ROOT / "src" / "presentation" / "ui" / "screens"
_SIDEBAR_DIR = _REPO_ROOT / "src" / "presentation" / "ui" / "components" / "sidebar"


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
    configure_app_qml(Palette.as_ui_dict(), get_icon_loader(), Palette.as_icon_dict())
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
