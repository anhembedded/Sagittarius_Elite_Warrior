"""A screen whose log lines belong in the Output pane (`EPIC-033F`).

The workbench has one Output dock at the bottom, Visual Studio's Output
window: a combo box chooses which source's lines it shows. A screen that keeps
a log offers its `LogListModel` as one channel instead of drawing a log card
of its own, and the window adds every screen's channel to the one pane.

The view implements it: the log was the view's to display, and the view holds
the view model that owns the lines.

A `Protocol`: the implementers are views, `QWidget`s, and Shiboken forbids a
second `QObject`-derived base and conflicts with `ABCMeta`
(`architecture-rule.md` §2.1, reason (a)). It lives here, not in
`core/contracts`, because it names the Engine's `OutputChannel`, which only
presentation may know.

Plausible extensions, each a local change: a screen with two channels (return
a tuple, one loop in the window); a channel that asks to be shown when a line
arrives at WARNING (one property on the channel).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from sagittarius_engine.extensions.pyside_mvc.workbench.output_pane import (
    OutputChannel,
)


@runtime_checkable
class IOutputSource(Protocol):
    """Offers the screen's log as a channel of the Output pane."""

    def output_channel(self) -> OutputChannel | None:
        """The channel, or `None` when the screen keeps no log in this run
        (a desk whose venue is disabled builds no view model)."""
        ...
