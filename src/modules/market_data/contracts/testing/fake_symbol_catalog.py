"""The verified fake for `ISymbolCatalog` (HLD §10.3).

**Who needs it.** The shared symbol picker (three screens) and Data
Management's auto-discover read this list, and `ISymbolCatalog` is a
*foreign* port to both, so `Mock(spec=ISymbolCatalog)` is not an option —
`test_no_foreign_port_is_mocked.py` fails on it, because a mock agrees with
whatever the test asserts and cannot notice the day the port's real
behaviour changes.

**What it does and does not do.** It holds the symbols a test hands it and
applies the port's normalisation, sharing `normalised_symbols()` from the
port's own module rather than copying it. It has no exchange, so `force_refresh` changes
nothing about *what* comes back — it is recorded instead, because that is
what a consumer's test asserts: the refresh button asked for a refresh, and
the picker's first open did not.

**Not `FakeSymbolCatalogRepository`.** That one is the *storage* port's fake
(`get_symbols`/`save_symbols`). This one answers the published question. A
consumer's test wants this; a test for the module's own storage wants that.
"""

from __future__ import annotations

from collections.abc import Sequence

from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_symbol_catalog import (
    ISymbolCatalog,
    normalised_symbols,
)


class FakeSymbolCatalog(ISymbolCatalog):
    """The tradeable-symbol list a test controls, and no exchange."""

    def __init__(
        self,
        symbols: Sequence[str] | None = None,
        market: MarketType = MarketType.SPOT,
    ) -> None:
        """`symbols` seeds `market`'s catalog as a completed fetch would have,
        so a consumer's test starts from the state it needs in one line. Every
        other market starts empty, as a real catalog is per market; `seed()`
        without a market seeds this one."""
        self._default_market = market
        self._symbols: dict[MarketType, tuple[str, ...]] = {
            market: normalised_symbols(list(symbols or []))
        }
        #: Every call, as `force_refresh` was passed. A consumer asserts on
        #: this to show the manual refresh reached the module — a fact about
        #: the screen, not about the exchange.
        self.reads: list[bool] = []
        #: The market of every call, in order.
        self.markets_read: list[MarketType] = []

    def list_symbols(
        self, market: MarketType, *, force_refresh: bool = False
    ) -> tuple[str, ...]:
        self.reads.append(force_refresh)
        self.markets_read.append(market)
        return self._symbols.get(market, ())

    # -- what a consumer's test usually wants to know ------------------------

    def seed(self, symbols: Sequence[str], market: MarketType | None = None) -> None:
        """Replace `market`'s catalog, as a refresh from the exchange would."""
        self._symbols[market or self._default_market] = normalised_symbols(
            list(symbols)
        )

    def was_refreshed(self) -> bool:
        """Whether any call asked to bypass the cache."""
        return any(self.reads)
