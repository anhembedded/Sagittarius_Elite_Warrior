from typing import Optional, Sequence

from PySide6 import QtCore, QtWidgets

DEFAULT_TIMEFRAMES = ("1m", "5m", "15m", "1h", "1d")


class ChartToolbar(QtWidgets.QWidget):
    """
    @brief Row of timeframe-selector buttons meant for a Card header (BaseCard.add_to_header).
    @details Dumb component (Rule 1: no business logic, no engine/presenter knowledge) — emits
    sig_timeframe_changed(interval) on click and highlights the active button. Does not fetch
    or re-render any data itself.
    """

    sig_timeframe_changed = QtCore.Signal(str)

    def __init__(
        self,
        timeframes: Sequence[str] = DEFAULT_TIMEFRAMES,
        active: Optional[str] = None,
        parent: Optional[QtWidgets.QWidget] = None,
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
            btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(f"Switch to {timeframe} timeframe")
            btn.clicked.connect(lambda checked, t=timeframe: self._on_clicked(t))
            self._buttons[timeframe] = btn
            layout.addWidget(btn)

        self.set_active(active or (timeframes[0] if timeframes else None))

    def _on_clicked(self, timeframe: str) -> None:
        self.set_active(timeframe)
        self.sig_timeframe_changed.emit(timeframe)

    def set_active(self, timeframe: Optional[str]) -> None:
        for tf, btn in self._buttons.items():
            btn.setChecked(tf == timeframe)
