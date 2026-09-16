"""`QmlOverlay` fails loudly — the one promise left in this file.

It was `test_qml_modal_bodies.py`, holding the two `EPIC-015` bậc 1 pilots:
`TimezonePickerDialog` (moved to `kit.PickerOverlay` in `EPIC-025` PR 4.3e,
restated at `…/screens/backtest/test_select_dialogs.py`) and
`CapitalDialogWidget` (moved in PR 4.3f, restated at
`…/screens/backtest/test_capital_dialog.py`). Renamed rather than deleted
because the third test never was about either of them: `QmlOverlay` is still
the host of every `.qml` ADR D21 has not reached yet, and a `QQuickWidget`
whose source fails to load renders an empty rectangle and says nothing. This
file is the one place that behaviour is pinned, and it goes with the last
`.qml`.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


def test_a_broken_qml_file_raises_instead_of_rendering_a_blank_box(qapp, tmp_path):
    """A `QQuickWidget` whose source fails to load renders an empty rectangle
    and says nothing. `QmlOverlay` turns that into an exception once, so every
    migrated modal inherits the loud failure rather than each discovering it."""
    from Sagittarius_Elite_Warrior.src.presentation.ui.qml import QmlOverlay

    broken = tmp_path / "Broken.qml"
    broken.write_text("import QtQuick\nItem { this is not qml }\n")

    with pytest.raises(RuntimeError, match="QML failed to load"):
        QmlOverlay("X", qml_file=broken, context={})
