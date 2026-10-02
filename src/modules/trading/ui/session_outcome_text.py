"""What a screen says when trading is enabled, refused or stopped.

@details One copy for the single Trading screen, the Dev Board and each desk
(`EPIC-028K`): the table lived word for word in two presenters, and a third
copy in the desks would have been the next one to drift.

`EnumLabels`, not a bare dict: the table was once missing
`SUPERSEDED_BY_CONCURRENT_STATE_CHANGE`, and a `.get(..., generic)` hid it.
Construction now refuses an incomplete table at import.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.emergency_stop_result import (
    EmergencyStopResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.enable_trading_result import (
    EnableTradingBlockReason,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.enum_labels import EnumLabels

ENABLE_BLOCK_MESSAGES = EnumLabels(
    EnableTradingBlockReason,
    {
        EnableTradingBlockReason.TRADING_VENUE_DISABLED: (
            "Trading venue is disabled in configuration — set it to Futures Testnet "
            "or Spot Testnet to enable trading."
        ),
        EnableTradingBlockReason.CONNECTION_NOT_READY: (
            "Connection to the exchange is not ready — check your API key/network connection."
        ),
        EnableTradingBlockReason.UNEXPECTED_POSITIONS: (
            "The account has unexpected open positions — please handle them manually "
            "on the exchange before enabling trading."
        ),
        EnableTradingBlockReason.SUPERSEDED_BY_CONCURRENT_STATE_CHANGE: (
            "Another operation (usually EMERGENCY STOP) changed the state while "
            "reconciliation was in progress — trading was not enabled. Check the "
            "state and try again if you still want to enable it."
        ),
    },
)


def emergency_stop_log_lines(result: EmergencyStopResult) -> tuple[str, ...]:
    """The log lines for one Emergency Stop: a heading, then each step with
    its mark and detail."""
    steps = (
        ("Disable trading", result.trading_disabled),
        ("Cancel pending orders", result.orders_cancelled),
        ("Close positions", result.positions_closed),
    )
    lines = [
        f"  {index}. {label} ... {'✔' if step.succeeded else '✘'} {step.detail}"
        for index, (label, step) in enumerate(steps, start=1)
    ]
    return ("EMERGENCY STOP", *lines)
