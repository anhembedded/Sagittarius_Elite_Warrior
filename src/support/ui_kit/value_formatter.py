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
| quantity under a `ratio_key` (a ratio: Sharpe, profit factor) | two decimals; infinity reads `∞` | `1.50`, `-63.24`, `∞` |
| quantity in a `BYTES_KEY` column | a size in bytes, in the largest unit it fills | `512 B`, `3.20 MB` |
| money or percent under a `signed_key` (a profit, a loss, a change) | an arrow and a sign; zero has neither | `▲ +12.50`, `▼ -9.00`, `▲ +1.25%`, `0.00` |
| text, side, status | as given | `LONG` |

A figure that says how a position or a bot is doing — a profit, a loss, a
change — carries its direction in the text as well as in its colour
(`ui-presentation-rule.md` §1: colour is never the only signal), so a column
or read-out row whose key is a `signed_key` writes an arrow and a sign.
Sorting is on the raw value and is unaffected.

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

Capability: Write a price, number, percentage or time for display
    Also: format, decimals, number to text, f-string, round
    Use: APP_VALUE_FORMATTER, write_value, signed_key
    User: src/modules/backtesting/ui/coordinators/data_sync_coordinator.py
    Status: stable
"""

from __future__ import annotations

import math
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Final

from Sagittarius_Elite_Warrior.src.core.vo.number_text import (
    MAX_DECIMALS,
    money_text,
    price_text,
    without_negative_zero,
    without_trailing_zeros,
)
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

#: The last part of the key of a column, or read-out row, that holds a ratio of
#: two figures (`ColumnKind.QUANTITY`): a profit factor, a Sharpe ratio. It has
#: no unit and a trader reads it to two decimals, not by magnitude; a profit
#: factor with no losing trade is infinite, which reads `∞`. A read-out has
#: several ratios and a key is unique in it, so a row says it with
#: `ratio_key("sharpe")`, which is `"sharpe.ratio"`.
RATIO_KEY: Final = "ratio"


def ratio_key(name: str) -> str:
    """The key of a read-out row named `name` that holds a ratio."""
    return f"{name}.{RATIO_KEY}"


def _is_ratio_key(key: str) -> bool:
    return key == RATIO_KEY or key.endswith(f".{RATIO_KEY}")


#: The last part of the key of a column, or read-out row, that holds a figure
#: whose direction matters: a profit, a loss, a change (`ColumnKind.MONEY` or
#: `ColumnKind.PERCENT`). It reads with an arrow and a sign: `▲ +12.50`,
#: `▼ -9.00`; a value that rounds to zero reads plain. A row says it with
#: `signed_key("pnl")`, which is `"pnl.signed"`.
SIGNED_KEY: Final = "signed"
_UP_ARROW: Final = "▲"
_DOWN_ARROW: Final = "▼"
_SIGNED_KINDS: Final = frozenset({ColumnKind.MONEY, ColumnKind.PERCENT})


def signed_key(name: str) -> str:
    """The key of a column, or read-out row, named `name` that holds a signed figure."""
    return f"{name}.{SIGNED_KEY}"


def _is_signed_key(key: str) -> bool:
    return key == SIGNED_KEY or key.endswith(f".{SIGNED_KEY}")


def _signed_text(text: str, number: float) -> str:
    """`text`, the figure written plainly, with its direction: an arrow, and a sign for a gain.

    The direction is the number's (`sign_tone` decides its colour on the same number), so a
    figure too small for its decimals keeps its arrow (`▲ +0.00`); only exactly zero has none."""
    if not math.isfinite(number):
        return text
    if number == 0:
        return text.lstrip("-")
    if number > 0:
        return f"{_UP_ARROW} +{text}"
    return f"{_DOWN_ARROW} {text}"


_INFINITY: Final = "∞"
_RATIO_DECIMALS: Final = 2
#: The key of a column, or read-out row, that holds a size in bytes
#: (`ColumnKind.QUANTITY`).
BYTES_KEY: Final = "bytes"

_BYTE_UNITS: Final = ("B", "KB", "MB", "GB", "TB")
_BYTES_PER_UNIT: Final = 1024

_TIMEFRAME_CODES: Final = {frame.to_seconds(): frame.value for frame in TimeFrame}

#: The kinds a symbol's filters quantize: a price in ticks, a quantity in
#: steps. Money keeps its two decimals, whatever the cell knows.
_SYMBOL_QUANTIZED: Final = frozenset({ColumnKind.PRICE, ColumnKind.QUANTITY})


def _quantized_text(value: float, precision: Precision) -> str:
    """`value` in whole quanta, with exactly the quantum's decimals."""
    return f"{precision.quantize(value):,.{precision.decimals}f}"


def _ratio_text(value: float) -> str:
    if math.isinf(value):
        return _INFINITY if value > 0 else f"-{_INFINITY}"
    return without_negative_zero(f"{value:,.{_RATIO_DECIMALS}f}")


def _bytes_text(count: float) -> str:
    """`count` bytes in the largest unit it fills: `512 B`, `3.20 MB`."""
    size = abs(count)
    unit = 0
    # Compare as it will be written: 1,048,575 bytes is 1,023.999 KB, which
    # two decimals would print as 1,024.00 KB rather than 1.00 MB.
    while round(size, 2) >= _BYTES_PER_UNIT and unit < len(_BYTE_UNITS) - 1:
        size /= _BYTES_PER_UNIT
        unit += 1
    if unit == 0:
        return f"{count:,.0f} {_BYTE_UNITS[0]}"
    return f"{math.copysign(size, count):,.2f} {_BYTE_UNITS[unit]}"


def _quantity_text(value: float) -> str:
    return without_negative_zero(without_trailing_zeros(f"{value:,.{MAX_DECIMALS}f}"))


def _number_text(kind: ColumnKind, number: float, context: FormatContext) -> str | None:
    """A number of a numeric `kind`, or `None` for the plain formatter's way."""
    if kind is ColumnKind.QUANTITY and _is_ratio_key(context.key):
        return _ratio_text(number)
    if (
        context.precision is not None
        and kind in _SYMBOL_QUANTIZED
        and math.isfinite(number)
    ):
        return _quantized_text(number, context.precision)
    if kind is ColumnKind.PRICE:
        return price_text(number)
    if kind is ColumnKind.QUANTITY:
        if context.key == BYTES_KEY and math.isfinite(number):
            return _bytes_text(number)
        return _quantity_text(number)
    if kind is ColumnKind.MONEY:
        return money_text(number)
    return None


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
        text = _number_text(kind, number, context)
        written = self._plain.format(kind, value, context) if text is None else text
        if kind in _SIGNED_KINDS and _is_signed_key(context.key):
            return _signed_text(written, number)
        return written


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


def write_value(
    kind: ColumnKind,
    value: DisplayValue,
    key: str = "",
    precision: Precision | None = None,
) -> str:
    """One value outside a table — a confirmation message, a status line —
    written exactly as a cell of that kind (and, for a key that has a rule of
    its own such as `TIMEFRAME_KEY`, that key) would write it; `precision` is
    the symbol's quantum when the caller knows it, as a column's would be."""
    return APP_VALUE_FORMATTER.format(
        kind, value, FormatContext(key or kind.value, precision)
    )
