"""`SymbolCatalogService` — cache first, exchange only when it must.

`EPIC-025` PR 1.2 renamed the subject: this was
`ListAvailableSymbolsQueryHandler`, and the query it handled is gone with the
dispatch surface nothing called any more. The five guarantees below are
unchanged, and they are the ones the published `ISymbolCatalog` contract
cannot pin because it has no exchange to stub.

Driven through `FakeSymbolCatalogRepository`, the port's verified fake, rather than
`Mock(spec=ISymbolCatalogRepository)`. The port is market_data's own, so a mock
would not break HLD §10.3 rule 4 — but it was hiding something anyway.

With a mock, `save_symbols` records the call and does nothing, so the only thing
a test can assert is **that it was called with a particular list**. That couples
the test to an argument and still says nothing about whether the catalog ends up
holding the right symbols. The fake stores them and normalises exactly as the
real one does, so these tests now assert the **effect** a user would see next
time the picker opens — and the last test below asserts something no mock-based
version could have: that a lower-case symbol from the exchange is persisted
upper-cased.
"""

from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.modules.market_data.application.queries.list_available_symbols.handler import (
    SymbolCatalogService,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_exchange_client import (
    IExchangeClient,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_symbol_catalog_repository import (
    FakeSymbolCatalogRepository,
)


def _exchange(symbols: list[str]) -> Mock:
    """`IExchangeClient` stays a mock: it is the network, and the point of most
    of these tests is whether it gets called at all."""
    client = Mock(spec=IExchangeClient)
    client.get_available_symbols.return_value = symbols
    return client


def _factory_for(client: Mock) -> Mock:
    """The service takes a **factory** (`BUG-045`: building a client is a
    network call), so these tests count both — whether a client was built at
    all, and whether it was asked."""
    return Mock(return_value=client)


def test_a_populated_catalog_answers_without_touching_the_exchange():
    exchange = _exchange(["SHOULD_NOT_BE_ASKED"])
    catalog = FakeSymbolCatalogRepository(["BTCUSDT", "ETHUSDT"])

    result = SymbolCatalogService(lambda: exchange, catalog).list_symbols()

    assert result == ("BTCUSDT", "ETHUSDT")
    exchange.get_available_symbols.assert_not_called()


def test_an_empty_catalog_is_filled_from_the_exchange():
    exchange = _exchange(["SOLUSDT"])
    catalog = FakeSymbolCatalogRepository()

    result = SymbolCatalogService(lambda: exchange, catalog).list_symbols()

    assert result == ("SOLUSDT",)
    exchange.get_available_symbols.assert_called_once()
    # The effect, not the call: the next query answers from the catalog.
    assert catalog.get_symbols() == ["SOLUSDT"]


def test_force_refresh_replaces_a_populated_catalog():
    exchange = _exchange(["NEWPAIR"])
    catalog = FakeSymbolCatalogRepository(["OLDPAIR"])

    result = SymbolCatalogService(lambda: exchange, catalog).list_symbols(
        force_refresh=True
    )

    assert result == ("NEWPAIR",)
    exchange.get_available_symbols.assert_called_once()
    assert catalog.get_symbols() == ["NEWPAIR"], "the stale symbol must be gone"


def test_an_exchange_answer_is_persisted_normalised():
    """What the mock-based version could not see. The handler passes the
    exchange's list straight through to `save_symbols()`, so the *catalog* is
    what guarantees the picker gets clean, upper-cased, de-duplicated symbols.
    The contract suite pins that guarantee for both implementations; this test
    pins that this service actually goes through it."""
    exchange = _exchange([" ethusdt ", "BTCUSDT", "btcusdt"])
    catalog = FakeSymbolCatalogRepository()

    SymbolCatalogService(lambda: exchange, catalog).list_symbols(force_refresh=True)

    assert catalog.get_symbols() == ["BTCUSDT", "ETHUSDT"]


def test_an_empty_exchange_answer_does_not_wipe_the_catalog():
    """The handler's `and symbols` guard. An exchange outage returning `[]` must
    not destroy a good catalog — the user would lose their picker over a
    transient failure."""
    exchange = _exchange([])
    catalog = FakeSymbolCatalogRepository(["BTCUSDT"])

    result = SymbolCatalogService(lambda: exchange, catalog).list_symbols(
        force_refresh=True
    )

    # Behaviour kept exactly (ADR D12): the answer is what the exchange said,
    # while the catalog keeps what it had. A caller therefore sees an empty
    # picker for this one read and a populated one on the next — which is the
    # old handler's behaviour, not a decision this PR made.
    assert result == ()
    assert catalog.get_symbols() == ["BTCUSDT"]


def test_a_cached_read_never_even_builds_an_exchange_client():
    """`BUG-045` — constructing `PythonBinanceClient` performs a network call,
    and three Presenters resolve this port while a *screen* is being built. So
    "did not fetch" is not enough: it must not have built a client either.

    The first version of `SymbolCatalogService` took the client eagerly, and
    the gate caught it by failing four integration tests against the live
    exchange.
    """
    client = _exchange(["SHOULD_NOT_BE_ASKED"])
    factory = _factory_for(client)
    catalog = FakeSymbolCatalogRepository(["BTCUSDT"])

    SymbolCatalogService(factory, catalog).list_symbols()

    factory.assert_not_called()


def test_a_refresh_builds_the_client_once():
    client = _exchange(["BTCUSDT"])
    factory = _factory_for(client)

    SymbolCatalogService(factory, FakeSymbolCatalogRepository()).list_symbols(
        force_refresh=True
    )

    factory.assert_called_once()
