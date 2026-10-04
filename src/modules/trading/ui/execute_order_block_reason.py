"""`EPIC-024B` — human-readable text for `ExecuteOrderResult.blocked_by`/
`CancelOrderResult.blocked_by`, shared by `DashboardPresenter` and the
desks' order panel and account tabs (`architecture-rule.md` §5 /
`test_no_cross_screen_imports.py` — a screen-to-screen import is forbidden,
so this lives here, not in any screen's own presenter module).
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.execute_order_result import (
    ExecuteOrderNotionalRejection,
    ExecuteOrderSafetyGate,
    ExecuteOrderStopRejection,
    ExecuteOrderTypeRejection,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.trading_limits import (
    TradingLimitViolation,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.enum_labels import EnumLabels

#: `ExecuteOrderResult.blocked_by`/`CancelOrderResult.blocked_by` share
#: `ExecuteOrderSafetyGate` — one table covers the manual order card and
#: the Open Orders "Huỷ" button, on both screens.
_SAFETY_GATE_MESSAGES = EnumLabels(
    ExecuteOrderSafetyGate,
    {
        ExecuteOrderSafetyGate.TRADING_VENUE_DISABLED: (
            "Trading venue is disabled in configuration — set it to Futures Testnet "
            "or Spot Testnet to enable trading."
        ),
        ExecuteOrderSafetyGate.TRADING_SWITCH_OFF: (
            "Trading is OFF — enable trading before placing/cancelling an order."
        ),
        ExecuteOrderSafetyGate.CONNECTION_NOT_READY: (
            "Connection to the exchange is not ready — check your API key/network connection."
        ),
        #: `EPIC-025` PR 2.1f — the same words `DashboardPresenter` used to
        #: print from its own hard block, now that the refusal comes back as a
        #: gate from the order path instead. The text is the user's decision of
        #: 2026-09-09 (`PRO-003` §4.1.2) and is kept verbatim: what changed is
        #: which layer decided, not what the operator is told.
        ExecuteOrderSafetyGate.SYMBOL_LEASED: (
            "Blocked: this symbol is managed by an armed strategy — manually trading "
            "the exact symbol the strategy is watching can make the strategy lose "
            "track of its real position (even while it is currently Flat). Use "
            "Emergency Stop or disarm the strategy first, or trade manually on a "
            "different symbol."
        ),
    },
)

_LIMIT_VIOLATION_MESSAGES = EnumLabels(
    TradingLimitViolation,
    {
        TradingLimitViolation.MAX_ORDERS_PER_SESSION: (
            "Maximum number of orders allowed for this session has been reached."
        ),
        TradingLimitViolation.MAX_NOTIONAL_PER_ORDER: (
            "Order value exceeds the maximum allowed per order."
        ),
        TradingLimitViolation.MAX_POSITIONS_PER_SYMBOL: (
            "This symbol already has an open position — no more can be opened."
        ),
        TradingLimitViolation.MIN_ORDER_INTERVAL: (
            "Order submitted too soon after the previous order on the same symbol."
        ),
        TradingLimitViolation.OWNER_BUDGET_OPEN_ORDERS: (
            "The bot already has as many open orders as its budget allows."
        ),
        TradingLimitViolation.OWNER_BUDGET_EXPOSURE: (
            "This buy would take the bot's exposure above its budget."
        ),
        TradingLimitViolation.OWNER_BUDGET_SELL_EXCEEDS_INVENTORY: (
            "This sell is larger than what the bot bought and still holds."
        ),
        TradingLimitViolation.OWNER_BUDGET_SPACING: (
            "Order sent too soon after the bot's previous order."
        ),
        TradingLimitViolation.OWNER_BUDGET_RATE: (
            "The bot has sent as many orders as its budget allows in this window."
        ),
        TradingLimitViolation.OWNER_BUDGET_MISSING: (
            "The order carries a bot's tag, but no budget is registered for it on this symbol."
        ),
    },
)


def format_execute_order_block_reason(
    blocked_by: ExecuteOrderSafetyGate
    | ExecuteOrderNotionalRejection
    | ExecuteOrderStopRejection
    | ExecuteOrderTypeRejection
    | TradingLimitViolation
    | None,
) -> str:
    """@brief Human message for any member of `ExecuteOrderResult.
    blocked_by`'s union — the manual order card needs all three kinds
    (`trade_once_formatter.py`'s CLI-only counterpart never had to)."""
    if isinstance(blocked_by, ExecuteOrderSafetyGate):
        return _SAFETY_GATE_MESSAGES[blocked_by]
    if isinstance(blocked_by, TradingLimitViolation):
        return _LIMIT_VIOLATION_MESSAGES[blocked_by]
    if blocked_by is ExecuteOrderNotionalRejection.MIN_NOTIONAL:
        return "Order value (after rounding) is below the symbol's minimum notional."
    if blocked_by is ExecuteOrderTypeRejection.NOT_SENDABLE_ON_VENUE:
        return "This order type cannot be sent on this venue yet."
    if blocked_by is ExecuteOrderStopRejection.STOP_ON_WRONG_SIDE:
        return (
            "The stop price is already crossed: a buy stop must be above the "
            "last price and a sell stop below it, or the order would trigger at once."
        )
    return "Unknown reason."  # pragma: no cover - blocked_by is None handled by callers first
