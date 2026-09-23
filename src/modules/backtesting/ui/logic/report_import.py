"""`BOT-115C` — reading a saved `.sagi-report.json` back into the Backtest
screen: the read/convert half of "import and view read-only", matching
`report_export.py`'s own write/convert half (`BOT-115B`).

@details Pure functions plus the one file read, same split as
`report_export.py` for the same reason: I/O and format conversion live in
`logic/`, the Presenter only decides *when* to call them.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.backtest_report import (
    BacktestReport,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.backtest_fsm_matrix import (
    BacktestExecutionMode,
    BacktestRunConfig,
)

#: Same join convention `performance_metrics_view.build_result_warning_text()`
#: already uses for a multi-note single-line warning.
_NOTE_SEPARATOR = "   •   "

_ENGINE_VERSION_MISMATCH_NOTE = (
    "This report was produced by engine v{report_version} — the running "
    "engine is v{current_version}, so re-running it may score differently."
)
_STRATEGY_UNKNOWN_NOTE = (
    'Strategy "{strategy_key}" is no longer registered — this result can '
    "still be viewed, but re-running it needs a different strategy."
)
_METRICS_MISMATCH_NOTE = (
    "The stored metrics do not match what recomputing them from this "
    "report's own trades produces — the file may have been edited by hand."
)


def read_backtest_report_bytes(path: str) -> bytes:
    """The inverse of `report_export.write_backtest_report()` — a plain
    file read; `load_backtest_report()` auto-detects gzip from the bytes'
    own magic number, never guessed from the path's extension."""
    with open(path, "rb") as report_file:
        return report_file.read()


def backtest_report_to_run_config(report: BacktestReport) -> BacktestRunConfig:
    """The inverse of `report_export.build_backtest_report()` — rebuilds a
    `BacktestRunConfig` (`strategy_key`/`execution_mode` recombined from
    `provenance`, `BacktestReportConfig`'s own docstring explains the
    split) so an imported run can be presented through exactly the same
    `_present_result()` path a freshly finished run uses."""
    config = report.config
    return BacktestRunConfig(
        strategy_key=report.provenance.strategy_key,
        timeframe=config.timeframe,
        initial_balance=config.initial_balance,
        start_time=config.start_time,
        end_time=config.end_time,
        strategy_params=(
            dict(config.strategy_params) if config.strategy_params is not None else None
        ),
        currency=config.currency,
        symbol=config.symbol,
        execution_mode=BacktestExecutionMode(report.provenance.execution_mode),
        tick_resolution=config.tick_resolution,
        calc_on_order_fills=config.calc_on_order_fills,
        position_sizing=config.position_sizing,
        broker_config=config.broker_config,
    )


def build_report_provenance_warning_text(
    report: BacktestReport,
    *,
    strategy_key_unknown: bool,
    metrics_mismatch: bool,
    current_engine_version: str,
) -> str:
    """One combined warning line for every provenance concern `BOT-078`
    names (task §3): `load_backtest_report()`'s own `strategy_key_unknown`/
    `metrics_mismatch` flags, plus a live engine-version comparison made
    here. A single joined line rather than one colored badge per concern —
    this screen has no existing badge widget to reuse, and `resultWarningText`
    already renders exactly this kind of multi-note line for
    `build_result_warning_text()`; empty when nothing to say.

    The "missing out_of_sample" check the task also names is deliberately
    not included: nearly every ordinary run has no out-of-sample split
    (it is opt-in), so flagging its absence specifically on import would
    warn about the common case, not a real provenance concern.
    """
    notes: list[str] = []
    if report.provenance.engine_version != current_engine_version:
        notes.append(
            _ENGINE_VERSION_MISMATCH_NOTE.format(
                report_version=report.provenance.engine_version,
                current_version=current_engine_version,
            )
        )
    if strategy_key_unknown:
        notes.append(
            _STRATEGY_UNKNOWN_NOTE.format(strategy_key=report.provenance.strategy_key)
        )
    if metrics_mismatch:
        notes.append(_METRICS_MISMATCH_NOTE)
    return _NOTE_SEPARATOR.join(notes)
