"""`BUG-202` — a deliberate bot action opens the venue's order session, in one place.

@details The venue's order session closes by Emergency Stop and opens by a deliberate
action (`EPIC-034C`, `ITradingSession.ensure_ready`). Five bot-side actions open it,
each through this module and nowhere else: Start (`GridStartPreconditions`), a Resume
from HALTED (`BotRunner.resume`, whose proposal registers the budget the session
refuses while closed), a Resume from RECOVERING (the same call, `BUG-204`: the session a
restart leaves closed is what the bot waits for), the headless operator's `bot stop` on a
running host (`StopBotForOperatorCommandHandler`, `EPIC-038J`) and the Bots screen's Stop
(`StopBotCommandHandler`, `BUG-274`); the headless `run --resume-recovering` sends each
RECOVERING bot its own Resume (`ResumeRecoveringForHostCommandHandler`). They share the
reconciliation, the refusal's words and the log line: `order_session_refusal_words` is the
primitive, `order_session_refusal` its answer as a `BotCommandResult` for a bot's Start or
Resume, `order_session_refusal_for_stop` the same for a Stop. An automated caller (a
reconciliation, a stop retry, the loss cap, the shutdown policy) never asks: a late order
must not undo an Emergency Stop.

The opening is announced as opened for the bot that asked (`BOT-183`), so it wakes no other bot.
A Stop is the exception (`BUG-274`): the session it opens is announced as opened for the person,
because a RECOVERING bot opened for itself reconciles and lays what it holds, a new real-money
order ahead of the Stop already queued behind it.

`BUG-250` — a Resume and a Stop pass the venue's position claims (`grid_position_claims`): a host
stop leaves a Futures bot's position under its protective stop, and the session a restart leaves
closed refused every position, the bot's own included. A Start passes none.
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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_position_claim import (
    OwnerPositionClaim,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.session_block_words import (
    refusal_words,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.session_opener import (
    OpenedByPerson,
    SessionOpener,
)

logger = logging.getLogger("App.Bots.OrderSession")


def order_session_refusal_words(
    session: ITradingSession,
    subject: str,
    opened_for: SessionOpener = None,
    claims: tuple[OwnerPositionClaim, ...] = (),
) -> str | None:
    """Open the venue's order session if it is closed; `None` when it is open,
    else the refusal in the session's own words. `subject` names who asked, for
    the log ("Bot ab12cd", "Venue spot_testnet"). `opened_for` is the bot the opening
    serves (`BOT-183`): the announcement names it, so the venue's other RECOVERING bots
    keep waiting for their own resume; `OpenedByPerson.PERSON` for a person's action that is no
    bot's (`BOT-197`); `None` only when no opener is known, which still wakes them. `claims`
    (`BUG-250`) are the venue's runs that may own a position the closed session would otherwise
    refuse: passed by a bot acting on its own run (a Resume, a Stop), never by a Start."""
    opened = session.ensure_ready(opened_for, claims)
    if opened.ready:
        logger.info(
            "%s: order session open (already open: %s) [order-session]",
            subject,
            opened.already_open,
        )
        return None
    logger.info(
        "%s: order session not opened: %s (%d position(s) not excused) [order-session]",
        subject,
        opened.block_reason,
        len(opened.unexplained_positions),
    )
    return refusal_words(opened)


def order_session_refusal(
    session: ITradingSession,
    bot_id: str,
    claims: tuple[OwnerPositionClaim, ...] = (),
) -> BotCommandResult | None:
    """The same, for a command on one bot: the refusal as a `VENUE_NOT_READY` result."""
    words = order_session_refusal_words(session, f"Bot {bot_id}", bot_id, claims)
    if words is None:
        return None
    return BotCommandResult.refused(BotRefusal.VENUE_NOT_READY, words, bot_id)


def order_session_refusal_for_stop(
    session: ITradingSession,
    bot_id: str,
    claims: tuple[OwnerPositionClaim, ...] = (),
) -> BotCommandResult | None:
    """`BUG-274` — the same, for a person's Stop: the opening is announced as opened for the
    person, so it wakes no bot, the stopped one included. Opened for the bot, a RECOVERING bot
    would reconcile and lay what it holds before the Stop already queued behind the opening
    cancels it."""
    words = order_session_refusal_words(
        session, f"Bot {bot_id}", OpenedByPerson.PERSON, claims
    )
    if words is None:
        return None
    return BotCommandResult.refused(BotRefusal.VENUE_NOT_READY, words, bot_id)
