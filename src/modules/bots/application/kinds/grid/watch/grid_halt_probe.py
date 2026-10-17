"""`EPIC-042C` - how a Grid sees that a transient halt's cause has cleared (ADR 042 §2.2).

Two reasons are common to every bot and so recoverable on a Spot Grid today:

  · `price_feed_stale` - clear when a tick has been heard **since the bot began waiting** and the
    last one is younger than `RECOVERY_TICK_MAX_AGE_SECONDS`. A feed silent since the halt is not
    clear, and neither is one that ticks twice a minute;
  · `user_stream_down` - clear when the venue's user-data stream reports CONNECTED
    (`IUserStreamStatus`).

A code the probe does not know never clears (`knows`), so a reason added to a layer without a
probe waits and, after `stalled_after`, tells the owner; it never recovers on a guess.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_run_context import (
    GridRunContext,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_halt_condition_probe import (
    IHaltConditionProbe,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_user_stream_status import (
    IUserStreamStatus,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.price_freshness import (
    RECOVERY_TICK_MAX_AGE_SECONDS,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.halt_recovery_policy import (
    PRICE_FEED_STALE,
    USER_STREAM_DOWN,
    HaltCode,
)

_KNOWN: frozenset[HaltCode] = frozenset({PRICE_FEED_STALE, USER_STREAM_DOWN})


class GridHaltProbe(IHaltConditionProbe):
    """Reads one Grid's price age and its venue's stream."""

    def __init__(self, context: GridRunContext, streams: IUserStreamStatus) -> None:
        self._context = context
        self._streams = streams

    def knows(self, code: HaltCode) -> bool:
        return code in _KNOWN

    def is_clear(self, code: HaltCode, waiting_since: float) -> bool:
        if code == PRICE_FEED_STALE:
            return self._context.price_age.heard_since(
                waiting_since, RECOVERY_TICK_MAX_AGE_SECONDS
            )
        if code == USER_STREAM_DOWN:
            return self._streams.is_connected(self._context.state.bot.definition.venue)
        return False
