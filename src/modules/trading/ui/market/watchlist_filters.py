"""`WatchlistFilters` — reads the chosen market's exchange filters once the
Watchlist goes live, so its prices and volumes are written in each symbol's
tick and step (`EPIC-033N`).

@par Why when it goes live, and on a worker
The table reads the filters from the cache on the UI thread, on every paint
(`MarketMetadataPrecisions`), so something must fill the cache, and a fetch
is an HTTP round trip. Opening the mode must not open a connection
(`BUG-045`, `BUG-107`), so the read waits for the person's own start of the
stream, which opens connections anyway, and runs on a worker. Binance answers
the whole catalog in one call (`ISymbolMetadataProvider.get_or_fetch`), so
one symbol's read fills every row's.

@par Why a failure is logged and not raised
Without filters the Watchlist still shows every price, rounded by magnitude;
a failed read is a cosmetic loss, never a reason to stop the stream. It is
logged at `WARNING`, which the gate's log scan reads, so it is never silent.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Signal
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_symbol_metadata_provider import (
    ISymbolMetadataProvider,
)
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

logger = logging.getLogger("App.Trading.Market")


class WatchlistFilters(QObject):
    """Fetches one market's filters off the UI thread and says when done."""

    #: The market's filters were read (or the read failed and was logged); the
    #: Watchlist writes its cells again. Emitted on the worker thread, so a
    #: slot on a `QObject` of the UI thread runs queued there.
    fetched = Signal()

    def __init__(
        self,
        provider: ISymbolMetadataProvider,
        threads: IThreadManager,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._provider = provider
        self._threads = threads

    def fetch(self, market: MarketType, symbols: tuple[str, ...]) -> None:
        """Reads `market`'s catalog through the first of `symbols`; nothing
        to read for no symbol."""
        if not symbols:
            return
        logger.info("[market] reading %s filters for the Watchlist", market.value)
        self._threads.submit(self._run, market, symbols[0])

    def _run(self, market: MarketType, symbol: str) -> None:
        """A worker thread: touches no widget, reports through `fetched`."""
        try:
            found = self._provider.get_or_fetch(market, symbol)
        except Exception as exc:  # noqa: BLE001 - worker boundary: see the module docstring
            logger.warning(
                "[market] could not read %s filters: %s. The Watchlist rounds "
                "its prices by magnitude.",
                market.value,
                exc,
            )
            return
        logger.info(
            "[market] %s filters read (%s listed: %s)",
            market.value,
            symbol,
            found is not None,
        )
        self.fetched.emit()
