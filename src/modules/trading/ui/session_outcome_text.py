"""What a screen says when the order session is refused or stopped.

@details One copy for each desk (`EPIC-028K`; the Dev Board's too, until
`EPIC-033P`): the table
lived word for word in two presenters (one was the Trading screen's, retired
in `EPIC-028M`), and a third
copy in the desks would have been the next one to drift.

`EnumLabels`, not a bare dict: the table was once missing
`SUPERSEDED_BY_CONCURRENT_STATE_CHANGE`, and a `.get(..., generic)` hid it.
Construction now refuses an incomplete table at import.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.emergency_stop_result import (
    EmergencyStopResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.session_block_words import (
    SESSION_BLOCK_WORDS,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.session_ready_result import (
    SessionBlockReason,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.enum_labels import EnumLabels

SESSION_BLOCK_MESSAGES = EnumLabels(SessionBlockReason, dict(SESSION_BLOCK_WORDS))


def emergency_stop_log_lines(result: EmergencyStopResult) -> tuple[str, ...]:
    """The log lines for one Emergency Stop: a heading, then each step with
    its mark and detail."""
    steps = (
        ("Close the order session", result.trading_disabled),
        ("Cancel pending orders", result.orders_cancelled),
        ("Close positions", result.positions_closed),
    )
    lines = [
        f"  {index}. {label} ... {'✔' if step.succeeded else '✘'} {step.detail}"
        for index, (label, step) in enumerate(steps, start=1)
    ]
    return ("EMERGENCY STOP", *lines)
