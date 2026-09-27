"""Application port for caching live order-rounding symbol metadata
(`EPIC-021C`/`EPIC-027I`), for whichever market the active `TradingVenue`
trades.

@details Same shape as `ISymbolMarketMetadataCache` (`BOT-095E1`) — not a
reuse of it. That port is hard-typed to `SymbolMarketMetadata`, the
backtest-side float entity; caching a genuinely different, `Decimal`
entity (`SymbolOrderMetadata`) through it would be a type-level lie, not a
saved abstraction.

One instance serves whichever single market the active `TradingVenue`
trades — never both at once, since exactly one venue is resolved at boot
(`ONBOARDING.md` §7's authority table; `binance_bot_module.py`). A Futures
symbol and a Spot symbol can share the same string (`BTCUSDT` names two
different instruments), which would be a real collision in one shared
cache keyed by bare `symbol` if both markets were ever live simultaneously
in one process — they are not, so this cache does not key by market. If
that ever changes, key by `(TradingVenue, symbol)` here first.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.symbol_order_metadata import (
    SymbolOrderMetadata,
)


class ISymbolOrderMetadataCache(ABC):
    """Port for in-memory and persistent live order-rounding metadata
    caches."""

    @abstractmethod
    def get(self, symbol: str) -> SymbolOrderMetadata | None:
        """Retrieves cached metadata for a symbol if present."""

    @abstractmethod
    def put(self, metadata: SymbolOrderMetadata) -> None:
        """Stores or updates metadata for a symbol."""

    @abstractmethod
    def has(self, symbol: str) -> bool:
        """Checks if metadata for a symbol exists in cache."""

    @abstractmethod
    def clear(self) -> None:
        """Empties the cache."""
