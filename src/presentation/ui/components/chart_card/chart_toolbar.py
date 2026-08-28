from collections.abc import Sequence

from PySide6 import QtCore, QtWidgets
from Sagittarius_Elite_Warrior.src.presentation.ui.assets import Palette
from Sagittarius_Elite_Warrior.src.presentation.ui.components.timeframe_picker import (
    TimeframePickerOverlay,
    all_options,
)

#: The quick-pick pills. Five, because this row lives in a chart header and
#: sixteen would not fit — that constraint is real and stays.
#:
#: `EPIC-014`: what changed is that this tuple no longer *decides what the
#: user may choose*. It used to be the whole timeframe UI, and it was also
#: `BackTestViewModel.timeframeOptions` and the validity test for the
#: `DEFAULT_INTERVAL` config key, so a constant sizing a header row was
#: silently rejecting eleven timeframes the domain, the exchange and the
#: database all support. The `…` button below reaches all sixteen.
DEFAULT_TIMEFRAMES = ("1m", "5m", "15m", "1h", "1d")

#: Label of the button that opens the full picker. Replaced by the active
#: timeframe's own code whenever that timeframe has no pill of its own —
#: otherwise choosing `4h` left every pill unselected and the row said
#: nothing about what was actually being charted.
_MORE_LABEL = "…"
_MORE_TOOLTIP = "Chọn khung thời gian khác"


class ChartToolbar(QtWidgets.QWidget):
    """
    @brief Row of timeframe-selector buttons meant for a Card header (`ChartCard.add_to_header`).
    @details Dumb component (Rule 1: no business logic, no engine/presenter knowledge) — emits
    sig_timeframe_changed(interval) on click and highlights the active button. Does not fetch
    or re-render any data itself.
    """

    sig_timeframe_changed = QtCore.Signal(str)

    #: Room for the widest thing a pill holds (`15m`) once the padding below
    #: is applied, and for a code like `12h` on the `…` button.
    _BUTTON_MAX_WIDTH = 52

    #: A bare `…` is one narrow glyph. Measured on a real `ChartCard`, the
    #: button laid out at **13x19 px** — a muted sliver that reads as a
    #: separator, not a control, which is exactly how it was reported: the
    #: button was there and nobody could see it. The padding below fixes the
    #: cause for every button in the row; this floor keeps the narrowest
    #: labels (`…`, `1d`) from still ending up smaller than a comfortable
    #: target.
    _BUTTON_MIN_WIDTH = 34

    def __init__(
        self,
        timeframes: Sequence[str] = DEFAULT_TIMEFRAMES,
        active: str | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._buttons: dict[str, QtWidgets.QPushButton] = {}

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        for timeframe in timeframes:
            btn = QtWidgets.QPushButton(timeframe)
            btn.setCheckable(True)
            btn.setMinimumWidth(self._BUTTON_MIN_WIDTH)
            btn.setMaximumWidth(self._BUTTON_MAX_WIDTH)
            btn.setCursor(QtCore.Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked, t=timeframe: self._on_clicked(t))
            self._buttons[timeframe] = btn
            layout.addWidget(btn)

        self._picker: TimeframePickerOverlay | None = None
        self._active: str | None = None
        self._btn_more = QtWidgets.QPushButton(_MORE_LABEL)
        self._btn_more.setObjectName("btnTimeframeMore")
        self._btn_more.setCheckable(True)
        self._btn_more.setMinimumWidth(self._BUTTON_MIN_WIDTH)
        self._btn_more.setMaximumWidth(self._BUTTON_MAX_WIDTH)
        self._btn_more.setCursor(QtCore.Qt.PointingHandCursor)
        self._btn_more.setToolTip(_MORE_TOOLTIP)
        self._btn_more.clicked.connect(self._open_picker)
        layout.addWidget(self._btn_more)

        self.set_active(active or (timeframes[0] if timeframes else None))

    def _on_clicked(self, timeframe: str) -> None:
        self.set_active(timeframe)
        self.sig_timeframe_changed.emit(timeframe)

    def _open_picker(self) -> None:
        """Opens the full timeframe picker.

        @details This is still a dumb component: it opens a chooser for the
        very thing it already chooses and emits the same signal, so no
        consumer learns anything new and neither has to duplicate the
        wiring. Owning the dialog here rather than exposing a
        `sig_more_requested` is what keeps Backtest and Dev Board from
        growing two copies of it — which is exactly how the pickers this
        replaces multiplied in the first place.
        """
        # `clicked` on a checkable button has already toggled it. What the
        # row shows as selected is decided by `set_active()`, not by opening
        # a dialog, so re-assert it: otherwise dismissing the picker left the
        # `…` button lit alongside the pill that is actually active.
        self.set_active(self._active)
        if self._picker is None:
            self._picker = TimeframePickerOverlay(
                get_options=lambda: [option.code for option in all_options()],
                get_current=lambda: self._active or "",
                parent=self,
            )
            self._picker.timeframe_chosen.connect(self._on_clicked)
        self._picker.show()
        self._picker.raise_()

    def set_active(self, timeframe: str | None) -> None:
        """Highlights `timeframe`, wherever it lives.

        @details A timeframe with no pill of its own is shown *on* the `…`
        button rather than nowhere. Before `EPIC-014` the row simply had no
        selection in that case, which was reachable on every launch:
        `EPIC-010D` restores a remembered interval, and `DEFAULT_INTERVAL`
        can name any of the sixteen.
        """
        self._active = timeframe
        for tf, btn in self._buttons.items():
            active = tf == timeframe
            btn.setChecked(active)
            btn.setStyleSheet(self._button_style(active))

        is_off_pill = timeframe is not None and timeframe not in self._buttons
        self._btn_more.setText(timeframe if is_off_pill else _MORE_LABEL)
        self._btn_more.setChecked(is_off_pill)
        self._btn_more.setStyleSheet(self._button_style(is_off_pill))

    @staticmethod
    def _button_style(active: bool) -> str:
        """
        @brief The pill chrome for one timeframe button.

        @details Written here rather than inherited from the app's global
        `qdarktheme` sheet, which is where these buttons used to get their
        look. That worked only while no ancestor had a stylesheet of its own.
        `EPIC-007E` moved `ChartCard` onto the engine's `Card`, whose
        `apply_role()` writes **unscoped** QSS — properties with no selector,
        which Qt cascades into every descendant — and the buttons lost their
        borders to it.

        The cascade is the engine's defect, filed as `BUG-008` there. This is
        not a workaround for it: a toolbar that only looks right when nothing
        above it is styled was already relying on an accident. Owning its own
        appearance is what it should have done from the start, and it stays
        correct after `BUG-008` is fixed.
        """
        return (
            f"QPushButton {{"
            f"background-color: "
            f"{Palette.STATE_ACTIVE_TINT if active else Palette.STATE_IDLE_BG};"
            f"border: 1px solid "
            f"{Palette.ACCENT if active else Palette.STATE_NAV_BORDER};"
            f"border-radius: 4px;"
            f"color: {Palette.ACCENT if active else Palette.MUTED};"
            f"font-size: 11px;"
            f"font-weight: {'bold' if active else 'normal'};"
            # Horizontal padding, not `0`. With none, each button collapsed
            # to the width of its own glyphs — `1d` at 16px, `…` at 13px —
            # so the row read as loose text rather than as buttons.
            f"padding: 2px 8px;"
            f"}}"
            f"QPushButton:hover {{background-color: {Palette.STATE_HOVER_BG};}}"
        )
