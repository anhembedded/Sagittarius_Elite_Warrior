"""`EPIC-029E` — the level table is ADR §3.2, cell by cell, plus `settled`.

`_EXPECTED` is typed from the ADR independently of the matrix, so a cell changed
in one and not the other fails here; every undeclared pair must raise.
"""

from __future__ import annotations

import itertools

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_level_fsm_matrix import (
    GRID_LEVEL_TRANSITIONS,
    InvalidLevelTransitionError,
    LevelEvent,
    LevelState,
    next_level_state,
)

S = LevelState
E = LevelEvent

_EXPECTED: dict[tuple[S, E], S] = {
    (S.EMPTY, E.PLACE): S.PLACING,
    (S.EMPTY, E.ADOPT): S.RESTING,
    (S.PLACING, E.ACCEPTED_OR_RESTING): S.RESTING,
    (S.PLACING, E.PARTIAL_FILL): S.PARTIAL,
    (S.PLACING, E.FULL_FILL): S.FILLED,
    (S.PLACING, E.ENDED): S.EMPTY,
    (S.RESTING, E.PARTIAL_FILL): S.PARTIAL,
    (S.RESTING, E.FULL_FILL): S.FILLED,
    (S.RESTING, E.ENDED): S.EMPTY,
    (S.PARTIAL, E.PARTIAL_FILL): S.PARTIAL,
    (S.PARTIAL, E.FULL_FILL): S.FILLED,
    (S.PARTIAL, E.ENDED): S.EMPTY,
    (S.FILLED, E.SETTLED): S.EMPTY,
}

_UNDECLARED = [pair for pair in itertools.product(S, E) if pair not in _EXPECTED]


def test_the_matrix_declares_exactly_the_adr_table() -> None:
    assert GRID_LEVEL_TRANSITIONS == _EXPECTED


@pytest.mark.parametrize(("pair", "target"), sorted(_EXPECTED.items()))
def test_every_declared_transition(pair: tuple[S, E], target: S) -> None:
    assert next_level_state(*pair) is target


@pytest.mark.parametrize("pair", _UNDECLARED)
def test_every_undeclared_transition_raises_naming_it(pair: tuple[S, E]) -> None:
    state, event = pair
    with pytest.raises(InvalidLevelTransitionError) as raised:
        next_level_state(state, event)
    assert raised.value.state is state
    assert raised.value.event is event
    assert state.value in str(raised.value)
    assert event.value in str(raised.value)
