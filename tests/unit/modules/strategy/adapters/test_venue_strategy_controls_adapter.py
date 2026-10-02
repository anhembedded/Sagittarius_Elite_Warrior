"""`EPIC-028K` — each desk's strategy controls are its own venue's.

@details Resolved from the container `bind_published_ports` fills, so the
binding is what is tested (`CS-002`), not an adapter this file built itself.
`ICommandDispatcher` is a `core/` port; the recording double answers every
command with success and keeps it, and the command names the venue it was
addressed to. Each venue's session is a real `LiveStrategySession`.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.live_strategy_session import (
    LiveStrategySession,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.venue_strategy_sessions import (
    VenueStrategySessions,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.use_cases.arm_strategy import (
    ArmStrategyCommand,
    ArmStrategyResult,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.use_cases.disarm_strategy import (
    DisarmStrategyCommand,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.composition.port_bindings import (
    bind_published_ports,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.disarm_strategy_result import (
    DisarmStrategyResult,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.live_strategy_config import (
    LiveStrategyConfig,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.armed_strategy_config import (
    ArmedStrategyConfig,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_strategy_controls import (
    IVenueStrategyControls,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from sagittarius_engine.infrastructure.config.dict_config import DictConfig
from sagittarius_engine.infrastructure.container.std_container import StdLibContainer
from sagittarius_engine.interfaces.i_config import IConfig

_FUTURES = TradingVenue.FUTURES_TESTNET
_SPOT = TradingVenue.SPOT_TESTNET


class _RecordingDispatcher(ICommandDispatcher):
    def __init__(self) -> None:
        self.commands: list[object] = []

    def dispatch(self, handler_class: type, input_dto: object | None = None) -> object:
        self.commands.append(input_dto)
        if isinstance(input_dto, ArmStrategyCommand):
            return ArmStrategyResult(armed=True)
        return DisarmStrategyResult(disarmed=True)


class _EngineBuildingFactory:
    """Stands in for `LiveStrategyFactory.build()`: the session only holds
    the pair it returns."""

    def build(self, config: LiveStrategyConfig) -> tuple[object, object]:
        engine = Mock()
        engine.on_tick.return_value = None
        return engine, Mock()


class _NotServedError(Exception):
    pass


def _controls() -> tuple[IVenueStrategyControls, _RecordingDispatcher, dict]:
    sessions = {
        _FUTURES: LiveStrategySession(_EngineBuildingFactory()),  # type: ignore[arg-type]
        _SPOT: LiveStrategySession(_EngineBuildingFactory()),  # type: ignore[arg-type]
    }

    def build(venue: TradingVenue) -> LiveStrategySession:
        if venue not in sessions:
            raise _NotServedError(venue)
        return sessions[venue]

    dispatcher = _RecordingDispatcher()
    container = StdLibContainer()
    container.singleton(IConfig, DictConfig())
    container.singleton(ICommandDispatcher, dispatcher)
    container.singleton(VenueStrategySessions, VenueStrategySessions(build))
    bind_published_ports(container)
    return container.resolve(IVenueStrategyControls), dispatcher, sessions


def test_a_desks_arm_and_disarm_are_addressed_to_its_own_venue() -> None:
    controls, dispatcher, _ = _controls()

    controls.get(_SPOT).arming.arm(
        ArmedStrategyConfig(
            strategy_key="rsi_reversion", symbol="ETHUSDT", interval="1h"
        )
    )
    controls.get(_FUTURES).arming.disarm()

    arm, disarm = dispatcher.commands
    assert isinstance(arm, ArmStrategyCommand)
    assert arm.venue is _SPOT
    assert isinstance(disarm, DisarmStrategyCommand)
    assert disarm.venue is _FUTURES


def test_a_desk_reads_its_own_venues_armed_strategy() -> None:
    controls, _, sessions = _controls()
    sessions[_SPOT].arm(
        LiveStrategyConfig(
            strategy_key="rsi_reversion", symbol="ETHUSDT", interval="1h"
        )
    )

    spot = controls.get(_SPOT).armed.armed()
    futures = controls.get(_FUTURES).armed.armed()

    assert spot.config is not None
    assert spot.config.symbol == "ETHUSDT"
    assert futures.config is None


def test_a_venue_gets_the_same_controls_every_time() -> None:
    controls, _, _ = _controls()

    assert controls.get(_SPOT) is controls.get(_SPOT)
    assert controls.get(_SPOT).venue is _SPOT


def test_a_venue_nothing_serves_is_refused_and_never_cached() -> None:
    """The session is asked first, so a refused venue leaves nothing half
    built behind for the next call to hand out."""
    controls, _, _ = _controls()

    for _attempt in range(2):
        with pytest.raises(_NotServedError):
            controls.get(TradingVenue.DISABLED)
