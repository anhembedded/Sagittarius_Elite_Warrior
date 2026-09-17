"""`kit.ProgressBanner` — a caption, a bar, and a Cancel button.

Restated from `test_progress_banner_widget.py` when `EPIC-025` PR 4.3l deleted
`ProgressBanner.qml` and the `QQuickWidget` that hosted it. All four promises
are the same sentences; what changed is that they read a `QProgressBar` and a
`QPushButton` instead of `setProperty` values on a QML root.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from Sagittarius_Elite_Warrior.src.support.ui_kit.kit import ProgressBanner


def test_the_setters_reach_the_controls(qtbot):
    banner = ProgressBanner()
    qtbot.addWidget(banner)

    banner.set_status_text("Syncing BTCUSDT…")
    banner.set_percent(37.5)
    banner.set_cancel_label("Stop")

    assert banner._status.text() == "Syncing BTCUSDT…"
    # Tenths of a percent, so 37.5% is not rounded to 38.
    assert banner._bar.value() == 375
    assert banner._cancel.text() == "Stop"


def test_a_percent_outside_the_range_is_clamped(qtbot):
    banner = ProgressBanner()
    qtbot.addWidget(banner)

    banner.set_percent(-5.0)
    assert banner._bar.value() == 0

    banner.set_percent(140.0)
    assert banner._bar.value() == banner._bar.maximum()


def test_set_indeterminate_shows_a_sweep_and_is_reversible(qtbot):
    """`StyledProgressBar` remembers the range it came from, which is what
    makes "back to a measured bar" possible at all."""
    banner = ProgressBanner()
    qtbot.addWidget(banner)
    banner.set_percent(50.0)

    banner.set_indeterminate(True)
    assert banner._bar.indeterminate is True

    banner.set_indeterminate(False)
    assert banner._bar.indeterminate is False
    assert banner._bar.maximum() == 1000


def test_set_cancelling_disables_the_button_without_renaming_it(qtbot):
    """Two of the three callers have their own word for "cancelling", so this
    class does not invent one — they say it with `set_cancel_label`."""
    banner = ProgressBanner()
    qtbot.addWidget(banner)
    banner.set_cancel_label("Cancel sync")

    banner.set_cancelling(True)

    assert banner._cancel.isEnabled() is False
    assert banner._cancel.text() == "Cancel sync"

    banner.set_cancelling(False)
    assert banner._cancel.isEnabled() is True


def test_clicking_cancel_emits_cancel_requested(qtbot):
    banner = ProgressBanner()
    qtbot.addWidget(banner)

    with qtbot.waitSignal(banner.cancelRequested, timeout=1000):
        banner._cancel.click()


def test_the_banner_carries_no_stylesheet_of_its_own(qtbot):
    banner = ProgressBanner()
    qtbot.addWidget(banner)

    assert banner.styleSheet() == ""
    assert banner._status.styleSheet() == ""
