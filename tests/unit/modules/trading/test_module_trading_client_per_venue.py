"""`EPIC-028B` — which venue gets a trading client, against the real wiring.

@details The successor of `EPIC-021F`'s lock on
`TradingModule._bind_trading_client_if_enabled()`, which `EPIC-028B`
deleted with the other single-venue bindings. The promise is unchanged and
still locked in both directions: a venue that cannot trade never gets a
client that could place an order, and a venue that can gets its own
venue's client, never the other venue's (`EPIC-027K`: a Futures client
signing with Spot credentials).

What moved is where the promise is kept. There is no `ITradingClient`
binding to leave unbound any more; `SubmitOrderCommandHandler` refuses a
venue whose `supports_order_submission` is false before it looks up any
adapter, and every other venue's client comes from that venue's own
`VenueContext.client_factory`.

Real components throughout: the Engine's `StdLibContainer`, `DictConfig`
and `MemoryEventBus`, and the same `bind_adapters()`/`bind_state()`
`TradingModule.register()` calls. The `ITaskManager` is only stored.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_trading_client import (
    FuturesTradingClient,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_trading_client import (
    SpotTradingClient,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.preview_order import (
    PreviewOrderQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.submit_order import (
    SubmitOrderCommand,
    SubmitOrderCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.composition.adapter_bindings import (
    bind_adapters,
)
from Sagittarius_Elite_Warrior.src.modules.trading.composition.state_bindings import (
    bind_state,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    IVenueContexts,
    VenueNotEnabledError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_submission_mode import (
    OrderSubmissionMode,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from sagittarius_engine.infrastructure.config.dict_config import DictConfig
from sagittarius_engine.infrastructure.container.std_container import StdLibContainer
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus
from sagittarius_engine.interfaces.i_config import IConfig
from sagittarius_engine.interfaces.i_event_bus import IEventBus
from sagittarius_engine.interfaces.i_task_manager import ITaskManager


def _container(venue: TradingVenue | None) -> StdLibContainer:
    """`venue` through the legacy scalar key, the shape an existing install
    boots with; `None` is a fresh install with no value at all."""
    container = StdLibContainer()
    values = (
        {} if venue is None else {ConfigKeys.EXCHANGE_TRADING_VENUE.value: venue.value}
    )
    container.singleton(IConfig, DictConfig(values))
    container.singleton(IEventBus, MemoryEventBus())
    container.singleton(ITaskManager, Mock())
    bind_adapters(container)
    bind_state(container)
    return container


def _submit_on(venue: TradingVenue) -> SubmitOrderCommand:
    return SubmitOrderCommand(
        order_request=PreviewOrderQuery(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("0.01"),
            reference_price=Decimal(60000),
            venue=venue,
        )
    )


@pytest.mark.parametrize("configured", [None, TradingVenue.DISABLED])
def test_a_venue_that_cannot_trade_is_refused_before_any_client_exists(
    configured: TradingVenue | None,
) -> None:
    """The dangerous direction: order placement reachable while trading is
    off. `DISABLED` is the primary venue here, so `IVenueContexts` would
    hand its adapters out; only the handler's own gate stands between the
    command and a client."""
    handler = _container(configured).resolve(SubmitOrderCommandHandler)

    with pytest.raises(VenueNotEnabledError):
        handler.execute(_submit_on(TradingVenue.DISABLED))


@pytest.mark.parametrize(
    ("venue", "client_type"),
    [
        (TradingVenue.FUTURES_TESTNET, FuturesTradingClient),
        (TradingVenue.SPOT_TESTNET, SpotTradingClient),
    ],
)
def test_a_venue_that_can_trade_creates_its_own_venues_client(
    venue: TradingVenue, client_type: type
) -> None:
    context = _container(venue).resolve(IVenueContexts).get(venue)

    client = context.client_factory.create(OrderSubmissionMode.VALIDATE_ONLY)

    assert isinstance(client, client_type)
