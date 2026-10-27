"""`BUG-276` - the best price a Grid heard while it waited for its range and its trigger.

The entry is judged on samples (a mark read every few seconds on a position venue, the streamed
close on Spot), so a wick that touched the trigger between two of them leaves the bot waiting with
no trace. This keeps what the bot heard on the side its trigger wants - the lowest price for a bot
that wants a lower one, the highest for the other - and saves it with the record for the screen to
say. A bot with no trigger price keeps nothing: the screen shows the value beside a trigger only.
A restart or a resume starts from the value the record already holds, so the first price after it
cannot overwrite a low the bot saw before. It decides nothing: the gate and the entry (`GridRangeEntry`) are untouched.

The wick counts as the bar's extremes the bot observed while listening (`GridTickExtremes`,
`BUG-191`), not the ones from before it did. Touched only on the bot's worker.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_run_context import (
    GridRunContext,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.watch.grid_tick_extremes import (
    GridTickExtremes,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_price_tick import (
    PriceTick,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_entry_gate import (
    better_is_lower,
)

#: The most often an improved best price is written to the bot's record; a better one heard in
#: between is held and written on the next price after this.
WAITING_BEST_SAVE_SECONDS: float = 5.0


class GridWaitingBest:
    """Remembers, for one wait, the best price heard on the trigger's side."""

    def __init__(self, context: GridRunContext) -> None:
        self._context = context
        self._extremes = GridTickExtremes()
        self._best: Decimal | None = None
        self._seeded = False
        self._unsaved = False
        self._saved_at: float | None = None

    def note(self, tick: PriceTick) -> None:
        """A price arrived. Starts a new wait's memory on the first one after a wait began, and
        forgets everything once the bot no longer waits."""
        if self._context.state.state is not BotLifecycleState.AWAITING_RANGE:
            self._forget()
            return
        if self._context.params.trigger_price is None:
            return
        self._seed()
        low, high = self._extremes.observed(tick)
        candidate = low if better_is_lower(self._context.params) else high
        if self._best is None or self._beats(candidate, self._best):
            self._best = candidate
            self._unsaved = True
        if self._unsaved:
            self._save()

    def _seed(self) -> None:
        """Start a wait from what the record holds (a restart, a resume), once."""
        if not self._seeded:
            self._seeded = True
            self._best = self._context.state.runtime.waiting_best_price

    def _beats(self, candidate: Decimal, best: Decimal) -> bool:
        if better_is_lower(self._context.params):
            return candidate < best
        return candidate > best

    def _save(self) -> None:
        now = self._context.monotonic.seconds()
        if (
            self._saved_at is not None
            and now - self._saved_at < WAITING_BEST_SAVE_SECONDS
        ):
            return
        self._saved_at = now
        self._unsaved = False
        state = self._context.state
        state.update(replace(state.runtime, waiting_best_price=self._best))

    def _forget(self) -> None:
        self._extremes.reset()
        self._best = None
        self._seeded = False
        self._unsaved = False
        self._saved_at = None
