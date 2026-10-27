"""`EPIC-047H` — one venue's budget for the host's reads for the VPS tab: its ledger, its costs, and when it may read again.

@details Weight is the venue's, shared by every bot on it, so the budget is per venue (the testnet
and the mainnet are two limits). `VenueBudget` answers one question at a time: *may a read of this
kind go now, and if not, for how long must everything on this venue wait?* The answer is the later
of three things: the gate's own pause (it is closed to routine requests from 70 % of the minute's
weight, and the exit reserve above it is never ours), the ceiling (`seconds_until_room`) and a hold
already running.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.modules.operations.application.vps_refresh_costs import (
    ExpectedCosts,
    ReadKind,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.vps_weight_ledger import (
    WeightLedger,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.weight_reading import (
    WeightReading,
)

_SECONDS_PER_MINUTE = 60.0
#: How long a venue waits when nothing can be measured or a single read can never fit.
BLOCKED_HOLD_S = 60.0


@dataclass(frozen=True, slots=True)
class Verdict:
    """`wait_s` is 0 when the read may go now."""

    wait_s: float
    #: Why it waits, for the log: `hold`, `gate`, `ceiling` or `too_dear`; empty when it may go.
    reason: str = ""

    @property
    def may_go(self) -> bool:
        return self.wait_s <= 0


class VenueBudget:
    def __init__(self, ceiling_pct: float) -> None:
        self._ceiling_pct = ceiling_pct
        self.ledger = WeightLedger()
        self.costs = ExpectedCosts()
        self._held_until = 0.0

    def ceiling_weight(self, reading: WeightReading) -> int:
        return int(reading.limit * self._ceiling_pct / 100)

    def judge(
        self, kind: ReadKind, reading: WeightReading, now: float, wall: float
    ) -> Verdict:
        """May a read of `kind` go now? Pure: it holds nothing; `hold` does."""
        if now < self._held_until:
            return Verdict(self._held_until - now, "hold")
        if not reading.routine_open:
            return Verdict(_until_next_minute(wall), "gate")
        need = self.costs.expected(kind)
        wait = self.ledger.seconds_until_room(need, self.ceiling_weight(reading), now)
        if math.isinf(wait):
            return Verdict(BLOCKED_HOLD_S, "too_dear")
        return Verdict(wait, "ceiling") if wait > 0 else Verdict(0.0)

    def hold(self, wait_s: float, now: float) -> None:
        """Nothing on this venue is read before `now + wait_s`."""
        self._held_until = max(self._held_until, now + wait_s)

    def pace(self, cost: int, reading: WeightReading, now: float) -> None:
        """Spread the ceiling evenly over the minute: after a read that cost `cost`, the next waits the share of
        the minute `cost` is of the ceiling. A read never follows another back to back, so a venue that was held
        (a closed gate, a full ledger) and opens again is read at the ceiling's even rate and not in a burst."""
        ceiling = self.ceiling_weight(reading)
        if cost > 0 and ceiling > 0:
            self.hold(
                min(cost / ceiling * _SECONDS_PER_MINUTE, _SECONDS_PER_MINUTE), now
            )

    @property
    def held_until(self) -> float:
        return self._held_until


def _until_next_minute(wall: float) -> float:
    """The gate closes to the end of the minute (`ExchangeCallPolicy.note_used_weight`); one second more is its own margin."""
    return _SECONDS_PER_MINUTE - (wall % _SECONDS_PER_MINUTE) + 1.0
