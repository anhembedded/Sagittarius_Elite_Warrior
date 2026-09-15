"""`ISymbolCatalog`'s contract, against both implementations (HLD §10.3).

**Both halves are unit tests, deliberately.** The real one is
`SymbolCatalogService` over `FakeSymbolCatalogRepository` — itself a verified
fake with its own suite (PR 0.4a-3) — and a stub `IExchangeClient`. There is
no file and no socket in that composition, so this tier proves the whole
promise (`ci-rule.md` §6 — the tier is chosen by what the test touches, not
by which class it names). `JsonSymbolCatalogRepository`'s own suite runs in
`tests/integration/` for the real storage.
"""

from __future__ import annotations

from collections.abc import Sequence
from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.modules.market_data.application.queries.list_available_symbols import (
    SymbolCatalogService,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_exchange_client import (
    IExchangeClient,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_symbol_catalog import (
    ISymbolCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.contract_symbol_catalog import (
    GivenSymbols,
    SymbolCatalogContract,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_symbol_catalog import (
    FakeSymbolCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_symbol_catalog_repository import (
    FakeSymbolCatalogRepository,
)


def _exchange_answering(symbols: list[str]) -> Mock:
    """`IExchangeClient` is the network and market_data's own port, so a mock
    is allowed here (HLD §10.3 rule 4 is about *foreign* ports) — and what
    matters in this file is mostly whether it is asked at all."""
    client = Mock(spec=IExchangeClient)
    client.get_available_symbols.return_value = symbols
    return client


class TestFakeSymbolCatalog(SymbolCatalogContract):
    """The fake's half — what every consumer's test will be driving."""

    @pytest.fixture
    def impl(self) -> ISymbolCatalog:
        return FakeSymbolCatalog()

    @pytest.fixture
    def given_symbols(self, impl: ISymbolCatalog) -> GivenSymbols:
        assert isinstance(impl, FakeSymbolCatalog)
        return impl.seed


class TestTheRealService(SymbolCatalogContract):
    """The real one's half — this is what makes the fake *verified*."""

    @pytest.fixture
    def catalog_repo(self) -> FakeSymbolCatalogRepository:
        return FakeSymbolCatalogRepository()

    @pytest.fixture
    def impl(self, catalog_repo: FakeSymbolCatalogRepository) -> ISymbolCatalog:
        # An exchange with nothing to say, so the suite's "empty reads empty"
        # guarantee is about the catalog rather than about a stub's list.
        return SymbolCatalogService(lambda: _exchange_answering([]), catalog_repo)

    @pytest.fixture
    def given_symbols(self, catalog_repo: FakeSymbolCatalogRepository) -> GivenSymbols:
        def store(symbols: Sequence[str]) -> None:
            catalog_repo.save_symbols(list(symbols))

        return store


class TestTheFakesOwnHelpers:
    """`reads`, `was_refreshed()` and `seed()` — not on the port, so the
    contract suite cannot cover them.

    `BUG-120`'s guard requires this: a helper a fake adds beyond its port is
    covered by nobody unless its own module tests it, and the "no" cases are
    the ones that matter — a helper that can only say yes is the `Mock` it
    replaced.
    """

    def test_was_refreshed_says_no_before_anything_was_read(self) -> None:
        assert FakeSymbolCatalog().was_refreshed() is False

    def test_was_refreshed_says_no_for_an_ordinary_read(self) -> None:
        fake = FakeSymbolCatalog(["BTCUSDT"])

        fake.list_symbols()

        assert fake.was_refreshed() is False

    def test_was_refreshed_says_yes_once_a_refresh_was_asked_for(self) -> None:
        """The picker's manual 🔄 (`BUG-066`) is the only caller that passes
        it, and "the button reached the module" is the fact its test needs."""
        fake = FakeSymbolCatalog(["BTCUSDT"])

        fake.list_symbols(force_refresh=True)

        assert fake.was_refreshed() is True

    def test_reads_records_every_call_in_order(self) -> None:
        fake = FakeSymbolCatalog()

        fake.list_symbols()
        fake.list_symbols(force_refresh=True)

        assert fake.reads == [False, True]

    def test_seed_replaces_the_catalog_and_normalises(self) -> None:
        fake = FakeSymbolCatalog(["OLDPAIR"])

        fake.seed([" ethusdt ", "BTCUSDT"])

        assert fake.list_symbols() == ("BTCUSDT", "ETHUSDT")


class TestWhatOnlyTheRealServiceCanAnswer:
    """`force_refresh`'s fetch half: the fake has no exchange, so the
    contract suite stops at "the flag was recorded" and the rest lives here."""

    def test_a_refresh_bypasses_a_populated_catalog(self) -> None:
        exchange = _exchange_answering(["NEWPAIR"])
        catalog = FakeSymbolCatalogRepository(["OLDPAIR"])

        result = SymbolCatalogService(lambda: exchange, catalog).list_symbols(
            force_refresh=True
        )

        assert result == ("NEWPAIR",)
        exchange.get_available_symbols.assert_called_once()

    def test_an_ordinary_read_of_a_populated_catalog_never_asks_the_exchange(
        self,
    ) -> None:
        exchange = _exchange_answering(["SHOULD_NOT_BE_ASKED"])
        catalog = FakeSymbolCatalogRepository(["BTCUSDT"])

        SymbolCatalogService(lambda: exchange, catalog).list_symbols()

        exchange.get_available_symbols.assert_not_called()
