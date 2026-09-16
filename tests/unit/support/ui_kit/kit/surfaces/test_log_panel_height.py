"""`BOT-127` — the console band must not hold space it has nothing to show in.

`PageShell` lays its console band out at the band's size hint (stretch 0), and
that hint came from `QListView`'s Qt default, which is a constant with no
relation to the model. Measured on the real app at 1920x1080: the Trading
screen's console held **244px while showing a single line of log**, taken
permanently from the workspace above it.

These lock the height on the thing that actually determines it — the number of
rows — rather than on a pixel figure, which would be the same hard-coded band
height in a different place.
"""

from __future__ import annotations

from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt
from Sagittarius_Elite_Warrior.src.support.ui_kit.kit.surfaces.log_panel import (
    _MAX_VISIBLE_ROWS,
    LogPanel,
)

#: Qt's own "no parent" sentinel, hoisted out of the signature: calling
#: `QModelIndex()` in a default argument builds it once at import and shares it,
#: which `B008` flags for exactly the mutable-default reasons this repo's own
#: rules give.
_NO_PARENT = QModelIndex()


class _Rows(QAbstractListModel):
    """The narrowest model `LogPanel` accepts — only `rowCount` matters here."""

    def __init__(self, count: int) -> None:
        super().__init__()
        self._count = count

    def rowCount(self, parent: QModelIndex = _NO_PARENT) -> int:  # noqa: N802
        return 0 if parent.isValid() else self._count

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        return f"line {index.row()}" if role == Qt.ItemDataRole.DisplayRole else None


def _panel(qtbot) -> LogPanel:
    panel = LogPanel("Console", copy_text="Copy", clear_text="Clear")
    qtbot.addWidget(panel)
    return panel


def test_an_empty_console_asks_for_less_than_a_full_one(qtbot) -> None:
    """The defect, stated as a relationship rather than a pixel count: an empty
    log used to ask for exactly as much as a full one, because neither figure
    came from the content."""
    empty = _panel(qtbot)
    full = _panel(qtbot)
    full.set_log_model(_Rows(_MAX_VISIBLE_ROWS * 2))

    assert empty.sizeHint().height() < full.sizeHint().height()


def test_the_height_grows_with_the_number_of_rows(qtbot) -> None:
    few = _panel(qtbot)
    few.set_log_model(_Rows(3))
    more = _panel(qtbot)
    more.set_log_model(_Rows(6))

    assert more.sizeHint().height() > few.sizeHint().height()


def test_the_height_stops_growing_at_the_cap(qtbot) -> None:
    """Past the cap the console scrolls instead of taking more of the screen —
    otherwise a busy session would push the workspace out entirely."""
    at_cap = _panel(qtbot)
    at_cap.set_log_model(_Rows(_MAX_VISIBLE_ROWS))
    far_past = _panel(qtbot)
    far_past.set_log_model(_Rows(_MAX_VISIBLE_ROWS * 20))

    assert far_past.sizeHint().height() == at_cap.sizeHint().height()


def test_an_empty_console_is_still_a_usable_panel(qtbot) -> None:
    """The floor: shrinking to nothing would trade one bad layout for another —
    a header with a hairline under it reads as broken, not as compact."""
    empty = _panel(qtbot)

    assert empty.sizeHint().height() > empty.header_actions.sizeHint().height()
