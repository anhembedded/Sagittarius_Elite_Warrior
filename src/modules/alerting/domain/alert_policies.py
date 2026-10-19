"""The numbers the hub and the worker follow, in one place and injectable so a
test needs no sleep."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from Sagittarius_Elite_Warrior.src.modules.alerting.domain.severity import Severity


@dataclass(frozen=True, slots=True)
class NoisePolicy:
    """Design §7: how a flood is kept down."""

    critical_dedup_window: timedelta = timedelta(minutes=1)
    other_dedup_window: timedelta = timedelta(minutes=15)
    coalesce_window: timedelta = timedelta(seconds=10)
    #: A venue-down alert stops hiding its bots' alerts after this long, so a
    #: source that never clears it cannot silence a venue for good.
    inhibition_ttl: timedelta = timedelta(hours=1)

    def dedup_window(self, severity: Severity) -> timedelta:
        if severity is Severity.CRITICAL:
            return self.critical_dedup_window
        return self.other_dedup_window


@dataclass(frozen=True, slots=True)
class DeliveryPolicy:
    """Design §7 and decision N2: how a delivery is retried and when it ends."""

    max_attempts: int = 5
    backoff_base: timedelta = timedelta(seconds=5)
    backoff_cap: timedelta = timedelta(minutes=5)
    #: A CRITICAL whose channel asks for more than this fails over at once.
    failover_after: timedelta = timedelta(minutes=5)
    #: An older alert is marked expired, never sent late (N2).
    expiry: timedelta = timedelta(hours=24)
    #: Per channel; CRITICAL is admitted beyond it, never dropped.
    capacity: int = 200
    #: `BOT-189`: how many fill messages (`ORDER_FILLED`) may wait on one channel. Past it the
    #: oldest are dropped and one "N fill messages skipped" line says so, so a CRITICAL is not
    #: sent behind a day of fills. A chosen bound, not a measured rate.
    fill_backlog: int = 25
    #: Finished alerts older than this leave the history.
    retention: timedelta = timedelta(days=30)

    def backoff_after(self, attempts: int) -> timedelta:
        """The wait after the `attempts`-th failure: doubling, capped."""
        wait = self.backoff_base * (1 << max(attempts - 1, 0))
        return min(wait, self.backoff_cap)
