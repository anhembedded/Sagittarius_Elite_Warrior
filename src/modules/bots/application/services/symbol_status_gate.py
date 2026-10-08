"""`EPIC-035E` — a Grid places nothing on a symbol the exchange does not trade.

The symbol's status (TRADING, BREAK, HALT, CANCEL_ONLY …) was parsed and no one
read it: the bot kept submitting and the exchange kept refusing. `admits()` is the
question asked before a run lays orders, on the bot's worker:

  · **Start** (STARTING), **a confirmed resume** (HALTED, about to lay the new
    ladder) and **a resume from PAUSED** (about to place what the pause held).
  · It reads the terms **again** each time (`LazyExchangeTerms.refresh`): a run
    lives for days and its first reading is a stale answer to this question.
  · A status other than TRADING refuses, naming it (`SYMBOL_NOT_TRADING`): a
    start is refused (`start_refused`, nothing was sent), a bot that is PAUSED
    stays PAUSED with the status on its detail, a HALTED one stays HALTED. The
    user resumes again once the symbol trades; nothing resumes it for them.
  · A symbol the exchange no longer lists (`SymbolRulesUnavailableError`) is a
    delisting (`SYMBOL_DELISTED`): the bot halts, which takes its ladder off.

A stop is not asked: it only cancels, and every status lets an order be
cancelled, CANCEL_ONLY included.

@par What this does not read
The status is whatever trading's cached symbol catalog holds, which the venue
re-reads at most daily until `EPIC-035U` refreshes it. Until then a symbol that
went BREAK minutes ago reads TRADING here, and the exchange's own refusal of the
next order is what pauses the bot (`GridLadderPlacer`). `EPIC-035U` makes this
gate exact without changing it.
"""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_run_context import (
    GridRunContext,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleEvent,
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.symbol_rules_unavailable_error import (
    SymbolRulesUnavailableError,
)

logger = logging.getLogger("App.Bots.GridExecutor")


class SymbolStatusGate:
    """Answers whether the exchange accepts new orders on the bot's symbol."""

    def __init__(self, context: GridRunContext) -> None:
        self._context = context

    def admits(self) -> bool:
        """Whether orders may be placed now; when not, the bot says why."""
        state = self._context.state
        try:
            self._context.terms_source.refresh()
        except SymbolRulesUnavailableError:
            self._delisted(
                f"the exchange no longer lists {state.bot.definition.symbol}"
            )
            return False
        terms = self._context.terms
        if terms.trades:
            return True
        self._not_trading(
            f"{state.bot.definition.symbol} is {terms.symbol_status} on the exchange; "
            "resume once it is TRADING"
        )
        return False

    def _not_trading(self, detail: str) -> None:
        state = self._context.state
        logger.warning(
            "Bot %s: %s; nothing was placed [symbol-status]", state.bot_id, detail
        )
        if state.state is BotLifecycleState.STARTING:
            state.transition(
                BotLifecycleEvent.START_REFUSED, GridReason.SYMBOL_NOT_TRADING, detail
            )
        else:
            state.update(
                state.runtime.with_reason(GridReason.SYMBOL_NOT_TRADING, detail)
            )

    def _delisted(self, detail: str) -> None:
        state = self._context.state
        logger.warning(
            "Bot %s: %s; the ladder is taken off [symbol-status]", state.bot_id, detail
        )
        event = (
            BotLifecycleEvent.START_REFUSED
            if state.state is BotLifecycleState.STARTING
            else BotLifecycleEvent.HALT
        )
        if state.can(event):
            state.transition(event, GridReason.SYMBOL_DELISTED, detail)
        else:
            state.update(state.runtime.with_reason(GridReason.SYMBOL_DELISTED, detail))
