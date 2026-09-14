"""The contract suite for `ISymbolCatalogRepository` (HLD §10.3).

Every implementation of the port runs these tests: the verified fake in unit
(`tests/unit/modules/market_data/contracts/`), the real JSON one in integration
against a temp file (`tests/integration/modules/market_data/contracts/`). A
subclass supplies the `impl` fixture and inherits the assertions.

**What belongs here, and what does not.** HLD §10.3 rule 2: a guarantee is in
the suite because a consumer relies on it. Three consumers —
`symbol_options_coordinator`, the backtest presenter and the dashboard presenter
— read this list straight into a symbol picker, so the shape of the list *is*
the contract: clean, upper-cased, unique, ordered. A guarantee nobody needs
(say, the on-disk file format) stays out; that is the real implementation's own
test.

**The suite is extended by consumers, not only by the provider.** A module that
needs a promise this file does not make adds the test here rather than asserting
it locally against a stub — that is the consumer-driven half of the mechanism,
and it is what keeps a second implementation honest.

Written as a mixin class rather than parametrised fixtures so a subclass reads
as what it is (`class TestFakeSymbolCatalog(SymbolCatalogContract)`) and can add
implementation-specific tests beside the inherited ones.
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_symbol_catalog_repository import (
    ISymbolCatalogRepository,
)


class SymbolCatalogContract:
    """Inherit this and provide `impl`. Every test here must pass for both."""

    @pytest.fixture
    def impl(self) -> ISymbolCatalogRepository:
        raise NotImplementedError(
            "a SymbolCatalogContract subclass must provide an `impl` fixture "
            "returning the ISymbolCatalogRepository under test"
        )

    # -- reading before anything was written --------------------------------

    def test_an_empty_catalog_reads_as_an_empty_list(
        self, impl: ISymbolCatalogRepository
    ) -> None:
        """Not `None`, and not an error. The first run of a fresh install hits
        this path — the real one has no file yet — and the symbol picker must
        render empty rather than crash on boot."""
        assert impl.get_symbols() == []

    # -- the round trip ------------------------------------------------------

    def test_saved_symbols_come_back(self, impl: ISymbolCatalogRepository) -> None:
        impl.save_symbols(["BTCUSDT", "ETHUSDT"])

        assert impl.get_symbols() == ["BTCUSDT", "ETHUSDT"]

    def test_a_second_save_replaces_the_first(
        self, impl: ISymbolCatalogRepository
    ) -> None:
        """Replaces, never merges. A sync that found fewer symbols than last
        time must be able to say so — a delisted symbol has to disappear."""
        impl.save_symbols(["BTCUSDT", "ETHUSDT"])

        impl.save_symbols(["SOLUSDT"])

        assert impl.get_symbols() == ["SOLUSDT"]

    def test_saving_nothing_clears_the_catalog(
        self, impl: ISymbolCatalogRepository
    ) -> None:
        impl.save_symbols(["BTCUSDT"])

        impl.save_symbols([])

        assert impl.get_symbols() == []

    # -- the shape of what comes back ---------------------------------------

    def test_symbols_come_back_upper_cased(
        self, impl: ISymbolCatalogRepository
    ) -> None:
        """The exchange is asked in upper case and every other module compares
        in upper case, so the catalog is the place that normalises — not each
        of the three pickers that read it."""
        impl.save_symbols(["btcusdt", "EthUsdt"])

        assert impl.get_symbols() == ["BTCUSDT", "ETHUSDT"]

    def test_surrounding_whitespace_is_trimmed(
        self, impl: ISymbolCatalogRepository
    ) -> None:
        impl.save_symbols([" BTCUSDT ", "\tETHUSDT\n"])

        assert impl.get_symbols() == ["BTCUSDT", "ETHUSDT"]

    def test_blank_entries_are_dropped(self, impl: ISymbolCatalogRepository) -> None:
        """A trailing comma in a hand-edited file, or an empty cell from an
        exchange response, must not become a blank row in the picker."""
        impl.save_symbols(["BTCUSDT", "", "   ", "ETHUSDT"])

        assert impl.get_symbols() == ["BTCUSDT", "ETHUSDT"]

    def test_duplicates_are_collapsed(self, impl: ISymbolCatalogRepository) -> None:
        """Including duplicates that differ only by case or padding — they are
        the same symbol, and a picker showing it twice is a bug the user sees."""
        impl.save_symbols(["BTCUSDT", "btcusdt", " BTCUSDT "])

        assert impl.get_symbols() == ["BTCUSDT"]

    def test_symbols_come_back_sorted(self, impl: ISymbolCatalogRepository) -> None:
        """Ordering is part of the contract, not an accident of storage: the
        picker shows the list as given, and a list whose order changed between
        two syncs of the same symbols is a UI that moves under the cursor."""
        impl.save_symbols(["SOLUSDT", "BTCUSDT", "ETHUSDT"])

        assert impl.get_symbols() == ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

    # -- isolation -----------------------------------------------------------

    def test_mutating_the_returned_list_does_not_change_the_catalog(
        self, impl: ISymbolCatalogRepository
    ) -> None:
        """The real one reads a file, so its result is always a fresh list. A
        fake handing out its own storage would let a consumer's test pass on
        behaviour the real implementation does not have — which is precisely
        the drift this mechanism exists to catch."""
        impl.save_symbols(["BTCUSDT"])

        impl.get_symbols().append("ETHUSDT")

        assert impl.get_symbols() == ["BTCUSDT"]
