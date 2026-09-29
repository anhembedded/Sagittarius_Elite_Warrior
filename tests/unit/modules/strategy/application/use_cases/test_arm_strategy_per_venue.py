"""`EPIC-028B` — one strategy can be armed per venue at the same time.

@details Both venues are served by the same `VenueStrategySessions` and
`IVenueTradingPorts`, as in the running app: Futures reports a Futures
trading session, Spot a Spot one. Each venue's strategy session is a real
`LiveStrategySession` over a real `StrategyRegistry`, so arming really builds
the strategy and a refusal is the handler's, not a stand-in's.
"""

from __future__ import annotations

from unittest.mock import Mock

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
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.strategy_registry import (
    StrategyRegistry,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.venue_strategy_sessions import (
    VenueStrategySessions,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.use_cases.arm_strategy import (
    ArmStrategyBlockReason,
    ArmStrategyCommand,
    ArmStrategyCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.use_cases.disarm_strategy import (
    DisarmStrategyCommand,
    DisarmStrategyCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.live_strategy_config import (
    LiveStrategyConfig,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.domain.strategies.ema_crossover_strategy import (
    EmaCrossoverStrategy,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.domain.strategies.ema_trend_pullback_strategy import (
    EmaTrendPullbackStrategy,
)
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

_FUTURES = TradingVenue.FUTURES_TESTNET
_SPOT = TradingVenue.SPOT_TESTNET
_LONG_ONLY = "ema_crossover"
_SHORT_CAPABLE = "ema_trend_confirm_pullback"


def _trading_session(market_type: MarketType) -> FakeTradingSession:
    session = FakeTradingSession()
    session.answer_with(
        TradingSessionSnapshot(
            enabled=False,
            orders_sent_this_session=0,
            known_open_symbols=(),
            market_type=market_type,
        )
    )
    return session


def _strategy_session() -> LiveStrategySession:
    registry = StrategyRegistry()
    registry.register(_LONG_ONLY, EmaCrossoverStrategy)
    registry.register(_SHORT_CAPABLE, EmaTrendPullbackStrategy)
    return LiveStrategySession(
        LiveStrategyFactory(registry, Mock(), Mock(), Mock(), Mock(), Mock())
    )


class _Desk:
    """Both venues, with the handlers every venue's screen dispatches to."""

    def __init__(self) -> None:
        by_venue = {_FUTURES: _strategy_session(), _SPOT: _strategy_session()}
        self.sessions = VenueStrategySessions(lambda venue: by_venue[venue])
        ports = FakeVenueTradingPorts(
            fake_venue_ports(
                _FUTURES, trading_session=_trading_session(MarketType.FUTURES_USD_M)
            ),
            fake_venue_ports(_SPOT, trading_session=_trading_session(MarketType.SPOT)),
        )
        self.arm = ArmStrategyCommandHandler(
            self.sessions, ports, LiveStrategyConfigStore(DictConfig())
        )
        self.disarm = DisarmStrategyCommandHandler(self.sessions, ports)


def _config(key: str, symbol: str) -> LiveStrategyConfig:
    return LiveStrategyConfig(strategy_key=key, symbol=symbol, interval="1m")


def test_each_venue_arms_its_own_strategy_at_the_same_time() -> None:
    desk = _Desk()

    futures = desk.arm.execute(
        ArmStrategyCommand(_config(_SHORT_CAPABLE, "BTCUSDT"), venue=_FUTURES)
    )
    spot = desk.arm.execute(
        ArmStrategyCommand(_config(_LONG_ONLY, "ETHUSDT"), venue=_SPOT)
    )

    assert futures.armed and spot.armed
    futures_config = desk.sessions.get(_FUTURES).config
    spot_config = desk.sessions.get(_SPOT).config
    assert futures_config is not None and futures_config.strategy_key == _SHORT_CAPABLE
    assert spot_config is not None and spot_config.strategy_key == _LONG_ONLY


def test_spot_still_refuses_a_short_capable_strategy_that_futures_accepts() -> None:
    desk = _Desk()
    config = _config(_SHORT_CAPABLE, "BTCUSDT")

    on_spot = desk.arm.execute(ArmStrategyCommand(config, venue=_SPOT))
    on_futures = desk.arm.execute(ArmStrategyCommand(config, venue=_FUTURES))

    assert on_spot.block_reason is ArmStrategyBlockReason.SPOT_SHORT_NOT_SUPPORTED
    assert on_futures.armed is True
    assert desk.sessions.get(_SPOT).is_armed is False


def test_disarming_one_venue_leaves_the_other_armed() -> None:
    desk = _Desk()
    desk.arm.execute(ArmStrategyCommand(_config(_LONG_ONLY, "BTCUSDT"), venue=_FUTURES))
    desk.arm.execute(ArmStrategyCommand(_config(_LONG_ONLY, "ETHUSDT"), venue=_SPOT))

    result = desk.disarm.execute(DisarmStrategyCommand(venue=_SPOT))

    assert result.disarmed is True
    assert desk.sessions.get(_SPOT).is_armed is False
    assert desk.sessions.get(_FUTURES).is_armed is True
