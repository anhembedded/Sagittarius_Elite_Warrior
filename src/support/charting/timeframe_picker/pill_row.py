"""The compact timeframe pill row that sits in a chart's header.

Reads only `TimeframeSelection.pinned_rows` and `current_code`: one checkable
button per pinned code, plus a "…" button that asks its host to open the full
picker. Opening is deliberately **not** this widget's decision — the host owns
the dialog, because the pinned set the dialog writes is state this row must also
reflect, so one owner has to hold both.

`EPIC-025` PR 4.3k: was `TimeframeToolbar.qml`, a `Repeater` of hand-drawn
`Rectangle`s inside a `QQuickWidget`. A checkable `QPushButton` is what a pill
is, so the row is buttons now and the current one is simply the checked one —
the platform draws that state, which is the whole of ADR D21.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QSizePolicy, QWidget

from .selection import TimeframeSelection

_MORE_TEXT = "…"
_MORE_TOOLTIP = "All timeframes"


class TimeframePillRow(QWidget):  # base-exempt: a container, not a surface
    """
    @brief One pill per pinned timeframe, and a button for the rest.

    @details Rebuilt whenever the selection changes, which is the honest shape
    for a row whose *membership* changes: pinning adds a pill and unpinning
    removes one, so there is no stable set of controls to update in place.
    """

    #: The host should open the full picker. Carries nothing: what opening
    #: means is the host's business.
    more_requested = Signal()

    def __init__(
        self, selection: TimeframeSelection, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setObjectName("timeframeToolbar")
        self._selection = selection
        self._buttons: dict[str, QPushButton] = {}

        self._row = QHBoxLayout(self)
        self._row.setContentsMargins(0, 0, 0, 0)
        self._row.setSpacing(4)
        # A compact row hugs its pills rather than stretching across whatever
        # space the chart header leaves — the opposite of every fill-the-panel
        # widget in this app, and what the QML host asked for with `HUG`.
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)

        selection.stateChanged.connect(self._rebuild)
        self._rebuild()

    def button_for(self, code: str) -> QPushButton | None:
        """A pill by its code, or `None` when that code is not pinned.

        Public for the same reason `ChecklistOverlay.checkbox_for` is: a
        consumer's test needs to click a pill, and reaching through a private
        layout is how a test starts depending on this widget's internals.
        """
        return self._buttons.get(code)

    def _rebuild(self) -> None:
        while self._row.count():
            entry = self._row.takeAt(0)
            if entry is None:  # pragma: no cover — count() > 0 guarantees one
                break
            widget = entry.widget()
            if widget is not None:
                # Detached before the deferred delete, which the main event
                # loop delivers rather than this call.
                widget.setParent(None)
                widget.deleteLater()
        self._buttons.clear()

        for pill in self._selection.pinned_rows:
            button = QPushButton(pill.code)
            button.setObjectName(f"timeframePill_{pill.code}")
            button.setCheckable(True)
            # Checked before connecting: seeding the current pill must not read
            # as the user having clicked it.
            button.setChecked(pill.current)
            button.clicked.connect(
                # Default-arg capture, not a closure over `pill`: a plain
                # closure would hand every pill the last code of the loop.
                lambda _checked=False, code=pill.code: self._selection.choose(code)
            )
            self._row.addWidget(button)
            self._buttons[pill.code] = button

        more = QPushButton(_MORE_TEXT)
        more.setObjectName("btnTimeframeMore")
        more.setToolTip(_MORE_TOOLTIP)
        more.clicked.connect(self.more_requested)
        self._row.addWidget(more)
