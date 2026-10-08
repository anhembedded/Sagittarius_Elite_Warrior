"""`EPIC-029E` / `EPIC-035C` — the stop of one Grid bot, as its worker runs it, on its worker.

Moves the bot to STOPPING (once), runs `GridStopSequence`, and hands the
outcome to `GridStopRetry`, which schedules the next attempt when the stop
waits on the exchange. Three callers reach it, all on the worker:

  · the user's Stop and a stop loss or take profit tick (`run`): from any state
    that declares `stop`; **in STOPPING it is a retry**, so the reason the stop
    began with stays (a stop loss is not rewritten as the user's click) and the
    retry rounds start over;
  · a scheduled retry (`GridStopRetry` calls back into `_retry`);
  · trading enabled while STOPPING (`after_switch_on`): the wait on the order
    session is over.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import replace
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_run_context import (
    GridRunContext,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_stop_retry import (
    GridStopRetry,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_stop_sequence import (
    GridStopSequence,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    BaseHandling,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_retry_scheduler import (
    IBotRetryScheduler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleEvent,
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)

logger = logging.getLogger("App.Bots.GridExecutor")


class GridStopper:
    """Stops a Grid, and retries the stop while it waits on the exchange."""

    def __init__(
        self,
        context: GridRunContext,
        retries: IBotRetryScheduler,
        post: Callable[[str, Callable[[], None]], None],
        price: Callable[[], Decimal],
    ) -> None:
        self._context = context
        self._price = price
        self._sequence = GridStopSequence(context)
        self._retry = GridStopRetry(context, retries, post)

    def run(self, base: BaseHandling, reason: GridReason, detail: str = "") -> None:
        state = self._context.state
        if state.state is not BotLifecycleState.STOPPING:
            if not state.can(BotLifecycleEvent.STOP):
                logger.info(
                    "Bot %s: stop ignored in %s", state.bot_id, state.state.value
                )
                return
            state.transition(BotLifecycleEvent.STOP, reason, detail or reason.value)
        sell = base is BaseHandling.SELL_AT_MARKET
        state.update(replace(state.runtime, sell_base_on_stop=sell))
        self._retry.begin_round()
        self._attempt(base)

    def after_switch_on(self) -> None:
        """Trading came back while STOPPING: run the stop the user chose."""
        self._retry.begin_round()
        self._rerun()

    def _attempt(self, base: BaseHandling) -> None:
        progress = self._sequence.run(base, self._price())
        self._retry.settle(progress, self._rerun)

    def _rerun(self) -> None:
        sell = self._context.state.runtime.sell_base_on_stop
        self._attempt(BaseHandling.SELL_AT_MARKET if sell else BaseHandling.KEEP)
