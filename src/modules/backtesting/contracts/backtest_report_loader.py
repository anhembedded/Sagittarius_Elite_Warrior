"""Untrusted bytes -> `BacktestReport`, never raising (BOT-115A).

@details The decode half of the schema split in `backtest_report.py`'s own
docstring; `backtest_report_serializer.py` is the matching encode half.

Provenance over trust (`BOT-078`): `load_backtest_report` never uses
`pickle`/`eval`/unsafe YAML — `json.loads` plus dataclasses built field by
field. Every enum is `str, Enum`, so reconstructing via `EnumClass(value)`
already rejects an unknown member; `_KNOWN_EXECUTION_MODES` does the same
job for `execution_mode`, which is a plain string (see `backtest_report.py`
for why). `strategy_key` is whitelisted against the caller's own
`valid_strategy_keys` — passed in, never imported, so this module never
depends on `StrategyRegistry` (an application-layer type) directly. Every
failure path returns a `BacktestReportLoadResult` with `error` set; nothing
here raises out to the caller.
"""

from __future__ import annotations

import gzip
import json
import math
from collections.abc import Collection
from datetime import datetime
from typing import Any

from Sagittarius_Elite_Warrior.src.core.vo.position_sizing import (
    PositionSizing,
    PositionSizingType,
)
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.backtest_metrics import (
    BacktestMetrics,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.backtest_report import (
    SCHEMA_VERSION,
    BacktestReport,
    BacktestReportConfig,
    BacktestReportLoadError,
    BacktestReportLoadErrorKind,
    BacktestReportLoadResult,
    BacktestReportProvenance,
    DataWindow,
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

#: Mirrors `BacktestExecutionMode`'s real values — see `backtest_report.py`
#: for why the enum itself isn't imported here.
_KNOWN_EXECUTION_MODES = frozenset({"BAR_CLOSE", "HISTORICAL_TICK"})

#: A relative tolerance loose enough for float round-trip/recompute noise,
#: tight enough that a hand-edited number still trips it.
_METRICS_RELATIVE_TOLERANCE = 1e-6
_METRICS_ABSOLUTE_TOLERANCE = 1e-9

#: First two bytes of any gzip member (RFC 1952) — used to auto-detect a
#: compressed payload on load without the caller having to say which it is.
_GZIP_MAGIC = b"\x1f\x8b"


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
