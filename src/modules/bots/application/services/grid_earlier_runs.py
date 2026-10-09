"""`BUG-196` — what a Grid's earlier runs left on the account.

@details A run counts only its own orders (ADR D6), so base a halted or stopped
run kept is neither sold by the new ladder nor in the bot's inventory. A Start
does not refuse for it (the owner may have kept it on purpose) and does not
carry it into the run (a hand-sale in between would make the bot believe it
holds what it does not); it asks trading how much the owner's earlier runs left,
capped by what the account still holds free, and records it on the run's
runtime, where the bot's figures show it. "Adopt into this run" is the extension
this record is the seam for.

A venue that does not answer leaves the figure at zero and says so in the log:
the start goes on, and nothing is claimed that was not read.
"""

from __future__ import annotations

import logging
from dataclasses import replace

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_budget import (
    bot_owner_id,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_run_context import (
    GridRunContext,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.earlier_runs_inventory import (
    EarlierRunsRequest,
)

logger = logging.getLogger("App.Bots.GridExecutor")


class GridEarlierRuns:
    """Records the base earlier runs left on the run that is starting."""

    def __init__(self, context: GridRunContext) -> None:
        self._context = context

    def record(self) -> None:
        state = self._context.state
        bot = state.bot
        run_started_at = bot.lifecycle.run_started_at
        if run_started_at is None:
            return
        answer = self._context.session.earlier_runs_inventory(
            EarlierRunsRequest(
                tag=bot.bot_id.value,
                symbol=bot.definition.symbol,
                base_asset=self._context.base_asset,
                since=bot.created_at,
                until=run_started_at,
            )
        )
        if not answer.is_known:
            logger.warning(
                "Bot %s: what earlier runs left is not known (%s); the start goes on "
                "[earlier-runs]",
                bot_owner_id(bot.bot_id.value),
                answer.unavailable,
            )
            return
        state.update(
            replace(
                state.runtime,
                earlier_runs_base=answer.quantity,
                earlier_runs_cost=answer.cost,
            )
        )
        if answer.is_left:
            logger.warning(
                "Bot %s: %s %s from earlier runs stays on the account and is not "
                "traded by this run (cost %s) [earlier-runs]",
                bot.bot_id.value,
                answer.quantity,
                self._context.base_asset,
                answer.cost,
            )
