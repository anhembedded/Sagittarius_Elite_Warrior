"""`BOT-229` - the earnings of `bot show`, in the order that adds up, each with its basis.

@details Realised (every sell and buy-back against the average cost, net of fees), the grid cycles
that are part of it (each sell against its own paired buy), what is held and valued, the costs, and
the total with its sum. The figures are the booked ones, unchanged: only the words and the order are
new, and they are the Bots tab's (`run_earnings.py`).
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.core.contracts.report import (
    CellKind,
    ReportCell,
    ReportRow,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_status_report import (
    BotStatusEntry,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.run_earnings import (
    EARNINGS_BASIS,
    NO_VALUE,
    TOTAL_PNL_BASIS,
    RunEarnings,
    cycles_text,
    grid_profit_text,
    held_text,
    plain_money,
    plain_price,
    realised_text,
    total_pnl_text,
    unrealised_text,
)


def _row(label: str, value: str, kind: CellKind = CellKind.TEXT) -> ReportRow:
    return ReportRow((ReportCell(label, 12), ReportCell(value, kind=kind)))


def earnings_rows(bot: BotStatusEntry) -> tuple[ReportRow, ...]:
    """`BOT-229`: every earnings figure in the order that adds up, each with its basis: realised,
    the grid cycles that are part of it, what is held and valued, the costs, and the total with
    its sum. The figures are the booked ones, unchanged; only the words and the order are new."""
    earnings = bot.earnings
    return (
        _row("Realised", realised_text(earnings, plain_money), CellKind.MONEY),
        _row("Grid profit", grid_profit_text(earnings, plain_money), CellKind.MONEY),
        _row("Cycles", cycles_text(earnings)),
        _row("Held", held_text(earnings, plain_price)),
        _row("Unrealised", unrealised_text(earnings, plain_money, plain_price)),
        _row("Fees paid", _money_or_none(earnings.commissions if earnings else None)),
        _row("Funding", _money_or_none(earnings.funding if earnings else None)),
        _row("Total PnL", total_pnl_text(earnings, plain_money), CellKind.MONEY),
        _row("", earnings_sum_text(earnings)),
        _row("", f"({TOTAL_PNL_BASIS})"),
        _row("", f"({EARNINGS_BASIS})"),
    )


def _money_or_none(value: Decimal | None) -> str:
    return NO_VALUE if value is None else plain_money(value)


def earnings_sum_text(earnings: RunEarnings | None) -> str:
    """The total as the sum of the figures above it, so it visibly adds up."""
    if (
        earnings is None
        or earnings.realised is None
        or earnings.total_pnl is None
        or earnings.funding is None
    ):
        return ""
    unrealised = earnings.unrealised or Decimal(0)
    return (
        f"= realised {plain_money(earnings.realised)} + unrealised "
        f"{plain_money(unrealised)} + funding {plain_money(earnings.funding)}"
    )
