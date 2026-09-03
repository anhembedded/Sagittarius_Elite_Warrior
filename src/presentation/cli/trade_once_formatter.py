"""Renders one `trade-once` attempt as the text `EPIC-021G` §5 specifies:
the candle/strategy decision, the four trading-limit checks (or the one
safety gate that blocked before they were ever evaluated), and the
DRY-RUN/LIVE outcome."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.application.use_cases.trading.execute_order.result import (
    ExecuteOrderNotionalRejection,
    ExecuteOrderResult,
    ExecuteOrderSafetyGate,
)
from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.domain.trading.policies.trading_limit_policy import (
    TradingLimitCheck,
    TradingLimitContext,
    TradingLimits,
    TradingLimitViolation,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.signal import Signal

_SAFETY_GATE_TEXT: dict[ExecuteOrderSafetyGate, str] = {
    ExecuteOrderSafetyGate.TRADING_VENUE_DISABLED: (
        "TradingVenue đang DISABLED — bật ở exchange.trading_venue=futures_testnet."
    ),
    ExecuteOrderSafetyGate.TRADING_SWITCH_OFF: (
        "Công tắc trading.enabled đang tắt — bật bằng EnableTradingCommand trước."
    ),
    ExecuteOrderSafetyGate.CONNECTION_NOT_READY: (
        "Kết nối sàn chưa sẵn sàng (không reachable, hoặc Hedge Mode) — chạy "
        "`exchange-status` để xem chi tiết."
    ),
}

_VIOLATION_TEXT: dict[TradingLimitViolation, str] = {
    TradingLimitViolation.MAX_ORDERS_PER_SESSION: "đã chạm số lệnh tối đa/phiên",
    TradingLimitViolation.MAX_NOTIONAL_PER_ORDER: "notional lệnh vượt trần",
    TradingLimitViolation.MAX_POSITIONS_PER_SYMBOL: "đã có vị thế đang mở",
    TradingLimitViolation.MIN_ORDER_INTERVAL: "quá gần lệnh trước trên cùng symbol",
}


def format_candle_and_signal(
    candle: MarketData, strategy_key: str, signal: Signal | None
) -> str:
    header = f"Nến gần nhất : {candle.close_time} UTC  close={candle.close_price:,.2f}"
    if signal is None:
        return (
            f"{header}\n"
            f"Chiến lược   : {strategy_key} → không có tín hiệu actionable "
            "(HOLD, hoặc chỉ báo chưa đủ dữ liệu warm-up)"
        )
    return (
        f"{header}\n"
        f"Chiến lược   : {strategy_key} → SIGNAL {signal.action.value} ({signal.reason})"
    )


def format_limit_checks(
    checks: tuple[TradingLimitCheck, ...],
    context: TradingLimitContext,
    limits: TradingLimits,
) -> str:
    by_violation = {check.violation: check.passed for check in checks}
    orders_mark = (
        "✔" if by_violation[TradingLimitViolation.MAX_ORDERS_PER_SESSION] else "✘"
    )
    notional_mark = (
        "✔" if by_violation[TradingLimitViolation.MAX_NOTIONAL_PER_ORDER] else "✘"
    )
    position_mark = (
        "✔" if by_violation[TradingLimitViolation.MAX_POSITIONS_PER_SYMBOL] else "✘"
    )
    interval_mark = (
        "✔" if by_violation[TradingLimitViolation.MIN_ORDER_INTERVAL] else "✘"
    )

    position_text = (
        "chưa có" if context.open_position_count_for_symbol == 0 else "đang mở"
    )
    interval_text = (
        "n/a"
        if context.time_since_last_order_for_symbol is None
        else f"{context.time_since_last_order_for_symbol.total_seconds():.0f}s"
    )

    return (
        f"Hạn mức      : lệnh {context.orders_sent_this_session + 1}/"
        f"{limits.max_orders_per_session} {orders_mark}   "
        f"notional {context.order_notional:,.2f} ≤ {limits.max_notional_per_order:,.2f} "
        f"{notional_mark}   vị thế: {position_text} {position_mark}\n"
        f"               khoảng cách lệnh trước: {interval_text} {interval_mark}"
    )


def format_result(result: ExecuteOrderResult, live_requested: bool) -> str:
    if result.blocked_by is not None and result.preview is None:
        gate = _SAFETY_GATE_TEXT.get(result.blocked_by, str(result.blocked_by))  # type: ignore[arg-type]
        return f"Chặn trước cả khi xem lệnh: {gate}\nKhông gửi lệnh nào."

    if isinstance(result.blocked_by, TradingLimitViolation):
        reason = _VIOLATION_TEXT.get(result.blocked_by, result.blocked_by.value)
        return (
            f"Hạn mức      : ✘ CHẶN — {reason} ({result.blocked_by.value})\n"
            "Không gửi lệnh nào."
        )

    if result.blocked_by is ExecuteOrderNotionalRejection.MIN_NOTIONAL:
        # `BUG-090` — `result.preview` is populated (normalization already
        # ran), so this must be checked before the fall-through DRY-RUN/LIVE
        # branches below, or a rejected order would print as if it went
        # through.
        preview = result.preview
        if preview is None:  # pragma: no cover - handler always populates it
            return "Trạng thái   : ✘ TỪ CHỐI MIN_NOTIONAL\nKhông gửi lệnh nào."
        return (
            f"Trạng thái   : ✘ TỪ CHỐI MIN_NOTIONAL — "
            f"{preview.estimated_notional:,.2f} USDT < "
            f"{preview.min_notional:,.2f} USDT\n"
            "Không gửi lệnh nào."
        )

    if not live_requested:
        return "Chế độ       : DRY-RUN → dừng ở đây. Thêm --live để đặt thật."

    order = result.submitted_order
    if order is None:
        return "Chế độ       : LIVE, nhưng không có lệnh nào được gửi."
    return (
        "Chế độ       : LIVE\n"
        f"Đã gửi       : {order.client_order_id}   → {order.status.name}\n"
        "Trạng thái   : sàn đã nhận — trạng thái khớp thật do EPIC-021H's "
        "User Data Stream báo lại, không có trong response gửi lệnh đồng bộ."
    )
