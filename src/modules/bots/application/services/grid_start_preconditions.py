"""`EPIC-029E`, `EPIC-034H` — the steps of a Grid's start that touch the session (ADR §3.1, D6, D12).

Everything that can be known before an order is `BotReadinessReader`'s, asked
by the Start use case first (`EPIC-034H`): the venue, the account, the
parameters' verdicts, the other bots, the lease's holder and the budget's caps.
What remains here has a side effect or needs the exchange to answer, and is
the refusal a race may still produce, in the same words. Checked by the start,
**before** the `start` transition, so a refusal leaves the bot in DRAFT or
STOPPED with nothing to clean up. In order:

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

from datetime import datetime

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_budget import (
    bot_owner_id,
    grid_budget,
    grid_registration,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import Bot
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    GridParams,
    GridParamsError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_trading_ports import (
    IVenueTradingPorts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerBudgetCaps,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.session_block_words import (
    refusal_words,
)


class GridStartPreconditions:
    """Answers `None` when a Grid may start, else the refusal."""

    def __init__(self, ports: IVenueTradingPorts, caps: OwnerBudgetCaps) -> None:
        self._ports = ports
        self._caps = caps

    def check(self, bot: Bot, now: datetime) -> BotCommandResult | None:
        bot_id = bot.bot_id.value
        symbol = bot.definition.symbol
        session = self._ports.get(bot.definition.venue).trading_session
        try:
            params = GridParams.from_config(bot.definition.config)
        except GridParamsError as exc:
            # Readiness judged these parameters moments ago; an edit in between
            # is the race, and it is refused in the Design step's words.
            return _refused(BotRefusal.PARAMETERS_REFUSED, str(exc), bot_id)
        owner = bot_owner_id(bot_id)
        if not session.claim_symbol(symbol, owner):
            return _refused(
                BotRefusal.SYMBOL_LEASED, f"{symbol} is held by another owner", bot_id
            )
        # `EPIC-034C` — the same reconciliation every order path passes: it
        # opens the session when closed, answers at once when open, and
        # refuses with the switch's own words on a foreign position. After the
        # refusals that cost nothing (the verdict, the lease), so a refused
        # start opens nothing; a refusal gives the lease back.
        opened = session.ensure_ready()
        if not opened.ready:
            session.release_symbol(symbol, owner)
            return _refused(BotRefusal.VENUE_NOT_READY, refusal_words(opened), bot_id)
        registration = session.register_owner_budget(
            grid_registration(bot_id, symbol, now, grid_budget(params, self._caps))
        )
        if not registration.registered:
            session.release_symbol(symbol, owner)
            refusal = registration.refusal.value if registration.refusal else ""
            cap = f" ({registration.exceeded_cap})" if registration.exceeded_cap else ""
            return _refused(BotRefusal.BUDGET_REFUSED, f"{refusal}{cap}", bot_id)
        return None


def _refused(refusal: BotRefusal, message: str, bot_id: str) -> BotCommandResult:
    return BotCommandResult.refused(refusal, message, bot_id)
