"""`EPIC-029E` — what must hold before a Grid may start (ADR §3.1, D6, D12).

Checked by the start, **before** the `start` transition, so a refusal leaves the
bot in DRAFT or STOPPED with nothing to clean up. In order, each naming its
refusal:

  1. **The venue** is a Spot venue this app trades on.
  2. **The parameters** draw no REFUSED verdict at the current price.
  3. **The lease**: the bot claims its symbol under its own owner id, so a
     manual order or a strategy on that symbol is refused from now on.
  4. **The order session** is open — Start opens it itself (`EPIC-034C`), after
     the refusals that cost nothing: the account is reconciled, and a position
     the app did not open refuses the start (the lease is given back).
  5. **The budget**: trading registers the bot's owner budget for this run
     (`run_started_at` is the moment the start is decided), deriving its
     inventory itself. A refused budget gives the lease back.
"""

from __future__ import annotations

from datetime import datetime

from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_exchange_terms import (
    exchange_terms_for,
)
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
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    BotKindInputs,
    MarketView,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_evaluation import (
    evaluate_grid,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_thresholds import (
    GridThresholds,
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

    def __init__(
        self,
        ports: IVenueTradingPorts,
        caps: OwnerBudgetCaps,
        thresholds: GridThresholds,
    ) -> None:
        self._ports = ports
        self._caps = caps
        self._thresholds = thresholds

    def check(self, bot: Bot, now: datetime) -> BotCommandResult | None:
        bot_id = bot.bot_id.value
        venue = bot.definition.venue
        if (
            venue.market_type is not MarketType.SPOT
            or venue not in self._ports.enabled()
        ):
            return _refused(
                BotRefusal.VENUE_NOT_READY,
                f"{venue.value} is not a Spot venue this app trades on",
                bot_id,
            )
        ports = self._ports.get(venue)
        session = ports.trading_session
        symbol = bot.definition.symbol
        terms = exchange_terms_for(ports.order_entry_terms, symbol, self._caps)
        book = ports.order_entry_terms.best_bid_ask_for(symbol)
        price = (book.bid_price + book.ask_price) / 2
        evaluation = evaluate_grid(
            BotKindInputs(bot.definition.config, terms, MarketView(price)),
            self._thresholds,
        )
        refused = [verdict for verdict in evaluation.verdicts if verdict.refuses]
        if refused or evaluation.params is None:
            reasons = "; ".join(f"{v.code}: {v.reason}" for v in refused)
            return _refused(BotRefusal.PARAMETERS_REFUSED, reasons, bot_id)
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
            grid_registration(
                bot_id, symbol, now, grid_budget(evaluation.params, self._caps)
            )
        )
        if not registration.registered:
            session.release_symbol(symbol, owner)
            refusal = registration.refusal.value if registration.refusal else ""
            cap = f" ({registration.exceeded_cap})" if registration.exceeded_cap else ""
            return _refused(BotRefusal.BUDGET_REFUSED, f"{refusal}{cap}", bot_id)
        return None


def _refused(refusal: BotRefusal, message: str, bot_id: str) -> BotCommandResult:
    return BotCommandResult.refused(refusal, message, bot_id)
