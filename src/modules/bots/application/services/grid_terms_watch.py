"""`EPIC-035U` — a bot that holds orders asks, between orders, whether the exchange changed its terms.

The symbol's filters were read once per executor, from a catalog the venue keeps
for a day; a tick size, a step or a minimum notional that changed mid-run
surfaced as the exchange's `-1013` on some later order and the bot went to ERROR.
Every beat of the price watch (`IBotFacts.on_price_age_check`, a task on the
bot's own queue) the bot asks, once per `TERMS_REFRESH_EVERY_SECONDS`, for the
symbol's terms **from the exchange** (`LazyExchangeTerms.refresh`, the same read
`SymbolStatusGate` makes at each Start and Resume, so the status it holds is as
fresh as the filters).

  · A changed tick size, step size, market step or minimum notional halts the
    bot with `EXCHANGE_TERMS_CHANGED`, naming each old and new value; the guard
    takes the ladder off, and a resume plans it again on the new numbers.
  · A symbol the exchange no longer lists halts it with `SYMBOL_DELISTED`; a
    catalog that could not be reached (`SymbolCatalogUnreachableError`, also a
    `SymbolRulesUnavailableError`) is not a delisting.
  · A read that fails says nothing about the terms: it is logged and asked again
    at the next interval.
  · A changed fee only replaces the kept terms; it moves no level.

Asked in the states that hold orders or are laying them (`PRICE_STALENESS_HALTS`),
as the key probe is.
"""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_order_failure import (
    halt_with,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_run_context import (
    GridRunContext,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    ExchangeTerms,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    PRICE_STALENESS_HALTS,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.symbol_catalog_unreachable_error import (
    SymbolCatalogUnreachableError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.symbol_rules_unavailable_error import (
    SymbolRulesUnavailableError,
)

logger = logging.getLogger("App.Bots.GridExecutor")

#: How often a bot with orders asks the exchange for its symbol's terms: a
#: quarter of an hour, one `exchangeInfo` read, so a changed filter is found
#: well before the next order is built on it.
TERMS_REFRESH_EVERY_SECONDS: float = 900.0


def changed_filters(old: ExchangeTerms, new: ExchangeTerms) -> list[str]:
    """Each filter the ladder's numbers rest on that differs, "name old -> new"."""
    pairs = (
        ("tick size", old.tick_size, new.tick_size),
        ("step size", old.step_size, new.step_size),
        ("market step size", old.market_step, new.market_step),
        ("minimum notional", old.min_notional, new.min_notional),
    )
    return [
        f"{name} {before} -> {after}"
        for name, before, after in pairs
        if before != after
    ]


class GridTermsWatch:
    """Asks the exchange, on an interval, whether the bot's symbol terms changed."""

    def __init__(self, context: GridRunContext) -> None:
        self._context = context
        self._next_at = context.monotonic.seconds() + TERMS_REFRESH_EVERY_SECONDS

    def check(self) -> None:
        """One beat: refresh when the interval has passed and the bot holds orders."""
        state = self._context.state
        now = self._context.monotonic.seconds()
        if state.state not in PRICE_STALENESS_HALTS:
            self._next_at = now + TERMS_REFRESH_EVERY_SECONDS
            return
        if now < self._next_at:
            return
        self._next_at = now + TERMS_REFRESH_EVERY_SECONDS
        before = self._context.terms
        try:
            self._context.terms_source.refresh()
        except SymbolCatalogUnreachableError:
            # The fetch failed in transit: whether the symbol is still listed is
            # unknown, and a bad moment is no delisting. Asked again next interval.
            logger.warning(
                "Bot %s: the terms refresh could not reach the exchange; asking "
                "again [exchange-terms]",
                state.bot_id,
            )
            return
        except SymbolRulesUnavailableError:
            detail = f"the exchange no longer lists {state.bot.definition.symbol}"
            logger.warning(
                "Bot %s: %s; the ladder is taken off [exchange-terms]",
                state.bot_id,
                detail,
            )
            halt_with(state, GridReason.SYMBOL_DELISTED, detail)
            return
        # Converted at the seam: a read that raised (the exchange did not
        # answer) says nothing about the terms; it is logged and asked again.
        except Exception:
            logger.exception(
                "Bot %s: the terms refresh failed; asking again", state.bot_id
            )
            return
        changes = changed_filters(before, self._context.terms)
        if not changes:
            logger.debug("Bot %s: the exchange terms are unchanged", state.bot_id)
            return
        detail = (
            f"the exchange changed {state.bot.definition.symbol}'s filters: "
            f"{'; '.join(changes)}; resume to plan the ladder on the new numbers"
        )
        logger.warning("Bot %s: %s; halting [exchange-terms]", state.bot_id, detail)
        halt_with(state, GridReason.EXCHANGE_TERMS_CHANGED, detail)
