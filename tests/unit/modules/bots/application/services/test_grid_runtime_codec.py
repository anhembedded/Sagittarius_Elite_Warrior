"""`EPIC-029E` — a Grid runtime survives the store unchanged (ADR D4), and a
damaged one is refused naming the field, never guessed."""

from __future__ import annotations

from dataclasses import replace
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


def test_the_earnings_fields_round_trip() -> None:
    """`EPIC-035M` — total realised, start and mark price, unpriced fees."""
    runtime = replace(
        _busy_runtime(),
        realised_total=Decimal("14.87"),
        start_price=Decimal(100),
        mark_price=Decimal("125.5"),
        mark_price_at=AT,
        unpriced_fees=2,
    )

    assert decode_runtime(encode_runtime(runtime)) == runtime


def test_a_file_written_before_the_earnings_fields_still_reads() -> None:
    """A bot stored by an earlier build has none of them: zero, no price, nothing
    unpriced, and the total is then judged on what is known."""
    encoded = encode_runtime(replace(_busy_runtime(), realised_profit=Decimal("9.5")))
    for field in (
        "realised_total",
        "start_price",
        "mark_price",
        "mark_price_at",
        "unpriced_fees",
    ):
        encoded.pop(field)

    decoded = decode_runtime(encoded)

    assert decoded.realised_total == decoded.realised_profit > 0, (
        "the grid profit already earned is a floor for the total, never above it"
    )
    assert decoded.start_price is None
    assert decoded.mark_price is None
    assert decoded.mark_price_at is None
    assert decoded.unpriced_fees == 0
