"""`EPIC-028B` — `IVenueTradingPorts` against the real production wiring.

@details The Engine's real `StdLibContainer`, `DictConfig` and
`MemoryEventBus`, and the same `bind_adapters()`/`bind_state()`/
`bind_published_ports()` `TradingModule.register()` calls.
`ICommandDispatcher` is a `core/` port and records what it is asked to
dispatch, so the tests see which venue each published port stamps on its
commands without running a handler.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.cancel_order import (
    CancelOrderCommand,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_symbol_order_rules import (
    GetSymbolOrderRulesQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.venue_session_states import (
    VenueSessionStates,
)
from Sagittarius_Elite_Warrior.src.modules.trading.composition.adapter_bindings import (
    bind_adapters,
)
from Sagittarius_Elite_Warrior.src.modules.trading.composition.port_bindings import (
    bind_published_ports,
)
from Sagittarius_Elite_Warrior.src.modules.trading.composition.state_bindings import (
    bind_state,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.cancel_order_result import (
    CancelOrderResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_equity_curve import (
    IEquityCurve,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_order_submission import (
    IOrderSubmission,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_session import (
    ITradingSession,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    VenueNotEnabledError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_trading_ports import (
    IVenueTradingPorts,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from sagittarius_engine.infrastructure.config.dict_config import DictConfig
from sagittarius_engine.infrastructure.container.std_container import StdLibContainer
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus
from sagittarius_engine.interfaces.i_config import IConfig
from sagittarius_engine.interfaces.i_event_bus import IEventBus
from sagittarius_engine.interfaces.i_task_manager import ITaskManager

_FUTURES = TradingVenue.FUTURES_TESTNET
_SPOT = TradingVenue.SPOT_TESTNET


class _RecordingDispatcher(ICommandDispatcher):
    def __init__(self) -> None:
        self.dispatched: list[object] = []

    def dispatch(self, handler_class: type, input_dto: object | None = None) -> object:
        self.dispatched.append(input_dto)
        return CancelOrderResult(None, None)


def _container(dispatcher: _RecordingDispatcher) -> StdLibContainer:
    container = StdLibContainer()
    container.singleton(
        IConfig,
        DictConfig(
            {ConfigKeys.EXCHANGE_TRADING_VENUES.value: [_FUTURES.value, _SPOT.value]}
        ),
    )
    container.singleton(IEventBus, MemoryEventBus())
    container.singleton(ITaskManager, Mock())
    container.singleton(ICommandDispatcher, dispatcher)
    bind_adapters(container)
    bind_state(container)
    bind_published_ports(container)
    return container


@pytest.mark.parametrize("venue", [_FUTURES, _SPOT])
def test_each_venues_order_port_addresses_its_own_venue(venue: TradingVenue) -> None:
    dispatcher = _RecordingDispatcher()
    ports = _container(dispatcher).resolve(IVenueTradingPorts)

    ports.get(venue).order_submission.cancel("BTCUSDT", "abc")

    assert dispatcher.dispatched == [CancelOrderCommand("BTCUSDT", "abc", venue=venue)]


@pytest.mark.parametrize("venue", [_FUTURES, _SPOT])
def test_each_venues_order_entry_terms_address_its_own_venue(
    venue: TradingVenue,
) -> None:
    """`EPIC-028H` — the order panel's rules and fees read the desk's own
    venue."""
    dispatcher = _RecordingDispatcher()
    ports = _container(dispatcher).resolve(IVenueTradingPorts)

    with pytest.raises(TypeError):  # the recorder answers neither read
        ports.get(venue).order_entry_terms.terms_for("BTCUSDT")

    assert dispatcher.dispatched[0] == GetSymbolOrderRulesQuery(
        venue=venue, symbol="BTCUSDT"
    )


def test_each_venues_session_port_reads_its_own_state() -> None:
    container = _container(_RecordingDispatcher())
    ports = container.resolve(IVenueTradingPorts)
    container.resolve(VenueSessionStates).session_state(_SPOT).enable(set())

    spot = ports.get(_SPOT).trading_session.snapshot()
    futures = ports.get(_FUTURES).trading_session.snapshot()

    assert spot.enabled is True
    assert futures.enabled is False
    assert spot.market_type is _SPOT.market_type
    assert futures.market_type is _FUTURES.market_type


def test_ports_are_one_instance_per_venue() -> None:
    ports = _container(_RecordingDispatcher()).resolve(IVenueTradingPorts)

    assert ports.get(_SPOT) is ports.get(_SPOT)
    assert ports.get(_SPOT).equity_curve is not ports.get(_FUTURES).equity_curve
    assert ports.enabled() == (_FUTURES, _SPOT)


def test_the_single_published_ports_are_the_primary_venues_own() -> None:
    """The single Trading screen and Dev Board resolve these until the two
    desks exist; they must be the primary venue's instances, not a copy."""
    container = _container(_RecordingDispatcher())
    primary = container.resolve(IVenueTradingPorts).primary()

    assert primary.venue is _FUTURES
    assert container.resolve(IOrderSubmission) is primary.order_submission
    assert container.resolve(ITradingSession) is primary.trading_session
    assert container.resolve(IEquityCurve) is primary.equity_curve


def test_a_venue_that_is_not_served_has_no_ports() -> None:
    ports = _container(_RecordingDispatcher()).resolve(IVenueTradingPorts)

    with pytest.raises(VenueNotEnabledError):
        ports.get(TradingVenue.DISABLED)
