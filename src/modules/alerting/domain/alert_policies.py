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


@dataclass(frozen=True, slots=True)
class EarlyWarningPolicy:
    """`EPIC-036B1`: when an early warning is raised and how soon it may be raised again.

    Chosen bounds, not measured rates (agent decisions the owner may veto, recorded in
    `DECISION_2026-10-20_early_warnings.md`). The liquidation distances themselves are the
    bot's (`FuturesGridThresholds`); this policy only keeps the warning from repeating.
    """

    #: A bot's liquidation warning is raised at most this often, so a mark price that crosses
    #: the line again after a return to safety is not a new message each time.
    liquidation_cooldown: timedelta = timedelta(minutes=10)
    #: A user-data stream not connected for this long is an outage worth a message; the bots
    #: halt at two minutes (`UserStreamLimits.down_limit`), so this is the notice before the
    #: halt, and the routine reconnect after the 24 h cut (seconds) stays silent.
    stream_down_grace: timedelta = timedelta(seconds=60)
    #: A venue's stream outage is told at most this often.
    stream_cooldown: timedelta = timedelta(minutes=10)


DEFAULT_EARLY_WARNINGS = EarlyWarningPolicy()


@dataclass(frozen=True, slots=True)
class PacingPolicy:
    """`EPIC-036C2`: how many messages a channel sends in a period, so it keeps under the
    platform's rate limit instead of learning it from a 429 (research 036 §1: a client that keeps
    getting 429 is banned by IP, and a ban loses every alert).

    The figures are the platforms' documented limits taken with a margin, not measured rates: an
    implementation constant the owner may change. A burst above them is not lost, only spread
    (a wait is not an attempt)."""

    max_sends: int
    per: timedelta

    def __post_init__(self) -> None:
        if self.max_sends < 1 or self.per <= timedelta(0):
            raise ValueError(
                "A pacing policy needs at least one send per positive period"
            )


#: Discord documents about 5 requests per 2 s per webhook; one fewer keeps a margin.
DISCORD_PACING = PacingPolicy(max_sends=4, per=timedelta(seconds=2))

#: Telegram asks bots to avoid more than one message per second in a chat.
TELEGRAM_PACING = PacingPolicy(max_sends=1, per=timedelta(seconds=1))
