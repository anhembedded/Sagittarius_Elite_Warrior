"""A screen that goes live when it is shown, not when it is built
(`EPIC-033C`).

The workbench window builds every mode at start, so a presenter's
constructor runs whether or not the user ever opens it. Work that used to
start on construction because construction meant "the user opened this
screen" (a market stream, a database scan, the Dev Board's opt-in
auto-start) moves here, and the shell calls it each time the mode is shown,
with why it was shown: a `RESTORE` at start is not a click (`BUG-104`).

A `Protocol`: the implementers are presenters, `QObject`s, and Shiboken
forbids a second `QObject`-derived base and conflicts with `ABCMeta`
(`architecture-rule.md` §2.1, reason (a)).

Plausible extensions, each a local change: a `on_mode_hidden()` to pause a
stream while another mode shows (a second method here and one call in the
shell); a mode that refuses to be left (`can_leave`, already a seam on the
Engine's `ShellMode`).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from Sagittarius_Elite_Warrior.src.core.contracts.navigation_source import (
    NavigationSource,
)


@runtime_checkable
class IShownAsMode(Protocol):
    """Told each time its mode becomes the showing one."""

    def on_mode_shown(self, source: NavigationSource) -> None: ...
