"""`BUG-127` — the Backtest screen's exchange-filter source must be reachable.

The defect was not a wrong answer, it was an unreachable one:
`ISymbolMarketMetadataCache` was bound nowhere, so
`container.resolve(ISymbolMarketMetadataCache)` raised on every construction of
`BackTestPresenter`, landed in that constructor's `except`, and the screen got a
fresh empty cache nothing would ever write to. `refresh_market_rule_verification()`
therefore answered *"not verified against exchange rules"* for every symbol,
permanently, with the real filter evaluation below that branch unreachable in
production.

**Why this tier, and why the real composition root.** Every test that covered
this area passed, and each passed for the same reason: it supplied the
collaborator production forgot. The parser's test builds its own payload; the
cache adapter's test builds its own cache; the coordinator's tests inject
`get_market_metadata` directly. A test that constructs its subject can say
nothing about whether the application constructs it — `CS-002`, and now
[`CS-003`](../../../Docs/CASE_STUDIES/CS-003_the_port_nobody_bound.md). So this
one asks the graph `create_app()` really builds, which is the only thing that
could have failed.

It costs no network: container bindings resolve lazily, and the provider takes a
client **factory** rather than a client, for `BUG-045`'s reason — constructing
`PythonBinanceClient` performs a network call, and resolving a port must not.
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_symbol_market_metadata_cache import (
    ISymbolMarketMetadataCache,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_symbol_metadata_provider import (
    ISymbolMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.shell.composition_root import create_app
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager


@pytest.fixture
def container():
    """The real object graph, built the way both entry points build it."""
    return create_app(ConfigManager()).container


def test_the_symbol_metadata_cache_resolves(container) -> None:
    """The regression itself. Before the fix this raised
    `DependencyResolutionError: Cannot instantiate abstract class`, and the
    Backtest screen's `except` branch turned that into silence."""
    cache = container.resolve(ISymbolMarketMetadataCache)

    assert isinstance(cache, ISymbolMarketMetadataCache)


def test_the_symbol_metadata_provider_resolves(container) -> None:
    """The other half of the wiring: a store nobody fills is still broken, so
    the thing that fills it has to be reachable too (`BUG-127` had **two**
    missing wires — no binding, and no caller for the parser)."""
    provider = container.resolve(ISymbolMetadataProvider)

    assert isinstance(provider, ISymbolMetadataProvider)


def test_the_cache_is_one_instance_for_the_whole_app(container) -> None:
    """A per-caller cache is the defect wearing a binding: the Data Management
    sync warms it on a worker thread and the Backtest screen reads it on the
    main thread, so two instances would mean the reader never sees the write.
    `PositionRefreshService` (`BUG-117`) is the same lesson one layer down."""
    assert container.resolve(ISymbolMarketMetadataCache) is container.resolve(
        ISymbolMarketMetadataCache
    )


def test_resolving_the_provider_makes_no_exchange_client(container) -> None:
    """`BUG-045` / `BUG-107`: opening a screen must not open a network
    connection. The provider holds a client **factory**, so resolving it must
    leave `IExchangeClient` unbuilt — asked of the container's own
    instantiation record, not inferred."""
    from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_exchange_client import (
        IExchangeClient,
    )

    container.resolve(ISymbolMetadataProvider)

    registration = container.registrations().get(IExchangeClient)
    assert registration is not None, "IExchangeClient should still be registered"
    assert registration.instantiated is False, (
        "resolving the metadata provider built a Binance client — that is a "
        "network call on screen construction (BUG-045)"
    )
