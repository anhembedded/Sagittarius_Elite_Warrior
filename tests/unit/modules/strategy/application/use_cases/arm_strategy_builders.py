"""`EPIC-022B` — what the arm/disarm handler tests build: a real
`LiveStrategySession` over a real registry, the fakes behind the venue's
ports, and the two handlers (`test_arm_strategy.py`,
`test_arm_strategy_session.py`)."""

from __future__ import annotations

from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.live_strategy_session import (
    LiveStrategySession,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.venue_strategy_sessions import (
    VenueStrategySessions,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.use_cases.arm_strategy import (
    ArmStrategyCommand,
    ArmStrategyCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.use_cases.disarm_strategy import (
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
from Sagittarius_Elite_Warrior.tests.unit.modules.strategy.live_config_ports import (
    in_memory_config_store,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.recording_publisher import (
    RecordingPublisher,
)
from sagittarius_engine.infrastructure.config.dict_config import DictConfig

KEY = "ema_crossover"
FUTURES = TradingVenue.FUTURES_TESTNET
SPOT = TradingVenue.SPOT_TESTNET
#: `EPIC-027N` — registered alongside `KEY` so the SHORT-capable-strategy
#: refusal (AC2) has a real strategy that actually calls `self.short()` to
#: test against, not a stand-in that merely claims the capability.
SHORT_CAPABLE_KEY = "ema_trend_confirm_pullback"


def new_session() -> LiveStrategySession:
    """A real `LiveStrategySession` over a real `StrategyRegistry`, with
    only the two network-facing collaborators (`ICommandDispatcher`,
    `ITradingAccountReader`) mocked.

    Deliberately not a `Mock()` session: the parameter-validation path
    under test *is* `BaseStrategy.__init__` raising, and a mock strategy
    accepts every parameter name in existence — the test would pass
    against a handler that validated nothing at all (`ONBOARDING.md` §4,
    the `BUG-013` trap).
    """
    from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.live_strategy_factory import (
        LiveStrategyFactory,
    )
    from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.strategy_registry import (
        StrategyRegistry,
    )

    registry = StrategyRegistry()
    registry.register(KEY, EmaCrossoverStrategy)
    registry.register(SHORT_CAPABLE_KEY, EmaTrendPullbackStrategy)
    factory = LiveStrategyFactory(
        registry,
        Mock(),
        Mock(),
        Mock(),
        Mock(),
        Mock(),
        venue=TradingVenue.FUTURES_TESTNET,
    )
    return LiveStrategySession(factory)


def spot_state(
    spot_baseline_holdings: dict | None = None,
) -> FakeTradingSession:
    """`EPIC-027N` — a `FakeTradingSession` reporting a Spot venue, trading
    closed (so arming runs its own refusals first and the Spot-specific reason
    under test is the one reported)."""
    state = FakeTradingSession()
    state.answer_with(
        TradingSessionSnapshot(
            enabled=False,
            orders_sent_this_session=0,
            known_open_symbols=(),
            market_type=MarketType.SPOT,
            spot_baseline_holdings=spot_baseline_holdings,
        )
    )
    return state


def config_for(**overrides) -> LiveStrategyConfig:
    values = {"strategy_key": KEY, "symbol": "BTCUSDT", "interval": "1m"}
    values.update(overrides)
    return LiveStrategyConfig(**values)


def ports_for(state: FakeTradingSession, venue: TradingVenue) -> FakeVenueTradingPorts:
    """`EPIC-028B` — the one venue a test arms on, with the trading session it
    arranges."""
    return FakeVenueTradingPorts(fake_venue_ports(venue, trading_session=state))


def sessions_of(session: LiveStrategySession) -> VenueStrategySessions:
    return VenueStrategySessions(lambda _venue: session)


def arm_command(config: LiveStrategyConfig) -> ArmStrategyCommand:
    return ArmStrategyCommand(config, venue=FUTURES)


def arm_spot_command(config: LiveStrategyConfig) -> ArmStrategyCommand:
    return ArmStrategyCommand(config, venue=SPOT)


def disarm_handler(
    session: LiveStrategySession,
    state: FakeTradingSession,
    venue: TradingVenue = TradingVenue.FUTURES_TESTNET,
) -> DisarmStrategyCommandHandler:
    parts = (sessions_of(session), ports_for(state, venue))
    return DisarmStrategyCommandHandler(*parts, RecordingPublisher())


def arm_handler(
    session: LiveStrategySession,
    state: FakeTradingSession,
    venue: TradingVenue = TradingVenue.FUTURES_TESTNET,
) -> ArmStrategyCommandHandler:
    """It persists a successful arming itself (PR 4.3m `O6`): a real store
    over the engine's in-memory `IConfig`, never a `Mock`."""
    parts = (sessions_of(session), ports_for(state, venue))
    store = in_memory_config_store(DictConfig())
    return ArmStrategyCommandHandler(*parts, store, RecordingPublisher())
