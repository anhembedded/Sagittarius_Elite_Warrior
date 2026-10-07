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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.armed_strategy_changed_event import (
    ArmedStrategyChangedEvent,
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
from Sagittarius_Elite_Warrior.tests.unit.modules.strategy.live_config_ports import (
    in_memory_config_store,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.recording_publisher import (
    RecordingPublisher,
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


def _strategy_session(venue: TradingVenue) -> LiveStrategySession:
    registry = StrategyRegistry()
    registry.register(_LONG_ONLY, EmaCrossoverStrategy)
    registry.register(_SHORT_CAPABLE, EmaTrendPullbackStrategy)
    return LiveStrategySession(
        LiveStrategyFactory(
            registry,
            Mock(),
            Mock(),
            Mock(),
            Mock(),
            Mock(),
            venue=venue,
        )
    )


class _Desk:
    """Both venues, with the handlers every venue's screen dispatches to."""

    def __init__(self) -> None:
        by_venue = {
            _FUTURES: _strategy_session(_FUTURES),
            _SPOT: _strategy_session(_SPOT),
        }
        self.sessions = VenueStrategySessions(lambda venue: by_venue[venue])
        self.trading = {
            _FUTURES: _trading_session(MarketType.FUTURES_USD_M),
            _SPOT: _trading_session(MarketType.SPOT),
        }
        ports = FakeVenueTradingPorts(
            *(
                fake_venue_ports(venue, trading_session=session)
                for venue, session in self.trading.items()
            )
        )
        self.published = RecordingPublisher()
        self.arm = ArmStrategyCommandHandler(
            self.sessions,
            ports,
            in_memory_config_store(DictConfig()),
            self.published,
        )
        self.disarm = DisarmStrategyCommandHandler(self.sessions, ports, self.published)


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


def _open_position(desk: _Desk, venue: TradingVenue, symbol: str) -> None:
    """The venue's session open, with a position the app opened on `symbol`."""
    desk.trading[venue].answer_with(
        TradingSessionSnapshot(
            enabled=True,
            orders_sent_this_session=1,
            known_open_symbols=(symbol,),
            market_type=MarketType.FUTURES_USD_M,
        )
    )


def _changes(desk: _Desk) -> list[tuple[TradingVenue, bool]]:
    return [
        (event.venue, event.armed)
        for event in desk.published.of_type(ArmedStrategyChangedEvent)
    ]


def test_an_arm_and_a_disarm_each_say_which_venue_changed() -> None:
    """`EPIC-033K` stage 3: the Trade mode's chart draws its venue's armed
    strategy, which the Bots mode arms; it hears of each change here."""
    desk = _Desk()

    desk.arm.execute(ArmStrategyCommand(_config(_LONG_ONLY, "ETHUSDT"), venue=_SPOT))
    desk.disarm.execute(DisarmStrategyCommand(venue=_SPOT))

    assert _changes(desk) == [(_SPOT, True), (_SPOT, False)]


def test_a_refused_arm_or_disarm_says_nothing_changed() -> None:
    desk = _Desk()

    refused = desk.arm.execute(
        ArmStrategyCommand(_config(_SHORT_CAPABLE, "BTCUSDT"), venue=_SPOT)
    )
    armed = desk.arm.execute(
        ArmStrategyCommand(_config(_LONG_ONLY, "BTCUSDT"), venue=_FUTURES)
    )
    _open_position(desk, _FUTURES, "BTCUSDT")
    blocked = desk.disarm.execute(DisarmStrategyCommand(venue=_FUTURES))

    assert refused.armed is False and armed.armed is True
    assert blocked.disarmed is False
    assert _changes(desk) == [(_FUTURES, True)]
