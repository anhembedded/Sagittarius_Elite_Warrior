"""State behind `PositionsTable.qml` — a pure display projection, no
filtering (`EPIC-021I`).

@details Push-based, unlike `TradeLogVM`'s callback-based `refresh()`:
positions arrive incrementally through `OrderFeed`
(`PositionChangedEvent`), so `TradingPresenter` is the one place that
knows the full current set at any moment — this VM only ever renders
whatever it is handed.
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import Property, QObject, Signal

from .positions_row import PositionRow, position_rows_to_qml


class PositionsVM(QObject):
    """@brief The full set of currently open positions, as QML-facing rows."""

    stateChanged = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._rows: list[dict[str, object]] = []

    @Property("QVariantList", notify=stateChanged)
    def rows(self) -> list[dict[str, object]]:
        return self._rows

    def set_rows(self, rows: Sequence[PositionRow]) -> None:
        self._rows = position_rows_to_qml(list(rows))
        self.stateChanged.emit()
