"""`BOT-192` — what a bot's run has earned, and the words that say it.

The Bots tab (`bot_facts.py`) and the `bot list` / `bot show` commands show the same figures in the
same words, so both build them here from the run's account (`BotProgress`). Qt-free on purpose: a
headless host installs no Qt, and the tab's formatter (`write_value`) lives behind it. The tab hands
the texts its own money writer; the commands use `plain_money` and `plain_price`, which call the same rules
(`core/vo/number_text.py`) as the tab's formatter.

A figure the run cannot give is unknown, never zero: `NO_VALUE` when there is no account to read,
`NO_PRICE_YET` when the total waits for a price the bot has not heard.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.core.vo.number_text import (
    money_text,
    price_text,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_progress import (
    BotProgress,
)

#: A figure this bot does not have yet: no fill, no inventory, no run.
NO_VALUE = "—"
#: The total needs the price the bot itself last heard, and it has heard none.
NO_PRICE_YET = "no price yet"

#: `BOT-202` - what the total is, said once for the Bots tab, `bot list` and `bot show`. It is the
#: bot's own account: the opening fee is in the cost of what is held and funding is added, and the
#: price is the close of the venue's 1-minute stream (the last trade), not the mark price.
TOTAL_PNL_BASIS = "net of fees and funding, at the bot's last trade price"
#: The Bots tab column and the `bot list` head; the fuller words are `TOTAL_PNL_BASIS`.
TOTAL_PNL_TITLE = "Total PnL (net)"
TOTAL_PNL_HEAD = TOTAL_PNL_TITLE.upper()
#: Said under `bot list`, so the head can stay short.
TOTAL_PNL_LEGEND = (
    f"{TOTAL_PNL_HEAD.removesuffix(' (NET)')} is {TOTAL_PNL_BASIS}. A Futures exchange's "
    "position PNL is gross of fees, excludes funding and uses its mark price, so it reads higher."
)
#: `bot show` on a position venue: Binance's number is `inventory x (mark - entry)`, and the bot
#: saves the last trade price, not the mark price, so it cannot rebuild that number.
EXCHANGE_UNREALISED_LABEL = "Unrealised, exchange basis"
NO_MARK_PRICE_SAVED = (
    "not available: the bot saves its last trade price, not the exchange's mark price"
)

type MoneyWriter = Callable[[Decimal], str]
type PriceWriter = Callable[[Decimal], str]


def plain_money(value: Decimal) -> str:
    """The Bots tab's money, written without Qt."""
    return money_text(float(value))


def plain_price(value: Decimal) -> str:
    """The Bots tab's price, written without Qt."""
    return price_text(float(value))


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
    #: What is held, at the bot's own last price; `None` without a price.
    unrealised: Decimal | None = None
    #: Whether the run holds base with a known cost (otherwise there is nothing to judge).
    holds_base: bool = False
    #: The last price the bot heard.
    mark_price: Decimal | None = None
    #: `BOT-202` - what the run's fills paid in commission, in the quote asset; `None` when not judged.
    commissions: Decimal | None = None
    #: `BOT-202` - funding settled on the position, signed (earned positive); `None` when not judged.
    funding: Decimal | None = None
    #: `BOT-202` - what the held base cost, the opening fee of a long included.
    cost: Decimal = Decimal(0)
    #: `BOT-202` - when the bot heard `mark_price` (its own clock); `None` before one.
    mark_price_at: datetime | None = None

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
            unrealised=pnl.unrealised if pnl is not None else None,
            holds_base=progress.inventory > 0 and progress.average_cost is not None,
            mark_price=progress.mark_price,
            commissions=pnl.commissions if pnl is not None else None,
            funding=pnl.funding if pnl is not None else None,
            cost=progress.cost,
            mark_price_at=progress.mark_price_at,
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


def unrealised_text(
    earnings: RunEarnings | None, money: MoneyWriter, price: PriceWriter
) -> str:
    """What is held, judged at the price the bot itself heard; kept apart from the profit."""
    if earnings is None or not earnings.holds_base:
        return NO_VALUE
    if earnings.unrealised is None or earnings.mark_price is None:
        return NO_PRICE_YET
    return f"{money(earnings.unrealised)} at {price(earnings.mark_price)}"


def exchange_unrealised_text(earnings: RunEarnings | None) -> str:
    """The Futures exchange's own position PNL (gross, at its mark price), which the bot cannot give.

    The saved run holds the last trade price only (`GridRuntime.mark_price` is the 1-minute close);
    the mark price is heard live and not saved, so this says so rather than quoting a figure at a
    price nobody heard.
    """
    if earnings is None or not earnings.holds_base:
        return NO_VALUE
    return NO_MARK_PRICE_SAVED
