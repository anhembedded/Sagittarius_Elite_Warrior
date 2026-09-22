"""`BacktestReport` — the schema for the one file format a backtest run
exports to and imports from (`BOT-115A`), the foundation of Epic `BOT-115`
(Persistence & Portability).

@details Types only. `backtest_report_serializer.py` turns one of these into
a plain JSON-safe `dict`/bytes; `backtest_report_loader.py` turns untrusted
bytes back into one, never raising. Split along that seam (schema vs encode
vs decode — three different abstraction levels, `architecture-rule.md` §5.1)
once this module crossed the 400-line threshold with all three together.

@par Why `config` is its own dataclass, not `BacktestRunConfig`
`BacktestRunConfig` (`ui/logic/backtest_fsm_matrix.py`) is a UI-layer type —
importing it here would point a domain-ish contract outward
(`architecture-rule.md` §3: dependencies point inward). `BacktestReportConfig`
below mirrors its run-parameter fields independently; `BOT-115B` maps one to
the other when it builds a report from a live run.

@par Why `execution_mode` is a plain string here
`BacktestExecutionMode` lives in the same UI-layer file for the same reason.
Moving it to `contracts/` is a real improvement but a separate, larger change
(it has other call sites across the UI layer) — out of this task's bounds.
`backtest_report_loader.py`'s `_KNOWN_EXECUTION_MODES` mirrors its two values
so an unknown string is still rejected explicitly, not silently accepted.

@par Provenance over trust (`BOT-078`)
A loaded report is untrusted input — see `backtest_report_loader.py` for how
`load_backtest_report` never uses `pickle`/`eval`/unsafe YAML, whitelists
every enum and `strategy_key`, and recomputes `BacktestMetrics` to flag a
report whose numbers disagree with its own trades.

@par Klines are never embedded
`committed_bars` (`BacktestResult`'s own field) is `list[MarketData]` — real
kline data, which the epic's own §3.1 decision keeps out of the report file
(tens of MB for a wide range). The serializer drops it; the loader always
reconstructs `None`, the same value `BacktestResult` uses for "read bars
from storage" — the presentation layer re-fetches by
`symbol`/`timeframe`/range on import instead.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from Sagittarius_Elite_Warrior.src.core.vo.position_sizing import PositionSizing
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.backtest_result import (
    BacktestResult,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.broker_simulation_config import (
    BrokerSimulationConfig,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.currency import (
    Currency,
)

#: Integer, strictly increasing. Checked first on every load; a version this
#: build does not understand is refused with a clear message, never guessed.
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class DataWindow:
    """The historical range a run actually covered — `None` timestamps mean
    an empty run (no klines), not "unknown"."""

    first_kline_open: datetime | None
    last_kline_close: datetime | None
    kline_count: int


@dataclass(frozen=True)
class BacktestReportProvenance:
    """Who/what/when produced this report — `BOT-078`: never displayed as if
    just computed."""

    engine_version: str
    app_version: str
    strategy_key: str
    created_at: datetime
    #: `BacktestExecutionMode.value` — see module docstring.
    execution_mode: str
    data_window: DataWindow


@dataclass(frozen=True)
class BacktestReportConfig:
    """Every run parameter needed to re-run the same backtest — everything
    `BacktestRunConfig` carries except `strategy_key`/`execution_mode`, which
    live on `BacktestReportProvenance` instead (Zero Redundancy: one run has
    exactly one strategy and one mode, so recording it twice invites the two
    copies to drift)."""

    symbol: str
    timeframe: TimeFrame
    initial_balance: float
    start_time: datetime | None
    end_time: datetime | None
    strategy_params: Mapping[str, Any] | None
    currency: Currency
    position_sizing: PositionSizing
    broker_config: BrokerSimulationConfig
    #: Only meaningful when provenance.execution_mode == "HISTORICAL_TICK"
    #: (`BOT-076`/`BOT-077`), same reasoning as their own defaults.
    tick_resolution: TimeFrame = TimeFrame.ONE_SECOND
    calc_on_order_fills: bool = False


@dataclass(frozen=True)
class BacktestReport:
    """One backtest run, fully self-describing: what was asked for
    (`config`), what came out (`result`), and where it came from
    (`provenance`)."""

    provenance: BacktestReportProvenance
    config: BacktestReportConfig
    result: BacktestResult
    schema_version: int = SCHEMA_VERSION


class BacktestReportLoadErrorKind(str, Enum):
    """Every way `load_backtest_report` can refuse a file — one Vietnamese
    message per kind, never a bare traceback (task §3 item 5)."""

    MALFORMED_JSON = "malformed_json"
    UNSUPPORTED_SCHEMA_VERSION = "unsupported_schema_version"
    INVALID_FIELD = "invalid_field"


@dataclass(frozen=True)
class BacktestReportLoadError:
    kind: BacktestReportLoadErrorKind
    message: str


@dataclass(frozen=True)
class BacktestReportLoadResult:
    """Either a usable `report`, or an `error` explaining why not — never
    both, matching `RunConfigOutcome`'s own precedent
    (`ui/logic/run_config_builder.py`)."""

    report: BacktestReport | None
    error: BacktestReportLoadError | None
    #: True when `provenance.strategy_key` isn't in the caller's own
    #: `StrategyRegistry` — `result` can still be viewed (dead data, no risk
    #: to display), but "load config to re-run" must be disabled: there is
    #: no strategy class left to run it with.
    strategy_key_unknown: bool = False
    #: True when recomputing `BacktestMetrics` from `result.trades`/
    #: `result.equity_curve` disagrees with the stored `result.metrics`
    #: beyond float noise — the file was hand-edited, or produced by a
    #: different engine version (`BOT-078`).
    metrics_mismatch: bool = False

    @property
    def is_valid(self) -> bool:
        return self.report is not None and self.error is None
