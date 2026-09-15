"""Reading the tradeable-symbol list: the implementation behind `ISymbolCatalog`.

**Why this file no longer handles a query.** Until `EPIC-025` PR 1.2 it was
`ListAvailableSymbolsQueryHandler`, an `IQueryHandler` two call sites
dispatched — the shared symbol picker and Data Management's auto-discover.
PR 1.2 published `ISymbolCatalog` and moved both onto it, which left the
query class, its `execute()` and its dispatcher binding with no caller
anywhere in `src/`: a registration kept alive for a hypothetical consumer,
which is the accidental complexity this epic exists to remove. The same
retirement PR 1.1a's cleanup made for `GetHistoricalKlinesQuery`, for the
same measured reason.

It still lives under `application/queries/` because it is still the query
side of this module: a read, and the write it does on the way (storing what
it fetched) is a cache fill, not a new fact about the market.
"""

import logging
from collections.abc import Callable

from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_exchange_client import (
    IExchangeClient,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_symbol_catalog import (
    ISymbolCatalog,
    normalised_symbols,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_symbol_catalog_repository import (
    ISymbolCatalogRepository,
)

logger = logging.getLogger("App.QueryHandler")


class SymbolCatalogService(ISymbolCatalog):
    """The symbols this context knows are open for trading.

    Reads `ISymbolCatalogRepository`'s stored copy when it holds anything,
    and fetches from `IExchangeClient` when it is empty or the caller asked
    for a refresh — storing what it fetched, so the next caller pays no
    round trip.
    """

    def __init__(
        self,
        exchange_client: Callable[[], IExchangeClient],
        catalog_repo: ISymbolCatalogRepository,
    ) -> None:
        """`exchange_client` is a **factory**, not a client, and `BUG-045` is
        why: constructing `PythonBinanceClient` performs a network call, and
        this service is resolved when a *screen* is built — three Presenters
        resolve `ISymbolCatalog` in their constructors so a Coordinator never
        has to reach into the container (`async-ui-action-rule.md`).

        Taking the client eagerly made opening a screen call Binance, which
        is `BUG-045`'s defect and `BUG-107`'s rule ("opening the Trading
        screen must not open a network connection"). The gate caught it
        immediately — four integration tests failed against the real
        exchange — and the factory is the fix: nothing is built until a read
        actually has to leave the cache.
        """
        self._exchange_client = exchange_client
        self._catalog_repo = catalog_repo

    def list_symbols(self, *, force_refresh: bool = False) -> tuple[str, ...]:
        if not force_refresh:
            cached = self._catalog_repo.get_symbols()
            if cached:
                logger.info(f"Loaded {len(cached)} tradeable symbols from local cache.")
                return normalised_symbols(cached)

        logger.debug("Reading the tradeable-symbol list from the exchange")
        symbols = self._exchange_client().get_available_symbols()
        logger.info(f"Fetched {len(symbols)} tradeable symbols from the exchange.")
        if symbols:
            # Only a non-empty answer is stored: writing an empty list would
            # overwrite a good cache with the result of a bad day at the
            # exchange, and the next caller would see "no symbols" as fact.
            self._catalog_repo.save_symbols(symbols)
        return normalised_symbols(symbols)
