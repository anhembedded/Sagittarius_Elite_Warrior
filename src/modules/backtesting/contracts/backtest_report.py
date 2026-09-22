"""`BacktestReport` — the one file format a backtest run exports to and
imports from (`BOT-115A`), the foundation of Epic `BOT-115` (Persistence &
Portability).

@details Domain-only (§1 of the task): a dataclass, `serialize`/`deserialize`
to a plain JSON-safe `dict`, and `dump`/`load` to/from bytes (gzip optional,
auto-detected on load). No file I/O beyond that, no UI — `BOT-115B`/`115C`
own the file dialog and the read-only screen state.

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
`_KNOWN_EXECUTION_MODES` mirrors its two values so an unknown string is still
rejected explicitly, not silently accepted.

@par Provenance over trust (`BOT-078`)
A loaded report is untrusted input: `load_backtest_report` never uses
`pickle`/`eval`/unsafe YAML, whitelists every enum against its own real
members (they are `str, Enum` — reconstructing via `EnumClass(value)` already
rejects an unknown value), whitelists `strategy_key` against the caller's own
live `StrategyRegistry` keys (passed in, never imported — same inward-only
reasoning as `config` above), and recomputes `BacktestMetrics` to flag a
report whose numbers disagree with its own trades.

@par Klines are never embedded
`committed_bars` (`BacktestResult`'s own field) is `list[MarketData]` — real
kline data, which the epic's own §3.1 decision keeps out of the report file
(tens of MB for a wide range). `serialize_backtest_result` drops it;
`deserialize_backtest_result` always reconstructs `None`, the same value
`BacktestResult` uses for "read bars from storage" — the presentation layer
re-fetches by `symbol`/`timeframe`/range on import instead.
"""

from __future__ import annotations

import gzip
import json
import math
from collections.abc import Collection, Mapping
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from Sagittarius_Elite_Warrior.src.core.vo.position_sizing import (
    PositionSizing,
    PositionSizingType,
)
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.backtest_metrics import (
    BacktestMetrics,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.backtest_result import (
    BacktestResult,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.broker_simulation_config import (
    BrokerSimulationConfig,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.commission_type import (
    CommissionType,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.currency import (
    Currency,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.exit_reason import (
    ExitReason,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.out_of_sample_validation import (
    OutOfSampleValidation,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.trade import Trade
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.position_side import (
    PositionSide,
)

#: Integer, strictly increasing. Checked first on every load; a version this
#: build does not understand is refused with a clear message, never guessed.
SCHEMA_VERSION = 1

#: Mirrors `BacktestExecutionMode`'s real values — see module docstring for
#: why the enum itself isn't imported here.
_KNOWN_EXECUTION_MODES = frozenset({"BAR_CLOSE", "HISTORICAL_TICK"})

#: A relative tolerance loose enough for float round-trip/recompute noise,
#: tight enough that a hand-edited number still trips it.
_METRICS_RELATIVE_TOLERANCE = 1e-6
_METRICS_ABSOLUTE_TOLERANCE = 1e-9

#: First two bytes of any gzip member (RFC 1952) — used to auto-detect a
#: compressed payload on load without the caller having to say which it is.
_GZIP_MAGIC = b"\x1f\x8b"


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


# --------------------------------------------------------------------- #
# Serialize — BacktestReport -> plain JSON-safe dict
# --------------------------------------------------------------------- #


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
    report's own `config` (see this module's docstring), which
    `deserialize_backtest_result` requires back as context."""
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


# --------------------------------------------------------------------- #
# Dump — dict -> bytes, optionally gzipped
# --------------------------------------------------------------------- #


def dump_backtest_report(
    report: BacktestReport, *, gzip_compress: bool = False
) -> bytes:
    payload = json.dumps(serialize_backtest_report(report)).encode("utf-8")
    return gzip.compress(payload) if gzip_compress else payload


# --------------------------------------------------------------------- #
# Deserialize / load — untrusted dict/bytes -> BacktestReport, never raises
# --------------------------------------------------------------------- #


def load_backtest_report(
    data: bytes, *, valid_strategy_keys: Collection[str]
) -> BacktestReportLoadResult:
    """Never raises: every failure mode returns a `BacktestReportLoadResult`
    with `error` set. `data` may be gzipped or not — detected from its own
    magic bytes, never guessed from a file extension."""
    try:
        raw = gzip.decompress(data) if data[:2] == _GZIP_MAGIC else data
        payload = json.loads(raw)
    except (OSError, gzip.BadGzipFile, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return _load_error(
            BacktestReportLoadErrorKind.MALFORMED_JSON,
            f"Tệp báo cáo bị hỏng hoặc không phải JSON hợp lệ: {exc}",
        )

    if not isinstance(payload, dict):
        return _load_error(
            BacktestReportLoadErrorKind.MALFORMED_JSON,
            "Tệp báo cáo không đúng định dạng — nội dung gốc phải là một object JSON.",
        )

    schema_version = payload.get("schema_version")
    if schema_version != SCHEMA_VERSION:
        if isinstance(schema_version, int) and schema_version > SCHEMA_VERSION:
            return _load_error(
                BacktestReportLoadErrorKind.UNSUPPORTED_SCHEMA_VERSION,
                f"Báo cáo này tạo bởi phiên bản mới hơn (schema_version={schema_version}) "
                f"mà bản app hiện tại (hỗ trợ tới {SCHEMA_VERSION}) chưa hiểu được. "
                "Vui lòng cập nhật app.",
            )
        return _load_error(
            BacktestReportLoadErrorKind.UNSUPPORTED_SCHEMA_VERSION,
            f"Phiên bản báo cáo không được hỗ trợ: {schema_version!r}.",
        )

    try:
        report = _deserialize_report(payload)
    except (KeyError, TypeError, ValueError) as exc:
        return _load_error(
            BacktestReportLoadErrorKind.INVALID_FIELD,
            f"Tệp báo cáo thiếu trường hoặc sai kiểu dữ liệu: {exc}",
        )

    strategy_key_unknown = report.provenance.strategy_key not in valid_strategy_keys
    recomputed = BacktestMetrics.compute(
        report.result.trades, report.result.equity_curve, report.config.initial_balance
    )
    metrics_mismatch = not _metrics_agree(recomputed, report.result.metrics)

    return BacktestReportLoadResult(
        report=report,
        error=None,
        strategy_key_unknown=strategy_key_unknown,
        metrics_mismatch=metrics_mismatch,
    )


def _load_error(
    kind: BacktestReportLoadErrorKind, message: str
) -> BacktestReportLoadResult:
    return BacktestReportLoadResult(
        report=None, error=BacktestReportLoadError(kind=kind, message=message)
    )


def _deserialize_report(payload: dict[str, Any]) -> BacktestReport:
    provenance = _deserialize_provenance(_require_dict(payload, "provenance"))
    config = _deserialize_config(_require_dict(payload, "config"))
    result = deserialize_backtest_result(
        _require_dict(payload, "result"),
        symbol=config.symbol,
        initial_balance=config.initial_balance,
    )
    return BacktestReport(
        provenance=provenance,
        config=config,
        result=result,
        schema_version=payload["schema_version"],
    )


def _deserialize_provenance(payload: dict[str, Any]) -> BacktestReportProvenance:
    execution_mode = payload["execution_mode"]
    if execution_mode not in _KNOWN_EXECUTION_MODES:
        raise ValueError(f"unknown execution_mode {execution_mode!r}")
    window = _require_dict(payload, "data_window")
    return BacktestReportProvenance(
        engine_version=payload["engine_version"],
        app_version=payload["app_version"],
        strategy_key=payload["strategy_key"],
        created_at=datetime.fromisoformat(payload["created_at"]),
        execution_mode=execution_mode,
        data_window=DataWindow(
            first_kline_open=_optional_fromisoformat(window["first_kline_open"]),
            last_kline_close=_optional_fromisoformat(window["last_kline_close"]),
            kline_count=window["kline_count"],
        ),
    )


def _deserialize_config(payload: dict[str, Any]) -> BacktestReportConfig:
    sizing = _require_dict(payload, "position_sizing")
    broker = _require_dict(payload, "broker_config")
    return BacktestReportConfig(
        symbol=payload["symbol"],
        timeframe=TimeFrame(payload["timeframe"]),
        initial_balance=payload["initial_balance"],
        start_time=_optional_fromisoformat(payload["start_time"]),
        end_time=_optional_fromisoformat(payload["end_time"]),
        strategy_params=payload["strategy_params"],
        currency=Currency(payload["currency"]),
        position_sizing=PositionSizing(
            type=PositionSizingType(sizing["type"]), value=sizing["value"]
        ),
        broker_config=BrokerSimulationConfig(
            slippage_ticks=broker["slippage_ticks"],
            tick_size=broker["tick_size"],
            commission_type=CommissionType(broker["commission_type"]),
            commission_value=broker["commission_value"],
            pyramiding=broker["pyramiding"],
            long_leverage=broker["long_leverage"],
            short_leverage=broker["short_leverage"],
            stop_loss_pct=broker["stop_loss_pct"],
            take_profit_pct=broker["take_profit_pct"],
        ),
        tick_resolution=TimeFrame(payload["tick_resolution"]),
        calc_on_order_fills=payload["calc_on_order_fills"],
    )


def deserialize_backtest_result(
    payload: dict[str, Any], *, symbol: str, initial_balance: float
) -> BacktestResult:
    out_of_sample_payload = payload["out_of_sample"]
    out_of_sample = (
        _deserialize_out_of_sample(
            out_of_sample_payload, symbol=symbol, initial_balance=initial_balance
        )
        if out_of_sample_payload is not None
        else None
    )
    trades = [_deserialize_trade(t) for t in payload["trades"]]
    equity_curve = _deserialize_equity_curve(_require_dict(payload, "equity_curve"))
    return BacktestResult(
        symbol=symbol,
        initial_balance=initial_balance,
        final_balance=payload["final_balance"],
        trades=trades,
        equity_curve=equity_curve,
        metrics=_deserialize_metrics(_require_dict(payload, "metrics")),
        out_of_sample=out_of_sample,
        committed_bars=None,
    )


def _deserialize_out_of_sample(
    payload: dict[str, Any], *, symbol: str, initial_balance: float
) -> OutOfSampleValidation:
    return OutOfSampleValidation(
        in_sample=deserialize_backtest_result(
            _require_dict(payload, "in_sample"),
            symbol=symbol,
            initial_balance=initial_balance,
        ),
        out_of_sample=deserialize_backtest_result(
            _require_dict(payload, "out_of_sample"),
            symbol=symbol,
            initial_balance=initial_balance,
        ),
        in_sample_ratio=payload["in_sample_ratio"],
    )


#: Every field `BacktestMetrics` declares, in constructor order — used to
#: rebuild one generically rather than naming all 20 fields twice.
_BACKTEST_METRICS_FIELD_NAMES = tuple(BacktestMetrics.__dataclass_fields__)


def _deserialize_metrics(payload: dict[str, Any]) -> BacktestMetrics:
    return BacktestMetrics(
        **{name: payload[name] for name in _BACKTEST_METRICS_FIELD_NAMES}
    )


def _deserialize_trade(payload: dict[str, Any]) -> Trade:
    return Trade(
        symbol=payload["symbol"],
        entry_time=datetime.fromisoformat(payload["entry_time"]),
        entry_price=payload["entry_price"],
        exit_time=datetime.fromisoformat(payload["exit_time"]),
        exit_price=payload["exit_price"],
        quantity=payload["quantity"],
        pnl=payload["pnl"],
        pnl_percent=payload["pnl_percent"],
        fees_paid=payload["fees_paid"],
        entry_reason=payload["entry_reason"],
        exit_reason=ExitReason(payload["exit_reason"]),
        metadata=payload["metadata"],
        side=PositionSide(payload["side"]),
        leverage=payload["leverage"],
        mae_percent=payload["mae_percent"],
        mfe_percent=payload["mfe_percent"],
    )


def _deserialize_equity_curve(
    payload: dict[str, Any],
) -> list[tuple[datetime, float]]:
    times = payload["t"]
    values = payload["v"]
    if len(times) != len(values):
        raise ValueError(
            f"equity_curve columns disagree in length: {len(times)} times, "
            f"{len(values)} values"
        )
    return [(datetime.fromisoformat(t), v) for t, v in zip(times, values, strict=True)]


def _optional_fromisoformat(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value is not None else None


def _require_dict(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload[key]
    if not isinstance(value, dict):
        raise TypeError(f"{key!r} must be an object, got {type(value).__name__}")
    return value


def _metrics_agree(a: BacktestMetrics, b: BacktestMetrics) -> bool:
    """Field-by-field comparison tolerant of float round-trip/recompute
    noise — exact equality for `int`/`bool` fields, `math.isclose` for
    `float` ones."""
    for name in _BACKTEST_METRICS_FIELD_NAMES:
        left, right = getattr(a, name), getattr(b, name)
        if isinstance(left, bool) or isinstance(right, bool):
            if left != right:
                return False
        elif isinstance(left, float) or isinstance(right, float):
            if not math.isclose(
                left,
                right,
                rel_tol=_METRICS_RELATIVE_TOLERANCE,
                abs_tol=_METRICS_ABSOLUTE_TOLERANCE,
            ):
                return False
        elif left != right:
            return False
    return True
