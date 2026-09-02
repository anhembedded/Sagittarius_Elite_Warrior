from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    Qt,
    Signal,
    Slot,
)
from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData

_LARGE_PRICE_THRESHOLD = 100.0
_THOUSAND = 1_000.0
_MILLION = 1_000_000.0


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
    """Converts one domain candle to its display row.

    Extracted from `KLineInspectorTableModel.set_klines()`'s loop body
    (`qml/KlineInspectorTable/`, 2026-08-30) so a second consumer — the QML
    port, which does not paginate through this model (see that widget's
    NOTES.md) — can build the same rows without duplicating this
    conversion. Behaviour is unchanged; `set_klines()` now calls this too.
    """
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


def kline_display_row_to_qml(row: KLineDisplayRow) -> dict[str, object]:
    """Converts to the plain-dict shape a QML `ListView`/`Repeater` model
    expects — same role names `_ROLE_NAMES` declares, so a QML delegate
    reading `modelData.<key>` sees the identical field set whichever of the
    two models (this one, paginated, or the QML port's, virtualized) is
    behind it."""
    return {
        "timestampMs": row.timestamp_ms,
        "formattedTime": row.formatted_time,
        "openPrice": row.open_str,
        "highPrice": row.high_str,
        "lowPrice": row.low_str,
        "closePrice": row.close_str,
        "volume": row.volume_str,
        "quoteVolume": row.quote_volume_str,
        "trades": row.trades,
        "isBullish": row.is_bullish,
        "changePct": row.change_pct_str,
    }


class KLineInspectorTableModel(QAbstractTableModel):
    """
    @brief Table model for the KLine Data Inspector modal in DataManagementScreen.
    @details
    Supports in-memory pagination and fast timestamp jumping for large datasets.
    """

    TimestampRole = Qt.ItemDataRole.UserRole + 1
    FormattedTimeRole = Qt.ItemDataRole.UserRole + 2
    OpenRole = Qt.ItemDataRole.UserRole + 3
    HighRole = Qt.ItemDataRole.UserRole + 4
    LowRole = Qt.ItemDataRole.UserRole + 5
    CloseRole = Qt.ItemDataRole.UserRole + 6
    VolumeRole = Qt.ItemDataRole.UserRole + 7
    QuoteVolumeRole = Qt.ItemDataRole.UserRole + 8
    TradesRole = Qt.ItemDataRole.UserRole + 9
    IsBullishRole = Qt.ItemDataRole.UserRole + 10
    ChangePctRole = Qt.ItemDataRole.UserRole + 11

    _ROLE_NAMES: ClassVar[dict[int, bytes]] = {
        TimestampRole: b"timestampMs",
        FormattedTimeRole: b"formattedTime",
        OpenRole: b"openPrice",
        HighRole: b"highPrice",
        LowRole: b"lowPrice",
        CloseRole: b"closePrice",
        VolumeRole: b"volume",
        QuoteVolumeRole: b"quoteVolume",
        TradesRole: b"trades",
        IsBullishRole: b"isBullish",
        ChangePctRole: b"changePct",
    }

    paginationChanged = Signal()

    def __init__(self, parent=None, page_size: int = 100) -> None:
        super().__init__(parent)
        self._all_rows: list[KLineDisplayRow] = []
        self._page_size = max(10, page_size)
        self._current_page = 1

    # ---------------- QAbstractTableModel Interface ----------------

    def rowCount(self, parent: QModelIndex | None = None) -> int:
        if parent is not None and parent.isValid():
            return 0
        return len(self._current_page_rows())

    def columnCount(self, parent: QModelIndex | None = None) -> int:
        if parent is not None and parent.isValid():
            return 0
        return len(self._ROLE_NAMES)

    def roleNames(self) -> dict[int, bytes]:
        return self._ROLE_NAMES

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        rows = self._current_page_rows()
        if not (0 <= index.row() < len(rows)):
            return None

        row = rows[index.row()]

        if role == self.TimestampRole:
            return row.timestamp_ms
        if role == self.FormattedTimeRole:
            return row.formatted_time
        if role == self.OpenRole:
            return row.open_str
        if role == self.HighRole:
            return row.high_str
        if role == self.LowRole:
            return row.low_str
        if role == self.CloseRole:
            return row.close_str
        if role == self.VolumeRole:
            return row.volume_str
        if role == self.QuoteVolumeRole:
            return row.quote_volume_str
        if role == self.TradesRole:
            return row.trades
        if role == self.IsBullishRole:
            return row.is_bullish
        if role == self.ChangePctRole:
            return row.change_pct_str

        return None

    # ---------------- Pagination & Data Operations ----------------

    @property
    def total_records(self) -> int:
        return len(self._all_rows)

    @property
    def total_pages(self) -> int:
        if not self._all_rows:
            return 1
        return (len(self._all_rows) + self._page_size - 1) // self._page_size

    @property
    def current_page(self) -> int:
        return self._current_page

    @property
    def page_size(self) -> int:
        return self._page_size

    def _current_page_rows(self) -> list[KLineDisplayRow]:
        start = (self._current_page - 1) * self._page_size
        end = start + self._page_size
        return self._all_rows[start:end]

    def set_klines(self, klines: list[MarketData]) -> None:
        """Populates the model from domain MarketData entities."""
        self.beginResetModel()
        self._all_rows = [market_data_to_kline_row(k) for k in klines]
        self._current_page = 1
        self.endResetModel()
        self.paginationChanged.emit()

    @Slot(int)
    def set_page(self, page: int) -> None:
        """Sets the current active page."""
        target_page = max(1, min(page, self.total_pages))
        if target_page == self._current_page:
            return

        self.beginResetModel()
        self._current_page = target_page
        self.endResetModel()
        self.paginationChanged.emit()

    @Slot(int)
    def set_page_size(self, page_size: int) -> None:
        """Updates the page size and resets current page to 1."""
        new_size = max(10, page_size)
        if new_size == self._page_size:
            return

        self.beginResetModel()
        self._page_size = new_size
        self._current_page = 1
        self.endResetModel()
        self.paginationChanged.emit()

    @Slot(str)
    def jump_to_date(self, date_query: str) -> bool:
        """
        @brief Jumps to the page containing the specified date (e.g. '2024-05-01' or '2024-05-01 14:00').
        @returns True if a match was found and jumped to.
        """
        clean = date_query.strip()
        if not clean or not self._all_rows:
            return False

        # Find first row whose formatted_time starts with or contains date_query
        for idx, row in enumerate(self._all_rows):
            if clean in row.formatted_time:
                target_page = (idx // self._page_size) + 1
                self.set_page(target_page)
                return True

        return False

    def clear(self) -> None:
        self.beginResetModel()
        self._all_rows = []
        self._current_page = 1
        self.endResetModel()
        self.paginationChanged.emit()
