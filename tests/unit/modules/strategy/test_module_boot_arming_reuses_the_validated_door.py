"""Regression for the `EPIC-027N` PR #287 review's blocking finding.

`StrategyModule._arm_from_config()` used to call `LiveStrategySession.arm()`
directly — a second door past `ArmStrategyCommandHandler`'s validation, wide
open at every process boot. A stale saved config from a Futures run (a
SHORT-capable strategy, still USDT-quoted and at 1x leverage here so only the
SHORT-capability refusal is under test — the other two refusals already have
their own coverage in `test_arm_strategy.py`) would re-arm unchecked at boot
if the venue was later switched to Spot, letting a SHORT signal reach
`LiveTradingCoordinator.handle()`'s unguarded Futures-style sizing path with
zero Spot safety checks anywhere.

The fix routes `_arm_from_config()` through `IStrategyArming` — the same
`ArmStrategyCommand` dispatch every other arming caller already goes
through (`tests/unit/modules/strategy/contracts/test_strategy_arming_contract.
py`'s `_DirectDispatcher` pattern is reused here for the same reason: real
routing by handler class, no engine `IDispatcher` behind it). Revert
`_arm_from_config()` to call `session.arm()` directly and this test fails;
that `boot()` arms each enabled venue through its own arming is
`test_module_restores_each_venues_strategy.py`'s claim (`EPIC-028C`).
"""

from __future__ import annotations

from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.live_strategy_config_store import (
    LiveStrategyConfigStore,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.live_strategy_factory import (
    LiveStrategyFactory,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.live_strategy_session import (
    LiveStrategySession,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.strategy_arming_service import (
    StrategyArmingService,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.strategy_registry import (
    StrategyRegistry,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.venue_strategy_sessions import (
    VenueStrategySessions,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.use_cases.arm_strategy import (
    ArmStrategyCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.live_strategy_config import (
    LiveStrategyConfig,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.domain.strategies.ema_trend_pullback_strategy import (
    EmaTrendPullbackStrategy,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.module import StrategyModule
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_session import (
    TradingSessionSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_trading_session import (
    FakeTradingSession,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_trading_ports import (
    FakeVenueTradingPorts,
    fake_venue_ports,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from sagittarius_engine.infrastructure.config.dict_config import DictConfig

#: SHORT/COVER-capable (`test_supported_directions_guard.py`) — the exact
#: shape of strategy the reviewer's reproduction re-armed unchecked.
_SHORT_CAPABLE_KEY = "ema_trend_confirm_pullback"


class _DirectDispatcher(ICommandDispatcher):
    """Real routing by handler class, no engine `IDispatcher` behind it —
    the same stand-in `test_strategy_arming_contract.py` uses for exactly
    the same reason: what is under test is `StrategyArmingService`'s own
    dispatch, not the engine's routing."""

    def __init__(self, handlers: dict[type, object]) -> None:
        self._handlers = handlers

    def dispatch(self, handler_class: type, input_dto: object | None = None) -> object:
        return self._handlers[handler_class].execute(input_dto)


def test_boot_refuses_a_stale_short_capable_config_on_a_spot_venue() -> None:
    registry = StrategyRegistry()
    registry.register(_SHORT_CAPABLE_KEY, EmaTrendPullbackStrategy)

    trading_session = FakeTradingSession()
    trading_session.answer_with(
        TradingSessionSnapshot(
            enabled=False,
            orders_sent_this_session=0,
            known_open_symbols=(),
            market_type=MarketType.SPOT,
        )
    )
    session = LiveStrategySession(
        LiveStrategyFactory(
            registry,
            Mock(),
            Mock(),
            Mock(),
            Mock(),
            trading_session,
            venue=TradingVenue.FUTURES_TESTNET,
        )
    )
    venue = TradingVenue.SPOT_TESTNET
    config_store = LiveStrategyConfigStore(DictConfig())
    # A config a Futures run could have saved: 1x leverage and a USDT symbol
    # pass the other two Spot-only refusals cleanly, isolating the
    # SHORT-capability one the reviewer's reproduction hit.
    config_store.save(
        venue,
        LiveStrategyConfig(
            strategy_key=_SHORT_CAPABLE_KEY,
            symbol="BTCUSDT",
            interval="1m",
            leverage=1.0,
        ),
    )
    arming = StrategyArmingService(
        _DirectDispatcher(
            {
                ArmStrategyCommandHandler: ArmStrategyCommandHandler(
                    VenueStrategySessions(lambda _venue: session),
                    FakeVenueTradingPorts(
                        fake_venue_ports(venue, trading_session=trading_session)
                    ),
                    config_store,
                ),
            }
        ),
        config_store,
        venue,
    )

    StrategyModule._arm_from_config(config_store, venue, arming)

    assert not session.is_armed, (
        "boot armed a SHORT-capable strategy against a Spot venue — "
        "_arm_from_config() is bypassing ArmStrategyCommandHandler's "
        "Spot-only refusals again (EPIC-027N PR #287 review)"
    )
