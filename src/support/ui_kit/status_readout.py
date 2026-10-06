"""A one-row read-out for the status bar (`EPIC-033N`).

The Engine's `ReadoutForm` is a `QFormLayout` whose default contents margins
are the style's panel margins (11 px each side under Fusion), which make a
status bar twice as tall as its labels. A status bar item sits in a bar that
already supplies its own spacing, so this one has none of its own: the row's
title and value are the height of an ordinary status bar label."""

from __future__ import annotations

from collections.abc import Sequence

from Sagittarius_Elite_Warrior.src.support.ui_kit.value_formatter import (
    APP_VALUE_FORMATTER,
)
from sagittarius_engine.extensions.pyside_mvc.workbench import (
    ColumnSpec,
    ReadoutForm,
)


def status_readout(specs: Sequence[ColumnSpec]) -> ReadoutForm:
    """A `ReadoutForm` of `specs`, written by the application's formatter, with
    no margin around its rows."""
    form = ReadoutForm(specs, APP_VALUE_FORMATTER)
    layout = form.layout()
    if layout is None:
        raise TypeError("the Engine's ReadoutForm lays its rows out in a layout")
    layout.setContentsMargins(0, 0, 0, 0)
    return form
