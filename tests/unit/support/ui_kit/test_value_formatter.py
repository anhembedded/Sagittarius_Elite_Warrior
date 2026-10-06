"""`AppValueFormatter`: one way to write each kind of value (`EPIC-033N`).

Boundary values per kind: zero, negative, sub-unit, very large, and `None`.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.support.ui_kit.value_formatter import (
    TIMEFRAME_KEY,
    AppValueFormatter,
)
from sagittarius_engine.extensions.pyside_mvc.workbench import (
    ColumnKind,
    FormatContext,
    Precision,
)

_CONTEXT = FormatContext("cell")


def _text(kind: ColumnKind, value: object, time_zone: str = "UTC") -> str:
    return AppValueFormatter(time_zone).format(kind, value, _CONTEXT)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (64250.1, "64,250.10"),
        (1000.0, "1,000.00"),
        (999.99999, "1,000.00"),
        (999.994, "999.9940"),
        (0.99999999, "0.99999999"),
        (-0.000000001, "0"),
        (1.0, "1.0000"),
        (3.14159265, "3.1416"),
        (0.99, "0.99"),
        (0.00001234, "0.00001234"),
        (0.0, "0"),
        (-1500.5, "-1,500.50"),
    ],
)
def test_a_price_takes_its_decimals_from_its_magnitude(value, expected):
    assert _text(ColumnKind.PRICE, value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (1250.0, "1,250"),
        (0.0015, "0.0015"),
        (0.0, "0"),
        (2, "2"),
        (1e-9, "0"),
        (-0.0, "0"),
        (-1e-9, "0"),
    ],
)
def test_a_quantity_drops_trailing_zeros(value, expected):
    assert _text(ColumnKind.QUANTITY, value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (1234.567, "1,234.57"),
        (-9.0, "-9.00"),
        (0.0, "0.00"),
        (-0.004, "0.00"),
        (1e9, "1,000,000,000.00"),
    ],
)
def test_money_has_two_decimals(value, expected):
    assert _text(ColumnKind.MONEY, value) == expected


def test_a_percent_has_two_decimals_and_a_sign_of_its_own():
    assert _text(ColumnKind.PERCENT, 12.5) == "12.50%"
    assert _text(ColumnKind.PERCENT, -0.125) == "-0.12%"


def test_a_timestamp_is_written_in_the_display_time_zone():
    moment = datetime(2026, 10, 5, 3, 40, tzinfo=UTC)
    assert _text(ColumnKind.TIMESTAMP, moment) == "2026-10-05 03:40:00"
    assert _text(ColumnKind.TIMESTAMP, moment, "Asia/Ho_Chi_Minh") == (
        "2026-10-05 10:40:00"
    )


def test_a_duration_is_hours_minutes_seconds():
    assert _text(ColumnKind.DURATION, timedelta(hours=1, minutes=5)) == "1:05:00"
    assert _text(ColumnKind.DURATION, 90.0) == "0:01:30"


def test_text_kinds_are_written_as_given_and_none_is_blank():
    assert _text(ColumnKind.SIDE, "LONG") == "LONG"
    assert _text(ColumnKind.TEXT, 42) == "42"
    for kind in ColumnKind:
        assert _text(kind, None) == ""


def test_a_timeframe_column_reads_as_its_code_and_sorts_by_its_length():
    formatter = AppValueFormatter()
    context = FormatContext(TIMEFRAME_KEY)

    assert formatter.format(ColumnKind.DURATION, 60, context) == "1m"
    assert formatter.format(ColumnKind.DURATION, 900, context) == "15m"
    assert formatter.format(ColumnKind.DURATION, 3600, context) == "1h"
    # A length no timeframe has is still a duration, never a made-up code.
    assert formatter.format(ColumnKind.DURATION, 90, context) == "0:01:30"
    # The same length in any other column is a plain duration.
    assert _text(ColumnKind.DURATION, 60) == "0:01:00"


def _quoted(kind: ColumnKind, value: object, quantum: str) -> str:
    context = FormatContext("cell", Precision(Decimal(quantum)))
    return AppValueFormatter().format(kind, value, context)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("value", "quantum", "expected"),
    [
        # A tick coarser than the magnitude rule's two decimals.
        (64250.1, "0.1", "64,250.1"),
        # Finer than its four: a five-decimal tick on a unit price.
        (3.14159265, "0.00001", "3.14159"),
        # Trailing zeros the tick asks for stay: the exchange quotes them.
        (2.5, "0.001", "2.500"),
        # Half a tick, half to even; just over half rounds up.
        (0.125, "0.01", "0.12"),
        (0.12500001, "0.01", "0.13"),
        # A tick that is not a power of ten, and one above one.
        (101.37, "0.05", "101.35"),
        (64253.0, "10", "64,250"),
        # Below half a tick is zero, never negative zero.
        (-0.004, "0.01", "0.00"),
        (-1500.55, "0.1", "-1,500.6"),
    ],
)
def test_a_price_with_its_symbols_tick_is_written_in_whole_ticks(
    value, quantum, expected
):
    assert _quoted(ColumnKind.PRICE, value, quantum) == expected


@pytest.mark.parametrize(
    ("value", "quantum", "expected"),
    [
        (0.0153, "0.001", "0.015"),
        (1250.0, "1", "1,250"),
        (1.0, "0.00001", "1.00000"),
        (0.0, "0.001", "0.000"),
    ],
)
def test_a_quantity_with_its_symbols_step_is_written_in_whole_steps(
    value, quantum, expected
):
    assert _quoted(ColumnKind.QUANTITY, value, quantum) == expected


def test_a_precision_leaves_money_percent_and_non_finite_values_to_their_rules():
    assert _quoted(ColumnKind.MONEY, 1234.567, "0.1") == "1,234.57"
    assert _quoted(ColumnKind.PERCENT, 12.5, "1") == "12.50%"
    assert _quoted(ColumnKind.PRICE, float("inf"), "0.01") == _text(
        ColumnKind.PRICE, float("inf")
    )
    assert _quoted(ColumnKind.PRICE, None, "0.01") == ""
