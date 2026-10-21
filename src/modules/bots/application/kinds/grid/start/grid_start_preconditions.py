"""`EPIC-029E`, `EPIC-034H` — the steps of a Grid's start that touch the session (ADR §3.1, D6, D12).

Everything that can be known before an order is `BotReadinessReader`'s, asked
by the Start use case first (`EPIC-034H`): the venue, the account, the
parameters' verdicts, the other bots, the lease's holder and the budget's caps.
What remains here has a side effect or needs the exchange to answer, and is
the refusal a race may still produce, in the same words. Checked by the start,
**before** the `start` transition, so a refusal leaves the bot in DRAFT or
STOPPED with nothing to clean up. In order:

  0. **Another owner's orders** (`BUG-259`): an order of the symbol that carries a bot tag no bot of
     this data root holds refuses the start before anything is claimed.
  1. **The lease**: the bot claims its symbol under its own owner id, so a
     manual order or a strategy on that symbol is refused from now on.
  2. **The order session** is open — Start opens it itself (`EPIC-034C`), after
     the refusals that cost nothing: the account is reconciled, and a position
     the app did not open refuses the start (the lease is given back).
  3. **The budget**: trading registers the bot's owner budget for this run
     (`run_started_at` is the moment the start is decided), deriving its
     inventory itself. A refused budget gives the lease back.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import datetime

from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_budget import (
    bot_owner_id,
    grid_registration,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_position_claims import (
    venue_position_claims,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.start.other_owner_orders import (
    other_owner_refusal,
    other_owner_tags,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.orders.order_session_opening import (
    order_session_refusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.venue.symbol_brackets import (
    BracketsUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_grid_budgets import (
    IGridBudgets,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    ExposureKind,
    exposure_limits_of,
    venue_profile_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import Bot
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    RESUME_PROPOSES_STATES,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_exposure_check import (
    exposure_refusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_kind import (
    GRID_MARKETS,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    GridParams,
    GridParamsError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_control_unavailable_error import (
    AccountControlUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_trading_ports import (
    IVenueTradingPorts,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

logger = logging.getLogger("App.Bots.GridExecutor")


class GridStartPreconditions:
    """Answers `None` when a Grid may start, else the refusal. A Resume from HALTED
    asks the one step it shares, the order session (`BUG-202`)."""

    def __init__(self, ports: IVenueTradingPorts, budgets: IGridBudgets) -> None:
        self._ports = ports
        self._budgets = budgets

    def open_session_for_resume(
        self, bot: Bot, venue_bots: Iterable[Bot]
    ) -> BotCommandResult | None:
        """A resume from HALTED proposes a ladder, which registers the budget a
        closed session refuses; a resume from RECOVERING (`BUG-204`) waits for the
        session a restart leaves closed. Open it, as Start does, or say why it will not.

        `BUG-250`: unlike Start, a resume passes the venue's position claims (`venue_bots` are
        every bot the store holds): the position a host stop left under the bot's protective
        stop is its own, and the exchange's tagged history says so."""
        held_bots = tuple(venue_bots)
        if bot.state in RESUME_PROPOSES_STATES:
            # A resume that lays a ladder is a start by another door (`BUG-259`); a RECOVERING
            # bot only reconciles its own orders and is not asked.
            other_owners = self._other_owners_refusal(bot, held_bots)
            if other_owners is not None:
                return other_owners
        venue = bot.definition.venue
        session = self._ports.get(venue).trading_session
        return order_session_refusal(
            session, bot.bot_id.value, venue_position_claims(venue, held_bots)
        )

    def check(
        self, bot: Bot, now: datetime, venue_bots: Iterable[Bot]
    ) -> BotCommandResult | None:
        """`venue_bots` are the bots this data root holds: their tags are not another owner's
        (`BUG-259`); the starting bot's own is always known. Required: a caller that left it out
        would call its own siblings foreign."""
        bot_id = bot.bot_id.value
        symbol = bot.definition.symbol
        session = self._ports.get(bot.definition.venue).trading_session
        try:
            params = GridParams.from_config(bot.definition.config)
        except GridParamsError as exc:
            # Readiness judged these parameters moments ago; an edit in between
            # is the race, and it is refused in the Design step's words.
            return _refused(BotRefusal.PARAMETERS_REFUSED, str(exc), bot_id)
        # The venue's profile is the last word on what a definition may ask of it, whatever
        # readiness said a moment ago.
        exposure = exposure_refusal(
            params, exposure_limits_of(bot.definition.venue, GRID_MARKETS)
        )
        if exposure is not None:
            return _refused(BotRefusal.PARAMETERS_REFUSED, exposure.reason, bot_id)
        # Read before the symbol is claimed: a read that fails then leaves no lease behind.
        try:
            budget = self._budgets.budget_of(bot.definition.venue, symbol, params)
        except (BracketsUnavailableError, AccountControlUnavailableError) as exc:
            return _refused(
                BotRefusal.VENUE_NOT_READY,
                f"The venue's limits for {symbol} could not be read: {exc}",
                bot_id,
            )
        other_owners = self._other_owners_refusal(bot, venue_bots)
        if other_owners is not None:
            return other_owners
        owner = bot_owner_id(bot_id)
        if not session.claim_symbol(symbol, owner):
            holder = session.lease_holder(symbol) or "another owner"
            return _refused(
                BotRefusal.SYMBOL_LEASED, f"{symbol} is held by {holder}", bot_id
            )
        # `EPIC-034C` — the same reconciliation every order path passes: it
        # opens the session when closed, answers at once when open, and
        # refuses with the switch's own words on a foreign position. After the
        # refusals that cost nothing (the verdict, the lease), so a refused
        # start opens nothing; a refusal gives the lease back.
        not_opened = order_session_refusal(session, bot_id)
        if not_opened is not None:
            session.release_symbol(symbol, owner)
            return not_opened
        registration = session.register_owner_budget(
            grid_registration(bot_id, symbol, now, budget)
        )
        if not registration.registered:
            session.release_symbol(symbol, owner)
            refusal = registration.refusal.value if registration.refusal else ""
            cap = f" ({registration.exceeded_cap})" if registration.exceeded_cap else ""
            return _refused(BotRefusal.BUDGET_REFUSED, f"{refusal}{cap}", bot_id)
        return None

    def _other_owners_refusal(
        self, bot: Bot, venue_bots: Iterable[Bot]
    ) -> BotCommandResult | None:
        """Another owner's tagged orders on the symbol refuse the start (`BUG-259`). Read before
        the symbol is claimed, so a refusal leaves nothing behind."""
        bot_id = bot.bot_id.value
        symbol = bot.definition.symbol
        activity = self._ports.get(bot.definition.venue).account_activity
        try:
            orders = activity.open_orders(symbol)
        except Exception as exc:  # noqa: BLE001 - converted at the seam into a refusal
            logger.warning(
                "Bot %s: the open orders of %s could not be read (%s) [other-owner]",
                bot_id,
                symbol,
                exc,
            )
            return _refused(
                BotRefusal.VENUE_NOT_READY,
                f"The open orders of {symbol} could not be read: {exc}",
                bot_id,
            )
        known = frozenset({bot_id, *(held.bot_id.value for held in venue_bots)})
        tags = other_owner_tags(orders, symbol, known)
        if not tags:
            return None
        message = other_owner_refusal(
            symbol, tags, nets_positions=_nets_positions(bot.definition.venue)
        )
        logger.warning("Bot %s: start refused, %s [other-owner]", bot_id, message)
        return _refused(BotRefusal.VENUE_NOT_READY, message, bot_id)


def _nets_positions(venue: TradingVenue) -> bool:
    """Whether `venue` holds one netted position per symbol: the venue profile decides, not the
    market (`test_only_the_venue_profile_decides_the_market`)."""
    profile = venue_profile_of(venue)
    return profile is not None and profile.exposure_kind is ExposureKind.POSITION


def _refused(refusal: BotRefusal, message: str, bot_id: str) -> BotCommandResult:
    return BotCommandResult.refused(refusal, message, bot_id)
