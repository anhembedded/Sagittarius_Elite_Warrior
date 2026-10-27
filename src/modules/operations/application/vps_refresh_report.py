"""`EPIC-047H` — what the refresher tells the host's log, once per cause (`logging-rule.md`, tag `[vps-refresh]`).

@details A refresh that fails every two minutes must not write a line every two minutes: a failure is told once per
cause until a read succeeds (then once that it reads again), a venue that is too dear or unmeasured is told once, and
a summary line says how much weight the reads spent every fifty reads. The reason is a fixed phrase naming the part
that failed (`ExchangeBotReadRefresh`), never an exchange's own words, which may carry what a key or a URL carried.
"""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

logger = logging.getLogger("App.Operations.VpsRefresh")

#: A summary line every this many reads.
SUMMARY_EVERY_READS = 50


class RefreshReport:
    def __init__(self, ceiling_pct: float) -> None:
        self._ceiling_pct = ceiling_pct
        self._failing: dict[str, str] = {}
        self._unmeasured: set[TradingVenue] = set()
        self._too_dear: set[TradingVenue] = set()
        self._reads = 0
        self._spent = 0

    def read(self, key: str, kind: str, problem: str, read_at: object) -> None:
        """One read of `kind` for `key` (a bot id or a venue) ended: `problem` is empty when it was read."""
        slot = f"{key}/{kind}"
        if problem:
            if self._failing.get(slot) != problem:
                self._failing[slot] = problem
                logger.warning(
                    "[vps-refresh] %s %s: %s; the last good read is kept [read-failed]",
                    key,
                    kind,
                    problem,
                )
            return
        if self._failing.pop(slot, None) is not None:
            logger.info("[vps-refresh] %s %s: reading again", key, kind)
        logger.debug(
            "[vps-refresh] %s %s read at %s, ROUTINE priority", kind, key, read_at
        )

    def forget(self, bot_id: str) -> None:
        """The bot is gone: its failures are not worth remembering."""
        for key in [k for k in self._failing if k.startswith(f"{bot_id}/")]:
            del self._failing[key]

    def held(self, venue: TradingVenue, wait_s: float, reason: str) -> None:
        if reason == "too_dear" and venue not in self._too_dear:
            self._too_dear.add(venue)
            logger.warning(
                "[vps-refresh] %s: one read costs more than the weight ceiling allows; "
                "the refresh waits. Raise operations.vps_facts_weight_ceiling_pct (at most 10) or lower the load [ceiling]",
                venue.value,
            )
        else:
            logger.debug(
                "[vps-refresh] %s held for %.0f s (%s)", venue.value, wait_s, reason
            )

    def unmeasured(self, venue: TradingVenue) -> None:
        if venue not in self._unmeasured:
            self._unmeasured.add(venue)
            logger.warning(
                "[vps-refresh] %s: the venue's weight is not measured, so the ceiling cannot be held; nothing is read there [unmeasured]",
                venue.value,
            )

    def spent(self, weight: int) -> None:
        self._reads += 1
        self._spent += weight
        if self._reads % SUMMARY_EVERY_READS == 0:
            logger.info(
                "[vps-refresh] %d reads for the tab spent %d weight since the last line (ceiling %.0f %% of the venue's minute) [vps-refresh-summary]",
                self._reads,
                self._spent,
                self._ceiling_pct,
            )
            self._reads = self._spent = 0
