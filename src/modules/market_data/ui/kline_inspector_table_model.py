"""The candle table behind the K-line inspector — one row per stored candle.

**What changed in `EPIC-025` PR 0.4b.** Two models used to render these rows:
this one, which paginated in memory 100 candles at a time, and
`KlineInspectorVM`, which held the whole list for the QML `ListView`. Both are
gone as a pair; what is left is this model, serving `DisplayRole` per
`(row, column)` and `headerData()` so a `QTableView` can render it (ADR D20).

**The pagination went with them, and that decision is not new.** It was taken
when the QML port shipped (`EPIC-015`, `KlineInspectorTable/NOTES.md`) and the
user has been running it since: the fetch is already bounded at 10,000 candles
by `KLineInspectorCoordinator.run_inspect_klines`, and a virtualizing view
renders only the visible rows, so a page number is a control with nothing to
control. `QTableView` virtualizes exactly as that `ListView` did. What went
with it is the *dead* half — `set_page`, `set_page_size`, `jump_to_date` and
the four view-model properties reading them, none of which any widget has
called since `EPIC-015`. Jump-to-date was a real feature and is still absent;
it is recorded as such in `Tasks/epics/EPIC-025A_...`, not quietly dropped.

**Colour, and why this table has some when the status table does not.** ADR
D21 leaves colour "only where it carries meaning". Bullish against bearish is
that case — it is the first thing a trader reads off a candle list, and the
QML delegate coloured the close and change cells for exactly that reason.
The two values are **not** redeclared here: they are `chart_card`'s own
`BULL_COLOR`/`BEAR_COLOR`, which that package documents as "not chrome — a
candle body is green because it closed up". The same candle is green on the
chart and in this table because it is the same constant, and this repository
has been bitten enough times by a second copy of one value.

**Values, not text (`EPIC-033N`).** A row holds the candle's numbers and the
table writes them through the application's formatter, so a price reads here
as it reads on every other screen. Until then this file had its own
`_format_price` and `_format_volume` (a compact `1.23M`), and set a monospace
font family on every cell, which `ui-presentation-rule.md` §1 now forbids.
The table stays in time order: the candles arrive that way and the view is
not sorted until the user clicks a header.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar, Final

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.support.charting.chart_card.theme import (
    BEAR_COLOR,
    BULL_COLOR,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.table_model import RowTableModel
from sagittarius_engine.extensions.pyside_mvc.workbench import (
    ColumnKind,
    ColumnSpec,
    DisplayValue,
)

BULLISH_COLOR: Final = QColor(BULL_COLOR)
BEARISH_COLOR: Final = QColor(BEAR_COLOR)


@dataclass(frozen=True)
class KLineDisplayRow:
    """
    @brief One historical OHLCV candle, as values the table writes by kind.
    """

    open_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    trades: int
    is_bullish: bool
    #: Close against open, in percent.
    change_percent: float


def market_data_to_kline_row(k: MarketData) -> KLineDisplayRow:
    """Converts one domain candle to its display row."""
    change = (
        (k.close_price - k.open_price) / k.open_price * 100 if k.open_price > 0 else 0.0
    )
    return KLineDisplayRow(
        open_time=k.open_time,
        open=k.open_price,
        high=k.high_price,
        low=k.low_price,
        close=k.close_price,
        volume=k.volume,
        trades=k.number_of_trades,
        is_bullish=k.close_price >= k.open_price,
        change_percent=change,
    )


class KLineInspectorTableModel(RowTableModel[KLineDisplayRow]):
    """
    @brief Every stored candle for one symbol/interval shard.
    """

    COLUMNS: ClassVar[tuple[ColumnSpec, ...]] = (
        ColumnSpec("time", "Time", ColumnKind.TIMESTAMP),
        ColumnSpec("open", "Open", ColumnKind.PRICE),
        ColumnSpec("high", "High", ColumnKind.PRICE),
        ColumnSpec("low", "Low", ColumnKind.PRICE),
        ColumnSpec("close", "Close", ColumnKind.PRICE),
        ColumnSpec("volume", "Volume", ColumnKind.QUANTITY),
        ColumnSpec("change", "Change", ColumnKind.PERCENT),
        ColumnSpec("trades", "Trades", ColumnKind.QUANTITY),
    )

    #: The two cells that say which way the candle went.
    _DIRECTIONAL_KEYS: ClassVar[frozenset[str]] = frozenset({"close", "change"})

    def _value(self, row: KLineDisplayRow, column: int) -> DisplayValue:
        values: tuple[DisplayValue, ...] = (
            row.open_time,
            row.open,
            row.high,
            row.low,
            row.close,
            row.volume,
            row.change_percent,
            row.trades,
        )
        return values[column]

    def _is_emphasised(self, row: KLineDisplayRow, column: int) -> bool:
        """The close is the price a candle is read by."""
        return self.COLUMNS[column].key == "close"

    def _role_data(self, row: KLineDisplayRow, column: int, role: int) -> object:
        key = self.COLUMNS[column].key
        if role == Qt.ItemDataRole.ForegroundRole and key in self._DIRECTIONAL_KEYS:
            return BULLISH_COLOR if row.is_bullish else BEARISH_COLOR
        return None

    # -- reading and writing the candle list -------------------------------

    @property
    def total_records(self) -> int:
        return len(self._rows)

    def set_klines(self, klines: list[MarketData]) -> None:
        """Populates the model from domain `MarketData` entities."""
        self.set_rows([market_data_to_kline_row(k) for k in klines])
