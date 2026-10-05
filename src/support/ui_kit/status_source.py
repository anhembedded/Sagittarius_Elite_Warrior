"""A screen that puts state in the window's status bar (`EPIC-033H`).

HLD §11.2.2: the connection state is shown in the status bar as text, in
every mode, beside the venue. The status bar is the window's, and a mode is
built into it; a screen that knows a piece of such state offers the widget
that shows it, and the window adds each one to its status bar once, for every
mode. It is the shape `IOutputSource` gave the Output pane: the view offers,
the window places.

A `Protocol`: the implementers are views, `QWidget`s, and Shiboken forbids a
second `QObject`-derived base and conflicts with `ABCMeta`
(`architecture-rule.md` §2.1, reason (a)).

Plausible extensions, each a local change: a widget shown only while its own
mode shows (a mode id beside the widget; `WorkbenchShell.add_status_widget`
already takes one); run progress from Backtest (one more implementer).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from PySide6.QtWidgets import QWidget


@runtime_checkable
class IStatusSource(Protocol):
    """Offers widgets for the window's status bar, shown in every mode."""

    def status_widgets(self) -> Sequence[QWidget]:
        """The widgets, left to right; each is placed once."""
        ...
