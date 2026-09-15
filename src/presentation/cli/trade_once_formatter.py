"""Renders one `trade-once` attempt as the text `EPIC-021G` §5 specifies:
the candle/strategy decision, the four trading-limit checks (or the one
safety gate that blocked before they were ever evaluated), and the
DRY-RUN/LIVE outcome."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.domain.value_objects.signal import Signal
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.execute_order_result import (
    ExecuteOrderNotionalRejection,
    ExecuteOrderResult,
    ExecuteOrderSafetyGate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.domain.policies.trading_limit_policy import (
    TradingLimitCheck,
    TradingLimitContext,
    TradingLimits,
    TradingLimitViolation,
)

_SAFETY_GATE_TEXT: dict[ExecuteOrderSafetyGate, str] = {
    ExecuteOrderSafetyGate.TRADING_VENUE_DISABLED: (
        "TradingVenue is DISABLED — enable it via exchange.trading_venue=futures_testnet."
    ),
    ExecuteOrderSafetyGate.TRADING_SWITCH_OFF: (
        "The trading.enabled switch is off — turn it on with EnableTradingCommand first."
    ),
    ExecuteOrderSafetyGate.CONNECTION_NOT_READY: (
        "Exchange connection not ready (unreachable, or Hedge Mode) — run "
        "`exchange-status` for details."
    ),
}

_VIOLATION_TEXT: dict[TradingLimitViolation, str] = {
    TradingLimitViolation.MAX_ORDERS_PER_SESSION: "reached the max orders per session",
    TradingLimitViolation.MAX_NOTIONAL_PER_ORDER: "order notional exceeds the cap",
    TradingLimitViolation.MAX_POSITIONS_PER_SYMBOL: "already has an open position",
    TradingLimitViolation.MIN_ORDER_INTERVAL: "too soon after the previous order on this symbol",
}


def format_candle_and_signal(
    candle: MarketData, strategy_key: str, signal: Signal | None
) -> str:
    header = f"Latest candle: {candle.close_time} UTC  close={candle.close_price:,.2f}"
    if signal is None:
        return (
            f"{header}\n"
            f"Strategy     : {strategy_key} → no actionable signal "
            "(HOLD, or the indicator has not warmed up yet)"
        )
    return (
        f"{header}\n"
        f"Strategy     : {strategy_key} → SIGNAL {signal.action.value} ({signal.reason})"
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

    position_text = "none" if context.open_position_count_for_symbol == 0 else "open"
    interval_text = (
        "n/a"
        if context.time_since_last_order_for_symbol is None
        else f"{context.time_since_last_order_for_symbol.total_seconds():.0f}s"
    )

    return (
        f"Limits       : order {context.orders_sent_this_session + 1}/"
        f"{limits.max_orders_per_session} {orders_mark}   "
        f"notional {context.order_notional:,.2f} ≤ {limits.max_notional_per_order:,.2f} "
        f"{notional_mark}   position: {position_text} {position_mark}\n"
        f"               time since previous order: {interval_text} {interval_mark}"
    )


def format_result(result: ExecuteOrderResult, live_requested: bool) -> str:
    if result.blocked_by is not None and result.preview is None:
        gate = _SAFETY_GATE_TEXT.get(result.blocked_by, str(result.blocked_by))  # type: ignore[arg-type]
        return f"Blocked before the order preview even ran: {gate}\nNo order was sent."

    if isinstance(result.blocked_by, TradingLimitViolation):
        reason = _VIOLATION_TEXT.get(result.blocked_by, result.blocked_by.value)
        return (
            f"Limits       : ✘ BLOCKED — {reason} ({result.blocked_by.value})\n"
            "No order was sent."
        )

    if result.blocked_by is ExecuteOrderNotionalRejection.MIN_NOTIONAL:
        # `BUG-090` — `result.preview` is populated (normalization already
        # ran), so this must be checked before the fall-through DRY-RUN/LIVE
        # branches below, or a rejected order would print as if it went
        # through.
        preview = result.preview
        if preview is None:  # pragma: no cover - handler always populates it
            return "Status       : ✘ REJECTED MIN_NOTIONAL\nNo order was sent."
        return (
            f"Status       : ✘ REJECTED MIN_NOTIONAL — "
            f"{preview.estimated_notional:,.2f} USDT < "
            f"{preview.min_notional:,.2f} USDT\n"
            "No order was sent."
        )

    if not live_requested:
        return (
            "Mode         : DRY-RUN → stopping here. Add --live to place a real order."
        )

    order = result.submitted_order
    if order is None:
        return "Mode         : LIVE, but no order was sent."
    return (
        "Mode         : LIVE\n"
        f"Submitted    : {order.client_order_id}   → {order.status.name}\n"
        "Status       : accepted by the exchange — the real fill status is "
        "reported back by EPIC-021H's User Data Stream, not present in the "
        "synchronous order-submission response."
    )
