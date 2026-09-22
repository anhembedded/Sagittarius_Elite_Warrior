"""`BOT-115B` — building, naming and writing a `BacktestReport` for the
"Save report" button on the Backtest screen.

@details Pure functions plus the one file write, kept out of
`backtest_presenter.py` the same way `trade_log_export.py` keeps CSV export
out of it — I/O lives in `logic/`, the Presenter only decides *when* to call
it (mirrors `export_trades_to_csv`'s own precedent exactly).
"""

from __future__ import annotations

import importlib.metadata
import os
import re
from datetime import datetime

from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.backtest_report import (
    BacktestReport,
    BacktestReportConfig,
    BacktestReportProvenance,
    DataWindow,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.backtest_report_serializer import (
    dump_backtest_report,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.backtest_result import (
    BacktestResult,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.backtest_fsm_matrix import (
    BacktestRunConfig,
)

#: Where "Save report" writes by default when `ConfigKeys.BACKTEST_REPORTS_DIR`
#: says nothing — `./reports` relative to the working directory, the same
#: `config.get(...) or <cwd>/<name>` shape `DATABASE_DIR` already uses.
DEFAULT_REPORTS_DIR_NAME = "reports"

#: The distribution name `sagittarius_engine` installs under — used to read
#: its real installed version rather than inventing a second "engine
#: version" concept nothing else in this app tracks.
_ENGINE_DISTRIBUTION_NAME = "sagittarius-engine"
_UNKNOWN_VERSION = "unknown"

_UNSAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9_.-]+")


def resolve_engine_version() -> str:
    """The installed `sagittarius-engine` package version, or `"unknown"`
    when it can't be determined (e.g. an editable/unpackaged dev checkout) —
    never raises, since a report's provenance being incomplete is far better
    than "Save report" crashing over it."""
    try:
        return importlib.metadata.version(_ENGINE_DISTRIBUTION_NAME)
    except importlib.metadata.PackageNotFoundError:
        return _UNKNOWN_VERSION


def resolve_default_reports_dir(configured_dir: str | None) -> str:
    """`configured_dir` is `IConfig.get(ConfigKeys.BACKTEST_REPORTS_DIR.value)`
    — falsy (unset) falls back to `<cwd>/reports`, created if missing so the
    file dialog always opens somewhere real."""
    reports_dir = configured_dir or os.path.join(os.getcwd(), DEFAULT_REPORTS_DIR_NAME)
    os.makedirs(reports_dir, exist_ok=True)
    return reports_dir


def suggest_report_filename(run_config: BacktestRunConfig, created_at: datetime) -> str:
    """e.g. `ETHUSDT_5m_ema_crossover_20260820_1432.sagi-report.json` — every
    character from the run's own identity, sanitized for the filesystem
    rather than assumed safe (a strategy key or symbol is app data, not
    something this function should trust blindly)."""
    stamp = created_at.strftime("%Y%m%d_%H%M")
    raw = (
        f"{run_config.symbol}_{run_config.timeframe.value}_"
        f"{run_config.strategy_key}_{stamp}"
    )
    safe = _UNSAFE_FILENAME_CHARS.sub("_", raw)
    return f"{safe}.sagi-report.json"


def build_backtest_report(
    run_config: BacktestRunConfig,
    result: BacktestResult,
    *,
    app_version: str,
    engine_version: str,
    created_at: datetime,
) -> BacktestReport:
    """Maps one completed run's `BacktestRunConfig`/`BacktestResult` to the
    persisted `BacktestReport` shape (`BOT-115A`)."""
    first_open, last_close, kline_count = _data_window(result)
    return BacktestReport(
        provenance=BacktestReportProvenance(
            engine_version=engine_version,
            app_version=app_version,
            strategy_key=run_config.strategy_key,
            created_at=created_at,
            execution_mode=run_config.execution_mode.value,
            data_window=DataWindow(
                first_kline_open=first_open,
                last_kline_close=last_close,
                kline_count=kline_count,
            ),
        ),
        config=BacktestReportConfig(
            symbol=run_config.symbol,
            timeframe=run_config.timeframe,
            initial_balance=run_config.initial_balance,
            start_time=run_config.start_time,
            end_time=run_config.end_time,
            strategy_params=run_config.strategy_params,
            currency=run_config.currency,
            position_sizing=run_config.position_sizing,
            broker_config=run_config.broker_config,
            tick_resolution=run_config.tick_resolution,
            calc_on_order_fills=run_config.calc_on_order_fills,
        ),
        result=result,
    )


def _data_window(
    result: BacktestResult,
) -> tuple[datetime | None, datetime | None, int]:
    """`committed_bars` (Realtime, `BOT-076`) is the real klines the run
    evaluated; Static leaves it `None` (its own docstring: "read straight
    from storage"), so `equity_curve` — exactly one point per bar for that
    mode — stands in instead. An empty run (no data at all) reports
    `None`/`None`/`0`, an honest empty window rather than a guess."""
    if result.committed_bars:
        return (
            result.committed_bars[0].open_time,
            result.committed_bars[-1].close_time,
            len(result.committed_bars),
        )
    if result.equity_curve:
        return (
            result.equity_curve[0][0],
            result.equity_curve[-1][0],
            len(result.equity_curve),
        )
    return None, None, 0


def write_backtest_report(report: BacktestReport, path: str) -> int:
    """Writes `report` to `path`, gzip-compressed when the name ends `.gz`
    (`load_backtest_report` auto-detects either on read, so the writer is
    the only place that decides). Returns the file's size in bytes, for the
    caller's own confirmation log line."""
    data = dump_backtest_report(report, gzip_compress=path.endswith(".gz"))
    with open(path, "wb") as report_file:
        report_file.write(data)
    return len(data)
