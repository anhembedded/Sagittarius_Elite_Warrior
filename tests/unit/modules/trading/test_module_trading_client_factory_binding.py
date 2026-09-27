"""`ITradingClientFactory`'s venue-branching bind (`EPIC-027K`), locked
against a real container — the same doctrine
`test_module_metadata_provider_binding.py`/`test_module_account_reader_binding.py`
already established for their own venue-branched ports
(`architecture-rule.md` §7.3: a docstring is not what breaks when reality
changes, a test is).

Distinct from `test_module_trading_client_binding.py`: that file locks
`TradingModule._bind_trading_client_if_enabled()`'s conditional bind of the
fixed-`OrderSubmissionMode.LIVE` `ITradingClient` singleton (unbound while
`TradingVenue.DISABLED`). This file locks the always-constructible
`ITradingClientFactory` itself — the port every call site that needs a
specific `OrderSubmissionMode` (e.g. `preview_order`'s `VALIDATE_ONLY`)
resolves directly, registered unconditionally regardless of whether trading
is enabled.

Real components throughout (`test_no_foreign_port_is_mocked.py`'s own
doctrine): `StdLibContainer` is the Engine's real `IContainer`, `DictConfig`
its real in-memory `IConfig`, and `bind_adapters()` is the same production
wiring `TradingModule.register()` calls.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_trading_client_factory import (
    FuturesTradingClientFactory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_trading_client import (
    SpotTradingClient,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_trading_client_factory import (
    SpotTradingClientFactory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.composition.adapter_bindings import (
    bind_adapters,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_client_factory import (
    ITradingClientFactory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_submission_mode import (
    OrderSubmissionMode,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from sagittarius_engine.infrastructure.config.dict_config import DictConfig
from sagittarius_engine.infrastructure.container.std_container import StdLibContainer
from sagittarius_engine.interfaces.i_config import IConfig


def _container_with_venue(venue: TradingVenue | None) -> StdLibContainer:
    container = StdLibContainer()
    config = (
        DictConfig()
        if venue is None
        else DictConfig({ConfigKeys.EXCHANGE_TRADING_VENUE.value: venue.value})
    )
    container.singleton(IConfig, config)
    bind_adapters(container)
    return container


def test_factory_is_futures_by_default():
    """No config value at all — the same shape a fresh install boots
    with. Registered unconditionally, unlike `ITradingClient` itself, so
    this must resolve even though trading is not enabled."""
    container = _container_with_venue(None)

    factory = container.resolve(ITradingClientFactory)

    assert isinstance(factory, FuturesTradingClientFactory)


def test_factory_is_futures_when_venue_is_explicitly_disabled():
    container = _container_with_venue(TradingVenue.DISABLED)

    factory = container.resolve(ITradingClientFactory)

    assert isinstance(factory, FuturesTradingClientFactory)


def test_factory_is_spot_when_venue_is_spot_testnet():
    """`EPIC-027K` — before this bind existed, every venue silently
    resolved `FuturesTradingClientFactory`, which would sign a Spot Testnet
    request with Futures-only fields (`positionSide`/`reduceOnly`)."""
    container = _container_with_venue(TradingVenue.SPOT_TESTNET)

    factory = container.resolve(ITradingClientFactory)

    assert isinstance(factory, SpotTradingClientFactory)


def test_spot_factory_produces_a_spot_trading_client():
    """The factory's own job, not just its type: `create()` must hand back
    an actual `SpotTradingClient`, the concrete adapter this task built."""
    container = _container_with_venue(TradingVenue.SPOT_TESTNET)
    factory = container.resolve(ITradingClientFactory)

    client = factory.create(OrderSubmissionMode.VALIDATE_ONLY)

    assert isinstance(client, SpotTradingClient)
