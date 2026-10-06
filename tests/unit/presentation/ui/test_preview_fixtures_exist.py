"""
UI Preview Convention (BOT-031), the half that needs Qt: every `build_preview()`
`scripts/preview_qml.py` discovers builds cleanly in offscreen mode, with zero
exceptions. (It also read each preview's QML errors until `EPIC-033M` deleted
the last `.qml`; `test_quick_widget_only_in_embed.py` now bans `QQuickWidget`
from `src/` outright, so there is no QML left to report one.)

The static half — every presenter package has a `preview.py` defining
`build_preview`, and no preview uses a relative import — moved to
`tests/unit/architecture/test_every_presenter_package_has_a_preview.py`
(`EPIC-030G`): the check that lived here listed its targets from
`src/presentation/ui/screens/`, a directory `EPIC-025` deleted, and fell back
to an empty list, so it had been checking only the sidebar.
"""

from __future__ import annotations

import os

from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.scripts.preview_qml import discover_previews

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_discover_previews_finds_all_targets():
    """
    Asserts discover_previews() auto-discovers all screen keys.
    """
    previews = discover_previews()
    expected_keys = {"bots_screen", "data_management", "market_mode", "backtest"}
    assert expected_keys.issubset(set(previews.keys())), (
        f"discover_previews() missing expected keys. Found: {list(previews.keys())}"
    )


def test_all_discovered_previews_build_cleanly(qapp):
    """
    Constructs every discovered preview in offscreen Qt mode.
    """
    previews = discover_previews()
    assert len(previews) > 0, "No previews discovered"

    for name, build_fn in previews.items():
        widget = build_fn()
        assert isinstance(widget, QWidget), (
            f"Preview for '{name}' did not return a QWidget"
        )

        widget.deleteLater()
        qapp.processEvents()
