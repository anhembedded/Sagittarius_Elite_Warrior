"""Application port for reading USD-M Futures order-rounding metadata by
symbol (`EPIC-021C`)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.domain.entities.futures_symbol_metadata import (
    FuturesSymbolMetadata,
)


class IMarketMetadataProvider(ABC):
    """@brief Port for resolving one symbol's futures order-rounding rules.

    @details Deliberately two operations, not one: `get_or_fetch()` is the
    cheap, cache-first path every order-construction call site uses;
    `refresh()` is the explicit, always-hits-the-network path
    `EPIC-021D`'s connection check uses to make sure metadata isn't
    silently stale before the first real order goes out. Binance's
    `exchangeInfo` returns the whole symbol catalog in one call — there is
    no cheaper per-symbol refresh to offer instead.
    """

    @abstractmethod
    def get_or_fetch(self, symbol: str) -> FuturesSymbolMetadata | None:
        """@brief Returns cached metadata for `symbol`, fetching and
        caching the whole catalog first if the cache is empty.
        @return `None` if `symbol` does not exist in the catalog even after
        a fetch — never a default/placeholder metadata standing in for a
        symbol that was never actually found.
        """

    @abstractmethod
    def refresh(self) -> None:
        """@brief Unconditionally re-fetches the whole symbol catalog from
        the exchange and repopulates the cache."""
