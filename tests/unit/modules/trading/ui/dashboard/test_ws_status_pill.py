"""`WsStatusPill` — Dev Board's websocket status readout.

Restated from `test_status_pill_widget.py` when `EPIC-025` PR 4.3l deleted
`StatusPill.qml` and its `QQuickWidget` host. Three of the four promises are the
same sentences against two `QLabel`s; the fourth — that the widget loads with a
real QML root object — has no subject, and its place is taken by the one thing
the QML version could not be asked: that an unknown tone still renders.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtGui import QPalette
from Sagittarius_Elite_Warrior.src.modules.trading.ui.dashboard.ws_status_pill import (
    WsStatusPill,
)


def _dot_colour(pill: WsStatusPill) -> str:
    return pill._dot.palette().color(QPalette.ColorRole.WindowText).name()


def test_set_text_reaches_the_label(qtbot):
    pill = WsStatusPill()
    qtbot.addWidget(pill)

    pill.set_text("WS: streaming")

    assert pill._label.text() == "WS: streaming"


@pytest.mark.parametrize("tone", ["idle", "active", "success", "danger"])
def test_every_tone_in_the_vocabulary_renders(qtbot, tone):
    """The four names `dashboard_presenter.py`'s `_WS_STATUS_BY_MODE` maps
    `UIMode` onto — not `Tone`'s three, which have no word for "active"."""
    pill = WsStatusPill()
    qtbot.addWidget(pill)

    pill.set_tone(tone)

    assert pill._dot.isVisible() is False  # never shown; the panel is not up
    assert _dot_colour(pill)


def test_the_three_live_tones_read_differently_from_each_other(qtbot):
    pill = WsStatusPill()
    qtbot.addWidget(pill)

    colours = set()
    for tone in ("active", "success", "danger"):
        pill.set_tone(tone)
        colours.add(_dot_colour(pill))

    assert len(colours) == 3


def test_idle_keeps_the_platforms_own_colour(qtbot):
    """A connection doing nothing gets no verdict, which is what every other
    widget in this app does with `Tone.NEUTRAL`."""
    pill = WsStatusPill()
    qtbot.addWidget(pill)

    pill.set_tone("danger")
    toned = _dot_colour(pill)
    pill.set_tone("idle")

    assert _dot_colour(pill) != toned
    assert (
        _dot_colour(pill)
        == pill._label.palette().color(QPalette.ColorRole.WindowText).name()
    )


def test_an_unknown_tone_renders_as_idle_rather_than_raising(qtbot):
    """A pill is a status readout: failing to draw one would hide the status
    it exists to report."""
    pill = WsStatusPill()
    qtbot.addWidget(pill)

    pill.set_tone("nonsense")

    assert _dot_colour(pill) == QPalette().color(QPalette.ColorRole.WindowText).name()


def test_set_show_dot_hides_and_shows_the_dot(qtbot):
    pill = WsStatusPill()
    qtbot.addWidget(pill)

    pill.set_show_dot(False)
    assert pill._dot.isVisibleTo(pill) is False

    pill.set_show_dot(True)
    assert pill._dot.isVisibleTo(pill) is True
