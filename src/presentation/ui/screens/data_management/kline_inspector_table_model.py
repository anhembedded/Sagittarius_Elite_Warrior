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
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, Final

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QObject,
    QPersistentModelIndex,
    Qt,
)
from PySide6.QtGui import QColor, QFont
from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.support.charting.chart_card.theme import (
    BEAR_COLOR,
    BULL_COLOR,
)

_LARGE_PRICE_THRESHOLD = 100.0
_THOUSAND = 1_000.0
_MILLION = 1_000_000.0

#: The two meaningful colours in this widget (ADR D21), as `QColor`s of the
#: hex strings `chart_card/theme.py` already carries — imported, not copied,
#: the same way `strategy_overlay` imports them. A `QColor` rather than the
#: string because `ForegroundRole` wants a colour, not CSS.
BULLISH_COLOR: Final = QColor(BULL_COLOR)
BEARISH_COLOR: Final = QColor(BEAR_COLOR)

type AnyIndex = QModelIndex | QPersistentModelIndex


@dataclass(frozen=True)
class KLineDisplayRow:
    """
    @brief Immutable presentation row for one historical OHLCV candle.
    """

    timestamp_ms: int
    formatted_time: str
    open_str: str
    high_str: str
    low_str: str
    close_str: str
    volume_str: str
    quote_volume_str: str
    trades: int
    is_bullish: bool
    change_pct_str: str


def _format_price(val: float) -> str:
    if val >= _LARGE_PRICE_THRESHOLD:
        return f"{val:,.2f}"
    if val >= 1:
        return f"{val:.4f}"
    return f"{val:.8f}".rstrip("0").rstrip(".")


def _format_volume(val: float) -> str:
    if val >= _MILLION:
        return f"{val / _MILLION:.2f}M"
    if val >= _THOUSAND:
        return f"{val / _THOUSAND:.2f}K"
    return f"{val:.4f}".rstrip("0").rstrip(".")


def market_data_to_kline_row(k: MarketData) -> KLineDisplayRow:
    """Converts one domain candle to its display row."""
    ts_ms = int(k.open_time.timestamp() * 1000)
    is_bull = k.close_price >= k.open_price
    chg = (
        (k.close_price - k.open_price) / k.open_price * 100 if k.open_price > 0 else 0.0
    )
    return KLineDisplayRow(
        timestamp_ms=ts_ms,
        formatted_time=k.open_time.strftime("%Y-%m-%d %H:%M:%S"),
        open_str=_format_price(k.open_price),
        high_str=_format_price(k.high_price),
        low_str=_format_price(k.low_price),
        close_str=_format_price(k.close_price),
        volume_str=_format_volume(k.volume),
        quote_volume_str=_format_volume(k.quote_asset_volume),
        trades=k.number_of_trades,
        is_bullish=is_bull,
        change_pct_str=f"{chg:+.2f}%",
    )


class KLineInspectorTableModel(QAbstractTableModel):
    """
    @brief Every stored candle for one symbol/interval shard, already
    formatted for display.
    """

    TIME_COLUMN: Final = 0
    OPEN_COLUMN: Final = 1
    HIGH_COLUMN: Final = 2
    LOW_COLUMN: Final = 3
    CLOSE_COLUMN: Final = 4
    VOLUME_COLUMN: Final = 5
    CHANGE_COLUMN: Final = 6
    TRADES_COLUMN: Final = 7

    _HEADERS: ClassVar[tuple[str, ...]] = (
        "Time (UTC)",
        "Open",
        "High",
        "Low",
        "Close",
        "Volume",
        "Change",
        "Trades",
    )

    #: Every numeric column. A price column only lines up if its digits do.
    _NUMERIC_COLUMNS: ClassVar[frozenset[int]] = frozenset(
        {
            OPEN_COLUMN,
            HIGH_COLUMN,
            LOW_COLUMN,
            CLOSE_COLUMN,
            VOLUME_COLUMN,
            CHANGE_COLUMN,
            TRADES_COLUMN,
        }
    )

    #: The two cells that say which way the candle went.
    _DIRECTIONAL_COLUMNS: ClassVar[frozenset[int]] = frozenset(
        {CLOSE_COLUMN, CHANGE_COLUMN}
    )

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._rows: list[KLineDisplayRow] = []

    # ------------------------------------------------------------------ #
    # QAbstractTableModel contract
    # ------------------------------------------------------------------ #

    def rowCount(self, parent: AnyIndex | None = None) -> int:
        if parent is not None and parent.isValid():
            return 0
        return len(self._rows)

    def columnCount(self, parent: AnyIndex | None = None) -> int:
        if parent is not None and parent.isValid():
            return 0
        return len(self._HEADERS)

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> object:
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation != Qt.Orientation.Horizontal:
            return None
        if not 0 <= section < len(self._HEADERS):
            return None
        return self._HEADERS[section]

    def data(self, index: AnyIndex, role: int = Qt.ItemDataRole.DisplayRole) -> object:
        row = self.row_for(index)
        if row is None:
            return None
        column = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            return self._display_text(row, column)
        if (
            role == Qt.ItemDataRole.TextAlignmentRole
            and column in self._NUMERIC_COLUMNS
        ):
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        if role == Qt.ItemDataRole.FontRole:
            # Monospace on every cell: a column of prices is only comparable
            # at a glance if every digit is the same width — the same reason
            # `_KLineRowWidget` gave before any of this was QML.
            font = QFont()
            font.setStyleHint(QFont.StyleHint.Monospace)
            font.setFamily("monospace")
            if column == self.CLOSE_COLUMN:
                font.setBold(True)
            return font
        if (
            role == Qt.ItemDataRole.ForegroundRole
            and column in self._DIRECTIONAL_COLUMNS
        ):
            return BULLISH_COLOR if row.is_bullish else BEARISH_COLOR
        return None

    def _display_text(self, row: KLineDisplayRow, column: int) -> str:
        return {
            self.TIME_COLUMN: row.formatted_time,
            self.OPEN_COLUMN: row.open_str,
            self.HIGH_COLUMN: row.high_str,
            self.LOW_COLUMN: row.low_str,
            self.CLOSE_COLUMN: row.close_str,
            self.VOLUME_COLUMN: row.volume_str,
            self.CHANGE_COLUMN: row.change_pct_str,
            self.TRADES_COLUMN: str(row.trades),
        }.get(column, "")

    # ------------------------------------------------------------------ #
    # Reading and writing the candle list
    # ------------------------------------------------------------------ #

    def row_for(self, index: AnyIndex) -> KLineDisplayRow | None:
        if not index.isValid():
            return None
        if not 0 <= index.row() < len(self._rows):
            return None
        return self._rows[index.row()]

    @property
    def total_records(self) -> int:
        return len(self._rows)

    def set_klines(self, klines: list[MarketData]) -> None:
        """Populates the model from domain `MarketData` entities."""
        self.beginResetModel()
        self._rows = [market_data_to_kline_row(k) for k in klines]
        self.endResetModel()

    def clear(self) -> None:
        self.beginResetModel()
        self._rows = []
        self.endResetModel()
