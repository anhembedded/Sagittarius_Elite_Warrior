"""`EPIC-039L` — one protective stop's lifecycle, declared in one place (decision D5, D6, D8).

A Futures Grid's exchange-side stop has a life of its own. The record of it is saved **before**
the request is sent, and the request is resolved by reading the order by its client id, so a
crash or a lost answer never leaves a stop nobody knows about. It is cancelled only once the
bot's own exposure is closed. Every change of its state is a row of
`PROTECTIVE_STOP_TRANSITIONS`; nothing else sets it (`code/quality.md` §3, FSM cohesion).

  · `intend` — the account position is non-zero and the plan has a stop-loss price: the id and
    the trigger price are saved (ABSENT → INTENDED);
  · `accepted` — the exchange has it, `NEW` (INTENDED → STANDING);
  · `rejected` — the exchange refused it (INTENDED → ABSENT); a position that stands is then
    closed, the bot is never left bare. A send with no answer leaves the record INTENDED: the
    next look finds the order among the open ones (`accepted`) or sends it again under the same
    id, which the exchange takes once it is not open;
  · `triggered` — it is on no open list, the account is flat and its status read by client id
    says the trigger traded (STANDING → TRIGGERED); the order itself is asked, never the
    history or the attribution of a fill;
  · `expired` — the same absence, but the exchange ended it without a fill, "canceled by the
    system" (STANDING → ENDED): nothing is left to protect, the next position gets a new one;
  · `exposure_closed` — the bot's own exposure is closed, so the stop may go (STANDING →
    CANCELLING);
  · `exposure_reopened` — the cancel did not finish and the position is back on its side, so the
    order that still stands goes on standing (CANCELLING → STANDING);
  · `cancelled`, `unknown_order` — the cancel is done, or the exchange has no such order any
    more (CANCELLING → ENDED);
  · `missing_with_position` — it is not among the open orders while a position stands (the
    exchange ended it, "canceled by the system", or it was cancelled by hand): it is placed
    again (STANDING → ABSENT);
  · `settled` — the position it closed is accounted for (TRIGGERED → ENDED).

`ENDED` is terminal: the record is dropped on the next save.
"""

from __future__ import annotations

from enum import Enum


class ProtectiveStopState(str, Enum):
    """Where one protective stop is. The values are what the store writes."""

    ABSENT = "absent"
    INTENDED = "intended"
    STANDING = "standing"
    CANCELLING = "cancelling"
    TRIGGERED = "triggered"
    ENDED = "ended"


class ProtectiveStopEvent(str, Enum):
    """What can happen to one protective stop."""

    INTEND = "intend"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    TRIGGERED = "triggered"
    EXPIRED = "expired"
    EXPOSURE_CLOSED = "exposure_closed"
    EXPOSURE_REOPENED = "exposure_reopened"
    CANCELLED = "cancelled"
    UNKNOWN_ORDER = "unknown_order"
    MISSING_WITH_POSITION = "missing_with_position"
    SETTLED = "settled"


class InvalidProtectiveStopTransitionError(ValueError):
    """The table declares no transition for this state and event."""

    def __init__(self, state: ProtectiveStopState, event: ProtectiveStopEvent) -> None:
        super().__init__(
            f"A protective stop in {state.value} cannot take {event.value!r}"
        )
        self.state = state
        self.event = event


_S = ProtectiveStopState
_E = ProtectiveStopEvent

#: (current state, event) -> next state, row by row as the module is designed
#: (`Docs/MODULES/bots/state-machines.md`).
PROTECTIVE_STOP_TRANSITIONS: dict[
    tuple[ProtectiveStopState, ProtectiveStopEvent], ProtectiveStopState
] = {
    (_S.ABSENT, _E.INTEND): _S.INTENDED,
    (_S.INTENDED, _E.ACCEPTED): _S.STANDING,
    (_S.INTENDED, _E.REJECTED): _S.ABSENT,
    (_S.STANDING, _E.TRIGGERED): _S.TRIGGERED,
    (_S.STANDING, _E.EXPIRED): _S.ENDED,
    (_S.STANDING, _E.EXPOSURE_CLOSED): _S.CANCELLING,
    (_S.STANDING, _E.MISSING_WITH_POSITION): _S.ABSENT,
    (_S.CANCELLING, _E.EXPOSURE_REOPENED): _S.STANDING,
    (_S.CANCELLING, _E.CANCELLED): _S.ENDED,
    (_S.CANCELLING, _E.UNKNOWN_ORDER): _S.ENDED,
    (_S.TRIGGERED, _E.SETTLED): _S.ENDED,
}


def next_protective_stop_state(
    state: ProtectiveStopState, event: ProtectiveStopEvent
) -> ProtectiveStopState:
    """The table's cell for `(state, event)`.

    @raise InvalidProtectiveStopTransitionError The table declares no such transition.
    """
    try:
        return PROTECTIVE_STOP_TRANSITIONS[(state, event)]
    except KeyError:
        raise InvalidProtectiveStopTransitionError(state, event) from None
