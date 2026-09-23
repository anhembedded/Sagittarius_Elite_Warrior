"""Tests for `logic/report_import.py` (BOT-115C)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from Sagittarius_Elite_Warrior.src.core.vo.position_sizing import (
    PositionSizing,
    PositionSizingType,
)
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.backtest_report_loader import (
    load_backtest_report,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.backtest_result import (
    BacktestResult,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.broker_simulation_config import (
    BrokerSimulationConfig,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.currency import (
    Currency,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.trade import Trade
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.backtest_fsm_matrix import (
    BacktestExecutionMode,
    BacktestRunConfig,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.report_export import (
    build_backtest_report,
    write_backtest_report,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.report_import import (
    backtest_report_to_run_config,
    build_report_provenance_warning_text,
    read_backtest_report_bytes,
)

_T0 = datetime(2024, 1, 1, tzinfo=UTC)


def _run_config(**overrides) -> BacktestRunConfig:
    defaults = {
        "strategy_key": "ema_crossover",
        "timeframe": TimeFrame.FIVE_MINUTES,
        "initial_balance": 10_000.0,
        "start_time": _T0 - timedelta(days=30),
        "end_time": _T0,
    }
    defaults.update(overrides)
    return BacktestRunConfig(**defaults)


def _trade() -> Trade:
    return Trade(
        symbol="BTCUSDT",
        entry_time=_T0,
        entry_price=100.0,
        exit_time=_T0 + timedelta(hours=1),
        exit_price=110.0,
        quantity=1.0,
        pnl=10.0,
        pnl_percent=1.0,
        fees_paid=0.1,
    )


# ---------------------------------------------------------------------------
# read_backtest_report_bytes
# ---------------------------------------------------------------------------


def test_read_backtest_report_bytes_returns_exactly_what_was_written(tmp_path):
    path = tmp_path / "run.sagi-report.json"
    path.write_bytes(b'{"hello": "world"}')

    assert read_backtest_report_bytes(str(path)) == b'{"hello": "world"}'


# ---------------------------------------------------------------------------
# backtest_report_to_run_config — round-trip through the real export/import
# ---------------------------------------------------------------------------


def test_backtest_report_to_run_config_round_trips_every_field(tmp_path):
    broker_config = BrokerSimulationConfig(commission_value=0.05, long_leverage=3.0)
    sizing = PositionSizing(type=PositionSizingType.FIXED_CASH, value=500.0)
    original = _run_config(
        symbol="ETHUSDT",
        currency=Currency.USDT,
        position_sizing=sizing,
        broker_config=broker_config,
        strategy_params={"fast": 9},
        tick_resolution=TimeFrame.ONE_SECOND,
        calc_on_order_fills=True,
        execution_mode=BacktestExecutionMode.HISTORICAL_TICK,
    )
    result = BacktestResult.compute(
        symbol=original.symbol,
        initial_balance=original.initial_balance,
        final_balance=10_500.0,
        trades=[_trade()],
        equity_curve=[
            (_T0, original.initial_balance),
            (_T0 + timedelta(hours=1), 10_500.0),
        ],
    )
    report = build_backtest_report(
        original, result, app_version="1.0.0", engine_version="2.4.0", created_at=_T0
    )
    path = str(tmp_path / "run.sagi-report.json")
    write_backtest_report(report, path)

    loaded = load_backtest_report(
        read_backtest_report_bytes(path), valid_strategy_keys={original.strategy_key}
    )
    assert loaded.is_valid
    rebuilt = backtest_report_to_run_config(loaded.report)

    assert rebuilt == original


def test_backtest_report_to_run_config_round_trips_a_none_strategy_params(tmp_path):
    original = _run_config(strategy_params=None)
    result = BacktestResult.compute(
        symbol=original.symbol,
        initial_balance=original.initial_balance,
        final_balance=original.initial_balance,
        trades=[],
        equity_curve=[],
    )
    report = build_backtest_report(
        original, result, app_version="1.0.0", engine_version="2.4.0", created_at=_T0
    )
    path = str(tmp_path / "run.sagi-report.json")
    write_backtest_report(report, path)

    loaded = load_backtest_report(
        read_backtest_report_bytes(path), valid_strategy_keys={original.strategy_key}
    )
    rebuilt = backtest_report_to_run_config(loaded.report)

    assert rebuilt.strategy_params is None
    assert rebuilt == original


# ---------------------------------------------------------------------------
# build_report_provenance_warning_text
# ---------------------------------------------------------------------------


def _loaded_report(tmp_path, **overrides):
    config = _run_config(**overrides)
    result = BacktestResult.compute(
        symbol=config.symbol,
        initial_balance=config.initial_balance,
        final_balance=config.initial_balance,
        trades=[],
        equity_curve=[],
    )
    report = build_backtest_report(
        config, result, app_version="1.0.0", engine_version="2.4.0", created_at=_T0
    )
    path = str(tmp_path / "run.sagi-report.json")
    write_backtest_report(report, path)
    return load_backtest_report(
        read_backtest_report_bytes(path), valid_strategy_keys={config.strategy_key}
    )


def test_provenance_warning_is_empty_when_nothing_is_wrong(tmp_path):
    loaded = _loaded_report(tmp_path)

    text = build_report_provenance_warning_text(
        loaded.report,
        strategy_key_unknown=loaded.strategy_key_unknown,
        metrics_mismatch=loaded.metrics_mismatch,
        current_engine_version="2.4.0",
    )

    assert text == ""


def test_provenance_warning_names_a_different_engine_version(tmp_path):
    loaded = _loaded_report(tmp_path)

    text = build_report_provenance_warning_text(
        loaded.report,
        strategy_key_unknown=False,
        metrics_mismatch=False,
        current_engine_version="3.0.0",
    )

    assert "2.4.0" in text
    assert "3.0.0" in text


def test_provenance_warning_names_an_unknown_strategy(tmp_path):
    loaded = _loaded_report(tmp_path, strategy_key="ema_crossover")

    text = build_report_provenance_warning_text(
        loaded.report,
        strategy_key_unknown=True,
        metrics_mismatch=False,
        current_engine_version="2.4.0",
    )

    assert "ema_crossover" in text


def test_provenance_warning_flags_a_metrics_mismatch(tmp_path):
    loaded = _loaded_report(tmp_path)

    text = build_report_provenance_warning_text(
        loaded.report,
        strategy_key_unknown=False,
        metrics_mismatch=True,
        current_engine_version="2.4.0",
    )

    assert "hand" in text or "mismatch" in text.lower() or "edited" in text.lower()


def test_provenance_warning_joins_multiple_notes_with_the_shared_separator(tmp_path):
    loaded = _loaded_report(tmp_path)

    text = build_report_provenance_warning_text(
        loaded.report,
        strategy_key_unknown=True,
        metrics_mismatch=True,
        current_engine_version="3.0.0",
    )

    assert text.count("   •   ") == 2
