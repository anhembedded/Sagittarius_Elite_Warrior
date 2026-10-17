"""`BUG-202` — a deliberate bot action opens the venue's order session, in one place.

@details The venue's order session closes by Emergency Stop and opens by a deliberate
action (`EPIC-034C`, `ITradingSession.ensure_ready`). Four bot-side actions open it,
each through this module and nowhere else: Start (`GridStartPreconditions`), a Resume
from HALTED (`BotRunner.resume`, whose proposal registers the budget the session
refuses while closed), a Resume from RECOVERING (the same call, `BUG-204`: the session a
restart leaves closed is what the bot waits for) and the headless
`run --resume-recovering` (`ResumeRecoveringForHostCommandHandler`) and the operator's `bot stop`
on a running host (`StopBotForOperatorCommandHandler`, `EPIC-038J`). They share the reconciliation, the refusal's
words and the log line: `order_session_refusal_words` is the primitive,
`order_session_refusal` its answer as a `BotCommandResult`. An automated caller (a
reconciliation, a stop retry) never asks: a late order must not undo an Emergency Stop.
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


def order_session_refusal_words(session: ITradingSession, subject: str) -> str | None:
    """Open the venue's order session if it is closed; `None` when it is open,
    else the refusal in the session's own words. `subject` names who asked, for
    the log ("Bot ab12cd", "Venue spot_testnet")."""
    opened = session.ensure_ready()
    if opened.ready:
        logger.info(
            "%s: order session open (already open: %s) [order-session]",
            subject,
            opened.already_open,
        )
        return None
    logger.info(
        "%s: order session not opened: %s [order-session]",
        subject,
        opened.block_reason,
    )
    return refusal_words(opened)


def order_session_refusal(
    session: ITradingSession, bot_id: str
) -> BotCommandResult | None:
    """The same, for a command on one bot: the refusal as a `VENUE_NOT_READY` result."""
    words = order_session_refusal_words(session, f"Bot {bot_id}")
    if words is None:
        return None
    return BotCommandResult.refused(BotRefusal.VENUE_NOT_READY, words, bot_id)
