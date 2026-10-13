"""Measure this machine's clock against the exchange's, for the host's health line (`EPIC-038D`).

The `run` host calls `measure()` before it publishes each snapshot (`IHealthProbe`).
It asks through `VenueReads.connection` - the read the `clock-skew` pre-flight check
makes - so the exchange is asked its time in one way, with the same timeout and the
same classification of what can go wrong. It reads only: no order is placed, tested
or simulated. A fresh scope per call, so every interval asks the exchange again.

An exchange that does not answer is not an error to raise: the skew is recorded as
unknown, which the health line shows as `na`, and the next interval asks again.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_health_probe import IHealthProbe
from Sagittarius_Elite_Warrior.src.core.contracts.preflight_scope import (
    PreflightScope,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.preflight.venue_reads import (
    VenueReads,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.health.clock_skew_recorder import (
    ClockSkewRecorder,
)

PROBE_NAME = "clock-skew"


class ClockSkewProbe(IHealthProbe):
    def __init__(self, reads: VenueReads, recorder: ClockSkewRecorder) -> None:
        self._reads = reads
        self._recorder = recorder

    @property
    def name(self) -> str:
        return PROBE_NAME

    def measure(self) -> None:
        scope = PreflightScope()
        for name in self._reads.named(scope):
            context = self._reads.context(name)
            if context is None:
                continue
            status = self._reads.connection(scope, name, context)
            self._recorder.record(name, status.server_time_skew_ms)
