"""`EPIC-016` — the contract `MainWindow` depends on instead of concrete
`Sidebar`.

@details `typing.Protocol`, not `abc.ABC` — `architecture-rule.md` §2.1
reason (b): `Sidebar` already inherits `BaseView` (engine, `QObject`-based),
and `architecture-rule.md` §2 forbids multiple inheritance, so it cannot
also inherit an `ABC`. Same precedent as `ITab`
(`components/sidebar/tab_interface.py`).

@par `select_section()` / `set_navigation()` are deliberately absent
The original design proposal included `select_section()` for a future
accordion-style section focus, and a `set_navigation()` to replace the whole
nav structure post-construction. Neither has a caller: `Sidebar` has no
collapsible sections today (every `SectionDescriptor` defaults to
non-collapsible), and `MainWindow` builds the sidebar once, from
`ScreenRegistry.build_sidebar_navigation()`, with no scenario that
re-registers screens at runtime. Adding either now would be exactly the
speculative generality this codebase's own rules forbid. Add whichever one
is actually needed, on both this Protocol and `Sidebar`, when a real caller
exists.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from PySide6.QtCore import SignalInstance


@runtime_checkable
class ISidebar(Protocol):
    """The navigation sidebar, as `MainWindow` needs to see it."""

    @property
    def sig_navigate(self) -> SignalInstance:
        """Emits `(route_name: str)` when the user clicks a nav entry."""
        ...

    @property
    def collapsed_changed(self) -> SignalInstance:
        """Emits when the sidebar's collapsed/expanded state changes."""
        ...

    @property
    def is_collapsed(self) -> bool: ...

    def set_collapsed(self, collapsed: bool) -> None:
        """Sets the collapsed state directly — for restoring a remembered
        value at boot, bypassing the toggle button's own state machine."""
        ...

    def set_active(self, route_name: str) -> None:
        """Highlights the entry matching `route_name`."""
        ...
