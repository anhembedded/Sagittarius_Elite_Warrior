"""`ListAvailableSymbolsQuery` — cache first, exchange only when it must.

Driven through `FakeSymbolCatalog`, the port's verified fake, rather than
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
    ListAvailableSymbolsQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.application.queries.list_available_symbols.query import (
    ListAvailableSymbolsQuery,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_exchange_client import (
    IExchangeClient,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_symbol_catalog import (
    FakeSymbolCatalog,
)


def _exchange(symbols: list[str]) -> Mock:
    """`IExchangeClient` stays a mock: it is the network, and the point of most
    of these tests is whether it gets called at all."""
    client = Mock(spec=IExchangeClient)
    client.get_available_symbols.return_value = symbols
    return client


def test_a_populated_catalog_answers_without_touching_the_exchange():
    exchange = _exchange(["SHOULD_NOT_BE_ASKED"])
    catalog = FakeSymbolCatalog(["BTCUSDT", "ETHUSDT"])

    result = ListAvailableSymbolsQueryHandler(exchange, catalog).execute(
        ListAvailableSymbolsQuery(force_refresh=False)
    )

    assert result == ["BTCUSDT", "ETHUSDT"]
    exchange.get_available_symbols.assert_not_called()


def test_an_empty_catalog_is_filled_from_the_exchange():
    exchange = _exchange(["SOLUSDT"])
    catalog = FakeSymbolCatalog()

    result = ListAvailableSymbolsQueryHandler(exchange, catalog).execute(
        ListAvailableSymbolsQuery(force_refresh=False)
    )

    assert result == ["SOLUSDT"]
    exchange.get_available_symbols.assert_called_once()
    # The effect, not the call: the next query answers from the catalog.
    assert catalog.get_symbols() == ["SOLUSDT"]


def test_force_refresh_replaces_a_populated_catalog():
    exchange = _exchange(["NEWPAIR"])
    catalog = FakeSymbolCatalog(["OLDPAIR"])

    result = ListAvailableSymbolsQueryHandler(exchange, catalog).execute(
        ListAvailableSymbolsQuery(force_refresh=True)
    )

    assert result == ["NEWPAIR"]
    exchange.get_available_symbols.assert_called_once()
    assert catalog.get_symbols() == ["NEWPAIR"], "the stale symbol must be gone"


def test_an_exchange_answer_is_persisted_normalised():
    """What the mock-based version could not see. The handler passes the
    exchange's list straight through to `save_symbols()`, so the *catalog* is
    what guarantees the picker gets clean, upper-cased, de-duplicated symbols.
    The contract suite pins that guarantee for both implementations; this test
    pins that this handler actually goes through it."""
    exchange = _exchange([" ethusdt ", "BTCUSDT", "btcusdt"])
    catalog = FakeSymbolCatalog()

    ListAvailableSymbolsQueryHandler(exchange, catalog).execute(
        ListAvailableSymbolsQuery(force_refresh=True)
    )

    assert catalog.get_symbols() == ["BTCUSDT", "ETHUSDT"]


def test_an_empty_exchange_answer_does_not_wipe_the_catalog():
    """The handler's `and symbols` guard. An exchange outage returning `[]` must
    not destroy a good catalog — the user would lose their picker over a
    transient failure."""
    exchange = _exchange([])
    catalog = FakeSymbolCatalog(["BTCUSDT"])

    result = ListAvailableSymbolsQueryHandler(exchange, catalog).execute(
        ListAvailableSymbolsQuery(force_refresh=True)
    )

    assert result == []
    assert catalog.get_symbols() == ["BTCUSDT"]
