"""`AppValueFormatter` — how this application writes a value of each kind
(`EPIC-033N`).

The Engine decides *where* a value is formatted: one delegate for every table
cell (`configure_item_view`) and one read-out form (`ReadoutForm`), both
calling an `IValueFormatter`. This class decides *how*, once for the whole
application, so a price prints the same on the Watchlist, a desk and a
backtest report. Before it, each screen had its own helper
(`kline_inspector_table_model._format_price`, `position_row`'s f-strings,
`amount_text.format_amount`), and the same price printed with two decimals on
one screen and four on another.

| Kind | Written as | Example |
| :--- | :--- | :--- |
| price | decimals by magnitude: two from 1 000, four from 1, else up to eight with trailing zeros dropped | `64,250.10`, `3.1416`, `0.00001234` |
| quantity | up to eight decimals, trailing zeros dropped | `1,250`, `0.0015` |
| money | two decimals | `1,234.56`, `-9.00` |
| percent | two decimals and `%` | `12.50%` |
| timestamp (a `datetime`; a naive one is UTC) | `YYYY-MM-DD HH:MM:SS` in the display time zone | `2026-10-05 03:40:00` |
| duration | `h:mm:ss` | `1:05:00` |
| duration in a `TIMEFRAME_KEY` column | the timeframe's code | `15m`, `1h`, `1M` |
| quantity in a `BYTES_KEY` column | a size in bytes, in the largest unit it fills | `512 B`, `3.20 MB` |
| text, side, status | as given | `LONG` |

A size is a quantity of bytes, and the key says so as a timeframe's does:
units step by 1 024 (`KB`, `MB`, `GB`), the way the platform's file manager
writes them, two decimals above a byte.

A timeframe is a duration — it sorts by length, so `1m` comes before `15m`
before `1h` — but it reads as the code a trader knows; the column says so by
its key, which is what `FormatContext` is for. Numbers are grouped by
thousands; a value that rounds to zero reads `0`, never `-0`. A price below
half of 0.00000001 rounds to `0`: eight decimals is the finest any exchange
quotes. `None` is an empty cell: the value is
unknown, and a blank says so without a glyph to mistake for a number.

@par Precision per symbol
A price or a quantity whose cell knows its symbol's filters arrives with a
`FormatContext.precision` — the tick size or the step size, answered by the
table model per cell (`RowTableModel.SYMBOL_QUOTED`, the Engine's
`PRECISION_ROLE`). It is then rounded to that quantum and written with
exactly its decimals: `64,250.1` at a tick of 0.1, `0.015` at a step of
0.001, `3.14160` at a tick of 0.00001. Without one (filters not fetched yet, a
table whose rows carry no symbol) the magnitude rule above decides.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Final

from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.support.ui_kit.services.display_timezone_service import (
    DEFAULT_TIMEZONE,
    format_display_datetime,
)
from sagittarius_engine.extensions.pyside_mvc.workbench import (
    ColumnKind,
    DisplayValue,
    FormatContext,
    PlainValueFormatter,
    Precision,
)

#: The key of a column, or read-out row, that holds a timeframe as its length
#: in seconds (`ColumnKind.DURATION`).
TIMEFRAME_KEY: Final = "timeframe"

#: The key of a column, or read-out row, that holds a size in bytes
#: (`ColumnKind.QUANTITY`).
BYTES_KEY: Final = "bytes"

_BYTE_UNITS: Final = ("B", "KB", "MB", "GB", "TB")
_BYTES_PER_UNIT: Final = 1024

_TIMEFRAME_CODES: Final = {frame.to_seconds(): frame.value for frame in TimeFrame}

#: The kinds a symbol's filters quantize: a price in ticks, a quantity in
#: steps. Money keeps its two decimals, whatever the cell knows.
_SYMBOL_QUANTIZED: Final = frozenset({ColumnKind.PRICE, ColumnKind.QUANTITY})

_LARGE_PRICE: Final = 1_000
_UNIT_PRICE: Final = 1
_MAX_DECIMALS: Final = 8


def _without_trailing_zeros(text: str) -> str:
    return text.rstrip("0").rstrip(".") if "." in text else text


def _without_negative_zero(text: str) -> str:
    """`-0.00` is a value that rounded to zero; it reads as zero, unsigned."""
    return text[1:] if text.startswith("-") and set(text[1:]) <= set("0.,") else text


def _price_text(value: float) -> str:
    # A band is chosen by the value as the band below it would print it:
    # 999.99999 prints 1,000.0000 at four decimals, so it is a 1,000 price
    # and takes two; 0.99999999 still prints below 1 at eight, so it keeps them.
    if abs(round(value, 4)) >= _LARGE_PRICE:
        return _without_negative_zero(f"{value:,.2f}")
    if abs(round(value, _MAX_DECIMALS)) >= _UNIT_PRICE:
        return _without_negative_zero(f"{value:,.4f}")
    return _without_negative_zero(
        _without_trailing_zeros(f"{value:,.{_MAX_DECIMALS}f}")
    )


def _quantized_text(value: float, precision: Precision) -> str:
    """`value` in whole quanta, with exactly the quantum's decimals."""
    return f"{precision.quantize(value):,.{precision.decimals}f}"


def _bytes_text(count: float) -> str:
    """`count` bytes in the largest unit it fills: `512 B`, `3.20 MB`."""
    size = abs(count)
    unit = 0
    while size >= _BYTES_PER_UNIT and unit < len(_BYTE_UNITS) - 1:
        size /= _BYTES_PER_UNIT
        unit += 1
    if unit == 0:
        return f"{count:,.0f} {_BYTE_UNITS[0]}"
    return f"{math.copysign(size, count):,.2f} {_BYTE_UNITS[unit]}"


def _quantity_text(value: float) -> str:
    return _without_negative_zero(
        _without_trailing_zeros(f"{value:,.{_MAX_DECIMALS}f}")
    )


class AppValueFormatter:
    """The application's `IValueFormatter`; see the module docstring."""

    def __init__(self, time_zone: str = DEFAULT_TIMEZONE) -> None:
        self._time_zone = time_zone
        self._plain = PlainValueFormatter()

    def format(
        self, kind: ColumnKind, value: DisplayValue, context: FormatContext
    ) -> str:
        if value is None:
            return ""
        if isinstance(value, datetime):
            return format_display_datetime(value, tz_name=self._time_zone)
        if (
            kind is ColumnKind.DURATION
            and context.key == TIMEFRAME_KEY
            and isinstance(value, int | float)
            and int(value) in _TIMEFRAME_CODES
        ):
            return _TIMEFRAME_CODES[int(value)]
        if isinstance(value, str | timedelta) or not kind.is_numeric:
            return self._plain.format(kind, value, context)
        number = float(value)
        if (
            context.precision is not None
            and kind in _SYMBOL_QUANTIZED
            and math.isfinite(number)
        ):
            return _quantized_text(number, context.precision)
        if kind is ColumnKind.PRICE:
            return _price_text(number)
        if (
            kind is ColumnKind.QUANTITY
            and context.key == BYTES_KEY
            and math.isfinite(number)
        ):
            return _bytes_text(number)
        if kind is ColumnKind.QUANTITY:
            return _quantity_text(number)
        if kind is ColumnKind.MONEY:
            return _without_negative_zero(f"{number:,.2f}")
        return self._plain.format(kind, value, context)


#: The one instance every table and read-out of this application writes with.
APP_VALUE_FORMATTER: Final = AppValueFormatter()


class ZonedValueFormatter:
    """`AppValueFormatter` in a time zone its screen chooses and may change.

    The Backtest mode shows its trades in the display time zone the person
    picks (a view setting: data and runs are UTC). A table's delegate keeps
    the formatter it was configured with, so the zone is asked each time a
    value is written; the screen resets its model when the zone changes, and
    every cell is written again in the new one."""

    def __init__(self, time_zone: Callable[[], str]) -> None:
        self._time_zone = time_zone

    def format(
        self, kind: ColumnKind, value: DisplayValue, context: FormatContext
    ) -> str:
        return AppValueFormatter(self._time_zone()).format(kind, value, context)


def write_value(kind: ColumnKind, value: DisplayValue, key: str = "") -> str:
    """One value outside a table — a confirmation message, a status line —
    written exactly as a cell of that kind (and, for a key that has a rule of
    its own such as `TIMEFRAME_KEY`, that key) would write it."""
    return APP_VALUE_FORMATTER.format(kind, value, FormatContext(key or kind.value))
