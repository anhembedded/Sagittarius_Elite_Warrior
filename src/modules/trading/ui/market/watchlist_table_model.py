"""The Watchlist table — one row per tracked symbol, updated live from
`MarketTickEvent` (`BOT-019`).

Colour on the `% Change` column is the one case
`ui-presentation-rule.md` §1 already sanctions ("colour only where it
carries meaning"): win/loss direction, drawn by `Tone` on the application's
palette (`EPIC-043C`) with an arrow and a sign beside it in the text; a
change of exactly zero has neither colour nor arrow.

**The tick flash (`EPIC-043D`).** When the person turns it on (Tools → Options → Appearance,
off by default) a price that moves takes the up or down tone for `FLASH_MILLISECONDS` and then
returns to the platform's colour. The direction is also a shape: while a price flashes, an up or
down triangle stands beside it (`triangle-up`, `triangle-down`, in the tone's colour), so the flash
is never the only signal. (The `% Change` column's arrow is the change since the day's open, a
different fact, and often the other way.) One single-shot timer, a child of this model,
ends the flashes; it dies with the model and is stopped whenever no flash is left.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import ClassVar, Final

from PySide6.QtCore import QObject, Qt, QTimer
from PySide6.QtWidgets import QApplication, QStyle
from Sagittarius_Elite_Warrior.src.support.ui_kit.meaning_colours import (
    Tone,
    sign_tone,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.table_model import RowTableModel
from Sagittarius_Elite_Warrior.src.support.ui_kit.tone_icon import tone_icon
from Sagittarius_Elite_Warrior.src.support.ui_kit.value_formatter import signed_key
from sagittarius_engine.extensions.pyside_mvc.workbench import (
    ColumnKind,
    ColumnSpec,
    DisplayValue,
)

#: The shape beside a price while it flashes, by the direction it moved.
_FLASH_ICONS: Final = {Tone.POSITIVE: "triangle-up", Tone.NEGATIVE: "triangle-down"}

#: How long a ticking price keeps its tone: long enough to catch the eye, short enough that a
#: busy symbol is mostly at rest.
FLASH_MILLISECONDS: Final = 600


@dataclass
class WatchlistRow:
    """One tracked symbol's latest known price/change/volume.

    Every field beyond `symbol` is `None` until the first tick for that
    symbol arrives — a symbol is seeded into the table the moment the
    watchlist starts tracking it (`WatchlistTableModel.set_symbols()`), so
    the user sees the full list immediately rather than an empty table
    until ticks start flowing.
    """

    symbol: str
    last_price: float | None = None
    percent_change: float | None = None
    volume: float | None = None


class WatchlistTableModel(RowTableModel[WatchlistRow]):
    """@brief Table model backing the Watchlist screen's symbol table."""

    SYMBOL_COLUMN: Final = 0
    PRICE_COLUMN: Final = 1
    PERCENT_CHANGE_COLUMN: Final = 2

    COLUMNS: ClassVar[tuple[ColumnSpec, ...]] = (
        ColumnSpec("symbol", "Symbol", ColumnKind.TEXT, stretch=True),
        ColumnSpec("last_price", "Last price", ColumnKind.PRICE),
        ColumnSpec(signed_key("change"), "% Change", ColumnKind.PERCENT),
        ColumnSpec("volume", "Volume", ColumnKind.QUANTITY),
    )
    #: A volume is a sum of the symbol's traded quantities, so its step.
    SYMBOL_QUOTED: ClassVar[frozenset[str]] = frozenset({"last_price", "volume"})

    def __init__(
        self,
        parent: QObject | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """@param clock Seconds, only ever compared with itself; a test hands one it advances."""
        super().__init__(parent)
        self._row_index: dict[str, int] = {}
        self._clock = clock
        self._flash_on = False
        #: Symbol -> the tone its price flashes and when that ends.
        self._flashes: dict[str, tuple[Tone, float]] = {}
        self._flash_timer = QTimer(self)
        self._flash_timer.setSingleShot(True)
        self._flash_timer.timeout.connect(self._end_flashes)

    # ------------------------------------------------------------------ #
    # Mutation API (driven by the Presenter)
    # ------------------------------------------------------------------ #

    def set_symbols(self, symbols: list[str]) -> None:
        """Replaces the tracked symbol list, one blank row per symbol.

        Called once at startup (and again if Settings' `DEFAULT_SYMBOLS`
        changes the tracked list) — never per tick, which is what
        `update_tick()` is for.
        """
        self._drop_flashes(())
        self.set_rows([WatchlistRow(symbol=symbol) for symbol in symbols])
        self._row_index = {row.symbol: index for index, row in enumerate(self._rows)}

    def track(self, symbols: Sequence[str]) -> None:
        """Tracks `symbols`, in that order: a symbol already listed keeps its
        latest price, change and volume, a new one starts blank
        (`EPIC-033V`), where `set_symbols` blanks them all."""
        known = {row.symbol: row for row in self._rows}
        self._drop_flashes(symbols)
        self.set_rows([known.get(symbol) or WatchlistRow(symbol) for symbol in symbols])
        self._row_index = {row.symbol: index for index, row in enumerate(self._rows)}

    def update_tick(
        self,
        symbol: str,
        last_price: float,
        percent_change: float,
        volume: float,
    ) -> None:
        """Updates one symbol's row in place, keeping the user's selection
        and scroll position — a tick for a symbol this watchlist is not
        tracking (`set_symbols()` was never called with it) is ignored."""
        index = self._row_index.get(symbol)
        if index is None:
            return
        self._start_flash(symbol, self._rows[index].last_price, last_price)
        self._rows[index] = WatchlistRow(
            symbol=symbol,
            last_price=last_price,
            percent_change=percent_change,
            volume=volume,
        )
        self.dataChanged.emit(
            self.index(index, 0), self.index(index, self.columnCount() - 1)
        )

    # -- the tick flash ------------------------------------------------------

    def set_tick_flash(self, enabled: bool) -> None:
        """Turns the flash on or off; off, every flash in progress ends at once."""
        self._flash_on = enabled
        if not enabled:
            self._drop_flashes(())

    def _start_flash(self, symbol: str, before: float | None, after: float) -> None:
        """A price that moved takes its direction's tone; the first price seen, or one that did
        not move, says nothing."""
        if not self._flash_on or before is None or after == before:
            return
        tone = Tone.POSITIVE if after > before else Tone.NEGATIVE
        self._flashes[symbol] = (tone, self._clock() + FLASH_MILLISECONDS / 1000)
        if not self._flash_timer.isActive():
            self._flash_timer.start(FLASH_MILLISECONDS)

    def _end_flashes(self) -> None:
        """Ends the flashes that are over and re-arms the timer for the next one to end."""
        now = self._clock()
        over = [symbol for symbol, (_, ends) in self._flashes.items() if ends <= now]
        for symbol in over:
            del self._flashes[symbol]
            self._repaint_price(symbol)
        if self._flashes:
            soonest = min(ends for _, ends in self._flashes.values())
            self._flash_timer.start(max(1, round((soonest - now) * 1000)))
        else:
            self._flash_timer.stop()

    def _drop_flashes(self, keep: Sequence[str]) -> None:
        """Ends every flash but the `keep` symbols', and the timer with the last of them."""
        dropped = [symbol for symbol in self._flashes if symbol not in keep]
        for symbol in dropped:
            del self._flashes[symbol]
            self._repaint_price(symbol)
        if not self._flashes:
            self._flash_timer.stop()

    def _repaint_price(self, symbol: str) -> None:
        index = self._row_index.get(symbol)
        if index is not None:
            cell = self.index(index, self.PRICE_COLUMN)
            self.dataChanged.emit(cell, cell)

    # -- what this table decides (the rest is `RowTableModel`'s) -----------

    def _value(self, row: WatchlistRow, column: int) -> DisplayValue:
        values: tuple[DisplayValue, ...] = (
            row.symbol,
            row.last_price,
            row.percent_change,
            row.volume,
        )
        return values[column]

    def _symbol(self, row: WatchlistRow) -> str | None:
        return row.symbol

    def _role_data(self, row: WatchlistRow, column: int, role: int) -> object:
        """A flashing price's direction, as a triangle beside it, in the flash's tone."""
        if role != Qt.ItemDataRole.DecorationRole or column != self.PRICE_COLUMN:
            return None
        tone = self._tone(row, column)
        if tone not in _FLASH_ICONS:
            return None
        size = QApplication.style().pixelMetric(QStyle.PixelMetric.PM_SmallIconSize)
        return tone_icon(_FLASH_ICONS[tone], tone, size)

    def _tone(self, row: WatchlistRow, column: int) -> Tone:
        """No tone before any tick has been seen: painting one direction by
        default would claim knowledge this row does not have. A price carries one only while
        its flash lasts."""
        if column == self.PRICE_COLUMN:
            tone, ends = self._flashes.get(row.symbol, (Tone.NEUTRAL, 0.0))
            return tone if self._clock() < ends else Tone.NEUTRAL
        if column != self.PERCENT_CHANGE_COLUMN:
            return Tone.NEUTRAL
        return sign_tone(row.percent_change)
