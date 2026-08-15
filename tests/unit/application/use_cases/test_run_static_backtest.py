"""Tests for RunStaticBacktestCommandHandler (BOT-021)."""

from datetime import UTC, datetime, timedelta
from typing import ClassVar
from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.application.services.strategy_registry import (
    StrategyRegistry,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.backtest.run_static_backtest import (
    RunStaticBacktestCommand,
    RunStaticBacktestCommandHandler,
)
from Sagittarius_Elite_Warrior.src.domain.backtesting.backtest_result import (
    BacktestResult,
)
from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.domain.events.backtest_completed_event import (
    BacktestCompletedEvent,
)
from Sagittarius_Elite_Warrior.src.domain.events.backtest_failed_event import (
    BacktestFailedEvent,
)
from Sagittarius_Elite_Warrior.src.domain.strategies.base_strategy import BaseStrategy
from Sagittarius_Elite_Warrior.src.domain.strategies.strategy_context import (
    StrategyContext,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.signal_action import (
    SignalAction,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame


class _ScriptedStrategy(BaseStrategy):
    """Test-only strategy that ignores indicators (`build_indicators()` is
    empty, so `StrategyEngine` calls `decide()` on every bar with no
    warm-up) and returns a scripted action by call index — lets the handler
    test pin exact fill timing without depending on any real indicator's
    warm-up length."""

    ACTIONS: ClassVar[dict[int, SignalAction]] = {
        2: SignalAction.BUY,
        5: SignalAction.SELL,
    }

    def setup(self) -> None:
        self._call_index = 0

    def build_indicators(self) -> dict:
        return {}

    def decide(self, context: StrategyContext) -> tuple[SignalAction, str]:
        action = self.ACTIONS.get(self._call_index, SignalAction.HOLD)
        self._call_index += 1
        if action is SignalAction.BUY:
            return self.buy("scripted buy")
        if action is SignalAction.SELL:
            return self.sell("scripted sell")
        return self.hold()


def _build_candle(index: int, open_price: float, close_price: float) -> MarketData:
    open_time = datetime(2024, 1, 1, tzinfo=UTC) + timedelta(hours=index)
    return MarketData(
        symbol="BTCUSDT",
        interval=TimeFrame.ONE_HOUR.value,
        open_time=open_time,
        open_price=open_price,
        high_price=max(open_price, close_price),
        low_price=min(open_price, close_price),
        close_price=close_price,
        volume=10.0,
        close_time=open_time + timedelta(hours=1),
        quote_asset_volume=1000.0,
        number_of_trades=5,
        taker_buy_base_asset_volume=5.0,
        taker_buy_quote_asset_volume=500.0,
    )


def _build_klines() -> list[MarketData]:
    # 8 candles; the scripted strategy signals BUY at index 2 and SELL at
    # index 5 (0-based decide() call order == candle order). The handler
    # must fill each at the *next* candle's open, never the signal bar's own
    # price.
    opens_closes = [
        (100.0, 105.0),
        (110.0, 115.0),
        (120.0, 125.0),  # BUY signal generated here
        (130.0, 135.0),  # -> filled here, at open=130
        (140.0, 145.0),
        (150.0, 155.0),  # SELL signal generated here
        (160.0, 165.0),  # -> filled here, at open=160
        (170.0, 175.0),
    ]
    return [
        _build_candle(i, open_price, close_price)
        for i, (open_price, close_price) in enumerate(opens_closes)
    ]


def _build_handler(
    klines: list[MarketData],
) -> tuple[RunStaticBacktestCommandHandler, Mock]:
    repo = Mock()
    repo.get_klines.return_value = klines
    registry = StrategyRegistry()
    registry.register("scripted", _ScriptedStrategy)
    event_bus = Mock()
    handler = RunStaticBacktestCommandHandler(
        repository=repo, strategy_registry=registry, event_bus=event_bus
    )
    return handler, event_bus


def test_fills_happen_at_the_next_bars_open_not_the_signal_bar():
    klines = _build_klines()
    handler, _ = _build_handler(klines)
    command = RunStaticBacktestCommand(
        symbol="BTCUSDT",
        interval=TimeFrame.ONE_HOUR,
        strategy_key="scripted",
        initial_balance=1000.0,
        fee_percent=0.0,
    )

    result = handler.execute(command)

    assert isinstance(result, BacktestResult)
    assert len(result.trades) == 1
    trade = result.trades[0]
    assert (
        trade.entry_price == 130.0
    )  # open of candle index 3, not 125 (signal bar close)
    assert trade.exit_price == 160.0  # open of candle index 6, not 155
    assert result.metrics.total_closed_trades == 1


def test_equity_curve_has_one_point_per_candle():
    klines = _build_klines()
    handler, _ = _build_handler(klines)
    command = RunStaticBacktestCommand(
        symbol="BTCUSDT", interval=TimeFrame.ONE_HOUR, strategy_key="scripted"
    )

    result = handler.execute(command)

    assert len(result.equity_curve) == len(klines)
    assert [t for t, _ in result.equity_curve] == [k.close_time for k in klines]


def test_emits_backtest_completed_event_with_the_returned_result():
    """StrategyEngine also emits SignalGeneratedEvent on the same bus for
    each actionable signal — this only checks the BacktestCompletedEvent
    among whatever else was emitted, not that it was the sole event."""
    klines = _build_klines()
    handler, event_bus = _build_handler(klines)
    command = RunStaticBacktestCommand(
        symbol="BTCUSDT", interval=TimeFrame.ONE_HOUR, strategy_key="scripted"
    )

    result = handler.execute(command)

    completed_events = [
        call.args[0]
        for call in event_bus.emit.call_args_list
        if isinstance(call.args[0], BacktestCompletedEvent)
    ]
    assert len(completed_events) == 1
    assert completed_events[0].result == result


def test_no_historical_data_emits_failed_event_and_returns_none():
    handler, event_bus = _build_handler(klines=[])
    command = RunStaticBacktestCommand(
        symbol="BTCUSDT", interval=TimeFrame.ONE_HOUR, strategy_key="scripted"
    )

    result = handler.execute(command)

    assert result is None
    event_bus.emit.assert_called_once()
    (emitted_event,), _ = event_bus.emit.call_args
    assert isinstance(emitted_event, BacktestFailedEvent)


def test_a_signal_on_the_last_bar_is_never_filled():
    """No future bar exists to fill it at — the order stays pending forever,
    same as it would in reality."""
    klines = _build_klines()[:3]  # ends right on the BUY signal bar (index 2)
    handler, _ = _build_handler(klines)
    command = RunStaticBacktestCommand(
        symbol="BTCUSDT", interval=TimeFrame.ONE_HOUR, strategy_key="scripted"
    )

    result = handler.execute(command)

    assert result.trades == []
    assert result.final_balance == command.initial_balance


# =========================================================================
# BOT-080: mandatory in-sample/out-of-sample validation on every run
# =========================================================================


def test_populates_out_of_sample_validation_when_the_range_can_be_split():
    klines = _build_klines()  # 8 candles
    handler, _ = _build_handler(klines)
    command = RunStaticBacktestCommand(
        symbol="BTCUSDT", interval=TimeFrame.ONE_HOUR, strategy_key="scripted"
    )

    result = handler.execute(command)

    assert result.out_of_sample is not None
    assert result.out_of_sample.in_sample_ratio == 0.7
    # 8 candles * 0.7 = 5.6 -> rounds to 6 in-sample, 2 out-of-sample; each
    # side is its own independent BacktestResult with 1 equity point/candle.
    assert len(result.out_of_sample.in_sample.equity_curve) == 6
    assert len(result.out_of_sample.out_of_sample.equity_curve) == 2
    # The full-range result (stat cards/chart/trade log) is untouched by
    # this — still all 8 candles, per the user's explicit decision that the
    # primary result stays full-range.
    assert len(result.equity_curve) == 8


def test_out_of_sample_is_none_when_the_range_is_too_short_to_split():
    klines = _build_klines()[:1]  # 1 candle -> round(1*0.7)=1 in-sample, 0 out
    handler, _ = _build_handler(klines)
    command = RunStaticBacktestCommand(
        symbol="BTCUSDT", interval=TimeFrame.ONE_HOUR, strategy_key="scripted"
    )

    result = handler.execute(command)

    assert result.out_of_sample is None


def test_in_sample_and_out_of_sample_are_simulated_independently_of_the_full_range():
    """Each split gets its OWN fresh strategy/exchange (BOT-080 §5's
    explicit constraint: "mỗi đoạn train/test là một BacktestResult độc
    lập") — the scripted strategy's call-index-based signals fire relative
    to each slice's own start, not the full range's."""
    klines = _build_klines()  # 8 candles
    handler, _ = _build_handler(klines)
    command = RunStaticBacktestCommand(
        symbol="BTCUSDT", interval=TimeFrame.ONE_HOUR, strategy_key="scripted"
    )

    result = handler.execute(command)

    # In-sample slice = first 6 candles: BUY fires at call-index 2 (filled at
    # candle 3's open, still within the slice), SELL fires at call-index 5
    # (the slice's own LAST candle) -> never filled within the slice, so the
    # open position gets force-closed at the slice's last close instead.
    in_sample_trades = result.out_of_sample.in_sample.trades
    assert len(in_sample_trades) == 1
    assert in_sample_trades[0].entry_price == 130.0  # candle 3's open
    assert in_sample_trades[0].exit_price == 155.0  # candle 5's close (force-closed)

    # Out-of-sample slice = last 2 candles: a fresh strategy instance's call
    # index restarts at 0, so neither of the scripted signals (indices 2/5)
    # ever fires.
    assert result.out_of_sample.out_of_sample.trades == []
