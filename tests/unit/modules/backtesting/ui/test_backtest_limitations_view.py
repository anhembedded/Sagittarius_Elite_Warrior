"""Tests for build_backtest_limitations (BOT-081)."""

from dataclasses import replace
from datetime import UTC, datetime

from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.backtest_metrics import (
    BacktestMetrics,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.backtest_result import (
    BacktestResult,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.exchange_filters import (
    ExchangeFilters,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.out_of_sample_validation import (
    OutOfSampleValidation,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.backtest_limitations_view import (
    build_backtest_limitations,
)

_T0 = datetime(2026, 1, 1, tzinfo=UTC)


def _result(out_of_sample: OutOfSampleValidation | None = None) -> BacktestResult:
    return BacktestResult(
        symbol="ETHUSDT",
        initial_balance=1000.0,
        final_balance=1000.0,
        trades=[],
        equity_curve=[],
        metrics=BacktestMetrics.compute([], [], 1000.0),
        out_of_sample=out_of_sample,
    )


def test_always_applicable_limitations_are_present_for_every_run():
    limitations = build_backtest_limitations(_result())

    joined = " ".join(limitations)
    assert "Slippage is a fixed number of ticks" in joined
    assert "network latency" in joined
    assert "orderbook" in joined
    assert "Trading fees" in joined


def test_no_limitation_claims_a_feature_the_engine_already_has():
    """EPIC-027D — slippage (`slippage_ticks`) and Stop Loss / Take Profit
    (BOT-041, BOT-105A/C) ship; a line saying otherwise is false."""
    joined = " ".join(build_backtest_limitations(_result()))

    assert "Does not simulate slippage" not in joined
    assert "No Stop Loss / Take Profit" not in joined


def test_a_static_run_states_the_next_open_fill_and_a_tick_run_does_not():
    static = " ".join(build_backtest_limitations(_result()))
    tick = " ".join(build_backtest_limitations(replace(_result(), committed_bars=[])))

    assert "Running mode: Static" in static
    assert "next candle's open price" in static
    assert "Running mode: Tick replay" in tick
    assert "next candle's open price" not in tick


def test_the_market_simulated_is_stated_with_its_ignored_shorts():
    spot = replace(_result(), market_type=MarketType.SPOT, ignored_short_signals=3)
    futures = replace(_result(), market_type=MarketType.FUTURES_USD_M)

    spot_notes = " ".join(build_backtest_limitations(spot))
    futures_notes = " ".join(build_backtest_limitations(futures))

    assert "Market: Spot" in spot_notes
    assert "(3 this run)" in spot_notes
    assert "Market: Futures (USDⓈ-M)" in futures_notes


def test_the_exchange_filters_are_stated_whether_applied_or_not():
    filters = ExchangeFilters(
        step_size=0.00001, min_quantity=0.00001, min_notional=5.0, tick_size=0.01
    )
    applied = " ".join(
        build_backtest_limitations(replace(_result(), exchange_filters=filters))
    )
    missing = " ".join(build_backtest_limitations(_result()))

    assert "quantity step 0.00001, minimum notional 5.00, tick 0.01" in applied
    assert "No exchange filters applied" in missing


def test_out_of_sample_note_appears_when_the_run_has_no_split():
    limitations = build_backtest_limitations(_result(out_of_sample=None))

    assert any("out-of-sample" in note for note in limitations)


def test_out_of_sample_note_is_absent_when_the_run_has_a_real_split():
    metrics = BacktestMetrics.compute([], [], 1000.0)
    healthy_result = BacktestResult(
        symbol="ETHUSDT",
        initial_balance=1000.0,
        final_balance=1000.0,
        trades=[],
        equity_curve=[],
        metrics=metrics,
    )
    validation = OutOfSampleValidation(
        in_sample=healthy_result,
        out_of_sample=healthy_result,
        in_sample_ratio=0.7,
    )

    limitations = build_backtest_limitations(_result(out_of_sample=validation))

    assert not any("out-of-sample" in note for note in limitations)
