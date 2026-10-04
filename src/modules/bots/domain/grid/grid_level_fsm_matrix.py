"""`EPIC-029E` — one Grid level's lifecycle, declared in one place (ADR D3, D10, §3.2).

Every change of a level's state is a row of `GRID_LEVEL_TRANSITIONS`; nothing
else sets it (`code/quality.md` §3, FSM cohesion). The live executor and the
backtest (`EPIC-029D`) share this table, so a fill means the same thing in both.

The ADR's columns, and the one this file adds:

  · `place` — the executor sends the level's order (EMPTY → PLACING);
  · `accepted_or_resting` — trading accepted it and it rests;
  · `partial_fill`, `full_fill` — a fill event; the executor accumulates the
    executed quantity per order (D10), so only the last one is `full_fill`;
  · `ended` — cancelled, expired or refused without filling whole. The level
    is EMPTY again; the runtime counts the end (two within a minute halt the
    bot, `LEVEL_KEEPS_ENDING`) and keeps any executed quantity as inventory;
  · `adopt` — reconciliation found an order carrying the bot's tag at this
    level that the saved state did not know (ADR §3.3 step 5);
  · `settled` **(added here)** — the ADR's prose: "FILLED emits the counter
    order one level away, and the level returns to EMPTY". The return is a
    transition too, so it is a column rather than an assignment.
"""

from __future__ import annotations

from enum import Enum


class LevelState(str, Enum):
    """Where one level is. The values are what the store writes."""

    EMPTY = "EMPTY"
    PLACING = "PLACING"
    RESTING = "RESTING"
    PARTIAL = "PARTIAL"
    FILLED = "FILLED"


class LevelEvent(str, Enum):
    """What can happen to one level (ADR §3.2, the column headers, plus `settled`)."""

    PLACE = "place"
    ACCEPTED_OR_RESTING = "accepted_or_resting"
    PARTIAL_FILL = "partial_fill"
    FULL_FILL = "full_fill"
    ENDED = "ended"
    ADOPT = "adopt"
    SETTLED = "settled"


class InvalidLevelTransitionError(ValueError):
    """The table declares no transition for this state and event."""

    def __init__(self, state: LevelState, event: LevelEvent) -> None:
        super().__init__(f"A level in {state.value} cannot take {event.value!r}")
        self.state = state
        self.event = event


_S = LevelState
_E = LevelEvent

#: (current state, event) -> next state. ADR §3.2, row by row, plus `settled`.
GRID_LEVEL_TRANSITIONS: dict[tuple[LevelState, LevelEvent], LevelState] = {
    (_S.EMPTY, _E.PLACE): _S.PLACING,
    (_S.EMPTY, _E.ADOPT): _S.RESTING,
    (_S.PLACING, _E.ACCEPTED_OR_RESTING): _S.RESTING,
    (_S.PLACING, _E.PARTIAL_FILL): _S.PARTIAL,
    (_S.PLACING, _E.FULL_FILL): _S.FILLED,
    (_S.PLACING, _E.ENDED): _S.EMPTY,
    (_S.RESTING, _E.PARTIAL_FILL): _S.PARTIAL,
    (_S.RESTING, _E.FULL_FILL): _S.FILLED,
    (_S.RESTING, _E.ENDED): _S.EMPTY,
    (_S.PARTIAL, _E.PARTIAL_FILL): _S.PARTIAL,
    (_S.PARTIAL, _E.FULL_FILL): _S.FILLED,
    (_S.PARTIAL, _E.ENDED): _S.EMPTY,
    (_S.FILLED, _E.SETTLED): _S.EMPTY,
}

#: The states in which a level has an order on the exchange.
HOLDS_ORDER: frozenset[LevelState] = frozenset({_S.PLACING, _S.RESTING, _S.PARTIAL})


def next_level_state(state: LevelState, event: LevelEvent) -> LevelState:
    """The table's cell for `(state, event)`.

    @raise InvalidLevelTransitionError The table declares no such transition.
    """
    try:
        return GRID_LEVEL_TRANSITIONS[(state, event)]
    except KeyError:
        raise InvalidLevelTransitionError(state, event) from None
