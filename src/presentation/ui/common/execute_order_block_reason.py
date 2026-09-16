"""`EPIC-024B` — human-readable text for `ExecuteOrderResult.blocked_by`/
`CancelOrderResult.blocked_by`, shared by `DashboardPresenter` and
`TradingPresenter` (`architecture-rule.md` §5 / `test_no_cross_screen_
imports.py` — a screen-to-screen import is forbidden, so this lives here,
not in either screen's own presenter module).
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.execute_order_result import (
    ExecuteOrderNotionalRejection,
    ExecuteOrderSafetyGate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.domain.policies.trading_limit_policy import (
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
            "Trading venue is disabled in configuration — only Futures Testnet is supported."
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
    },
)


def format_execute_order_block_reason(
    blocked_by: ExecuteOrderSafetyGate
    | ExecuteOrderNotionalRejection
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
    return "Unknown reason."  # pragma: no cover - blocked_by is None handled by callers first
