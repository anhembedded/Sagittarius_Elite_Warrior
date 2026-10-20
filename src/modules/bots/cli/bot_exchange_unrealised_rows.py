"""`BOT-202` - the row of `bot show` that says what the bot cannot tell of a Futures position.

A Futures exchange shows a position's PNL gross of fees, without funding and at its mark price. The
bot saves its last trade price, not the mark price, so it cannot rebuild that figure; the row says
so (`run_earnings.py` → `exchange_unrealised_text`) rather than print a number at a price nobody
heard. A venue that holds an inventory (Spot) has no such figure and gets no row.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.report import ReportCell, ReportRow
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_status_report import (
    BotStatusEntry,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.run_earnings import (
    EXCHANGE_UNREALISED_LABEL,
    exchange_unrealised_text,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    ExposureKind,
    venue_profile_of,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

#: The width of the label column, as the ladder's rows (their labels are as long).
_LABEL_WIDTH = 32


def exchange_unrealised_rows(bot: BotStatusEntry) -> tuple[ReportRow, ...]:
    """One row for a bot that holds a position; none for an inventory venue or an unknown venue."""
    try:
        profile = venue_profile_of(TradingVenue(bot.venue))
    except ValueError:
        return ()
    if profile is None or profile.exposure_kind is not ExposureKind.POSITION:
        return ()
    return (
        ReportRow(
            (
                ReportCell(EXCHANGE_UNREALISED_LABEL, _LABEL_WIDTH),
                ReportCell(exchange_unrealised_text(bot.earnings)),
            )
        ),
    )
