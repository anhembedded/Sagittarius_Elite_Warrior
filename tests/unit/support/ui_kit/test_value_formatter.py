"""`AppValueFormatter`: one way to write each kind of value (`EPIC-033N`).

Boundary values per kind: zero, negative, sub-unit, very large, and `None`.
"""

from datetime import UTC, datetime, timedelta

import pytest
from Sagittarius_Elite_Warrior.src.support.ui_kit.value_formatter import (
    TIMEFRAME_KEY,
    AppValueFormatter,
)
from sagittarius_engine.extensions.pyside_mvc.workbench import (
    ColumnKind,
    FormatContext,
)

_CONTEXT = FormatContext("cell")


def _text(kind: ColumnKind, value: object, time_zone: str = "UTC") -> str:
    return AppValueFormatter(time_zone).format(kind, value, _CONTEXT)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (64250.1, "64,250.10"),
        (1000.0, "1,000.00"),
        (999.99999, "1,000.0000"),
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
    [(1250.0, "1,250"), (0.0015, "0.0015"), (0.0, "0"), (2, "2"), (1e-9, "0")],
)
def test_a_quantity_drops_trailing_zeros(value, expected):
    assert _text(ColumnKind.QUANTITY, value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [(1234.567, "1,234.57"), (-9.0, "-9.00"), (0.0, "0.00"), (1e9, "1,000,000,000.00")],
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
