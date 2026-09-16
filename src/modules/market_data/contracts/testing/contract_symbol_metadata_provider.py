"""The contract suite for `ISymbolMetadataProvider` (HLD §10.3, `BUG-127`).

Both implementations run it: `FakeSymbolMetadataProvider`, and the real
`BinanceSymbolMetadataProvider` over a scripted `IExchangeClient` and the real
`InMemorySymbolMarketMetadataCache`.

**What it pins, and why each row is a contract rather than an implementation
detail.** `BUG-127` was not a wrong answer — it was a port nobody had wired, and
the reason nobody noticed is that every promise below had been *assumed* rather
than written down:

  · a symbol the exchange knows comes back, and is the symbol asked for — the
    consumer keys a UI message off it, so a near-miss is worse than nothing;
  · an unknown symbol comes back as `None`, **never** a placeholder standing in
    for a symbol that was never found (`domain-truth-rule.md`);
  · the second read of the same symbol costs no round trip, because the consumer
    calls this from a worker precisely so the main thread's read is free;
  · a **stale** entry is refetched. `BUG-098` is why this is a contract: the
    futures twin shipped `is_stale()` and never called it, so a filter was
    trusted for the life of the process after Binance had changed it;
  · `refresh()` reports how many symbols it cached, so a caller can log a real
    number rather than "done".

Case is not a contract: Binance returns upper case and every caller passes what
the user picked from a list the exchange itself produced. Both implementations
happen to upper-case the key, and a test asserting that would be pinning an
implementation detail two adapters share by accident.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_symbol_metadata_provider import (
    ISymbolMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.symbol_market_metadata import (
    LotSizeFilter,
    NotionalFilter,
    PriceFilter,
    SymbolMarketMetadata,
)

_KNOWN = "BTCUSDT"
_UNKNOWN = "NOPEUSDT"

#: Comfortably past `SymbolMarketMetadata`'s own staleness horizon, so the
#: stale row does not depend on what that horizon currently is.
_LONG_AGO = datetime.now(UTC) - timedelta(days=30)


def metadata_for(symbol: str, *, fetched_at: datetime | None = None):
    """A complete, plausible entry — every filter populated.

    A partial one would let an implementation pass by returning something
    shaped roughly right, which is the failure mode `CS-001` describes.
    """
    return SymbolMarketMetadata(
        symbol=symbol,
        status="TRADING",
        base_asset=symbol[:3],
        quote_asset="USDT",
        price_filter=PriceFilter(0.01, 1_000_000.0, 0.01),
        lot_size_filter=LotSizeFilter(0.00001, 9_000.0, 0.00001),
        notional_filter=NotionalFilter(5.0, apply_to_market=True),
        fetched_at=fetched_at or datetime.now(UTC),
    )


class SymbolMetadataProviderContract:
    """Inherit this and provide `impl`. Both implementations must pass it."""

    @pytest.fixture
    def impl(self) -> ISymbolMetadataProvider:
        raise NotImplementedError(
            "a SymbolMetadataProviderContract subclass must provide an `impl` "
            "fixture returning the ISymbolMetadataProvider under test"
        )

    def round_trips(self, impl: ISymbolMetadataProvider) -> int:
        """How many times `impl` has gone out to the exchange."""
        raise NotImplementedError(
            "a SymbolMetadataProviderContract subclass must report round trips"
        )

    def script(self, impl: ISymbolMetadataProvider, *entries) -> None:
        """Teach `impl`'s exchange about these entries."""
        raise NotImplementedError(
            "a SymbolMetadataProviderContract subclass must script its exchange"
        )

    def test_a_known_symbol_comes_back(self, impl) -> None:
        self.script(impl, metadata_for(_KNOWN))

        found = impl.get_or_fetch(_KNOWN)

        assert found is not None
        assert found.symbol == _KNOWN, (
            "the provider answered with a different symbol than the one asked "
            "for — the consumer puts this straight into a message about the "
            "user's own trading pair"
        )
        assert found.notional_filter.min_notional == 5.0

    def test_an_unknown_symbol_is_none_not_a_placeholder(self, impl) -> None:
        """`domain-truth-rule.md`: a convenience must not be presented as a
        fact. A default entry here would tell the Backtest screen that a symbol
        the exchange has never heard of passes the exchange's own rules."""
        self.script(impl, metadata_for(_KNOWN))

        assert impl.get_or_fetch(_UNKNOWN) is None

    def test_the_second_read_costs_no_round_trip(self, impl) -> None:
        """The reason the consumer calls this on a worker thread: the first read
        may go to the network, and the main thread's later reads must not."""
        self.script(impl, metadata_for(_KNOWN))
        impl.get_or_fetch(_KNOWN)
        after_first = self.round_trips(impl)

        impl.get_or_fetch(_KNOWN)

        assert self.round_trips(impl) == after_first

    def test_a_stale_entry_is_refetched(self, impl) -> None:
        """`BUG-098`: the futures twin had `is_stale()` for a whole epic and
        never called it, so a filter Binance had since changed was trusted for
        the life of the process."""
        self.script(impl, metadata_for(_KNOWN, fetched_at=_LONG_AGO))
        impl.get_or_fetch(_KNOWN)
        after_first = self.round_trips(impl)

        self.script(impl, metadata_for(_KNOWN))
        impl.get_or_fetch(_KNOWN)

        assert self.round_trips(impl) > after_first, (
            "a stale entry was served from the cache — the whole point of "
            "`fetched_at` is that filters expire"
        )

    def test_refresh_reports_how_many_it_cached(self, impl) -> None:
        self.script(impl, metadata_for(_KNOWN), metadata_for("ETHUSDT"))

        assert impl.refresh() == 2

    def test_refresh_on_an_empty_catalog_reports_zero_rather_than_raising(
        self, impl
    ) -> None:
        """A bad day at the exchange is an empty catalog, not an exception: the
        caller logs the number and carries on, which is what
        `DataSyncCoordinator` does after a sync that already succeeded."""
        assert impl.refresh() == 0
