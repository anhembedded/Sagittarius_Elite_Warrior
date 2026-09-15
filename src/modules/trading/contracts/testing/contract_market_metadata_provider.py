"""The contract suite for `IMarketMetadataProvider` (HLD §10.3).

Four guarantees, and HLD §10.3 rule 2 is why there are only four: *"a
guarantee no consumer needs is not in the suite"*. The consumers measured
today are the order-shaping path (`preview_order`, `execute_order`, the
payload mapper) and `EPIC-021D`'s connection check, and between them they
depend on exactly these:

1. a seeded symbol comes back;
2. an unknown symbol comes back as `None` — **never** a placeholder standing
   in for a symbol the exchange does not have. This is the one that matters:
   a caller rounding an order quantity against a default `step_size` would
   send a quantity the exchange rejects, or worse, accepts;
3. the lookup does not care how the caller cased the symbol, because the CLI
   passes what the user typed;
4. `refresh()` and `get_or_fetch()` are two operations, not one — the port's
   docstring says the first always leaves for the network and the second
   prefers the cache, and that difference is the reason the port has two
   methods at all.

**One hook.** A subclass supplies `given_metadata`, because the two
implementations are told what the catalog holds in different ways: the fake
is seeded, and the real `FuturesMetadataProvider` reads an
`IFuturesSymbolMetadataCache`. The asymmetry lives in the subclass, not in
the contract.

What this suite does **not** pin is what `refresh()` actually fetches: the
fake has no exchange. That half belongs to the real implementation's own
integration test against the fake exchange server — `EPIC-025` PR 1.3b, which
is when `FuturesMetadataProvider` stops needing the shared
`FuturesSessionFactory` that keeps it unconstructible in this tier.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.futures_symbol_metadata import (
    FuturesSymbolMetadata,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_market_metadata_provider import (
    IMarketMetadataProvider,
)

#: How a subclass puts metadata where its implementation reads it.
type GivenMetadata = Callable[[Sequence[FuturesSymbolMetadata]], None]


class MarketMetadataProviderContract:
    """Inherit this, provide `impl` and `given_metadata`. Both must pass it."""

    @pytest.fixture
    def impl(self) -> IMarketMetadataProvider:
        raise NotImplementedError(
            "a MarketMetadataProviderContract subclass must provide an `impl` "
            "fixture returning the IMarketMetadataProvider under test"
        )

    @pytest.fixture
    def given_metadata(self) -> GivenMetadata:
        raise NotImplementedError(
            "a MarketMetadataProviderContract subclass must provide a "
            "`given_metadata` fixture that puts metadata where its "
            "implementation reads it"
        )

    def test_a_known_symbol_comes_back(
        self,
        impl: IMarketMetadataProvider,
        given_metadata: GivenMetadata,
        btc_metadata: FuturesSymbolMetadata,
    ) -> None:
        given_metadata([btc_metadata])

        assert impl.get_or_fetch("BTCUSDT") == btc_metadata

    def test_an_unknown_symbol_is_none_and_never_a_placeholder(
        self,
        impl: IMarketMetadataProvider,
        given_metadata: GivenMetadata,
        btc_metadata: FuturesSymbolMetadata,
    ) -> None:
        """The port's own promise, and the expensive one to get wrong: a
        caller shaping an order rounds against `step_size`, so a default
        standing in for a symbol the exchange never listed produces a
        quantity the venue rejects."""
        given_metadata([btc_metadata])

        assert impl.get_or_fetch("NOSUCHUSDT") is None

    def test_the_lookup_ignores_the_case_the_caller_used(
        self,
        impl: IMarketMetadataProvider,
        given_metadata: GivenMetadata,
        btc_metadata: FuturesSymbolMetadata,
    ) -> None:
        """`trade-once --symbol btcusdt` is a thing a user types."""
        given_metadata([btc_metadata])

        assert impl.get_or_fetch("btcusdt") == btc_metadata

    def test_a_cached_read_is_not_a_refresh(
        self,
        impl: IMarketMetadataProvider,
        given_metadata: GivenMetadata,
        btc_metadata: FuturesSymbolMetadata,
    ) -> None:
        """Two methods, two costs. Reading a symbol that is already known
        must not go to the exchange — which is why the port does not offer
        one method with a flag."""
        given_metadata([btc_metadata])

        for _ in range(3):
            assert impl.get_or_fetch("BTCUSDT") == btc_metadata
