"""The monthly/yearly returns heatmap (`BOT-106D`)."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QGridLayout, QLabel, QVBoxLayout, QWidget

_MONTH_HEADERS = (
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
)  # fmt: skip

#: Alpha (0-255) tinting a month's background by its own return colour — the
#: same flat tint every coloured badge on this screen uses (e.g. the trade
#: row's PnL pill), never a magnitude-scaled gradient: a second derived-colour
#: rule would need its own justification and its own test.
_CELL_TINT_ALPHA = 40


class _HeatmapCell(QLabel):
    """One grid cell — a background tint via `QPalette` (never
    `setStyleSheet()`: `tests/unit/architecture/test_app_styling_only_shrinks.py`,
    ADR D21, ratchets that call down, not up) and foreground colour via
    inline HTML in `setText()`, the same technique `ChartPlotLayout` already
    uses for its crosshair label."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(56, 28)

    def set_empty(self) -> None:
        """No data for this month (`YearlyReturn.months`'s "absent, not
        zero") — plain dash, no tint: `setAutoFillBackground(False)` leaves
        the cell transparent instead of carrying over a previous tint."""
        self.setAutoFillBackground(False)
        self.setText("—")

    def set_value(self, text: str, color: str) -> None:
        self.setText(f'<span style="color:{color};">{text}</span>')
        self.setAutoFillBackground(True)
        palette = self.palette()
        tinted = QColor(color)
        tinted.setAlpha(_CELL_TINT_ALPHA)
        palette.setColor(QPalette.ColorRole.Window, tinted)
        self.setPalette(palette)


class MonthlyReturnsHeatmapWidget(QWidget):
    """`logic/performance_charts.py`'s `build_yearly_returns_rows()` output,
    one row per year: 12 month cells (blank where that month has no data,
    per `YearlyReturn.months`'s own "absent, not zero" contract) plus a
    compounded year-to-date column."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self._empty_label = QLabel("No trade data yet")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(self._empty_label)

        self._grid_container = QWidget()
        self._grid = QGridLayout(self._grid_container)
        self._grid.setSpacing(2)
        for column, header in enumerate((*_MONTH_HEADERS, "YTD"), start=1):
            label = QLabel(header)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._grid.addWidget(label, 0, column)
        self._grid_container.setVisible(False)
        outer.addWidget(self._grid_container)
        outer.addStretch(1)

        #: Every widget `set_rows()` has added below the header row — tracked
        #: explicitly rather than re-derived from `QGridLayout.rowCount()`,
        #: which does not shrink until a `deleteLater()`'d widget's next event
        #: loop turn (a naive "while rowCount() > 1" loop here would spin
        #: forever on the same still-alive row).
        self._row_widgets: list[QWidget] = []

    def set_rows(self, rows: list[dict[str, Any]]) -> None:
        has_rows = bool(rows)
        self._empty_label.setVisible(not has_rows)
        self._grid_container.setVisible(has_rows)

        for widget in self._row_widgets:
            self._grid.removeWidget(widget)
            widget.deleteLater()
        self._row_widgets = []

        for grid_row, row in enumerate(rows, start=1):
            year_label = QLabel(str(row["year"]))
            year_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._grid.addWidget(year_label, grid_row, 0)
            self._row_widgets.append(year_label)
            for column, month_cell in enumerate(row["months"], start=1):
                cell = _HeatmapCell(self._grid_container)
                if month_cell is None:
                    cell.set_empty()
                else:
                    cell.set_value(month_cell["text"], month_cell["color"])
                self._grid.addWidget(cell, grid_row, column)
                self._row_widgets.append(cell)
            ytd_cell = _HeatmapCell(self._grid_container)
            ytd_cell.set_value(row["ytdText"], row["ytdColor"])
            self._grid.addWidget(ytd_cell, grid_row, len(_MONTH_HEADERS) + 1)
            self._row_widgets.append(ytd_cell)
