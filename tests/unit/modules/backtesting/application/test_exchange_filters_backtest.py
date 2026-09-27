"""EPIC-027C — a real static run obeys the exchange filters it was given, and
its result records them and the entries they refused."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.backtesting.application.run_static_backtest import (
    RunStaticBacktestCommand,
    RunStaticBacktestCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.backtest_result import (
    BacktestResult,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.broker_simulation_config import (
    BrokerSimulationConfig,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.exchange_filters import (
    ExchangeFilters,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_data_repository import (
    FakeMarketDataRepository,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.strategy_engine_factory import (
    StrategyEngineFactory,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.strategy_registry import (
    StrategyRegistry,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.i_sizing_policy import (
    default_sizing_policy,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.domain.strategies.base_strategy import (
    BaseStrategy,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.domain.strategies.strategy_context import (
    StrategyContext,
)

_BASE_TIME = datetime(2024, 1, 1, tzinfo=UTC)
_BTC_SPOT = ExchangeFilters(
    step_size=0.00001, min_quantity=0.00001, min_notional=5.0, tick_size=0.01
)


class _AlwaysToggleStrategy(BaseStrategy):
    """BUY when flat, SELL when long — one round trip every two bars."""

    def build_indicators(self) -> dict:
        return {}

    def decide(self, context: StrategyContext) -> tuple:
        if context.current_position_side is None:
            return self.buy("enter")
        return self.sell("exit")


def _candles(price: float, count: int) -> list[MarketData]:
    span = timedelta(hours=1)
    return [
        MarketData(
            symbol="BTCUSDT",
            interval=TimeFrame.ONE_HOUR.value,
            open_time=_BASE_TIME + index * span,
            open_price=price,
            high_price=price,
            low_price=price,
            close_price=price,
            volume=1.0,
            close_time=_BASE_TIME + (index + 1) * span - timedelta(milliseconds=1),
            quote_asset_volume=price,
            number_of_trades=1,
            taker_buy_base_asset_volume=0.5,
            taker_buy_quote_asset_volume=price * 0.5,
        )
        for index in range(count)
    ]


def _run(initial_balance: float, filters: ExchangeFilters | None) -> BacktestResult:
    registry = StrategyRegistry()
    registry.register("toggle", _AlwaysToggleStrategy)
    handler = RunStaticBacktestCommandHandler(
        repository=FakeMarketDataRepository(
            _candles(33_333.0, 8), market=MarketType.SPOT
        ),
        engine_factory=StrategyEngineFactory(registry, Mock()),
        sizing_policy=default_sizing_policy(),
        event_publisher=Mock(),
    )
    result = handler.execute(
        RunStaticBacktestCommand(
            symbol="BTCUSDT",
            interval=TimeFrame.ONE_HOUR,
            strategy_key="toggle",
            initial_balance=initial_balance,
            fee_percent=0.0,
            broker_config=BrokerSimulationConfig(
                commission_value=0.0,
                market_type=MarketType.SPOT,
                exchange_filters=filters,
            ),
        )
    )
    assert isinstance(result, BacktestResult)
    return result


def test_no_quantity_is_finer_than_the_step_and_the_result_records_the_filters():
    """Business acceptance: a Spot BTCUSDT run with a 0.00001 step produces no
    quantity finer than the step — unrounded, 1,000 USDT at 33,333 would be
    0.0300003… BTC, which LOT_SIZE refuses."""
    result = _run(1_000.0, _BTC_SPOT)

    assert result.trades
    step = Decimal(repr(_BTC_SPOT.step_size))
    assert all(Decimal(repr(trade.quantity)) % step == 0 for trade in result.trades)
    assert result.exchange_filters == _BTC_SPOT
    assert result.rejected_entries == 0


def test_the_same_run_without_filters_trades_the_unrounded_quantity():
    result = _run(1_000.0, None)

    assert result.trades[0].quantity == pytest.approx(1_000.0 / 33_333.0)
    assert result.exchange_filters is None


def test_entries_below_the_minimum_notional_are_counted_and_nothing_trades():
    result = _run(4.0, _BTC_SPOT)

    assert result.trades == []
    assert result.rejected_entries > 0
    assert result.final_balance == pytest.approx(4.0)
