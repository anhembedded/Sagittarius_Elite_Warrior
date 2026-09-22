"""Tests for `BacktestReport` serialize/deserialize/dump/load (BOT-115A).

The round-trip test is the spine (task §4): every field of a full,
non-trivial report (short side, leverage, metadata, out_of_sample) must
survive export -> import unchanged, including a freshly recomputed
`BacktestMetrics` agreeing with what was stored.
"""

from __future__ import annotations

import gzip
import json
from datetime import UTC, datetime, timedelta

from Sagittarius_Elite_Warrior.src.core.vo.position_sizing import (
    PositionSizing,
    PositionSizingType,
)
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.backtest_report import (
    SCHEMA_VERSION,
    BacktestReport,
    BacktestReportConfig,
    BacktestReportLoadErrorKind,
    BacktestReportProvenance,
    DataWindow,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.backtest_report_loader import (
    deserialize_backtest_result,
    load_backtest_report,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.backtest_report_serializer import (
    dump_backtest_report,
    serialize_backtest_report,
    serialize_backtest_result,
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

_T0 = datetime(2024, 1, 1, tzinfo=UTC)


def _trade(
    pnl: float,
    *,
    side: PositionSide = PositionSide.LONG,
    leverage: float = 1.0,
    mae_percent: float = 0.0,
    mfe_percent: float = 0.0,
    metadata: dict | None = None,
) -> Trade:
    return Trade(
        symbol="BTCUSDT",
        entry_time=_T0,
        entry_price=100.0,
        exit_time=_T0 + timedelta(hours=1),
        exit_price=100.0 + pnl,
        quantity=1.0,
        pnl=pnl,
        pnl_percent=pnl / 10.0,
        fees_paid=0.25,
        entry_reason="EMA Crossover",
        exit_reason=ExitReason.TAKE_PROFIT,
        metadata=metadata or {"score": 0.87, "tag": "breakout"},
        side=side,
        leverage=leverage,
        mae_percent=mae_percent,
        mfe_percent=mfe_percent,
    )


def _equity_curve(n: int, start: float = 1000.0) -> list[tuple[datetime, float]]:
    return [(_T0 + timedelta(hours=i), start + i) for i in range(n)]


def _full_result(*, with_out_of_sample: bool = True) -> BacktestResult:
    trades = [
        _trade(100.0, side=PositionSide.LONG, mae_percent=-5.0, mfe_percent=12.0),
        _trade(
            -40.0,
            side=PositionSide.SHORT,
            leverage=5.0,
            mae_percent=-40.0,
            mfe_percent=8.0,
            metadata={},
        ),
    ]
    equity_curve = _equity_curve(5)
    out_of_sample = None
    if with_out_of_sample:
        out_of_sample = OutOfSampleValidation(
            in_sample=BacktestResult.compute(
                symbol="BTCUSDT",
                initial_balance=1000.0,
                final_balance=1200.0,
                trades=[_trade(200.0)],
                equity_curve=_equity_curve(3),
            ),
            out_of_sample=BacktestResult.compute(
                symbol="BTCUSDT",
                initial_balance=1000.0,
                final_balance=900.0,
                trades=[_trade(-100.0)],
                equity_curve=_equity_curve(3, start=900.0),
            ),
            in_sample_ratio=0.7,
        )
    return BacktestResult.compute(
        symbol="BTCUSDT",
        initial_balance=1000.0,
        final_balance=1060.0,
        trades=trades,
        equity_curve=equity_curve,
        out_of_sample=out_of_sample,
    )


def _full_report(*, with_out_of_sample: bool = True) -> BacktestReport:
    return BacktestReport(
        provenance=BacktestReportProvenance(
            engine_version="1.4.0",
            app_version="0.9.2",
            strategy_key="ema_trend_confirm_pullback",
            created_at=_T0,
            execution_mode="BAR_CLOSE",
            data_window=DataWindow(
                first_kline_open=_T0 - timedelta(days=30),
                last_kline_close=_T0,
                kline_count=43200,
            ),
        ),
        config=BacktestReportConfig(
            symbol="BTCUSDT",
            timeframe=TimeFrame.FIVE_MINUTES,
            initial_balance=1000.0,
            start_time=_T0 - timedelta(days=30),
            end_time=_T0,
            strategy_params={"fast": 9, "slow": 21},
            currency=Currency.USD,
            position_sizing=PositionSizing(
                type=PositionSizingType.PERCENT_OF_EQUITY, value=100.0
            ),
            broker_config=BrokerSimulationConfig(
                slippage_ticks=2,
                commission_type=CommissionType.PERCENT,
                commission_value=0.1,
                pyramiding=2,
                long_leverage=1.0,
                short_leverage=5.0,
                stop_loss_pct=1.5,
                take_profit_pct=3.0,
            ),
            tick_resolution=TimeFrame.ONE_SECOND,
            calc_on_order_fills=False,
        ),
        result=_full_result(with_out_of_sample=with_out_of_sample),
    )


# ---------------------------------------------------------------------------
# Round-trip — the spine test
# ---------------------------------------------------------------------------


def test_round_trip_preserves_every_field_including_out_of_sample_short_and_leverage():
    report = _full_report()

    loaded = load_backtest_report(
        dump_backtest_report(report),
        valid_strategy_keys={"ema_trend_confirm_pullback"},
    )

    assert loaded.is_valid
    assert loaded.error is None
    assert loaded.strategy_key_unknown is False
    assert loaded.metrics_mismatch is False
    restored = loaded.report
    assert restored is not None

    assert restored.provenance == report.provenance
    assert restored.config == report.config
    assert restored.result.final_balance == report.result.final_balance
    assert restored.result.trades == report.result.trades
    assert restored.result.equity_curve == report.result.equity_curve
    assert restored.result.metrics == report.result.metrics
    assert restored.result.out_of_sample == report.result.out_of_sample
    # Klines are never embedded (epic §3.1) — always None coming back, even
    # though nothing in this test ever set it either way on the original.
    assert restored.result.committed_bars is None


def test_round_trip_without_out_of_sample():
    report = _full_report(with_out_of_sample=False)

    loaded = load_backtest_report(
        dump_backtest_report(report),
        valid_strategy_keys={report.provenance.strategy_key},
    )

    assert loaded.is_valid
    assert loaded.report.result.out_of_sample is None


def test_dump_and_load_agree_with_and_without_gzip():
    report = _full_report()
    plain = dump_backtest_report(report, gzip_compress=False)
    compressed = dump_backtest_report(report, gzip_compress=True)

    assert compressed != plain
    assert plain[:2] != b"\x1f\x8b"
    assert compressed[:2] == b"\x1f\x8b"

    plain_loaded = load_backtest_report(
        plain, valid_strategy_keys={report.provenance.strategy_key}
    )
    gzip_loaded = load_backtest_report(
        compressed, valid_strategy_keys={report.provenance.strategy_key}
    )

    assert plain_loaded.is_valid
    assert gzip_loaded.is_valid
    assert plain_loaded.report == gzip_loaded.report


def test_equity_curve_round_trips_at_zero_one_and_many_points():
    for n in (0, 1, 2000):
        result = BacktestResult.compute(
            symbol="BTCUSDT",
            initial_balance=1000.0,
            final_balance=1000.0,
            trades=[],
            equity_curve=_equity_curve(n),
        )
        restored = deserialize_backtest_result(
            serialize_backtest_result(result), symbol="BTCUSDT", initial_balance=1000.0
        )
        assert restored.equity_curve == result.equity_curve


# ---------------------------------------------------------------------------
# Safe loading — untrusted input never crashes
# ---------------------------------------------------------------------------


def test_load_rejects_malformed_json():
    loaded = load_backtest_report(b"{not valid json", valid_strategy_keys=set())

    assert not loaded.is_valid
    assert loaded.error.kind is BacktestReportLoadErrorKind.MALFORMED_JSON


def test_load_rejects_a_json_array_at_the_top_level():
    loaded = load_backtest_report(b"[1, 2, 3]", valid_strategy_keys=set())

    assert not loaded.is_valid
    assert loaded.error.kind is BacktestReportLoadErrorKind.MALFORMED_JSON


def test_load_rejects_a_future_schema_version():
    payload = serialize_backtest_report(_full_report())
    payload["schema_version"] = SCHEMA_VERSION + 1
    data = json.dumps(payload).encode("utf-8")

    loaded = load_backtest_report(
        data, valid_strategy_keys={"ema_trend_confirm_pullback"}
    )

    assert not loaded.is_valid
    assert loaded.error.kind is BacktestReportLoadErrorKind.UNSUPPORTED_SCHEMA_VERSION
    assert "chưa hiểu được" in loaded.error.message


def test_load_rejects_a_missing_field_explicitly_rather_than_crashing():
    payload = serialize_backtest_report(_full_report())
    del payload["config"]["symbol"]
    data = json.dumps(payload).encode("utf-8")

    loaded = load_backtest_report(
        data, valid_strategy_keys={"ema_trend_confirm_pullback"}
    )

    assert not loaded.is_valid
    assert loaded.error.kind is BacktestReportLoadErrorKind.INVALID_FIELD


def test_load_rejects_an_unknown_enum_value_rather_than_guessing():
    payload = serialize_backtest_report(_full_report())
    payload["config"]["currency"] = "DOGE"
    data = json.dumps(payload).encode("utf-8")

    loaded = load_backtest_report(
        data, valid_strategy_keys={"ema_trend_confirm_pullback"}
    )

    assert not loaded.is_valid
    assert loaded.error.kind is BacktestReportLoadErrorKind.INVALID_FIELD


def test_load_rejects_mismatched_equity_curve_columns():
    payload = serialize_backtest_report(_full_report())
    payload["result"]["equity_curve"]["v"].append(1.0)
    data = json.dumps(payload).encode("utf-8")

    loaded = load_backtest_report(
        data, valid_strategy_keys={"ema_trend_confirm_pullback"}
    )

    assert not loaded.is_valid
    assert loaded.error.kind is BacktestReportLoadErrorKind.INVALID_FIELD


def test_load_flags_an_unknown_strategy_key_but_still_shows_the_result():
    report = _full_report()

    loaded = load_backtest_report(
        dump_backtest_report(report), valid_strategy_keys={"some_other_strategy"}
    )

    assert loaded.is_valid
    assert loaded.strategy_key_unknown is True
    assert loaded.report.result.trades == report.result.trades


def test_load_flags_hand_edited_metrics_that_disagree_with_the_trades():
    payload = serialize_backtest_report(_full_report())
    payload["result"]["metrics"]["net_profit"] = 999_999.0
    data = json.dumps(payload).encode("utf-8")

    loaded = load_backtest_report(
        data, valid_strategy_keys={"ema_trend_confirm_pullback"}
    )

    assert loaded.is_valid
    assert loaded.metrics_mismatch is True


def test_load_does_not_flag_metrics_mismatch_for_an_honest_report():
    report = _full_report()

    loaded = load_backtest_report(
        dump_backtest_report(report),
        valid_strategy_keys={report.provenance.strategy_key},
    )

    assert loaded.metrics_mismatch is False


def test_load_never_raises_on_arbitrary_garbage_bytes():
    """Fuzz-lite: a handful of adversarial byte strings a hostile or simply
    corrupted file might contain, none of which may propagate an exception
    out of `load_backtest_report` (task §3 item 5)."""
    garbage_inputs = [
        b"",
        b"\x00\x01\x02\xff",
        b"null",
        b"42",
        b'"just a string"',
        gzip.compress(b"not json inside a real gzip wrapper"),
        b"\x1f\x8b" + b"\x00" * 10,  # gzip magic bytes, corrupt body
    ]
    for garbage in garbage_inputs:
        loaded = load_backtest_report(garbage, valid_strategy_keys=set())
        assert not loaded.is_valid
        assert loaded.error is not None
