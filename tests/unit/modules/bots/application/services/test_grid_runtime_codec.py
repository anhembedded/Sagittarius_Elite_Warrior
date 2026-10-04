"""`EPIC-029E` — a Grid runtime survives the store unchanged (ADR D4), and a
damaged one is refused naming the field, never guessed."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_runtime_codec import (
    GridRuntimeCodecError,
    decode_runtime,
    encode_runtime,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_reactions import (
    LadderRules,
    LevelEnd,
    LevelFill,
    on_end,
    on_fill,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.grid_runtime_builders import (
    PRICES,
    STEP,
    order_id,
    started_ladder,
)

AT = datetime(2026, 10, 4, 9, tzinfo=UTC)


def _busy_runtime():  # type: ignore[no-untyped-def]
    runtime = started_ladder()
    runtime = on_fill(
        runtime,
        LevelFill(order_id(0), PRICES[0], Decimal("0.4"), Decimal("0.0004")),
        STEP,
        hold=False,
    ).runtime
    runtime = on_fill(
        runtime, LevelFill(order_id(1), PRICES[1], Decimal(1)), STEP, hold=True
    ).runtime
    runtime = on_end(
        runtime, LevelEnd(order_id(3), AT), LadderRules(STEP, Decimal(5)), hold=True
    ).runtime
    return runtime.with_reason(GridReason.SWITCH_OFF, "Emergency Stop on SPOT_TESTNET")


def test_a_busy_runtime_round_trips_exactly() -> None:
    runtime = _busy_runtime()

    assert decode_runtime(encode_runtime(runtime)) == runtime


def test_money_is_written_as_text() -> None:
    encoded = encode_runtime(_busy_runtime())

    assert encoded["inventory"] == "1.3996"
    levels = encoded["levels"]
    assert isinstance(levels, list)
    first = levels[0]
    assert isinstance(first, dict)
    assert first["price"] == "100"


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("inventory", "lots", "inventory is not a number"),
        ("inventory", "NaN", "inventory is not a finite number"),
        ("completed_cycles", "1", "completed_cycles is not a whole number"),
        ("levels", None, "levels is not a list"),
        ("reason", "bored", "reason is not one of GridReason"),
    ],
)
def test_a_damaged_field_is_refused_by_name(
    field: str, value: object, message: str
) -> None:
    encoded = encode_runtime(_busy_runtime())
    encoded[field] = value  # type: ignore[assignment]

    with pytest.raises(GridRuntimeCodecError, match=message):
        decode_runtime(encoded)


def test_a_naive_end_time_is_refused() -> None:
    encoded = encode_runtime(_busy_runtime())
    levels = encoded["levels"]
    assert isinstance(levels, list)
    level = levels[3]
    assert isinstance(level, dict)
    level["ended_at"] = ["2026-10-04T09:00:00"]

    with pytest.raises(GridRuntimeCodecError, match="timezone-aware"):
        decode_runtime(encoded)
