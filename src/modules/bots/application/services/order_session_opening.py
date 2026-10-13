"""`BUG-202` — a deliberate bot action opens the venue's order session, in one place.

@details The venue's order session closes by Emergency Stop and opens by a deliberate
action (`EPIC-034C`, `ITradingSession.ensure_ready`). Two bot actions trade without a
ladder in hand and so must open it: Start (`GridStartPreconditions`) and a Resume from
HALTED (`ResumeBotCommandHandler`, whose proposal registers the budget the session
refuses while closed). Both ask through `order_session_refusal`, so the reconciliation,
the refusal's words and the refusal's kind are the same for both. An automated caller
(a reconciliation, a stop retry) never asks: a late order must not undo an Emergency
Stop.
"""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_session import (
    ITradingSession,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.session_block_words import (
    refusal_words,
)

logger = logging.getLogger("App.Bots.OrderSession")


def order_session_refusal(
    session: ITradingSession, bot_id: str
) -> BotCommandResult | None:
    """Open the venue's order session if it is closed; `None` when it is open,
    else the refusal in the session's own words."""
    opened = session.ensure_ready()
    if opened.ready:
        logger.info(
            "Bot %s: order session open (already open: %s) [order-session]",
            bot_id,
            opened.already_open,
        )
        return None
    logger.info(
        "Bot %s: order session not opened: %s [order-session]",
        bot_id,
        opened.block_reason,
    )
    return BotCommandResult.refused(
        BotRefusal.VENUE_NOT_READY, refusal_words(opened), bot_id
    )
