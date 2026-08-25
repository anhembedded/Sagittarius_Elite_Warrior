from collections.abc import Sequence

from PySide6 import QtCore, QtWidgets
from Sagittarius_Elite_Warrior.src.presentation.ui.assets import Palette

DEFAULT_TIMEFRAMES = ("1m", "5m", "15m", "1h", "1d")


class ChartToolbar(QtWidgets.QWidget):
    """
    @brief Row of timeframe-selector buttons meant for a Card header (`ChartCard.add_to_header`).
    @details Dumb component (Rule 1: no business logic, no engine/presenter knowledge) — emits
    sig_timeframe_changed(interval) on click and highlights the active button. Does not fetch
    or re-render any data itself.
    """

    sig_timeframe_changed = QtCore.Signal(str)

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
            btn.setMaximumWidth(40)
            btn.setCursor(QtCore.Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked, t=timeframe: self._on_clicked(t))
            self._buttons[timeframe] = btn
            layout.addWidget(btn)

        self.set_active(active or (timeframes[0] if timeframes else None))

    def _on_clicked(self, timeframe: str) -> None:
        self.set_active(timeframe)
        self.sig_timeframe_changed.emit(timeframe)

    def set_active(self, timeframe: str | None) -> None:
        for tf, btn in self._buttons.items():
            active = tf == timeframe
            btn.setChecked(active)
            btn.setStyleSheet(self._button_style(active))

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
            f"padding: 2px 0;"
            f"}}"
            f"QPushButton:hover {{background-color: {Palette.STATE_HOVER_BG};}}"
        )
