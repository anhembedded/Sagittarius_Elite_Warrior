"""`EPIC-028K` — a live strategy's signals carry the venue it was built for.

@details Built through `LiveStrategyFactory.build()` over a real
`StrategyRegistry` and a real strategy, so the venue has to travel the whole
way: factory -> `build_engine` -> `StrategyEngine`. A reader tells one
venue's signals from another's by that field, so a factory that dropped the
venue would publish signals no venue claims.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.core.contracts.i_event_publisher import (
    IEventPublisher,
)
from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.live_strategy_factory import (
    LiveStrategyFactory,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.strategy_registry import (
    StrategyRegistry,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.live_strategy_config import (
    LiveStrategyConfig,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.domain.strategies.ema_crossover_strategy import (
    EmaCrossoverStrategy,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.signal_generated_event import (
    SignalGeneratedEvent,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from sagittarius_engine.domain.i_domain_event import IDomainEvent

_KEY = "ema_crossover"
#: A fall then a rally: the fast EMA crosses the slow one upward once.
_CLOSES = [100.0 - 2 * i for i in range(10)] + [82.0 + 3 * i for i in range(10)]


class _RecordingPublisher(IEventPublisher):
    def __init__(self) -> None:
        self.signals: list[SignalGeneratedEvent] = []

    def publish(self, event: IDomainEvent) -> None:
        if isinstance(event, SignalGeneratedEvent):
            self.signals.append(event)


def _candles() -> list[MarketData]:
    start = datetime(2026, 9, 1, tzinfo=UTC)
    return [
        MarketData(
            symbol="BTCUSDT",
            interval=TimeFrame.ONE_MINUTE.value,
            open_time=start + timedelta(minutes=i),
            open_price=close,
            high_price=close,
            low_price=close,
            close_price=close,
            volume=1.0,
            close_time=start + timedelta(minutes=i + 1),
            quote_asset_volume=close,
            number_of_trades=1,
            taker_buy_base_asset_volume=0.5,
            taker_buy_quote_asset_volume=close / 2,
        )
        for i, close in enumerate(_CLOSES)
    ]


def test_the_factorys_engine_publishes_signals_for_its_own_venue() -> None:
    registry = StrategyRegistry()
    registry.register(_KEY, EmaCrossoverStrategy)
    publisher = _RecordingPublisher()
    factory = LiveStrategyFactory(
        registry,
        publisher,
        Mock(),
        Mock(),
        Mock(),
        Mock(),
        venue=TradingVenue.SPOT_TESTNET,
    )
    engine, _coordinator = factory.build(
        LiveStrategyConfig(
            strategy_key=_KEY,
            symbol="BTCUSDT",
            interval="1m",
            strategy_params={"fast_period": 2, "slow_period": 4},
        )
    )

    for candle in _candles():
        engine.on_tick(candle)

    assert publisher.signals, "the series was chosen to cross once"
    assert {event.venue for event in publisher.signals} == {TradingVenue.SPOT_TESTNET}
