"""
UI Preview Convention (BOT-031), the half that needs Qt: every `build_preview()`
`scripts/preview_qml.py` discovers builds cleanly in offscreen mode, with zero
exceptions and zero QML errors.

The static half — every presenter package has a `preview.py` defining
`build_preview`, and no preview uses a relative import — moved to
`tests/unit/architecture/test_every_presenter_package_has_a_preview.py`
(`EPIC-030G`): the check that lived here listed its targets from
`src/presentation/ui/screens/`, a directory `EPIC-025` deleted, and fell back
to an empty list, so it had been checking only the sidebar.
"""

from __future__ import annotations

import os

from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.scripts.preview_qml import discover_previews
from Sagittarius_Elite_Warrior.src.support.ui_kit.theme_bootstrap import (
    seed_app_theme,
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_discover_previews_finds_all_targets():
    """
    Asserts discover_previews() auto-discovers all screen keys.
    """
    previews = discover_previews()
    expected_keys = {"bots_screen", "data_management", "dashboard", "backtest"}
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
