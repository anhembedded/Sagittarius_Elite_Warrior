"""`EPIC-026L` — the account-level loss cap (decision N3).

One figure per host, in the owner's quote asset. Every `SAMPLE_EVERY_SECONDS` the cap reads the
host's bots, adds up what they made or lost since 00:00 UTC (`LossCapLedger`) and, when the loss
reaches the figure, **trips**: the trip is recorded first, every bot is stopped through the Bots
tab's own Stop (`LossCapStopper`), and the owner is told (`AccountLossCapTrippedEvent`, CRITICAL).
A tripped cap stays tripped across a restart and a day roll-over until the owner acknowledges it
(`acknowledge`); while it is, no bot starts or resumes (`restart_refusal`, asked by the runner),
and a bot that gets going by a path that does not ask is stopped again by the next sample.

@par Failing closed
  · the cap cannot judge (the bots cannot be read, a bot file is refused, a bot that may hold
    risk has no result in the figure's quote asset) for `UNJUDGED_TRIP_AFTER` -> it trips;
  · its record exists and cannot be read -> it starts tripped (`RECORD_UNREADABLE`);
  · its record cannot be written -> it trips and stops anyway (the in-memory trip holds) and says
    so at ERROR: a restart would forget the trip until the next sample re-finds the loss.
  Unset figure = the cap is off and judges nothing; a trip that was recorded before the figure was
  removed still holds until acknowledged, so removing the figure is not an acknowledgement.

@par Threads
`sample` runs on the bots ticker's thread; `acknowledge` on the host's command thread;
`restart_refusal` and `status` on any caller's thread (the runner, the health publisher). One lock
guards the record; the reads, the stops and the publish happen outside it.

@par Extension cases
  · a drawdown percentage beside the amount - a second `loss_reached`-style test in
    `loss_cap_policy.py` and one more `LossCapTripReason`; the sample and the stop do not change;
  · a per-venue cap - one `AccountLossCap` per venue given its own sampler and record path.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.core.contracts.i_event_publisher import (
    IEventPublisher,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.loss_cap.loss_cap_sampler import (
    LossCapReading,
    LossCapSampler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.loss_cap.loss_cap_stopper import (
    LossCapStopper,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.account_loss_cap_tripped_event import (
    AccountLossCapTrippedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_clock import IBotClock
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_loss_cap_acknowledgement import (
    ILossCapAcknowledgement,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_loss_cap_hold import (
    ILossCapHold,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_loss_cap_status import (
    ILossCapStatus,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_loss_cap_store import (
    ILossCapStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.loss_cap_status import (
    LossCapStatus,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.loss_cap.loss_cap_figure import (
    LossCapFigure,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.loss_cap.loss_cap_ledger import (
    LossCapLedger,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.loss_cap.loss_cap_policy import (
    LossCapRecord,
    LossCapTrip,
    LossCapTripReason,
    loss_reached,
    unjudged_too_long,
)

logger = logging.getLogger("App.Bots.LossCap")

#: How often the host's bots are read and judged. Small beside a price move that matters to a
#: day's loss; the read is the status report, which `bot list` also reads.
SAMPLE_EVERY_SECONDS: float = 15.0

_ZERO = Decimal(0)


@dataclass(frozen=True, slots=True)
class LossCapParts:
    """What the cap reads, writes and uses, besides its figure and its record."""

    sampler: LossCapSampler
    stopper: LossCapStopper
    store: ILossCapStore
    events: IEventPublisher
    clock: IBotClock


class AccountLossCap(ILossCapHold, ILossCapStatus, ILossCapAcknowledgement):
    def __init__(
        self,
        parts: LossCapParts,
        figure: LossCapFigure | None,
        record: LossCapRecord,
        *,
        announce_restored_trip: bool = False,
    ) -> None:
        self._parts = parts
        self._figure = figure
        self._lock = threading.Lock()
        self._record = record
        self._unjudged_since: datetime | None = None
        self._unjudged = False
        self._write_failed = False
        #: A trip this process found rather than made (an unreadable record) is told at the
        #: first sample, because nobody was told when it happened.
        self._unannounced = announce_restored_trip and record.trip is not None

    # --- the two questions others ask ---

    def restart_refusal(self) -> str | None:
        with self._lock:
            trip = self._record.trip
        if trip is None:
            return None
        return (
            "The account-level loss cap is tripped "
            f"({_reason_words(trip)}): no bot starts or resumes until you acknowledge it with "
            "`main.py bot loss-cap-ack` on the running host."
        )

    def status(self) -> LossCapStatus:
        with self._lock:
            record, unjudged = self._record, self._unjudged
        trip = record.trip
        return LossCapStatus(
            figure=None if self._figure is None else self._figure.text(),
            day=record.ledger.day.isoformat(),
            day_pnl=record.ledger.day_pnl,
            tripped=trip is not None,
            trip_reason="" if trip is None else trip.reason.value,
            trip_detail="" if trip is None else trip.detail,
            unjudged=unjudged,
        )

    # --- the owner's acknowledgement ---

    def acknowledge(self) -> bool:
        """Clear a tripped cap; the day's loss so far is accepted and counting starts again from
        now. `False` when the cap was not tripped. Starts and resumes nothing."""
        with self._lock:
            if self._record.trip is None:
                return False
            ledger = self._record.ledger.rebased()
            self._record = LossCapRecord(ledger)
            self._unjudged_since = None
            self._unannounced = False
            record = self._record
        self._persist(record)
        logger.warning(
            "[loss-cap] acknowledged by the owner: bots may start again; the day's loss "
            "so far is accepted and counting starts again from now"
        )
        return True

    # --- the sample ---

    def sample(self) -> None:
        reading = self._parts.sampler.read()
        now = self._parts.clock.now()
        with self._lock:
            previous = self._record
            self._record = self._advanced(previous, reading, now)
            record = self._record
            unannounced = self._unannounced
            self._unannounced = False
            self._unjudged = reading.is_unjudged and self._figure is not None
        if record != previous:
            self._persist(record)
        trip = record.trip
        if trip is None:
            return
        stopping = 0
        try:
            stopping = self._stop_every_bot(reading)
        finally:
            # The owner is told even if the stops failed: the alert is the one thing that must go.
            if previous.trip is None or unannounced:
                self._announce(trip, stopping)

    # --- internals ---

    def _advanced(
        self, record: LossCapRecord, reading: LossCapReading, now: datetime
    ) -> LossCapRecord:
        if self._figure is None:
            return record
        today = now.date()
        ledger = (
            record.ledger if record.ledger.day == today else LossCapLedger.empty(today)
        )
        if not reading.failure:
            ledger = ledger.observe(reading.observations)
        self._unjudged_since = (
            (self._unjudged_since or now) if reading.is_unjudged else None
        )
        if record.trip is not None:
            return LossCapRecord(ledger, record.trip)
        return LossCapRecord(ledger, self._new_trip(ledger, reading, now, self._figure))

    def _new_trip(
        self,
        ledger: LossCapLedger,
        reading: LossCapReading,
        now: datetime,
        figure: LossCapFigure,
    ) -> LossCapTrip | None:
        loss = max(-ledger.day_pnl, _ZERO)
        if loss_reached(ledger.day_pnl, figure.amount):
            return LossCapTrip(
                LossCapTripReason.LOSS_REACHED,
                now,
                ledger.day,
                loss,
                figure.text(),
                f"the day's loss {loss:.2f} {figure.quote_asset} reached the cap of {figure.text()}",
            )
        if unjudged_too_long(self._unjudged_since, now):
            return LossCapTrip(
                LossCapTripReason.NOT_JUDGEABLE,
                now,
                ledger.day,
                loss,
                figure.text(),
                "the cap could not judge the bots for "
                f"{(now - (self._unjudged_since or now)).total_seconds():.0f} s: "
                f"{reading.why_unjudged()}",
            )
        return None

    def _stop_every_bot(self, reading: LossCapReading) -> int:
        if reading.failure:
            logger.error(
                "[loss-cap] tripped, but the bots could not be read (%s), so none was asked "
                "to stop; the next sample tries again",
                reading.failure,
            )
            return 0
        return self._parts.stopper.stop_all(reading.active)

    def _announce(self, trip: LossCapTrip, stopping: int) -> None:
        logger.critical(
            "[loss-cap] TRIPPED (%s): %s; %d bot(s) stopping; no bot starts until acknowledged",
            trip.reason.value,
            trip.detail,
            stopping,
        )
        self._parts.events.publish(
            AccountLossCapTrippedEvent(
                reason=trip.reason.value,
                figure=trip.figure,
                loss="" if trip.loss is None else f"{trip.loss:.2f}",
                detail=trip.detail,
                bots_stopped=stopping,
            )
        )

    def _persist(self, record: LossCapRecord) -> None:
        try:
            self._parts.store.write(record)
        except OSError as exc:
            if not self._write_failed or record.trip is not None:
                logger.error(
                    "[loss-cap] the record could not be written (%s)%s",
                    type(exc).__name__,
                    "; the trip holds in memory only and a restart would forget it"
                    if record.trip is not None
                    else "; the day's figures are kept in memory",
                )
            self._write_failed = True
            return
        self._write_failed = False


def _reason_words(trip: LossCapTrip) -> str:
    return f"{trip.detail}, {trip.at.strftime('%Y-%m-%d %H:%M')} UTC"
