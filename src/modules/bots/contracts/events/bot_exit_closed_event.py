"""`BOT-190` — an exit has closed the run's position and its last closing slice is booked.

The typed fact the `EXIT_CLOSED` alert is built on (`PRO-015` §2.3: "position closed, realized
loss"). The bot's state turns STOPPED before the closing market slices fill, and each slice is
booked later, so neither the status report nor `BotChangedEvent` can say when the result is final;
only the bot, after it booked the last slice, can.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sagittarius_engine.domain.base_event import BaseEvent


@dataclass
class BotExitClosedEvent(BaseEvent):
    """
    @brief Published once per exit, after the bot booked the closing slice that left no more than
    dust of the run's position, whatever the reason the stop began with.

    @details Kind-neutral and a pure notification: it is published after the booking and changes
    nothing the bot orders, cancels, sizes or confirms. `reason` is the stop's reason as
    `GridReason.value` spells it, so a consumer decides which stops it tells (an exit the owner
    asked for is a `user_stop`). The figures are the run's books right after that slice, fee
    included: `total_pnl` is the run's Total PnL (`pnl_summary`: realised plus what dust is left at
    the bot's last price plus funding), `None` while the bot has heard no price for dust it kept.
    `run_id` names the run (`bot_id` and the moment it started), so a consumer can tell an exit of
    one run from the next. Published from the bot's worker thread, so a consumer marshals itself.

    @par Not `frozen` - the same `BaseEvent` inheritance cost `BotChangedEvent` documents. Treat
    as read-only by convention.
    """

    bot_id: str
    run_id: str
    reason: str
    total_pnl: Decimal | None
    #: The run's profit from completed cycles only (`GridRuntime.realised_profit`).
    grid_profit: Decimal
    completed_cycles: int
    #: Fills whose fee could not be priced, so the total is short by them.
    unpriced_fees: int
    #: The asset the figures are in.
    quote_asset: str
