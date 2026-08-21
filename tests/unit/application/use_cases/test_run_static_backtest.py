"""Tests for RunStaticBacktestCommandHandler (BOT-021)."""

from datetime import UTC, datetime, timedelta
from typing import ClassVar
from unittest.mock import Mock

import pytest

from Sagittarius_Elite_Warrior.src.application.services.strategy_registry import (
    StrategyRegistry,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.backtest.run_static_backtest import (
    BacktestCancelled,
    RunStaticBacktestCommand,
    RunStaticBacktestCommandHandler,
)
from Sagittarius_Elite_Warrior.src.domain.backtesting.backtest_result import (
    BacktestResult,
)
from Sagittarius_Elite_Warrior.src.domain.backtesting.exit_reason import ExitReason
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
from Sagittarius_Elite_Warrior.src.domain.value_objects.broker_simulation_config import (
    BrokerSimulationConfig,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.position_side import (
    PositionSide,
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


def _configure_repo_with_klines(repo: Mock, klines: list[MarketData]) -> None:
    """
    @brief Makes a `Mock` stand in for `IMarketDataRepository`'s streaming
    contract (BUG-025) — `count_klines()`/`stream_klines()` mirror exactly
    what a real repository would report for the given static `klines` list,
    the same way the old tests configured `get_klines.return_value` before
    the handler moved off it.
    """

    def _count(
        *, symbol=None, interval=None, start_time=None, end_time=None, limit=None
    ) -> int:
        return len(klines) if limit is None else min(limit, len(klines))

    def _stream(
        *,
        symbol=None,
        interval=None,
        start_time=None,
        end_time=None,
        offset=None,
        limit=None,
        order_by_desc=False,
    ):
        rows = klines[offset:] if offset is not None else klines
        rows = rows[:limit] if limit is not None else rows
        return iter(rows)

    repo.count_klines.side_effect = _count
    repo.stream_klines.side_effect = _stream


def _build_handler(
    klines: list[MarketData],
) -> tuple[RunStaticBacktestCommandHandler, Mock]:
    repo = Mock()
    _configure_repo_with_klines(repo, klines)
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


# =========================================================================
# BOT-095C: cooperative cancellation and progress are business outcomes
# =========================================================================


def test_cancellation_during_out_of_sample_returns_explicit_outcome_without_event():
    """Regression for a dangerous false-positive: partial validation must
    never be labelled a completed backtest or emitted as one."""
    handler, event_bus = _build_handler(_build_klines())
    checks = 0

    def cancellation_requested() -> bool:
        nonlocal checks
        checks += 1
        # The 8-bar range splits to 6 in-sample / 2 out-of-sample. Cancel
        # at the first out-of-sample candle, after the in-sample pass ends.
        return checks >= 7

    result = handler.execute(
        RunStaticBacktestCommand(
            symbol="BTCUSDT",
            interval=TimeFrame.ONE_HOUR,
            strategy_key="scripted",
            cancellation_requested=cancellation_requested,
        )
    )

    assert isinstance(result, BacktestCancelled)
    assert result.phase == "out_of_sample"
    assert result.processed_bars == 6
    assert not any(
        isinstance(call.args[0], BacktestCompletedEvent)
        for call in event_bus.emit.call_args_list
    )


def test_progress_is_coalesced_and_reaches_full_range_completion():
    handler, _ = _build_handler(_build_klines())
    updates: list[tuple[str, int, int, float]] = []
    result = handler.execute(
        RunStaticBacktestCommand(
            symbol="BTCUSDT",
            interval=TimeFrame.ONE_HOUR,
            strategy_key="scripted",
            progress_callback=lambda phase, done, total, elapsed: updates.append(
                (phase, done, total, elapsed)
            ),
        )
    )

    assert isinstance(result, BacktestResult)
    assert updates[-1][0] == "full"
    assert updates[-1][1:][0:2] == (16, 16)
    # A callback per candle would flood the Qt event queue on long histories;
    # this 16-unit fixture emits only phase-start/phase-end updates.
    assert len(updates) == 6


# =========================================================================
# BOT-041: Stop-Loss must be checked every bar, not only on signal bars
# =========================================================================


class _BuyOnceThenHoldStrategy(BaseStrategy):
    """BUYs on its 2nd `decide()` call, then HOLDs forever — never emits a
    SELL. Proves a stop-loss can close the position on its own, with no
    strategy signal anywhere near the closing bar."""

    def setup(self) -> None:
        self._call_index = 0

    def build_indicators(self) -> dict:
        return {}

    def decide(self, context: StrategyContext) -> tuple[SignalAction, str]:
        call_index = self._call_index
        self._call_index += 1
        if call_index == 1:
            return self.buy("scripted buy")
        return self.hold()


def _build_stop_loss_klines() -> list[MarketData]:
    # BUY signal fires at call-index 1 (candle 1) -> filled at candle 2's
    # open (100.0). Stop-loss 5% below entry = 95.0.
    # Candle 2's own low (98.0) stays above the stop — no same-bar trigger.
    # Candles 3-4 stay above it too. Candle 5's low (90.0) breaches it, with
    # the strategy never having emitted another signal anywhere in between.
    opens_closes_highs_lows = [
        (100.0, 100.0, 101.0, 99.0),  # 0: HOLD
        (100.0, 100.0, 101.0, 99.0),  # 1: BUY signal generated here
        (100.0, 102.0, 103.0, 98.0),  # 2: filled at open=100.0; SL=95.0
        (102.0, 103.0, 104.0, 101.0),  # 3: still above SL
        (103.0, 104.0, 105.0, 102.0),  # 4: still above SL
        (104.0, 93.0, 104.5, 90.0),  # 5: low=90.0 breaches SL=95.0
        (93.0, 94.0, 95.0, 92.0),  # 6: irrelevant, position already closed
    ]
    return [
        MarketData(
            symbol="BTCUSDT",
            interval=TimeFrame.ONE_HOUR.value,
            open_time=datetime(2024, 1, 1, tzinfo=UTC) + timedelta(hours=i),
            open_price=o,
            high_price=h,
            low_price=low,
            close_price=c,
            volume=10.0,
            close_time=datetime(2024, 1, 1, tzinfo=UTC) + timedelta(hours=i + 1),
            quote_asset_volume=1000.0,
            number_of_trades=5,
            taker_buy_base_asset_volume=5.0,
            taker_buy_quote_asset_volume=500.0,
        )
        for i, (o, c, h, low) in enumerate(opens_closes_highs_lows)
    ]


def test_stop_loss_closes_the_position_on_a_bar_with_no_strategy_signal():
    klines = _build_stop_loss_klines()
    repo = Mock()
    _configure_repo_with_klines(repo, klines)
    registry = StrategyRegistry()
    registry.register("buy_once_hold", _BuyOnceThenHoldStrategy)
    handler = RunStaticBacktestCommandHandler(
        repository=repo, strategy_registry=registry, event_bus=Mock()
    )
    command = RunStaticBacktestCommand(
        symbol="BTCUSDT",
        interval=TimeFrame.ONE_HOUR,
        strategy_key="buy_once_hold",
        initial_balance=1_000.0,
        fee_percent=0.0,
        broker_config=BrokerSimulationConfig(commission_value=0.0, stop_loss_pct=5.0),
    )

    result = handler.execute(command)

    assert isinstance(result, BacktestResult)
    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.entry_price == pytest.approx(100.0)
    assert trade.exit_reason is ExitReason.STOP_LOSS
    assert trade.exit_price == pytest.approx(95.0)


# =========================================================================
# BOT-050: Short-selling flows end-to-end through the real handler/engine
# =========================================================================


class _ShortOnceThenCoverStrategy(BaseStrategy):
    """SHORTs on its 2nd `decide()` call, COVERs on its 5th — the
    short-selling mirror of `_ScriptedStrategy`, proving `SignalAction.
    SHORT`/`COVER` reach `PaperExchange` correctly through the real
    `StrategyEngine`/handler chain, not just a direct `PaperExchange.fill()`
    unit test."""

    ACTIONS: ClassVar[dict[int, SignalAction]] = {
        1: SignalAction.SHORT,
        4: SignalAction.COVER,
    }

    def setup(self) -> None:
        self._call_index = 0

    def build_indicators(self) -> dict:
        return {}

    def decide(self, context: StrategyContext) -> tuple[SignalAction, str]:
        action = self.ACTIONS.get(self._call_index, SignalAction.HOLD)
        self._call_index += 1
        if action is SignalAction.SHORT:
            return self.short("scripted short")
        if action is SignalAction.COVER:
            return self.cover("scripted cover")
        return self.hold()


def _build_short_klines() -> list[MarketData]:
    # SHORT signal fires at call-index 1 (candle 1) -> filled at candle 2's
    # open (130.0). COVER fires at call-index 4 (candle 4) -> filled at
    # candle 5's open (100.0, price dropped -> the short wins).
    opens_closes = [
        (100.0, 105.0),
        (110.0, 115.0),  # SHORT signal generated here
        (130.0, 125.0),  # -> filled here, at open=130 (entry)
        (120.0, 115.0),
        (110.0, 105.0),  # COVER signal generated here
        (100.0, 95.0),  # -> filled here, at open=100 (exit)
        (90.0, 85.0),
    ]
    return [
        _build_candle(i, open_price, close_price)
        for i, (open_price, close_price) in enumerate(opens_closes)
    ]


def test_short_and_cover_signals_flow_through_the_real_handler_and_engine():
    klines = _build_short_klines()
    repo = Mock()
    _configure_repo_with_klines(repo, klines)
    registry = StrategyRegistry()
    registry.register("short_once", _ShortOnceThenCoverStrategy)
    handler = RunStaticBacktestCommandHandler(
        repository=repo, strategy_registry=registry, event_bus=Mock()
    )
    command = RunStaticBacktestCommand(
        symbol="BTCUSDT",
        interval=TimeFrame.ONE_HOUR,
        strategy_key="short_once",
        initial_balance=1000.0,
        fee_percent=0.0,
    )

    result = handler.execute(command)

    assert isinstance(result, BacktestResult)
    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.side is PositionSide.SHORT
    assert trade.entry_price == pytest.approx(130.0)
    assert trade.exit_price == pytest.approx(100.0)
    # qty = 1000/130 (all-in, no fee); pnl = (130-100)*qty
    assert trade.pnl == pytest.approx((1000.0 / 130.0) * 30.0)
    assert trade.pnl > 0  # price dropped after entry -> the short won
