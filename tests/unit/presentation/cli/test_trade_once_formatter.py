from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.application.use_cases.trading.execute_order.result import (
    ExecuteOrderResult,
    ExecuteOrderSafetyGate,
)
from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.domain.trading.client_order_id import ClientOrderId
from Sagittarius_Elite_Warrior.src.domain.trading.order import Order
from Sagittarius_Elite_Warrior.src.domain.trading.order_status import OrderStatus
from Sagittarius_Elite_Warrior.src.domain.trading.order_type import OrderType
from Sagittarius_Elite_Warrior.src.domain.trading.policies.trading_limit_policy import (
    TradingLimitCheck,
    TradingLimitContext,
    TradingLimits,
    TradingLimitViolation,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.domain.value_objects.signal import Signal
from Sagittarius_Elite_Warrior.src.domain.value_objects.signal_action import (
    SignalAction,
)
from Sagittarius_Elite_Warrior.src.presentation.cli.trade_once_formatter import (
    format_candle_and_signal,
    format_limit_checks,
    format_result,
)

_LIMITS = TradingLimits(
    max_orders_per_session=20,
    max_notional_per_order=Decimal(500),
    max_positions_per_symbol=1,
    min_order_interval=timedelta(seconds=60),
)


def _candle() -> MarketData:
    dt = datetime(2026, 9, 1, 14, 35, tzinfo=UTC)
    return MarketData(
        symbol="BTCUSDT",
        interval="5m",
        open_time=dt,
        open_price=64000.0,
        high_price=64200.0,
        low_price=63900.0,
        close_price=64102.30,
        volume=100.0,
        close_time=dt,
        quote_asset_volume=1000.0,
        number_of_trades=10,
        taker_buy_base_asset_volume=50.0,
        taker_buy_quote_asset_volume=500.0,
    )


def test_format_candle_and_signal_shows_the_signal() -> None:
    signal = Signal(
        symbol="BTCUSDT",
        action=SignalAction.BUY,
        reason="ema_fast cắt lên trong xu hướng tăng",
        price=64102.30,
        time=datetime(2026, 9, 1, 14, 35, tzinfo=UTC),
    )
    text = format_candle_and_signal(_candle(), "ema_trend_confirm_pullback", signal)

    assert "SIGNAL BUY" in text
    assert "ema_trend_confirm_pullback" in text
    assert "64,102.30" in text


def test_format_candle_and_signal_no_signal() -> None:
    text = format_candle_and_signal(_candle(), "ema_trend_confirm_pullback", None)
    assert "không có tín hiệu" in text


def test_format_limit_checks_all_passing() -> None:
    context = TradingLimitContext(
        orders_sent_this_session=0,
        order_notional=Decimal("128.20"),
        open_position_count_for_symbol=0,
        time_since_last_order_for_symbol=None,
    )
    checks = (
        TradingLimitCheck(TradingLimitViolation.MAX_ORDERS_PER_SESSION, True),
        TradingLimitCheck(TradingLimitViolation.MAX_NOTIONAL_PER_ORDER, True),
        TradingLimitCheck(TradingLimitViolation.MAX_POSITIONS_PER_SYMBOL, True),
        TradingLimitCheck(TradingLimitViolation.MIN_ORDER_INTERVAL, True),
    )
    text = format_limit_checks(checks, context, _LIMITS)

    assert "lệnh 1/20" in text
    assert "128.20" in text
    assert "500.00" in text
    assert "chưa có" in text
    assert "n/a" in text
    assert "✘" not in text


def test_format_result_dry_run() -> None:
    result = ExecuteOrderResult(
        blocked_by=None,
        preview=object(),  # only presence/absence is checked by the formatter
        limit_checks=(),
        submitted_order=None,
    )
    text = format_result(result, live_requested=False)
    assert "DRY-RUN" in text
    assert "--live" in text


def test_format_result_blocked_by_trading_limit() -> None:
    result = ExecuteOrderResult(
        blocked_by=TradingLimitViolation.MAX_POSITIONS_PER_SYMBOL,
        preview=object(),
        limit_checks=(),
        submitted_order=None,
    )
    text = format_result(result, live_requested=False)
    assert "CHẶN" in text
    assert "max_positions_per_symbol" in text


def test_format_result_blocked_by_safety_gate() -> None:
    result = ExecuteOrderResult(
        blocked_by=ExecuteOrderSafetyGate.TRADING_SWITCH_OFF,
        preview=None,
        limit_checks=(),
        submitted_order=None,
    )
    text = format_result(result, live_requested=False)
    assert "Không gửi lệnh nào." in text


def test_format_result_live_submitted() -> None:
    order = Order(
        client_order_id=ClientOrderId("SEW-a91f4c72e0b8"),
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.002"),
        status=OrderStatus.NEW,
    )
    result = ExecuteOrderResult(
        blocked_by=None,
        preview=object(),
        limit_checks=(),
        submitted_order=order,
    )
    text = format_result(result, live_requested=True)

    assert "LIVE" in text
    assert "SEW-a91f4c72e0b8" in text
    assert "NEW" in text
