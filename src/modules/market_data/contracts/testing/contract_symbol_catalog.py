"""The contract suite for `ISymbolCatalog` (HLD §10.3).

Both implementations run it: `FakeSymbolCatalog`, and the real
`SymbolCatalogService` over `FakeSymbolCatalogRepository` (itself a verified
fake with its own suite) and a stub exchange client. Nothing here needs a
network or a file, because what this port promises is the *shape and
normalisation* of the answer plus the cache rule; fetching is
`IExchangeClient`'s contract, pinned by its own tests.

**The suite needs one hook.** Some guarantees are about what the
implementation answers *after* the catalog holds something, and the two get
there differently — the fake is seeded, the real service reads a repository.
So a subclass supplies `given_symbols`, a callable that puts symbols where
its implementation will find them. The subclass wiring the real service is
where that means "save them to the repository", which keeps the asymmetry in
the adapter-shaped place rather than in the contract.

What this suite does **not** pin is what `force_refresh=True` fetches: the
fake has no exchange. That half is `TestTheRealService`'s own business, next
to the suite, where a stub client can answer.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

import pytest
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_symbol_catalog import (
    ISymbolCatalog,
)

#: How a subclass puts symbols where its implementation reads them.
type GivenSymbols = Callable[[Sequence[str]], None]


class SymbolCatalogContract:
    """Inherit this, provide `impl` and `given_symbols`. Both must pass it."""

    @pytest.fixture
    def impl(self) -> ISymbolCatalog:
        raise NotImplementedError(
            "a SymbolCatalogContract subclass must provide an `impl` fixture "
            "returning the ISymbolCatalog under test"
        )

    @pytest.fixture
    def given_symbols(self) -> GivenSymbols:
        raise NotImplementedError(
            "a SymbolCatalogContract subclass must provide a `given_symbols` "
            "fixture that puts symbols where its implementation reads them"
        )

    # -- the ordinary answer -------------------------------------------------

    def test_an_empty_catalog_reads_empty(self, impl: ISymbolCatalog) -> None:
        """Not an error: a first run has fetched nothing yet, and both callers
        handle it by showing an empty picker."""
        assert impl.list_symbols() == ()

    def test_every_symbol_given_comes_back(
        self, impl: ISymbolCatalog, given_symbols: GivenSymbols
    ) -> None:
        given_symbols(["BTCUSDT", "ETHUSDT"])

        assert impl.list_symbols() == ("BTCUSDT", "ETHUSDT")

    # -- normalisation, which three pickers render directly ------------------

    def test_symbols_are_upper_cased(
        self, impl: ISymbolCatalog, given_symbols: GivenSymbols
    ) -> None:
        given_symbols(["btcusdt"])

        assert impl.list_symbols() == ("BTCUSDT",)

    def test_surrounding_whitespace_is_trimmed(
        self, impl: ISymbolCatalog, given_symbols: GivenSymbols
    ) -> None:
        given_symbols(["  BTCUSDT  "])

        assert impl.list_symbols() == ("BTCUSDT",)

    def test_duplicates_collapse(
        self, impl: ISymbolCatalog, given_symbols: GivenSymbols
    ) -> None:
        """A picker showing `BTCUSDT` twice is a visible defect, and the two
        sources of this list (a stored copy and a fresh fetch) had different
        answers before the port promised one."""
        given_symbols(["BTCUSDT", "btcusdt", " BTCUSDT "])

        assert impl.list_symbols() == ("BTCUSDT",)

    def test_blank_entries_are_dropped(
        self, impl: ISymbolCatalog, given_symbols: GivenSymbols
    ) -> None:
        given_symbols(["BTCUSDT", "", "   "])

        assert impl.list_symbols() == ("BTCUSDT",)

    def test_the_order_is_alphabetical_not_the_source_order(
        self, impl: ISymbolCatalog, given_symbols: GivenSymbols
    ) -> None:
        """The picker shows them in this order, so it is a promise, not an
        accident of whichever source answered."""
        given_symbols(["ETHUSDT", "BTCUSDT", "SOLUSDT"])

        assert impl.list_symbols() == ("BTCUSDT", "ETHUSDT", "SOLUSDT")

    # -- the snapshot is a snapshot ------------------------------------------

    def test_the_answer_is_an_immutable_snapshot(
        self, impl: ISymbolCatalog, given_symbols: GivenSymbols
    ) -> None:
        """`domain-truth-rule.md` — three consumers read this list, and one
        that sorted or trimmed it in place used to change what the next
        reader saw."""
        given_symbols(["BTCUSDT"])

        assert isinstance(impl.list_symbols(), tuple)

    def test_two_reads_answer_the_same(
        self, impl: ISymbolCatalog, given_symbols: GivenSymbols
    ) -> None:
        """A cached read and a stored read are the same answer — the shape a
        caller sees must not depend on which one it happened to get."""
        given_symbols(["BTCUSDT", "ethusdt"])

        assert impl.list_symbols() == impl.list_symbols()
