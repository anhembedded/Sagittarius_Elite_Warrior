"""
@brief `ProgressBanner` — a caption over a bar, with the Cancel button the
work it reports can be stopped by.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ..controls import StyledButton, StyledProgressBar

_DEFAULT_CANCEL_LABEL = "Cancel"
_PERCENT_SCALE = 10
_MAX_PERCENT = 100


def _percent_text(percent: float) -> str:
    return f"{round(percent)}%"


class ProgressBanner(QWidget):  # base-exempt: a container, not a surface
    """
    @brief A long operation's caption, its bar, and one button to stop it.

    @details
    **`StyledProgressBar`'s docstring called this composite and declined to
    build it.** *"The composite is recorded in `EPIC-007C` as a candidate; it
    has one instance, and its shape is a column"* — one instance was not enough
    to know what a shared version should look like. There are **three** now
    (the Backtest run banner, Data Management's sync banner, Dev Board's), and
    `EPIC-025` PR 4.3l is where they need it, because the `ProgressBanner.qml`
    all three had been embedding is deleted with the rest of the QML (ADR D21).

    The five setters and the one signal are the `.qml`'s own properties, name
    for name, so the three call sites did not change: `set_status_text`,
    `set_percent`, `set_indeterminate`, `set_cancelling`, `set_cancel_label`,
    and `cancelRequested`.

    **`set_cancelling(True)` disables the button and leaves its label alone.**
    A caller that wants "Cancelling…" on it says so with `set_cancel_label`;
    this class does not invent the word, because two of the three callers have
    their own phrasing for it.

    **The percentage is written on the bar, not beside it.** The `.qml` drew a
    second `Text` item for it (`progressBannerPercentText`) because a QML
    `ProgressBar` has no text of its own; `QProgressBar` does, and ADR D20
    prefers the platform component's own rendering to a hand-placed label. The
    number is the same one that scene showed — `Math.round(percent) + "%"` — so
    a reader sees no change.
    """

    #: The user asked to stop. Not a `bool`, and not a state: what cancelling
    #: *means* is the screen's, and every caller already has an action for it.
    cancelRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("progressBanner")

        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(6)

        # A plain `QLabel`, deliberately: `apply_role(..., CAPTION)` is what
        # every other caption in this repository uses, and HLD §11.4 drives
        # that count to zero in this very phase. A widget written *in* Phase 4
        # does not add to it — the same call 4.3d's dialog declined to make.
        self._status = QLabel()
        self._status.setObjectName("progressBannerStatusText")
        column.addWidget(self._status)

        row = QHBoxLayout()
        row.setSpacing(8)
        self._bar = StyledProgressBar()
        self._bar.setObjectName("progressBannerTrack")
        # Percent arrives as a float, and a bar takes integers: tenths of a
        # percent, so 3.7% is 37 rather than collapsing to 4.
        self._bar.setRange(0, _MAX_PERCENT * _PERCENT_SCALE)
        # `StyledProgressBar` hides its text by default, for a consumer whose
        # bar was 10px tall. This one is a full-height bar in a banner, which
        # is the case that docstring says turns it back on. The format is a
        # literal rather than Qt's `%p`, which would read 37 where the scene
        # this replaces read 38: `%p` truncates `value / maximum`, and tenths
        # of a percent is exactly the resolution that makes that visible.
        self._bar.setTextVisible(True)
        self._bar.setFormat(_percent_text(0.0))
        row.addWidget(self._bar, 1)

        self._cancel = StyledButton(_DEFAULT_CANCEL_LABEL)
        self._cancel.setObjectName("progressBannerCancel")
        self._cancel.clicked.connect(self.cancelRequested)
        row.addWidget(self._cancel)
        column.addLayout(row)

    def set_status_text(self, text: str) -> None:
        self._status.setText(text)

    def set_percent(self, value: float) -> None:
        """@param value 0..100. Ignored while indeterminate, which is the
        contract every caller already relied on."""
        clamped = max(0.0, min(float(value), _MAX_PERCENT))
        self._bar.setValue(round(clamped * _PERCENT_SCALE))
        self._bar.setFormat(_percent_text(clamped))

    def percent_text(self) -> str:
        """@brief What the bar currently reads, as the user sees it.

        @details Qt renders no text at all while the bar is indeterminate,
        which is the honest answer there: a sweep reports no percentage."""
        return self._bar.text()

    def set_indeterminate(self, indeterminate: bool) -> None:
        """A bar that reports no percentage: `StyledProgressBar` remembers the
        range it came from, so this is reversible."""
        self._bar.set_indeterminate(indeterminate)

    def set_cancelling(self, cancelling: bool) -> None:
        self._cancel.setEnabled(not cancelling)

    def set_cancel_label(self, text: str) -> None:
        self._cancel.setText(text)
