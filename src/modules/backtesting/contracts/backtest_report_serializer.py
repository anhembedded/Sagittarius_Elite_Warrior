"""`BacktestReport` -> plain JSON-safe `dict`/bytes (BOT-115A).

@details The encode half of the schema split in `backtest_report.py`'s own
docstring. `backtest_report_loader.py` is the matching decode half; keep
both in sync field-for-field when either changes.
"""

from __future__ import annotations

import gzip
import json
from dataclasses import asdict
from datetime import datetime
from typing import Any

from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.backtest_metrics import (
    BacktestMetrics,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.backtest_report import (
    BacktestReport,
    BacktestReportConfig,
    BacktestReportProvenance,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.backtest_result import (
    BacktestResult,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.out_of_sample_validation import (
    OutOfSampleValidation,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.trade import Trade


def serialize_backtest_report(report: BacktestReport) -> dict[str, Any]:
    return {
        "schema_version": report.schema_version,
        "provenance": _serialize_provenance(report.provenance),
        "config": _serialize_config(report.config),
        "result": serialize_backtest_result(report.result),
    }


def _serialize_provenance(provenance: BacktestReportProvenance) -> dict[str, Any]:
    return {
        "engine_version": provenance.engine_version,
        "app_version": provenance.app_version,
        "strategy_key": provenance.strategy_key,
        "created_at": provenance.created_at.isoformat(),
        "execution_mode": provenance.execution_mode,
        "data_window": {
            "first_kline_open": _optional_isoformat(
                provenance.data_window.first_kline_open
            ),
            "last_kline_close": _optional_isoformat(
                provenance.data_window.last_kline_close
            ),
            "kline_count": provenance.data_window.kline_count,
        },
    }


def _serialize_config(config: BacktestReportConfig) -> dict[str, Any]:
    return {
        "symbol": config.symbol,
        "timeframe": config.timeframe.value,
        "initial_balance": config.initial_balance,
        "start_time": _optional_isoformat(config.start_time),
        "end_time": _optional_isoformat(config.end_time),
        "strategy_params": dict(config.strategy_params)
        if config.strategy_params is not None
        else None,
        "currency": config.currency.value,
        "position_sizing": {
            "type": config.position_sizing.type.value,
            "value": config.position_sizing.value,
        },
        "broker_config": {
            "slippage_ticks": config.broker_config.slippage_ticks,
            "tick_size": config.broker_config.tick_size,
            "commission_type": config.broker_config.commission_type.value,
            "commission_value": config.broker_config.commission_value,
            "pyramiding": config.broker_config.pyramiding,
            "long_leverage": config.broker_config.long_leverage,
            "short_leverage": config.broker_config.short_leverage,
            "stop_loss_pct": config.broker_config.stop_loss_pct,
            "take_profit_pct": config.broker_config.take_profit_pct,
        },
        "tick_resolution": config.tick_resolution.value,
        "calc_on_order_fills": config.calc_on_order_fills,
    }


def serialize_backtest_result(result: BacktestResult) -> dict[str, Any]:
    """`symbol`/`initial_balance` are deliberately absent — they live on the
    report's own `config` (see `backtest_report.py`'s module docstring),
    which `deserialize_backtest_result` requires back as context."""
    return {
        "final_balance": result.final_balance,
        "metrics": _serialize_metrics(result.metrics),
        "trades": [_serialize_trade(t) for t in result.trades],
        "equity_curve": _serialize_equity_curve(result.equity_curve),
        "out_of_sample": (
            _serialize_out_of_sample(result.out_of_sample)
            if result.out_of_sample is not None
            else None
        ),
    }


def _serialize_out_of_sample(oos: OutOfSampleValidation) -> dict[str, Any]:
    return {
        "in_sample": serialize_backtest_result(oos.in_sample),
        "out_of_sample": serialize_backtest_result(oos.out_of_sample),
        "in_sample_ratio": oos.in_sample_ratio,
    }


def _serialize_metrics(metrics: BacktestMetrics) -> dict[str, Any]:
    return asdict(metrics)


def _serialize_trade(trade: Trade) -> dict[str, Any]:
    return {
        "symbol": trade.symbol,
        "entry_time": trade.entry_time.isoformat(),
        "entry_price": trade.entry_price,
        "exit_time": trade.exit_time.isoformat(),
        "exit_price": trade.exit_price,
        "quantity": trade.quantity,
        "pnl": trade.pnl,
        "pnl_percent": trade.pnl_percent,
        "fees_paid": trade.fees_paid,
        "entry_reason": trade.entry_reason,
        "exit_reason": trade.exit_reason.value,
        "metadata": dict(trade.metadata),
        "side": trade.side.value,
        "leverage": trade.leverage,
        "mae_percent": trade.mae_percent,
        "mfe_percent": trade.mfe_percent,
    }


def _serialize_equity_curve(
    equity_curve: list[tuple[datetime, float]],
) -> dict[str, list[Any]]:
    """Columnar, not a list of `{t, v}` objects — a multi-month 1m run is
    hundreds of thousands of points; columnar is ~3-4x smaller and parses
    faster (task §2's own measured reasoning)."""
    return {
        "t": [t.isoformat() for t, _ in equity_curve],
        "v": [v for _, v in equity_curve],
    }


def _optional_isoformat(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def dump_backtest_report(
    report: BacktestReport, *, gzip_compress: bool = False
) -> bytes:
    payload = json.dumps(serialize_backtest_report(report)).encode("utf-8")
    return gzip.compress(payload) if gzip_compress else payload
