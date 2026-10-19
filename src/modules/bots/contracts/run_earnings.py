"""`BOT-192` — what a bot's run has earned, and the words that say it.

The Bots tab (`bot_facts.py`) and the `bot list` / `bot show` commands show the same figures in the
same words, so both build them here from the run's account (`BotProgress`). Qt-free on purpose: a
headless host installs no Qt, and the tab's formatter (`write_value`) lives behind it. The tab hands
`earnings_text` its own money writer; the commands use `plain_money`, the formatter's money rule
(`test_plain_money_writes_what_the_tabs_formatter_writes` locks the two together).

A figure the run cannot give is unknown, never zero: `NO_VALUE` when there is no account to read,
`NO_PRICE_YET` when the total waits for a price the bot has not heard.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_progress import (
    BotProgress,
)

#: A figure this bot does not have yet: no fill, no inventory, no run.
NO_VALUE = "—"
#: The total needs the price the bot itself last heard, and it has heard none.
NO_PRICE_YET = "no price yet"

type MoneyWriter = Callable[[Decimal], str]


def plain_money(value: Decimal) -> str:
    """Two decimals, thousands grouped, a value that rounds to zero unsigned: the formatter's
    money rule without its Qt import."""
    text = f"{float(value):,.2f}"
    return text[1:] if text.startswith("-") and set(text[1:]) <= set("0.,") else text


@dataclass(frozen=True, slots=True)
class RunEarnings:
    """The earnings of one run, as its record has them."""

    #: The completed buy/sell cycles' profit (one part of the total).
    grid_profit: Decimal
    completed_cycles: int
    #: Realised plus unrealised at the bot's own last price; `None` while it cannot be judged.
    total_pnl: Decimal | None
    #: Whether the run's PnL was judged at all (`False`: the record carries no summary).
    judged: bool
    #: Fills whose fee could not be priced, so the total is short by them.
    unpriced_fees: int = 0

    @classmethod
    def of(cls, progress: BotProgress | None) -> RunEarnings | None:
        """`None` when the bot has no run account to read (a draft, a runtime that cannot be read)."""
        if progress is None:
            return None
        pnl = progress.pnl
        return cls(
            grid_profit=progress.realised_profit,
            completed_cycles=progress.completed_cycles,
            total_pnl=pnl.total if pnl is not None else None,
            judged=pnl is not None,
            unpriced_fees=pnl.unpriced_fees if pnl is not None else 0,
        )


def grid_profit_text(earnings: RunEarnings | None, money: MoneyWriter) -> str:
    return NO_VALUE if earnings is None else money(earnings.grid_profit)


def cycles_text(earnings: RunEarnings | None) -> str:
    return NO_VALUE if earnings is None else str(earnings.completed_cycles)


def total_pnl_text(earnings: RunEarnings | None, money: MoneyWriter) -> str:
    if earnings is None or not earnings.judged:
        return NO_VALUE
    if earnings.total_pnl is None:
        return NO_PRICE_YET
    fees = earnings.unpriced_fees
    note = (
        f" ({fees} fees could not be priced)"
        if fees > 1
        else " (1 fee could not be priced)"
        if fees
        else ""
    )
    return f"{money(earnings.total_pnl)}{note}"
