"""`EPIC-039L` - one protective stop's lifecycle, its record, and how the runtime saves it.

@details The transition table is the design of `Docs/MODULES/bots/state-machines.md`, row for row;
a pair it does not list is refused. The record round-trips through the codec exactly, and a runtime
saved before the stop existed reads as one with none."""

from __future__ import annotations

from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_runtime_codec import (
    decode_runtime,
    encode_runtime,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridRuntime,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.protective_stop import (
    ProtectiveStop,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.protective_stop_fsm_matrix import (
    PROTECTIVE_STOP_TRANSITIONS,
    InvalidProtectiveStopTransitionError,
    ProtectiveStopEvent,
    ProtectiveStopState,
    next_protective_stop_state,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide

_S, _E = ProtectiveStopState, ProtectiveStopEvent
_STOP = ProtectiveStop("SEW-abc123-0123456789", OrderSide.SELL, Decimal("59000.5"))


def test_a_stop_is_cancelled_only_through_exposure_closed() -> None:
    """There is no other way to `CANCELLING`: the bot's own exposure being closed is the only
    reason a stop may go (decision D6)."""
    into_cancelling = [
        (state, event)
        for (state, event), to in PROTECTIVE_STOP_TRANSITIONS.items()
        if to is _S.CANCELLING
    ]

    assert into_cancelling == [(_S.STANDING, _E.EXPOSURE_CLOSED)]


@pytest.mark.parametrize(
    ("state", "event"),
    [
        (_S.INTENDED, _E.EXPOSURE_CLOSED),
        (_S.ABSENT, _E.EXPOSURE_CLOSED),
        (_S.TRIGGERED, _E.EXPOSURE_CLOSED),
        (_S.ENDED, _E.INTEND),
        (_S.STANDING, _E.ACCEPTED),
    ],
)
def test_a_move_the_table_does_not_list_is_refused(
    state: ProtectiveStopState, event: ProtectiveStopEvent
) -> None:
    with pytest.raises(InvalidProtectiveStopTransitionError):
        next_protective_stop_state(state, event)


def test_a_stop_walks_from_intended_to_ended_and_is_then_dropped() -> None:
    standing = _STOP.moved(_E.ACCEPTED)
    assert standing is not None and standing.state is _S.STANDING
    cancelling = standing.moved(_E.EXPOSURE_CLOSED)
    assert cancelling is not None and cancelling.state is _S.CANCELLING

    assert cancelling.moved(_E.CANCELLED) is None


def test_a_stop_missing_while_a_position_stands_is_dropped_so_it_is_placed_again() -> (
    None
):
    standing = _STOP.moved(_E.ACCEPTED)
    assert standing is not None

    assert standing.moved(_E.MISSING_WITH_POSITION) is None


def test_the_record_survives_the_codec_exactly() -> None:
    standing = _STOP.moved(_E.ACCEPTED)
    assert standing is not None
    runtime = GridRuntime(levels=()).with_stop(standing)

    assert decode_runtime(encode_runtime(runtime)).protective_stops == (standing,)


def test_a_runtime_saved_before_the_stop_existed_has_none() -> None:
    data = encode_runtime(GridRuntime(levels=()))
    assert "protective_stops" not in data

    assert decode_runtime(data).protective_stops == ()


def test_a_stop_replaces_the_record_of_its_own_id_and_none_other() -> None:
    other = ProtectiveStop("SEW-abc123-9999999999", OrderSide.BUY, Decimal(70000))
    runtime = GridRuntime(levels=()).with_stop(_STOP).with_stop(other)
    standing = _STOP.moved(_E.ACCEPTED)
    assert standing is not None

    updated = runtime.with_stop(standing)

    assert updated.protective_stops == (other, standing)
    assert updated.without_stop(other.client_order_id).protective_stops == (standing,)
