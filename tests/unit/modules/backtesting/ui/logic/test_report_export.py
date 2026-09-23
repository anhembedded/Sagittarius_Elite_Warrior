"""Tests for `logic/report_export.py` (BOT-115B)."""

from __future__ import annotations

import importlib.metadata
from datetime import UTC, datetime, timedelta

from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
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
    resolve_default_reports_dir,
    resolve_engine_version,
    suggest_report_filename,
    write_backtest_report,
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


def _kline(open_time: datetime, close_time: datetime) -> MarketData:
    return MarketData(
        symbol="BTCUSDT",
        interval=TimeFrame.FIVE_MINUTES.value,
        open_time=open_time,
        open_price=100.0,
        high_price=101.0,
        low_price=99.0,
        close_price=100.5,
        volume=1.0,
        close_time=close_time,
        quote_asset_volume=100.0,
        number_of_trades=1,
        taker_buy_base_asset_volume=0.5,
        taker_buy_quote_asset_volume=50.0,
    )


# ---------------------------------------------------------------------------
# resolve_engine_version
# ---------------------------------------------------------------------------


def test_resolve_engine_version_returns_the_real_installed_version():
    assert resolve_engine_version() == importlib.metadata.version("sagittarius-engine")


def test_resolve_engine_version_falls_back_to_unknown_when_not_installed(
    monkeypatch,
):
    def _raise(_name: str) -> str:
        raise importlib.metadata.PackageNotFoundError

    monkeypatch.setattr(importlib.metadata, "version", _raise)

    assert resolve_engine_version() == "unknown"


# ---------------------------------------------------------------------------
# resolve_default_reports_dir
# ---------------------------------------------------------------------------


def test_resolve_default_reports_dir_falls_back_to_cwd_reports(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    reports_dir = resolve_default_reports_dir(None)

    assert reports_dir == str(tmp_path / "reports")
    assert (tmp_path / "reports").is_dir()


def test_resolve_default_reports_dir_uses_the_configured_dir_when_set(tmp_path):
    configured = tmp_path / "custom_reports"

    reports_dir = resolve_default_reports_dir(str(configured))

    assert reports_dir == str(configured)
    assert configured.is_dir()


# ---------------------------------------------------------------------------
# suggest_report_filename
# ---------------------------------------------------------------------------


def test_suggest_report_filename_includes_symbol_timeframe_strategy_and_timestamp():
    config = _run_config(symbol="ETHUSDT", strategy_key="ema_crossover")

    name = suggest_report_filename(config, datetime(2026, 8, 20, 14, 32, tzinfo=UTC))

    assert name == "ETHUSDT_5m_ema_crossover_20260820_1432.sagi-report.json"


def test_suggest_report_filename_sanitizes_unsafe_characters():
    config = _run_config(strategy_key="my strategy/v2")

    name = suggest_report_filename(config, _T0)

    assert "/" not in name
    assert " " not in name


# ---------------------------------------------------------------------------
# build_backtest_report — data window derivation
# ---------------------------------------------------------------------------


def test_build_backtest_report_data_window_from_committed_bars_when_present():
    config = _run_config(execution_mode=BacktestExecutionMode.HISTORICAL_TICK)
    bars = [
        _kline(_T0, _T0 + timedelta(minutes=5)),
        _kline(_T0 + timedelta(minutes=5), _T0 + timedelta(minutes=10)),
    ]
    result = BacktestResult.compute(
        symbol=config.symbol,
        initial_balance=config.initial_balance,
        final_balance=config.initial_balance,
        trades=[],
        equity_curve=[(_T0, 10_000.0)],
        committed_bars=bars,
    )

    report = build_backtest_report(
        config,
        result,
        app_version="1.0.0",
        engine_version="2.4.0",
        created_at=_T0,
    )

    assert report.provenance.data_window.first_kline_open == bars[0].open_time
    assert report.provenance.data_window.last_kline_close == bars[-1].close_time
    assert report.provenance.data_window.kline_count == 2


def test_build_backtest_report_data_window_from_equity_curve_when_no_committed_bars():
    config = _run_config()
    equity_curve = [
        (_T0, 10_000.0),
        (_T0 + timedelta(minutes=5), 10_010.0),
        (_T0 + timedelta(minutes=10), 10_020.0),
    ]
    result = BacktestResult.compute(
        symbol=config.symbol,
        initial_balance=config.initial_balance,
        final_balance=10_020.0,
        trades=[],
        equity_curve=equity_curve,
    )

    report = build_backtest_report(
        config, result, app_version="1.0.0", engine_version="2.4.0", created_at=_T0
    )

    assert report.provenance.data_window.first_kline_open == equity_curve[0][0]
    assert report.provenance.data_window.last_kline_close == equity_curve[-1][0]
    assert report.provenance.data_window.kline_count == 3


def test_build_backtest_report_data_window_is_honestly_empty_for_an_empty_run():
    config = _run_config()
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

    assert report.provenance.data_window.first_kline_open is None
    assert report.provenance.data_window.last_kline_close is None
    assert report.provenance.data_window.kline_count == 0


def test_build_backtest_report_maps_every_config_field():
    broker_config = BrokerSimulationConfig(commission_value=0.05, long_leverage=3.0)
    sizing = PositionSizing(type=PositionSizingType.FIXED_CASH, value=500.0)
    config = _run_config(
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
        symbol=config.symbol,
        initial_balance=config.initial_balance,
        final_balance=config.initial_balance,
        trades=[_trade()],
        equity_curve=[(_T0, config.initial_balance)],
    )

    report = build_backtest_report(
        config, result, app_version="1.0.0", engine_version="2.4.0", created_at=_T0
    )

    assert report.provenance.strategy_key == config.strategy_key
    assert report.provenance.execution_mode == "HISTORICAL_TICK"
    assert report.config.symbol == "ETHUSDT"
    assert report.config.currency is Currency.USDT
    assert report.config.position_sizing == sizing
    assert report.config.broker_config == broker_config
    assert report.config.strategy_params == {"fast": 9}
    assert report.config.tick_resolution is TimeFrame.ONE_SECOND
    assert report.config.calc_on_order_fills is True
    assert report.result is result


# ---------------------------------------------------------------------------
# write_backtest_report
# ---------------------------------------------------------------------------


def test_write_backtest_report_writes_a_file_that_loads_back(tmp_path):
    config = _run_config()
    result = BacktestResult.compute(
        symbol=config.symbol,
        initial_balance=config.initial_balance,
        final_balance=10_500.0,
        trades=[_trade()],
        equity_curve=[
            (_T0, config.initial_balance),
            (_T0 + timedelta(hours=1), 10_500.0),
        ],
    )
    report = build_backtest_report(
        config, result, app_version="1.0.0", engine_version="2.4.0", created_at=_T0
    )
    path = str(tmp_path / "run.sagi-report.json")

    size_bytes = write_backtest_report(report, path)

    assert size_bytes == (tmp_path / "run.sagi-report.json").stat().st_size
    with open(path, "rb") as report_file:
        loaded = load_backtest_report(
            report_file.read(), valid_strategy_keys={config.strategy_key}
        )
    assert loaded.is_valid
    assert loaded.report.result.trades == result.trades


def test_write_backtest_report_gzips_when_the_path_ends_gz(tmp_path):
    config = _run_config()
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
    gz_path = str(tmp_path / "run.sagi-report.json.gz")

    write_backtest_report(report, gz_path)

    with open(gz_path, "rb") as f:
        magic = f.read(2)
    assert magic == b"\x1f\x8b"
