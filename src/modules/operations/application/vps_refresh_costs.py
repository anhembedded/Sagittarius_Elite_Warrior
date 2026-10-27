"""`EPIC-047H` — what a read of the exchange for the VPS tab costs in weight: a planning figure, then what was seen.

@details The ceiling is enforced on the weight the exchange reports (the used-weight header, read
through `IVenueWeightMeter`), not on an estimate (decision record 2026-10-27, D4, §4a): a read is
measured as the header's rise around it. The IP's total includes the bots' own requests, so the
rise can only over-state what the refresh spent, which is the safe error. Where the header was not
seen to move, nothing is claimed beyond the planning figure.

The planning figures are what a read is assumed to cost *before* it is measured, and the floor of
every later estimate: an observation may raise the expected cost of a kind but never lower it below
the figure, because a quiet minute under-measures. They are the weights of the real chain, read off the
composed host over the fake exchange that charges what Binance documents (`EPIC-047H`, "Step one" and its
implementation notes): a warm facts read is 20 (account 5, `symbolConfig` 5, `positionRisk` 5, orders 2,
brackets 1, session 2), the first read after a start 81 (the position mode and the Multi-Assets mode, 30
each) and 50 whenever the Multi-Assets mode has aged past its five minutes; the planner inputs 25 (the fee
read is 20); the fills 10 a window of seven days on Futures (two history endpoints of 5).

**An observation is a median, not a maximum.** One dear read (the cold one) must not become the cost of
every read after it: a cost above the ceiling is a read that can never go, and nothing would then ever
re-measure it. The expected cost rises only when the *median* of the last `OBSERVATIONS_KEPT` reads of the
kind does, and only once `MIN_OBSERVATIONS` have been seen. Where the median still lands above the ceiling
(a busy stretch, or a ceiling lowered by setting), the refresher calls `forget`: the kind is tried again at
its planning figure and re-measured. A planning figure that alone exceeds the ceiling stays held, and is logged.
"""

from __future__ import annotations

from collections import deque
from enum import Enum

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.weight_reading import (
    WeightReading,
)

#: How many recent observations of one kind the expected cost is taken over.
OBSERVATIONS_KEPT = 5
#: Reads of a kind seen before its observations count towards the expected cost.
MIN_OBSERVATIONS = 3
_MINUTE_S = 60


class ReadKind(Enum):
    """One read of the exchange, the unit the ceiling is charged in: each is under any allowed ceiling's room."""

    #: One bot's exchange facts.
    FACTS = "facts"
    #: One bot's planner inputs (the fee read is the dear part: 20 weight on both markets).
    PLANNER = "planner"
    #: One bot's fills: 10 weight a seven-day window on Futures, 20 a day on Spot; three Futures windows assumed.
    FILLS = "fills"
    #: A venue's exchange info and the filters of its bots' symbols.
    STATIC = "static"
    #: The candle store of a bot's symbol, brought up to now for each pinned timeframe (a backfill).
    CANDLES = "candles"


#: Weight assumed for a read of each kind before one has been measured.
PLANNING_WEIGHT: dict[ReadKind, int] = {
    ReadKind.FACTS: 20,
    ReadKind.PLANNER: 25,
    ReadKind.FILLS: 30,
    ReadKind.STATIC: 5,
    ReadKind.CANDLES: 50,
}

#: Reads the venue's call policy does not see, so the header cannot measure them: `market_data`'s own REST client
#: fetches the candles (assumption A4, `EPIC-047H` "Step one"). They are charged their planning figure, which is
#: five syncs of one request each at a conservative 10 weight (the documented kline weight is 5 for up to 1 000 rows).
UNMEASURED_KINDS = frozenset({ReadKind.CANDLES})


def measured_weight(before: WeightReading, after: WeightReading, planning: int) -> int:
    """The weight the venue's header says was spent between two readings of it.

    Unseen header: the planning figure. No answer seen in between (every read came from a cache): 0.
    A minute boundary crossed: the whole of the new minute's used weight, an over-statement."""
    if before.used is None or before.seen_at is None:
        return planning if after.used is None else after.used
    if after.used is None or after.seen_at is None:
        return planning
    if after.seen_at == before.seen_at:
        return 0
    if int(after.seen_at // _MINUTE_S) != int(before.seen_at // _MINUTE_S):
        return after.used
    return max(after.used - before.used, 0)


class ExpectedCosts:
    """The weight the next read of each kind is expected to cost: its planning figure, or the median of its latest observations if that is more."""

    def __init__(self) -> None:
        self._seen: dict[ReadKind, deque[int]] = {
            kind: deque(maxlen=OBSERVATIONS_KEPT) for kind in ReadKind
        }

    def expected(self, kind: ReadKind) -> int:
        seen = sorted(self._seen[kind])
        typical = seen[len(seen) // 2] if len(seen) >= MIN_OBSERVATIONS else 0
        return max(PLANNING_WEIGHT[kind], typical)

    def observe(self, kind: ReadKind, weight: int) -> None:
        self._seen[kind].append(weight)

    def forget(self, kind: ReadKind) -> None:
        """Drop what was seen of `kind`: its expected cost falls back to the planning figure, so a read held
        as too dear on a busy stretch's measurements is tried again and measured afresh."""
        self._seen[kind].clear()
