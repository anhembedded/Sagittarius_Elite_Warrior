"""`EPIC-026L` — the account-level loss cap tripped and every bot is being stopped.

Published once per trip, after the record that holds every bot down is written (or after the
write failed, which the log says). `alerting` turns it into a CRITICAL alert.
"""

from __future__ import annotations

from dataclasses import dataclass

from sagittarius_engine.domain.base_event import BaseEvent


@dataclass
class AccountLossCapTrippedEvent(BaseEvent):
    """
    @brief The cap tripped; the owner must acknowledge before any bot starts again.

    @details Published from the cap's sampling thread (or the thread that booted the module, for
    a record that could not be read).
    """

    #: `LossCapTripReason.value`.
    reason: str
    #: The configured figure as written, e.g. `"500 USDT"`; empty when none was set.
    figure: str
    #: The day's loss as a positive amount in the figure's quote asset; empty when unknown.
    loss: str
    #: The owner's sentence: what happened and what to do.
    detail: str
    #: How many bots were asked to stop by this trip.
    bots_stopped: int = 0
