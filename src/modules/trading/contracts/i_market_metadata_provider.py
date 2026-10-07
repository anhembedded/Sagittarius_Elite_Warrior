"""Application port for reading live order-rounding metadata by symbol
(`EPIC-021C`/`EPIC-027I`), for whichever market the active `TradingVenue`
trades."""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.symbol_order_metadata import (
    SymbolOrderMetadata,
)


class IMarketMetadataProvider(ABC):
    """@brief Port for resolving one symbol's order-rounding rules.

    @details One implementer per market — `FuturesMetadataProvider`,
    `SpotMetadataProvider` (`EPIC-027I`) — chosen at composition by the
    active `TradingVenue`, mirroring `ITradingAccountReader`'s own
    venue-branching bind. The port itself takes no venue parameter: which
    market answers is fixed once, at boot, by which concrete class is
    bound, never by an argument a caller could request the wrong market
    with (the same reasoning `ITradingClientFactory.create()` already
    gives for taking no venue argument).

    @details Deliberately two operations, not one: `get_or_fetch()` is the
    cheap, cache-first path every order-construction call site uses;
    `refresh()` is the explicit, always-hits-the-network path
    `EPIC-021D`'s connection check uses to make sure metadata isn't
    silently stale before the first real order goes out. Binance's
    `exchangeInfo` returns the whole symbol catalog in one call — there is
    no cheaper per-symbol refresh to offer instead.
    """

    @abstractmethod
    def get_or_fetch(self, symbol: str) -> SymbolOrderMetadata | None:
        """@brief Returns cached metadata for `symbol`, fetching and
        caching the whole catalog first if the cache is empty.
        @return `None` if `symbol` does not exist in the catalog even after
        a fetch — never a default/placeholder metadata standing in for a
        symbol that was never actually found.
        @throws SymbolRulesUnavailableError The catalog could not be fetched;
        the message is a short plain reason, never an exchange page.
        """

    @abstractmethod
    def refresh(self) -> None:
        """@brief Unconditionally re-fetches the whole symbol catalog from
        the exchange and repopulates the cache.
        @throws SymbolRulesUnavailableError The catalog could not be fetched."""
