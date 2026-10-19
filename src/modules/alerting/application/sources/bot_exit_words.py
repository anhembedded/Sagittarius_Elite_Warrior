"""`BOT-189`, `BOT-190` — the words and the table of an exit (stop loss, take profit, range exit).

Split from `bot_alert_source.py`: which stop reasons are exits, what the owner reads when one
starts, and what he reads once it has closed the position.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_kind import AlertKind
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.run_earnings import (
    RunEarnings,
    cycles_text,
    grid_profit_text,
    plain_money,
    total_pnl_text,
)

#: `BOT-189`: a stop that began with one of these reasons (`GridReason.value`) is an exit the owner
#: must hear at once; the entry into STOPPING carries it, and the bot is closing its position.
EXIT_ON_STOP: Mapping[str, AlertKind] = MappingProxyType(
    {
        "stop_loss": AlertKind.STOP_LOSS_HIT,
        "take_profit": AlertKind.TAKE_PROFIT_HIT,
        "range_exit": AlertKind.RANGE_EXIT,
    }
)

#: What the owner reads about each exit, before the bot's own detail.
EXIT_SENTENCES: Mapping[AlertKind, str] = MappingProxyType(
    {
        AlertKind.STOP_LOSS_HIT: "The stop loss was reached",
        AlertKind.TAKE_PROFIT_HIT: "The take profit was reached in the app",
        AlertKind.RANGE_EXIT: "The price left the range and the bot closes there",
    }
)

#: What closed the position, as the closing message names it (`BOT-190`).
_EXIT_NAMES: Mapping[AlertKind, str] = MappingProxyType(
    {
        AlertKind.STOP_LOSS_HIT: "The stop loss",
        AlertKind.TAKE_PROFIT_HIT: "The take profit",
        AlertKind.RANGE_EXIT: "The range exit",
    }
)


def closed_detail(kind: AlertKind, earnings: RunEarnings | None) -> str:
    """What the owner reads when the exit `kind` has closed the position: the run's result."""
    return (
        f"{_EXIT_NAMES[kind]} closed the position and the bot is stopped.\n"
        f"The run's result: {total_pnl_text(earnings, plain_money)}. "
        f"Profit of its completed cycles: {grid_profit_text(earnings, plain_money)} "
        f"over {cycles_text(earnings)} cycle(s)."
    )
